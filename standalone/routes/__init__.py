"""Роутеры API."""
from .health import router as health_router
from .channels import router as channels_router
from .search import router as search_router
from .queue import router as queue_router
from .clips import router as clips_router
from .download import router as download_router
from .embeddings import router as embeddings_router
from .videos import router as videos_router

__all__ = [
    "health_router",
    "channels_router",
    "search_router",
    "queue_router",
    "clips_router",
    "download_router",
    "embeddings_router",
    "videos_router",
]
