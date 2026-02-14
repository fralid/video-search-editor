import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from .. import download as download_mod
from ..db import get_db
from ..queue_pipeline import enqueue_pipeline, register_download, pop_download, set_download_error
from ..schemas import DownloadRequest

logger = logging.getLogger("standalone.api")
router = APIRouter(prefix="/api", tags=["download"])


@router.post("/download/youtube")
def api_download_youtube(req: DownloadRequest, bg: BackgroundTasks):
    if not download_mod.YTDLP_EXE.exists():
        return JSONResponse(
            {"error": f"yt-dlp.exe не найден в {download_mod._YTDLP_DIR}"},
            status_code=500,
        )
    dl_key = req.url
    register_download(
        dl_key,
        {
            "video_id": f"dl-{hash(req.url) & 0xFFFFFF:06x}",
            "status": "downloading",
            "title": f"⬇️ {req.url.split('v=')[-1][:11]}",
            "url": req.url,
            "added_at": datetime.now().isoformat(),
        },
    )

    def _do():
        try:
            result = download_mod.download_video(req.url, req.quality, req.browser)
            if result["status"] == "error":
                logger.error("Download failed: %s", result.get("error"))
                set_download_error(dl_key, result.get("error", ""))
                return
            video_id = result["video_id"]
            title = result["title"]
            path = result["path"]
            already_existed = result["status"] == "exists"
            channel_name = result.get("channel_name")
            duration = result.get("duration")
            thumbnail_url = result.get("thumbnail_url")
            uploaded_at = result.get("uploaded_at")
            source_url = result.get("source_url") or req.url
            pop_download(dl_key)
            conn = get_db()
            exists = conn.execute("SELECT video_id FROM videos WHERE video_id=?", (video_id,)).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO videos (video_id, title, local_path, status, channel_name, duration, thumbnail_url, uploaded_at, source_url) VALUES (?,?,?,?,?,?,?,?,?)",
                    (video_id, title, path, "added", channel_name, duration, thumbnail_url, uploaded_at, source_url),
                )
                conn.commit()
                conn.close()
                enqueue_pipeline(video_id, title)
            else:
                if already_existed and (channel_name is not None or duration is not None or thumbnail_url is not None or uploaded_at is not None or source_url is not None):
                    conn.execute(
                        "UPDATE videos SET channel_name=COALESCE(?, channel_name), duration=COALESCE(?, duration), thumbnail_url=COALESCE(?, thumbnail_url), uploaded_at=COALESCE(?, uploaded_at), source_url=COALESCE(?, source_url) WHERE video_id=?",
                        (channel_name, duration, thumbnail_url, uploaded_at, source_url, video_id),
                    )
                    conn.commit()
                conn.close()
                if already_existed:
                    logger.info("Видео уже скачано и зарегистрировано, пропускаем: %s", video_id)
        except Exception as e:
            logger.error("Download exception: %s", e, exc_info=True)
            set_download_error(dl_key, str(e))

    bg.add_task(_do)
    return {"status": "downloading", "url": req.url, "quality": req.quality}


@router.get("/download/status")
def api_download_status():
    return {
        "available": download_mod.YTDLP_EXE.exists(),
        "path": str(download_mod._YTDLP_DIR),
    }
