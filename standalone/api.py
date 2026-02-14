"""FastAPI сервер — совместим с оригинальным React фронтендом."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import VIDEO_DIR, CLIPS_DIR
from .db import init_db
from .routes import (
    health_router,
    channels_router,
    search_router,
    queue_router,
    clips_router,
    download_router,
    embeddings_router,
    videos_router,
)


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

VIDEO_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files/videos", StaticFiles(directory=str(VIDEO_DIR)), name="videos")
app.mount("/files/clips", StaticFiles(directory=str(CLIPS_DIR)), name="clips")

app.include_router(health_router)
app.include_router(channels_router)
app.include_router(search_router)
app.include_router(queue_router)
app.include_router(clips_router)
app.include_router(download_router)
app.include_router(embeddings_router)
app.include_router(videos_router)

init_db()
