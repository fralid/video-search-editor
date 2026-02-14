"""Автообработка: мониторинг папки videos/ → транскрибация → индексация."""
import shutil
import time
import logging
import threading
from pathlib import Path

from .config import VIDEO_DIR, VIDEO_EXTENSIONS, WATCH_INTERVAL_SEC
from .db import get_db

logger = logging.getLogger("standalone.watcher")

_thread: threading.Thread | None = None
_running = False


def _process_new_video(video_path: Path):
    """Полный пайплайн: добавить → транскрибировать → индексировать."""
    video_id = video_path.stem
    title = video_id

    conn = get_db()
    exists = conn.execute("SELECT video_id FROM videos WHERE video_id=?", (video_id,)).fetchone()
    if exists:
        conn.close()
        return  # Уже обработан

    conn.execute(
        "INSERT INTO videos (video_id, title, local_path, status) VALUES (?,?,?,?)",
        (video_id, title, str(video_path), "added"),
    )
    conn.commit()
    conn.close()
    logger.info("Новое видео: %s", video_id)

    # Транскрибация
    try:
        import sys
        print(f"[WATCHER] Начинаю транскрибацию: {video_id}", flush=True)
        sys.stdout.flush()
        sys.stderr.flush()
        
        from .transcribe import transcribe
        result = transcribe(video_id)
        logger.info("Транскрибация %s: %s", video_id, result)
        print(f"[WATCHER] Транскрибация завершена: {video_id} -> {result}", flush=True)
    except Exception as e:
        import traceback
        logger.error("Ошибка транскрибации %s: %s", video_id, e)
        print(f"[WATCHER ERROR] Транскрибация {video_id}: {e}", flush=True)
        traceback.print_exc()
        conn = get_db()
        conn.execute("UPDATE videos SET status='error_transcribe' WHERE video_id=?", (video_id,))
        conn.commit()
        conn.close()
        # Очистка GPU при ошибке
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except:
            pass
        return

    # Очистка GPU между транскрибацией и индексацией
    try:
        import torch
        import gc
        from .models import release_whisper
        release_whisper()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except:
        pass

    # Индексация
    try:
        print(f"[WATCHER] Начинаю индексацию: {video_id}", flush=True)
        from .index import index_video
        result = index_video(video_id)
        logger.info("Индексация %s: %s", video_id, result)
        print(f"[WATCHER] Индексация завершена: {video_id} -> {result}", flush=True)
    except Exception as e:
        import traceback
        logger.error("Ошибка индексации %s: %s", video_id, e)
        print(f"[WATCHER ERROR] Индексация {video_id}: {e}", flush=True)
        traceback.print_exc()
        conn = get_db()
        conn.execute("UPDATE videos SET status='error_index' WHERE video_id=?", (video_id,))
        conn.commit()
        conn.close()


def _watch_loop():
    """Основной цикл: проверяем папку каждые N секунд."""
    global _running
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    while _running:
        try:
            for f in VIDEO_DIR.iterdir():
                if f.suffix.lower() in VIDEO_EXTENSIONS and f.is_file():
                    conn = get_db()
                    exists = conn.execute(
                        "SELECT video_id FROM videos WHERE video_id=?", (f.stem,)
                    ).fetchone()
                    conn.close()

                    if not exists:
                        _process_new_video(f)
        except Exception as e:
            logger.error("Watcher error: %s", e)

        time.sleep(WATCH_INTERVAL_SEC)


def start():
    """Запустить фоновый мониторинг папки."""
    global _thread, _running
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_watch_loop, daemon=True, name="video-watcher")
    _thread.start()
    logger.info("Watcher запущен: %s (каждые %dс)", VIDEO_DIR, WATCH_INTERVAL_SEC)


def stop():
    """Остановить мониторинг."""
    global _running
    _running = False
    logger.info("Watcher остановлен")
