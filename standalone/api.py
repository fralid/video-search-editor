"""FastAPI сервер — совместим с оригинальным React фронтендом."""
import json
import shutil
import threading
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import VIDEO_DIR, CLIPS_DIR, DATA_DIR, VIDEO_EXTENSIONS
from .db import get_db
from . import transcribe as transcribe_mod
from . import index as index_mod
from . import search as search_mod
from . import cut as cut_mod
from . import download as download_mod
from .metrics import compute_segmentation_metrics

logger = logging.getLogger("standalone.api")


# ── Фильтр шумных polling-запросов из uvicorn access log ──
class _QuietPollFilter(logging.Filter):
    """Скрывает повторяющиеся GET /api/queue и /api/health из access log."""
    _NOISY_PATHS = {"/api/queue", "/api/health", "/api/queue/", "/api/videos", "/api/channels"}
    
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(path in msg for path in self._NOISY_PATHS)

logging.getLogger("uvicorn.access").addFilter(_QuietPollFilter())

app = FastAPI(title="Video Search & Editor (Standalone)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы — видео и клипы
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files/videos", StaticFiles(directory=str(VIDEO_DIR)), name="videos")
app.mount("/files/clips", StaticFiles(directory=str(CLIPS_DIR)), name="clips")

# ===================== Очередь обработки =====================

import concurrent.futures
from datetime import datetime

# Макс 2 параллельные задачи (транскрибация + индексация)
_gpu_semaphore = threading.Semaphore(2)
_gpu_lock = _gpu_semaphore  # обратная совместимость для force-transcribe

# Очередь: {video_id: {status, title, added_at, started_at, error}}
_queue: dict = {}

# Очередь загрузок: {url: {status, title, url, added_at}}
_download_queue: dict = {}
_queue_lock = threading.Lock()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="pipeline")


def _queue_set(video_id: str, **kwargs):
    """Обновить запись в очереди (thread-safe)."""
    with _queue_lock:
        if video_id not in _queue:
            _queue[video_id] = {"video_id": video_id, "status": "waiting", "title": video_id}
        _queue[video_id].update(kwargs)


def _queue_remove(video_id: str):
    """Удалить из очереди."""
    with _queue_lock:
        _queue.pop(video_id, None)


def _get_queue_list() -> list:
    """Получить список очереди (pipeline + загрузки)."""
    with _queue_lock:
        dl_items = list(_download_queue.values())
        pipeline_items = list(_queue.values())
        return dl_items + pipeline_items


def _enqueue_pipeline(video_id: str, title: str = ""):
    """Поставить видео в очередь обработки."""
    _queue_set(video_id, status="waiting", title=title or video_id, added_at=datetime.now().isoformat())
    _executor.submit(_run_queued_pipeline, video_id)


def _run_queued_pipeline(video_id: str):
    """Wrapper для pipeline — управляет семафором и состоянием очереди."""
    # Проверяем, не удалили ли из очереди пока ждали
    with _queue_lock:
        if video_id not in _queue:
            return  # Удалён из очереди
    
    _queue_set(video_id, status="processing", started_at=datetime.now().isoformat())
    
    with _gpu_semaphore:
        try:
            _run_pipeline(video_id)
            _queue_set(video_id, status="done")
        except Exception as e:
            _queue_set(video_id, status="error", error=str(e))


# ===================== Health check =====================

