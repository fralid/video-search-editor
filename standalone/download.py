"""Скачивание видео с YouTube через yt-dlp.

Адаптировано из yt-dlp/yt-dlp.py:
- Режим 720p (быстрый, без перекодировки)  
- Режим лучшего качества (NVENC перекодировка)
- Cookies из браузера (Firefox рекомендуется)
- Сохранение в standalone_data/videos/
"""
import subprocess
import os
import re
import logging
from pathlib import Path
from typing import Optional, Tuple, List

from .config import VIDEO_DIR

logger = logging.getLogger("standalone.download")

# ─── Paths к портативным утилитам ────────────────────────

_YTDLP_DIR = Path(__file__).parent.parent / "yt-dlp"
YTDLP_EXE = _YTDLP_DIR / "yt-dlp.exe"
NODE_EXE = _YTDLP_DIR / "node.exe"
FFMPEG_EXE = _YTDLP_DIR / "ffmpeg.exe"

# ─── Cookies ─────────────────────────────────────────────

BROWSER_MAP = {
    "firefox": "firefox",
    "chrome": "chrome",
    "edge": "edge",
    "brave": "brave",
    "opera": "opera",
}

DEFAULT_BROWSER = "firefox"

# ─── User Agent ──────────────────────────────────────────

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/115.0.0.0 Safari/537.36"
)


def _check_ytdlp() -> bool:
    """Проверяем наличие yt-dlp.exe."""
    return YTDLP_EXE.exists()


def _build_command(
    url: str,
    quality: str = "720p",
    browser: str = "firefox",
    cookies_file: Optional[str] = None,
) -> Tuple[List[str], str]:
    """Собирает команду для скачивания.
    
    Args:
        url: YouTube URL
        quality: "720p" или "best"
        browser: браузер для cookies
        cookies_file: путь к файлу cookies (вместо браузера)
    
    Returns:
        (command, output_dir)
    """
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    output_template = str(VIDEO_DIR / "%(title)s.%(ext)s")

    command = [
        str(YTDLP_EXE),
        "--no-playlist",
        "--newline",
        "--user-agent", USER_AGENT,
        "--referer", "https://www.youtube.com/",
    ]

    # Node.js для обхода bot protection
    if NODE_EXE.exists():
        command.extend(["--js-runtimes", f"node:{NODE_EXE}"])

    # FFmpeg для мержа
    if FFMPEG_EXE.exists():
        command.extend(["--ffmpeg-location", str(FFMPEG_EXE)])

    if quality == "720p":
        # ──── Быстрый режим: 720p, без перекодировки ────
        command.extend([
            "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best",
            "--remux-video", "mp4",
            "-o", output_template,
        ])
    else:
        # ──── Лучшее качество: макс. разрешение ────
        command.extend([
            "-f", "bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "--remux-video", "mp4",
            "-o", output_template,
        ])

    # Cookies
    if cookies_file and os.path.exists(cookies_file):
        command.extend(["--cookies", cookies_file])
    elif browser in BROWSER_MAP:
        command.extend(["--cookies-from-browser", BROWSER_MAP[browser]])

    command.append(url)
    return command, str(VIDEO_DIR)


def _extract_title(line: str) -> Optional[str]:
    """Извлекает название видео из вывода yt-dlp."""
    # [download] Destination: path/to/title.mp4
    m = re.search(r'\[download\] Destination:\s*(.+)', line)
    if m:
        return Path(m.group(1).strip()).stem
    # [download] title has already been downloaded
    m = re.search(r'\[download\]\s+(.+?) has already been downloaded', line)
    if m:
        return Path(m.group(1).strip()).stem
    return None


def _extract_filename(line: str) -> Optional[str]:
    """Извлекает имя файла из вывода yt-dlp."""
    m = re.search(r'\[download\] Destination:\s*(.+)', line)
    if m:
        return m.group(1).strip()
    m = re.search(r'\[download\]\s+(.+?) has already been downloaded', line)
    if m:
        return m.group(1).strip()
    # [Merger] Merging formats into "path/file.mp4"
    m = re.search(r'\[Merger\] Merging formats into "(.+?)"', line)
    if m:
        return m.group(1).strip()
    return None


def _get_video_title(url: str, browser: str = "firefox") -> Optional[str]:
    """Получить название видео БЕЗ скачивания (yt-dlp --print title)."""
    if not _check_ytdlp():
        return None

    command = [
        str(YTDLP_EXE),
        "--no-playlist",
        "--print", "title",
        "--skip-download",
    ]

    if browser in BROWSER_MAP:
        command.extend(["--cookies-from-browser", BROWSER_MAP[browser]])

    command.append(url)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(_YTDLP_DIR),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        logger.warning("Не удалось получить title для %s: %s", url, e)

    return None


