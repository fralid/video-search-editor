"""Очередь обработки видео и пайплайн транскрипция → индексация."""
import threading
import concurrent.futures
import logging
from datetime import datetime

from . import transcribe as transcribe_mod
from . import index as index_mod

logger = logging.getLogger("standalone.queue_pipeline")

_gpu_semaphore = threading.Semaphore(2)
gpu_lock = _gpu_semaphore  # для force-transcribe / force-index

_queue: dict = {}
_download_queue: dict = {}
_queue_lock = threading.Lock()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="pipeline")


def _queue_set(video_id: str, **kwargs):
    with _queue_lock:
        if video_id not in _queue:
            _queue[video_id] = {"video_id": video_id, "status": "waiting", "title": video_id}
        _queue[video_id].update(kwargs)


def get_queue_list() -> list:
    with _queue_lock:
        dl_items = list(_download_queue.values())
        pipeline_items = list(_queue.values())
        return dl_items + pipeline_items


def enqueue_pipeline(video_id: str, title: str = ""):
    _queue_set(video_id, status="waiting", title=title or video_id, added_at=datetime.now().isoformat())
    _executor.submit(_run_queued_pipeline, video_id)


def queue_remove(video_id: str) -> tuple[bool, str | None]:
    """Удалить из очереди. Возвращает (success, error_message)."""
    with _queue_lock:
        item = _queue.get(video_id)
        if not item:
            return False, "Не найдено в очереди"
        if item["status"] == "processing":
            return False, "Нельзя удалить — уже обрабатывается"
        _queue.pop(video_id, None)
    return True, None


def is_in_queue(video_id: str) -> bool:
    with _queue_lock:
        return video_id in _queue


def queue_clear() -> int:
    with _queue_lock:
        to_remove = [vid for vid, item in _queue.items() if item["status"] in ("done", "error")]
        for vid in to_remove:
            del _queue[vid]
        dl_remove = [k for k, item in _download_queue.items() if item["status"] == "error"]
        for k in dl_remove:
            del _download_queue[k]
    return len(to_remove) + len(dl_remove)


def register_download(dl_key: str, entry: dict):
    with _queue_lock:
        _download_queue[dl_key] = entry


def pop_download(dl_key: str):
    with _queue_lock:
        _download_queue.pop(dl_key, None)


def set_download_error(dl_key: str, error: str):
    with _queue_lock:
        if dl_key in _download_queue:
            _download_queue[dl_key]["status"] = "error"
            _download_queue[dl_key]["error"] = error


def _run_pipeline(video_id: str):
    import time
    import torch
    import gc

    try:
        logger.info("Pipeline start: %s", video_id)
        with gpu_lock:
            transcribe_mod.transcribe(video_id)
            logger.info("Очистка памяти GPU перед индексацией...")
            from .models import release_whisper
            release_whisper()
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            time.sleep(1)
        index_mod.index_video(video_id)
        logger.info("Pipeline done: %s", video_id)
    except Exception as e:
        import traceback
        logger.error("Pipeline error %s: %s", video_id, e)
        logger.error("Traceback:\n%s", traceback.format_exc())
        print(f"[ERROR] Pipeline error {video_id}: {e}", flush=True)
        traceback.print_exc()
        try:
            from .models import release_whisper
            release_whisper()
        except Exception:
            pass


def _run_queued_pipeline(video_id: str):
    with _queue_lock:
        if video_id not in _queue:
            return
    _queue_set(video_id, status="processing", started_at=datetime.now().isoformat())
    with _gpu_semaphore:
        try:
            _run_pipeline(video_id)
            _queue_set(video_id, status="done")
        except Exception as e:
            _queue_set(video_id, status="error", error=str(e))