@app.get("/")
def root():
    return {"status": "ok", "service": "Video Search & Editor (Standalone)"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/videos/scan")
def api_scan_videos(bg: BackgroundTasks, process: bool = False):
    """Сканировать папку videos/ и зарегистрировать новые файлы.
    
    Args:
        process: если True, ставит новые видео в очередь транскрипции.
    """
    if not VIDEO_DIR.exists():
        return {"added": 0, "already": 0, "total_files": 0}
    
    conn = get_db()
    # Собираем уже известные video_id и local_path
    known_ids = set()
    known_paths = set()
    for row in conn.execute("SELECT video_id, local_path FROM videos").fetchall():
        known_ids.add(row["video_id"])
        if row["local_path"]:
            known_paths.add(str(Path(row["local_path"]).resolve()))
    
    added = []
    already = 0
    total_files = 0
    
    for f in VIDEO_DIR.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        total_files += 1
        
        resolved = str(f.resolve())
        # Генерируем video_id из имени файла
        video_id = f.stem
        
        # Проверяем — уже есть?
        if video_id in known_ids or resolved in known_paths:
            already += 1
            continue
        
        # Регистрируем
        title = f.stem  # имя файла без расширения
        conn.execute(
            "INSERT INTO videos (video_id, title, local_path, status) VALUES (?,?,?,?)",
            (video_id, title, resolved, "added"),
        )
        added.append({"video_id": video_id, "title": title})
    
    conn.commit()
    conn.close()
    
    # Опционально — ставим в очередь обработки
    if process:
        for v in added:
            _enqueue_pipeline(v["video_id"], v["title"])
    
    return {
        "added": len(added),
        "already": already,
        "total_files": total_files,
        "videos": added[:20],  # первые 20 для UI
    }


@app.post("/api/videos/process-pending")
def api_process_pending():
    """Найти все видео без транскрипции и поставить в очередь."""
    conn = get_db()
    rows = conn.execute("SELECT video_id, title FROM videos").fetchall()
    conn.close()
    
    enqueued = []
    skipped = 0
    
    for row in rows:
        video_id = row["video_id"]
        title = row["title"] or video_id
        
        # Проверяем — есть ли сегменты (транскрипция)
        conn2 = get_db()
        seg_count = conn2.execute(
            "SELECT COUNT(*) FROM segments WHERE video_id=?", (video_id,)
        ).fetchone()[0]
        conn2.close()
        
        if seg_count > 0:
            skipped += 1
            continue
        
        # Проверяем — уже в очереди?
        with _queue_lock:
            if video_id in _queue:
                skipped += 1
                continue
        
        _enqueue_pipeline(video_id, title)
        enqueued.append({"video_id": video_id, "title": title})
    
    return {
        "enqueued": len(enqueued),
        "skipped": skipped,
        "total": len(rows),
        "videos": enqueued[:20],
    }


# ===================== Популярные слова =====================

_STOP_WORDS = {
    # Русские
    "и", "в", "на", "не", "что", "это", "я", "он", "она", "мы", "вы", "они",
    "с", "а", "но", "да", "то", "по", "к", "из", "у", "за", "от", "до", "о",
    "как", "все", "так", "его", "её", "их", "мне", "вот", "бы", "ли", "уже",
    "ну", "тут", "там", "вас", "нас", "ещё", "ты", "же", "мой", "свой",
    "для", "вот", "нет", "если", "когда", "чтобы", "или", "тоже", "себя",
    "при", "для", "без", "под", "над", "про", "ни", "будет", "был", "была",
    "было", "быть", "есть", "очень", "потому", "только", "этот", "эта", "эти",
    "этого", "этой", "этих", "который", "которая", "которые", "которого",
    "может", "можно", "нужно", "надо", "просто", "сейчас", "потом", "здесь",
    "такой", "такая", "такие", "такого", "больше", "меня", "тебя", "него",
    "неё", "него", "чем", "где", "куда", "откуда", "почему", "зачем",
    # Английские
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "and", "but", "or",
    "nor", "not", "so", "if", "of", "in", "to", "for", "with", "on", "at",
    "by", "from", "as", "into", "that", "this", "it", "its", "you", "your",
    "we", "they", "he", "she", "i", "me", "my", "his", "her", "our", "their",
}


@app.get("/api/words/popular")
def api_popular_words(min_count: int = 3, limit: int = 100, min_length: int = 4):
    """Самые частые слова во всех транскриптах.
    
    Args:
        min_count: минимальное количество упоминаний
        limit: максимум слов в ответе
        min_length: минимальная длина слова
    """
    import re
    from collections import Counter
    
    conn = get_db()
    rows = conn.execute("SELECT text FROM segments_fts").fetchall()
    conn.close()
    
    counter: Counter = Counter()
    for row in rows:
        text = row["text"] if isinstance(row["text"], str) else str(row["text"])
        words = re.findall(r'[а-яА-ЯёЁa-zA-Z]+', text.lower())
        for w in words:
            if len(w) >= min_length and w not in _STOP_WORDS:
                counter[w] += 1
    
    # Фильтруем по min_count и сортируем
    popular = [
        {"word": word, "count": count}
        for word, count in counter.most_common(limit * 3)  # берём с запасом
        if count >= min_count
    ][:limit]
    
    return {"words": popular, "total_unique": len(counter)}


# ===================== Модели запросов =====================

class SearchRequest(BaseModel):
    query: str
    top_k: int = 30
    filter_tags: Optional[str] = None


class AddVideoRequest(BaseModel):
    url: str
    tags: Optional[str] = None


class BulkAddRequest(BaseModel):
    urls: list[str]
    tags: Optional[str] = None


class ManualClipRequest(BaseModel):
    video_id: str
    start: float
    end: float


class DownloadRequest(BaseModel):
    url: str
    quality: str = "720p"  # "720p" или "best"
    browser: str = "firefox"


# ===================== Поиск =====================

@app.post("/api/search")
def api_search(req: SearchRequest):
    results = search_mod.search(req.query, req.top_k)
    # Формат, который ожидает React
    return [
        {
            "segment_id": r["segment_id"],
            "video_id": r["video_id"],
            "start": r["start_sec"],
            "end": r["end_sec"],
            "text": r["text"],
            "score": r["score"],
        }
        for r in results
    ]


# ===================== Каналы =====================

@app.get("/api/channels")
def api_channels():
    # Standalone не имеет каналов — возвращаем пустой список
    return []


# ===================== Видео =====================

@app.get("/api/videos")
def api_list_videos(
    channel: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
):
    conn = get_db()
    rows = conn.execute(
        "SELECT video_id, title, status, local_path, created_at FROM videos ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        seg_count = 0
        conn2 = get_db()
        seg_count = conn2.execute(
            "SELECT COUNT(*) FROM segments WHERE video_id=?", (r["video_id"],)
        ).fetchone()[0]
        conn2.close()

        st = r["status"]
        result.append({
            "video_id": r["video_id"],
            "title": r["title"],
            "channel_id": "standalone",
            "channel_name": "Local",
            "description": f"{seg_count} сегментов",
            "tags": "",
            "duration": None,
            "thumbnail_url": None,
            "url": f"file://{r['local_path']}",
            "local_path": r["local_path"],
            "status_download": "done" if r["local_path"] else "pending",
            "status_transcribe": "done" if st in ("transcribed", "indexed") else ("pending" if st == "added" else st),
            "status_index": "done" if st == "indexed" else "pending",
            "created_at": r["created_at"],
        })

    return result[offset : offset + limit]


@app.post("/api/videos")
def api_add_video(req: AddVideoRequest, bg: BackgroundTasks):
    """Добавить видео. Для standalone — принимает путь к локальному файлу."""
    src = Path(req.url.replace("file://", ""))
    if not src.exists():
        return JSONResponse({"error": f"Файл не найден: {req.url}"}, status_code=400)

    video_id = src.stem
    dst = VIDEO_DIR / src.name
    if not dst.exists():
        shutil.copy2(src, dst)

    conn = get_db()
    exists = conn.execute("SELECT video_id FROM videos WHERE video_id=?", (video_id,)).fetchone()
    if exists:
        conn.close()
        return {"status": "already_exists", "video_id": video_id}

    conn.execute(
        "INSERT INTO videos (video_id, title, local_path, status) VALUES (?,?,?,?)",
        (video_id, req.tags or video_id, str(dst), "added"),
    )
    conn.commit()
    conn.close()

    _enqueue_pipeline(video_id, req.tags or video_id)
    return {"status": "processing_started", "video_id": video_id}


def _run_pipeline(video_id: str):
    """Фоновая обработка: транскрибация → индексация."""
    import time
    import torch
    import gc
    
    with _gpu_lock:
        try:
            logger.info("Pipeline start: %s", video_id)
            
            # Шаг 1: Транскрибация
            transcribe_mod.transcribe(video_id)
            
            # КРИТИЧНО: Очистка памяти GPU между транскрибацией и индексацией
            # Whisper (~7GB) должен быть полностью выгружен перед загрузкой embedding моделей
            logger.info("Очистка памяти GPU перед индексацией...")
            from .models import release_whisper
            release_whisper()
            
            # Дополнительная очистка и небольшая задержка для освобождения памяти
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            time.sleep(1)  # Даём время GPU освободить память
            
            # Шаг 2: Индексация (загрузит embedding модели)
            index_mod.index_video(video_id)
            
            logger.info("Pipeline done: %s", video_id)
        except Exception as e:
            import traceback
            logger.error("Pipeline error %s: %s", video_id, e)
            logger.error("Traceback:\n%s", traceback.format_exc())
            print(f"[ERROR] Pipeline error {video_id}: {e}", flush=True)
            traceback.print_exc()
            # Очистка памяти даже при ошибке
            try:
                from .models import release_whisper
                release_whisper()
            except:
                pass


@app.post("/api/videos/{video_id}/transcribe")
def api_transcribe(video_id: str, bg: BackgroundTasks, force: bool = False):
    if force:
        conn = get_db()
        conn.execute("DELETE FROM segments WHERE video_id=?", (video_id,))
        conn.commit()
        conn.close()

    def _do():
        with _gpu_lock:
            transcribe_mod.transcribe(video_id)

    bg.add_task(_do)
    return {"status": "transcription_started", "video_id": video_id}


@app.post("/api/videos/{video_id}/index")
def api_index(video_id: str, bg: BackgroundTasks):
    def _do():
        with _gpu_lock:
            index_mod.index_video(video_id)

    bg.add_task(_do)
    return {"status": "indexing_started", "video_id": video_id}


@app.post("/api/videos/{video_id}/reprocess")
def api_reprocess(video_id: str, bg: BackgroundTasks):
    conn = get_db()
    conn.execute("DELETE FROM segments WHERE video_id=?", (video_id,))
    conn.execute("UPDATE videos SET status='added' WHERE video_id=?", (video_id,))
    conn.commit()
    conn.close()

    _enqueue_pipeline(video_id)
    return {"status": "reprocessing_started", "video_id": video_id}


@app.delete("/api/videos/{video_id}")
def api_delete_video(video_id: str):
    conn = get_db()
    row = conn.execute("SELECT local_path FROM videos WHERE video_id=?", (video_id,)).fetchone()
    
    # Подсчитываем количество сегментов и клипов для статистики
    segments_count = conn.execute("SELECT COUNT(*) FROM segments WHERE video_id=?", (video_id,)).fetchone()[0]
    clips_count = conn.execute("SELECT COUNT(*) FROM clips WHERE video_id=?", (video_id,)).fetchone()[0]
    
    # Удаляем из БД
    conn.execute("DELETE FROM segments WHERE video_id=?", (video_id,))
    conn.execute("DELETE FROM clips WHERE video_id=?", (video_id,))
    conn.execute("DELETE FROM videos WHERE video_id=?", (video_id,))
    conn.commit()
    conn.close()

    # Удаляем эмбеддинги из ChromaDB
    try:
        from .index import _get_collection
        collection = _get_collection()
        # Удаляем все векторы с этим video_id из метаданных
        # Это удалит и сегменты, и чанки (которые имеют video_id в метаданных)
        deleted_count = collection.delete(where={"video_id": video_id})
        logger.info("Удалены эмбеддинги из ChromaDB для видео %s (удалено векторов: %s)", video_id, deleted_count)
    except Exception as e:
        logger.warning("Не удалось удалить эмбеддинги из ChromaDB для %s: %s", video_id, e)

    # Удаляем файл видео
    if row and row["local_path"]:
        p = Path(row["local_path"])
        if p.exists():
            try:
                p.unlink()
            except Exception as e:
                logger.warning("Не удалось удалить файл %s: %s", p, e)

    return {"status": "deleted", "stats": {"segments": segments_count, "clips": clips_count}}


@app.delete("/api/embeddings/{video_id}")
def api_delete_embeddings(video_id: str):
    """Удалить эмбеддинги из ChromaDB по video_id (даже если видео уже удалено из БД)."""
    try:
        from .index import _get_collection
        collection = _get_collection()
        
        # Проверяем, сколько векторов с этим video_id
        # Получаем все векторы с этим video_id для подсчета
        results = collection.get(where={"video_id": video_id})
        count_before = len(results.get("ids", [])) if results else 0
        
        if count_before == 0:
            return {"status": "not_found", "message": f"Эмбеддинги для видео '{video_id}' не найдены в ChromaDB"}
        
        # Удаляем все векторы с этим video_id
        collection.delete(where={"video_id": video_id})
        
        logger.info("Удалены эмбеддинги из ChromaDB для видео %s (удалено векторов: %d)", video_id, count_before)
        return {"status": "deleted", "video_id": video_id, "deleted_count": count_before}
    except Exception as e:
        logger.error("Ошибка удаления эмбеддингов для %s: %s", video_id, e, exc_info=True)
        return JSONResponse(
            {"status": "error", "message": f"Ошибка удаления эмбеддингов: {str(e)}"},
            status_code=500
        )


@app.get("/api/embeddings/orphaned")
def api_list_orphaned_embeddings():
    """Список всех video_id в ChromaDB, которых нет в БД (осиротевшие эмбеддинги)."""
    try:
        from .index import _get_collection
        collection = _get_collection()
        
        # Получаем все векторы из ChromaDB
        all_results = collection.get()
        all_video_ids = set()
        
        if all_results and "metadatas" in all_results:
            for meta in all_results["metadatas"]:
                if meta and "video_id" in meta:
                    all_video_ids.add(meta["video_id"])
        
        # Получаем все video_id из БД
        conn = get_db()
        db_video_ids = set(row[0] for row in conn.execute("SELECT video_id FROM videos").fetchall())
        conn.close()
        
        # Находим осиротевшие video_id
        orphaned = sorted(all_video_ids - db_video_ids)
        
        # Подсчитываем количество векторов для каждого осиротевшего video_id
        orphaned_stats = []
        for vid in orphaned:
            results = collection.get(where={"video_id": vid})
            count = len(results.get("ids", [])) if results else 0
            orphaned_stats.append({"video_id": vid, "vectors_count": count})
        
        return {
            "status": "ok",
            "orphaned_count": len(orphaned),
            "orphaned": orphaned_stats
        }
    except Exception as e:
        logger.error("Ошибка получения списка осиротевших эмбеддингов: %s", e, exc_info=True)
        return JSONResponse(
            {"status": "error", "message": f"Ошибка: {str(e)}"},
            status_code=500
        )


@app.get("/api/videos/{video_id}/transcript")
def api_transcript(video_id: str):
    conn = get_db()
    video = conn.execute("SELECT video_id, title FROM videos WHERE video_id=?", (video_id,)).fetchone()
    if not video:
        conn.close()
        return JSONResponse({"error": "not found"}, status_code=404)

    rows = conn.execute(
        "SELECT segment_id, start_sec, end_sec, text, words_json FROM segments WHERE video_id=? ORDER BY start_sec",
        (video_id,),
    ).fetchall()
    conn.close()

    segments = []
    for r in rows:
        words = []
        if r["words_json"]:
            try:
                words = json.loads(r["words_json"])
            except Exception:
                pass
        segments.append({
            "segment_id": r["segment_id"],
            "start": r["start_sec"],
            "end": r["end_sec"],
            "text": r["text"],
            "words": words,
        })

    return {
        "video_id": video["video_id"],
        "title": video["title"],
        "duration": segments[-1]["end"] if segments else 0,
        "segments": segments,
    }


@app.get("/api/videos/{video_id}/logs")
def api_logs(video_id: str):
    # Standalone не хранит логи — возвращаем пустой список
    return []


@app.get("/api/videos/{video_id}/metrics")
def api_get_metrics(video_id: str):
    """Получить метрики качества сегментации для видео."""
    conn = get_db()
    
    # Получаем RAW сегменты
    seg_rows = conn.execute(
        "SELECT segment_id, video_id, start_sec, end_sec, text, words_json "
        "FROM segments WHERE video_id=? ORDER BY start_sec",
        (video_id,),
    ).fetchall()
    
    if not seg_rows:
        conn.close()
        return {"error": "Нет сегментов для этого видео"}
    
    segments = [dict(r) for r in seg_rows]
    
    # Получаем чанки из ChromaDB
    try:
        from .index import _get_collection
        collection = _get_collection()
        chunk_results = collection.get(where={"video_id": video_id})
        
        chunks = []
        if chunk_results.get("metadatas"):
            for i, metadata in enumerate(chunk_results["metadatas"]):
                doc = chunk_results["documents"][i] if chunk_results.get("documents") else ""
                chunk_id = chunk_results["ids"][i] if chunk_results.get("ids") else f"chunk-{i}"
                chunks.append((
                    chunk_id,
                    metadata.get("start_sec", 0.0),
                    metadata.get("end_sec", 0.0),
                    doc
                ))
    except Exception as e:
        logger.warning("Не удалось получить чанки из ChromaDB: %s", e)
        chunks = []
    
    conn.close()
    
    # Вычисляем метрики
    metrics = compute_segmentation_metrics(segments, chunks, vad_chunks=None)
    
    return metrics


@app.post("/api/videos/bulk")
def api_bulk_add(req: BulkAddRequest, bg: BackgroundTasks):
    added = []
    for url in req.urls:
        src = Path(url.replace("file://", ""))
        if not src.exists():
            continue
        video_id = src.stem
        dst = VIDEO_DIR / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        conn = get_db()
        exists = conn.execute("SELECT video_id FROM videos WHERE video_id=?", (video_id,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO videos (video_id, title, local_path, status) VALUES (?,?,?,?)",
                (video_id, video_id, str(dst), "added"),
            )
            conn.commit()
            added.append({"video_id": video_id, "title": video_id})
            _enqueue_pipeline(video_id)
        conn.close()
    return {"status": "processing_started", "added": len(added), "errors": 0, "videos": added, "failed": []}


@app.post("/api/videos/import-channel")
def api_import_channel():
    return JSONResponse({"error": "Channel import not available in standalone mode"}, status_code=400)


@app.post("/api/videos/refresh-all-metadata")
def api_refresh_metadata():
    return {"status": "not_needed", "videos_to_update": 0}


# ===================== Скачивание YouTube =====================

@app.post("/api/download/youtube")
def api_download_youtube(req: DownloadRequest, bg: BackgroundTasks):
    """Скачать видео с YouTube и запустить pipeline."""
    if not download_mod.YTDLP_EXE.exists():
        return JSONResponse(
            {"error": f"yt-dlp.exe не найден в {download_mod._YTDLP_DIR}"},
            status_code=500,
        )

    # Сразу добавляем в очередь загрузок
    dl_key = req.url
    with _queue_lock:
        _download_queue[dl_key] = {
            "video_id": f"dl-{hash(req.url) & 0xFFFFFF:06x}",
            "status": "downloading",
            "title": f"⬇️ {req.url.split('v=')[-1][:11]}",
            "url": req.url,
            "added_at": datetime.now().isoformat(),
        }

    def _do():
        try:
            result = download_mod.download_video(req.url, req.quality, req.browser)
            if result["status"] == "error":
                logger.error("Download failed: %s", result.get("error"))
                with _queue_lock:
                    if dl_key in _download_queue:
                        _download_queue[dl_key]["status"] = "error"
                        _download_queue[dl_key]["error"] = result.get("error", "")
                return

            video_id = result["video_id"]
            title = result["title"]
            path = result["path"]
            already_existed = result["status"] == "exists"

            # Убираем из очереди загрузок
            with _queue_lock:
                _download_queue.pop(dl_key, None)

            # Регистрируем в БД
            conn = get_db()
            exists = conn.execute("SELECT video_id FROM videos WHERE video_id=?", (video_id,)).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO videos (video_id, title, local_path, status) VALUES (?,?,?,?)",
                    (video_id, title, path, "added"),
                )
                conn.commit()
                conn.close()
                # Новое видео — ставим в очередь
                _enqueue_pipeline(video_id, title)
            else:
                conn.close()
                if already_existed:
                    logger.info("Видео уже скачано и зарегистрировано, пропускаем: %s", video_id)
        except Exception as e:
            logger.error("Download exception: %s", e, exc_info=True)
            with _queue_lock:
                if dl_key in _download_queue:
                    _download_queue[dl_key]["status"] = "error"
                    _download_queue[dl_key]["error"] = str(e)

    bg.add_task(_do)
    return {"status": "downloading", "url": req.url, "quality": req.quality}


@app.get("/api/download/status")
def api_download_status():
    """Проверить наличие yt-dlp."""
    return {
        "available": download_mod.YTDLP_EXE.exists(),
        "path": str(download_mod._YTDLP_DIR),
    }


# ===================== Очередь =====================

@app.get("/api/queue")
def api_queue():
    """Получить текущую очередь обработки."""
    return _get_queue_list()


@app.delete("/api/queue/{video_id}")
def api_queue_remove(video_id: str):
    """Удалить видео из очереди."""
    with _queue_lock:
        item = _queue.get(video_id)
        if not item:
            return JSONResponse({"error": "Не найдено в очереди"}, status_code=404)
        if item["status"] == "processing":
            return JSONResponse({"error": "Нельзя удалить — уже обрабатывается"}, status_code=409)
        _queue.pop(video_id, None)
    return {"status": "removed", "video_id": video_id}


@app.post("/api/queue/clear")
def api_queue_clear():
    """Очистить завершённые и ошибочные записи."""
    with _queue_lock:
        to_remove = [vid for vid, item in _queue.items() if item["status"] in ("done", "error")]
        for vid in to_remove:
            del _queue[vid]
        # Также чистим ошибочные загрузки
        dl_remove = [k for k, item in _download_queue.items() if item["status"] == "error"]
        for k in dl_remove:
            del _download_queue[k]
    return {"cleared": len(to_remove) + len(dl_remove)}


# ===================== Клипы =====================

@app.post("/api/clips/manual")
def api_manual_clip(req: ManualClipRequest):
    result = cut_mod.cut_clip(req.video_id, req.start, req.end)
    if Path(result).exists():
        clip_name = Path(result).stem
        return {
            "clip_id": clip_name,
            "video_id": req.video_id,
            "start_sec": req.start,
            "end_sec": req.end,
            "download_url": f"/files/clips/{Path(result).name}",
        }
    return JSONResponse({"error": result}, status_code=500)
