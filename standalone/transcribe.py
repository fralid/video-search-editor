"""Транскрибация через Faster-Whisper (CTranslate2) — сохраняет RAW сегменты.
Семантическая нарезка происходит на этапе индексации (index.py).
"""
import json
import time
import logging
from pathlib import Path

from .config import WHISPER_MODEL, WHISPER_BATCH_SIZE
from .db import get_db
from .models import get_whisper, release_whisper

logger = logging.getLogger("standalone.transcribe")


def transcribe(video_id: str) -> str:
    """Транскрибировать видео, сохранить RAW сегменты в БД."""
    conn = get_db()
    row = conn.execute("SELECT local_path FROM videos WHERE video_id=?", (video_id,)).fetchone()
    if not row:
        conn.close()
        return f"Видео '{video_id}' не найдено"

    local_path = row["local_path"]
    if not local_path or not Path(local_path).exists():
        conn.close()
        return f"Файл не найден: {local_path}"

    cnt = conn.execute("SELECT COUNT(*) FROM segments WHERE video_id=?", (video_id,)).fetchone()[0]
    if cnt > 0:
        conn.close()
        return f"Уже {cnt} сегментов. Удалите для повторной транскрибации."
    conn.close()

    try:
        model = get_whisper()
    except Exception as e:
        logger.error("Не удалось загрузить Whisper: %s", e)
        return f"Ошибка загрузки Whisper: {e}"

    logger.info("Транскрибирую: %s", local_path)

    # Проверяем размер файла
    file_size_mb = Path(local_path).stat().st_size / (1024 * 1024)
    logger.info("Размер файла: %.1f MB", file_size_mb)
    print(f"[INFO] Файл: {local_path} ({file_size_mb:.1f} MB)", flush=True)

    t0 = time.time()

    try:
        # Faster-Whisper: простая транскрибация с word timestamps
        segments_gen, info = model.transcribe(
            local_path,
            beam_size=5,
            word_timestamps=True,
        )
        
        logger.info("Язык: '%s' (confidence: %.2f%%)", info.language, info.language_probability * 100)
        print(f"[INFO] Язык: {info.language} ({info.language_probability:.0%})", flush=True)

        # Собираем сегменты из генератора
        rows = []
        for idx, seg in enumerate(segments_gen):
            text = seg.text.strip()
            if not text:
                continue

            # Word timestamps
            words_data = None
            if seg.words:
                words_list = [
                    {"word": w.word.strip(), "start": w.start, "end": w.end}
                    for w in seg.words
                ]
                if words_list:
                    words_data = json.dumps(words_list, ensure_ascii=False)

            rows.append((
                f"{video_id}-{idx}", video_id,
                float(seg.start), float(seg.end),
                text, words_data
            ))

    except Exception as e:
        logger.error("Ошибка транскрибации: %s", e, exc_info=True)
        print(f"[ERROR] Транскрибация: {e}", flush=True)
        release_whisper()
        return f"Ошибка транскрибации: {e}"

    elapsed = time.time() - t0

    conn = get_db()
    conn.executemany(
        "INSERT OR REPLACE INTO segments (segment_id, video_id, start_sec, end_sec, text, words_json) VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.execute("UPDATE videos SET status='transcribed' WHERE video_id=?", (video_id,))
    conn.commit()
    conn.close()

    # Очистка
    release_whisper()

    if rows:
        dur = rows[-1][3]
        speed = dur / elapsed if elapsed > 0 else 0
        return f"{len(rows)} RAW сегментов за {elapsed:.0f}с ({speed:.1f}x realtime)"
    return "Пустое аудио"

