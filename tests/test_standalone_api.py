"""Базовые тесты API standalone-приложения (health, list videos)."""
import pytest
from fastapi.testclient import TestClient

from standalone.api import app

client = TestClient(app)


def test_health_returns_200():
    """GET /api/health возвращает 200 и status ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"


def test_root_returns_ok():
    """GET / возвращает описание сервиса."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert "service" in data


def test_list_videos_returns_list():
    """GET /api/videos возвращает список (пустой или с элементами)."""
    response = client.get("/api/videos")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        assert "video_id" in item
        assert "title" in item
        assert "status_download" in item
        assert "status_transcribe" in item


def test_search_returns_list():
    """POST /api/search возвращает список с ожидаемой структурой."""
    response = client.post(
        "/api/search",
        json={"query": "test", "top_k": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        assert "segment_id" in item
        assert "video_id" in item
        assert "start" in item or "start_sec" in item
        assert "end" in item or "end_sec" in item
        assert "text" in item
        assert "score" in item


def test_search_with_video_ids():
    """POST /api/search с video_ids принимается и возвращает список."""
    response = client.post(
        "/api/search",
        json={"query": "something", "top_k": 3, "video_ids": ["non-existent-id"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_queue_get_returns_list():
    """GET /api/queue возвращает список."""
    response = client.get("/api/queue")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_queue_delete_not_found():
    """DELETE /api/queue/{video_id} при отсутствии в очереди возвращает 404 или 409."""
    response = client.delete("/api/queue/nonexistent-video-id-12345")
    assert response.status_code in (404, 409)
    data = response.json()
    assert "error" in data


def test_scan_returns_structure():
    """POST /api/videos/scan возвращает added, already, total_files."""
    response = client.post("/api/videos/scan")
    assert response.status_code == 200
    data = response.json()
    assert "added" in data
    assert "already" in data
    assert "total_files" in data
    assert "videos" in data


def test_process_pending_returns_structure():
    """POST /api/videos/process-pending возвращает enqueued, skipped, total."""
    response = client.post("/api/videos/process-pending")
    assert response.status_code == 200
    data = response.json()
    assert "enqueued" in data
    assert "skipped" in data
    assert "total" in data
    assert "videos" in data


def test_add_video_invalid_path_returns_400():
    """POST /api/videos с несуществующим путём возвращает 400."""
    response = client.post(
        "/api/videos",
        json={"url": "file:///nonexistent/path/to/video.mp4"},
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
