"""Вырезка клипов через FFmpeg.

Улучшения из app/cut.py:
- precise (re-encode) vs fast (copy) режимы
- safety_pre/post margins для нарезки
- create_manual_clip() — произвольный диапазон
- Поддержка Linux system ffmpeg
"""
import subprocess
import logging
from pathlib import Path
from uuid import uuid4

from .config import CLIPS_DIR, FFMPEG_CRF, FFMPEG_PRESET
from .db import get_db

logger = logging.getLogger("standalone.cut")

# Safety margins (секунды до/после сегмента)
SAFETY_PRE = 0.3
SAFETY_POST = 0.5


def _find_ffmpeg() -> str:
    """Путь к FFmpeg: portable → system → PATH."""
    # 1. Портативный рядом с проектом
    local = Path(__file__).parent.parent / "ffmpeg.exe"
    if local.exists():
        return str(local)
    # 2. Linux system (Docker)
    system = Path("/usr/bin/ffmpeg")
    if system.exists():
        return str(system)
    # 3. PATH
    return "ffmpeg"


def _ffmpeg_cut(
    src: Path, dst: Path,
    start: float, end: float,
    precise: bool = True,
) -> bool:
    """Вырезать фрагмент видео.

    precise=True: re-encode (frame-accurate, медленнее)
    precise=False: copy (быстро, но может быть неточно на keyframes)
    """
    duration = max(end - start, 0.1)
    ffmpeg = _find_ffmpeg()

    if precise:
        cmd = [
            ffmpeg, "-y",
            "-ss", f"{start:.3f}",
            "-i", str(src),
            "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", str(FFMPEG_CRF),
            "-c:a", "aac", "-b:a", "192k",
            "-threads", "4",
            str(dst),
        ]
    else:
        cmd = [
            ffmpeg, "-y",
            "-ss", f"{start:.3f}",
            "-i", str(src),
            "-t", f"{duration:.3f}",
            "-c", "copy",
            str(dst),
        ]

    try:
        res = subprocess.run(cmd, capture_output=True, timeout=300, check=False)
        if res.returncode != 0:
            logger.error("FFmpeg ошибка: %s", res.stderr.decode("utf-8", errors="replace")[:500])
        return res.returncode == 0
    except FileNotFoundError:
        logger.error("FFmpeg не найден. Установите и добавьте в PATH.")
        return False
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg таймаут (> 5 мин)")
        return False


def cut_clip(
    video_id: str,
    start_sec: float,
    end_sec: float,
    precise: bool = True,
    with_margins: bool = True,
) -> str:
    """Вырезать клип из видео.

    Args:
        video_id: ID видео
        start_sec: начало (секунды)
        end_sec: конец (секунды)
        precise: True = re-encode (точно), False = copy (быстро)
        with_margins: добавлять safety margins

    Returns:
        Путь к файлу или строка с ошибкой
    """
    conn = get_db()
    row = conn.execute("SELECT local_path FROM videos WHERE video_id=?", (video_id,)).fetchone()
    conn.close()

    if not row or not row["local_path"]:
        return f"Видео '{video_id}' не найдено"

    src = Path(row["local_path"])
    if not src.exists():
        return f"Файл не найден: {src}"

    # Safety margins
    if with_margins:
        start = max(0.0, start_sec - SAFETY_PRE)
        end = end_sec + SAFETY_POST
    else:
        start = max(0.0, start_sec)
        end = end_sec

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    clip_id = str(uuid4())[:8]
    dst = CLIPS_DIR / f"{video_id}_{clip_id}.mp4"

    success = _ffmpeg_cut(src, dst, start, end, precise=precise)
    if not success:
        return "FFmpeg не смог вырезать клип"

    # Сохраняем в БД
    conn = get_db()
    conn.execute(
        "INSERT INTO clips VALUES (?,?,?,?,?,datetime('now'))",
        (clip_id, video_id, start, end, str(dst)),
    )
    conn.commit()
    conn.close()

    return str(dst)


def cut_manual(
    video_id: str,
    start_sec: float,
    end_sec: float,
) -> str:
    """Вырезать клип произвольного диапазона (без margins, точные границы)."""
    s = max(0.0, min(start_sec, end_sec))
    e = max(s + 0.1, max(start_sec, end_sec))
    return cut_clip(video_id, s, e, precise=True, with_margins=False)
