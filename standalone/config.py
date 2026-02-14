"""Настройки standalone-приложения."""
from pathlib import Path

# Пути
DATA_DIR = Path("./standalone_data")
VIDEO_DIR = DATA_DIR / "videos"
CLIPS_DIR = DATA_DIR / "clips"
CHROMA_DIR = DATA_DIR / "chroma"
DB_PATH = DATA_DIR / "app.db"

# Whisper - faster-whisper (CTranslate2), large-v3 для максимального качества
WHISPER_MODEL = "large-v3"       # CTranslate2 формат, ~3 GB VRAM
WHISPER_BATCH_SIZE = 16          # RTX 3090 24GB — агрессивный batch для скорости

# Embedding
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"

# Семантическая нарезка - короткие осмысленные сегменты (15-20 сек)
CHUNK_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_THRESHOLD = 0.55       # Порог сходства для разделения
CHUNK_MIN_CHARS = 80         # Минимум символов (~5-8 сек речи, одно предложение)
CHUNK_MAX_CHARS = 350        # Максимум символов (~15-20 сек речи)
CHUNK_MIN_SECONDS = 5        # Минимум длительности (одно предложение)
CHUNK_MAX_SECONDS = 20       # Максимум длительности (жёсткий лимит)

# Поиск
SEARCH_TOP_K = 20            # Кол-во результатов по умолчанию

# FFmpeg
FFMPEG_CRF = 23
FFMPEG_PRESET = "fast"

# Watcher (автообработка папки)
WATCH_INTERVAL_SEC = 5       # Как часто проверять папку
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v"}

# Chunking version
USE_CHUNKING_V2 = True       # Использовать улучшенную версию chunking с исправлением багов

