"""Общий кэш моделей — thread-safe загрузка + LRU cache для embeddings.

Три модели:
  1. Faster-Whisper large-v3 (CTranslate2) — транскрибация
  2. multilingual-e5-large (~1.7 GB) — embedding для поиска
  3. paraphrase-multilingual-MiniLM-L12-v2 (~470 MB) — семантическая нарезка

Паттерны из app/embedding.py:
- threading.Lock() для безопасной загрузки моделей
- @lru_cache для query embeddings (ускоряет повторные запросы)
"""
import gc
import hashlib
import time
import logging
import threading
from functools import lru_cache
from typing import List, Tuple

logger = logging.getLogger("standalone.models")

_cache = {}
_lock = threading.Lock()

# LRU cache для query embeddings — избегаем re-encode повторных запросов
_QUERY_CACHE_SIZE = 512


def get_embed_model():
    """Embedding модель (thread-safe, общая для index + search)."""
    with _lock:
        if "embed" in _cache:
            return _cache["embed"]

        from sentence_transformers import SentenceTransformer
        import torch
        from .config import EMBEDDING_MODEL

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Загрузка embedding '%s' на %s...", EMBEDDING_MODEL, device)
        t0 = time.time()
        model = SentenceTransformer(EMBEDDING_MODEL, device=device)
        logger.info("Embedding загружен за %.1f с", time.time() - t0)
        _cache["embed"] = model
        return model


def get_chunk_model():
    """Модель для семантической нарезки (thread-safe, лёгкая)."""
    with _lock:
        if "chunk" in _cache:
            return _cache["chunk"]

        from sentence_transformers import SentenceTransformer
        import torch
        from .config import CHUNK_MODEL

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Загрузка chunking '%s' на %s...", CHUNK_MODEL, device)
        t0 = time.time()
        model = SentenceTransformer(CHUNK_MODEL, device=device)
        logger.info("Chunking загружен за %.1f с", time.time() - t0)
        _cache["chunk"] = model
        return model


def get_whisper():
    """Faster-Whisper (CTranslate2) — thread-safe загрузка."""
    with _lock:
        if "whisper" in _cache:
            return _cache["whisper"]

        import torch
        from faster_whisper import WhisperModel
        from .config import WHISPER_MODEL

        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info("GPU: %s (%.1f GB)", gpu_name, gpu_mem)

        logger.info("Загрузка Faster-Whisper '%s' на %s (%s)...", WHISPER_MODEL, device, compute_type)
        t0 = time.time()
        model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type)
        logger.info("Whisper загружен за %.1f с", time.time() - t0)

        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info(0)
            logger.info("GPU после загрузки: %.1f GB свободно / %.1f GB всего", free / 1e9, total / 1e9)

        _cache["whisper"] = model
        return model


def release_whisper():
    """Выгрузить Whisper из GPU."""
    with _lock:
        if "whisper" not in _cache:
            return

        import torch
        del _cache["whisper"]
        gc.collect()

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("Whisper выгружен из GPU")


# ─── LRU Cache для query embeddings ────────────────────────

def _make_cache_key(text: str) -> str:
    """MD5 ключ для LRU cache (text может быть длинным)."""
    return hashlib.md5(text.encode()).hexdigest()


@lru_cache(maxsize=_QUERY_CACHE_SIZE)
def _cached_embed(cache_key: str, text: str) -> Tuple[float, ...]:
    """Кэшированный embedding одного текста. Возвращает tuple для hashability."""
    model = get_embed_model()
    embedding = model.encode([text], normalize_embeddings=True)[0]
    return tuple(embedding.tolist())


def embed_query(text: str) -> List[float]:
    """Embed запроса с LRU cache — повторные запросы мгновенны."""
    key = _make_cache_key(text)
    return list(_cached_embed(key, text))


def get_cache_stats() -> dict:
    """Статистика кэша для мониторинга."""
    return {
        "query_cache": _cached_embed.cache_info()._asdict(),
        "models_loaded": list(_cache.keys()),
    }


def clear_query_cache():
    """Очистить кэш query embeddings."""
    _cached_embed.cache_clear()
    logger.info("Query cache очищен")
