"""Pydantic-модели запросов API."""
from typing import Optional
from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    top_k: int = 30
    filter_tags: Optional[str] = None
    video_ids: Optional[list[str]] = None


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
    quality: str = "720p"
    browser: str = "firefox"


class VideoPatchRequest(BaseModel):
    channel_name: Optional[str] = None
    source_url: Optional[str] = None