def _get_metadata(url: str, browser: str = "firefox") -> dict:
    """Получить метаданные YouTube без скачивания: канал, дата, длительность, превью.
    Возвращает dict: channel_name, uploaded_at, duration, thumbnail_url (None при ошибке/отсутствии).
    """
    out = {
        "channel_name": None,
        "uploaded_at": None,
        "duration": None,
        "thumbnail_url": None,
    }
    if not _check_ytdlp():
        return out

    command = [
        str(YTDLP_EXE),
        "--no-playlist",
        "--skip-download",
        "--print", "%(channel)s",
        "--print", "%(upload_date)s",
        "--print", "%(duration)s",
        "--print", "%(thumbnail)s",
    ]
    if browser in BROWSER_MAP:
        command.extend(["--cookies-from-browser", BROWSER_MAP[browser]])
    command.append(url)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(_YTDLP_DIR),
        )
        if result.returncode != 0 or not result.stdout.strip():
            return out
        lines = [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
        if len(lines) >= 1:
            out["channel_name"] = lines[0] or None
        if len(lines) >= 2 and lines[1]:
            # YYYYMMDD -> YYYY-MM-DD
            d = lines[1]
            if len(d) == 8 and d.isdigit():
                out["uploaded_at"] = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            else:
                out["uploaded_at"] = d
        if len(lines) >= 3 and lines[2]:
            try:
                out["duration"] = int(float(lines[2]))
            except (ValueError, TypeError):
                pass
        if len(lines) >= 4:
            out["thumbnail_url"] = lines[3] or None
    except Exception as e:
        logger.warning("Не удалось получить метаданные для %s: %s", url, e)
    return out


def _file_exists_in_dir(title: str) -> Optional[Path]:
    """Проверить, есть ли файл с таким названием в VIDEO_DIR (любое расширение)."""
    if not VIDEO_DIR.exists():
        return None
    
    # Нормализуем title для сравнения (yt-dlp заменяет спецсимволы)
    # Ищем по всем видео-расширениям
    from .config import VIDEO_EXTENSIONS
    
    for f in VIDEO_DIR.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        # Точное совпадение stem
        if f.stem == title:
            return f
    
    return None


def download_video(
    url: str,
    quality: str = "720p",
    browser: str = "firefox",
    on_progress: Optional[callable] = None,
) -> dict:
    """Скачать одно видео.
    
    Args:
        url: YouTube URL
        quality: "720p" или "best"
        browser: браузер для cookies
        on_progress: callback(stage, line) для прогресса
    
    Returns:
        {"status": "ok"/"error"/"exists", "title": ..., "path": ..., "video_id": ...}
    """
    if not _check_ytdlp():
        return {"status": "error", "error": f"yt-dlp.exe не найден в {_YTDLP_DIR}"}

    meta = _get_metadata(url, browser)

    # ── Проверка: уже скачано? ──
    title_check = _get_video_title(url, browser)
    if title_check:
        existing = _file_exists_in_dir(title_check)
        if existing:
            logger.info("Видео уже скачано: %s → %s", title_check, existing)
            return {
                "status": "exists",
                "title": title_check,
                "path": str(existing),
                "video_id": existing.stem,
                "source_url": url,
                **{k: v for k, v in meta.items() if v is not None},
            }
    
    command, work_dir = _build_command(url, quality, browser)
    
    logger.info("Скачивание: %s (quality=%s, browser=%s)", url, quality, browser)
    
    title = None
    final_path = None
    
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(_YTDLP_DIR),
            bufsize=1,
        )

        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            
            # Извлекаем title и path
            t = _extract_title(line)
            if t:
                title = t
            
            f = _extract_filename(line)
            if f:
                final_path = f
            
            # Callback для прогресса
            if on_progress:
                stage = _detect_stage(line)
                on_progress(stage, line)
            
            logger.debug(line)

        proc.wait()

        if proc.returncode != 0:
            return {"status": "error", "error": f"yt-dlp завершился с кодом {proc.returncode}"}

        # Ищем скачанный файл
        if final_path:
            p = Path(final_path)
            if not p.is_absolute():
                p = _YTDLP_DIR / p
            if p.exists():
                # Если файл не в VIDEO_DIR — перемещаем
                if p.parent.resolve() != VIDEO_DIR.resolve():
                    dst = VIDEO_DIR / p.name
                    import shutil
                    shutil.move(str(p), str(dst))
                    final_path = str(dst)
                else:
                    final_path = str(p)

        # Fallback: ищем последний .mp4 в VIDEO_DIR
        if not final_path or not Path(final_path).exists():
            mp4s = sorted(VIDEO_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
            if mp4s:
                final_path = str(mp4s[0])
                title = title or mp4s[0].stem

        if not final_path or not Path(final_path).exists():
            return {"status": "error", "error": "Файл не найден после скачивания"}

        video_id = Path(final_path).stem
        title = title or video_id

        return {
            "status": "ok",
            "title": title,
            "path": final_path,
            "video_id": video_id,
            "source_url": url,
            **{k: v for k, v in meta.items() if v is not None},
        }

    except Exception as e:
        logger.error("Ошибка скачивания: %s", e)
        return {"status": "error", "error": str(e)}


def _detect_stage(line: str) -> str:
    """Определяет текущий этап по строке вывода yt-dlp."""
    lower = line.lower()
    if "extracting cookies" in lower or "[cookies]" in lower:
        return "cookies"
    if "[download] destination" in lower:
        return "downloading"
    if "[merger]" in lower or "merging formats" in lower:
        return "merging"
    if "[videoconvertor]" in lower or "converting video" in lower or "[ffmpeg]" in lower:
        return "converting"
    if "[download]" in lower and "%" in lower:
        return "progress"
    if "has already been downloaded" in lower:
        return "exists"
    return ""
