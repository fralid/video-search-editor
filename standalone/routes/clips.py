from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .. import cut as cut_mod
from ..schemas import ManualClipRequest

router = APIRouter(prefix="/api", tags=["clips"])


@router.post("/clips/manual")
def api_manual_clip(req: ManualClipRequest):
    result = cut_mod.cut_clip(req.video_id, req.start, req.end)
    if Path(result).exists():
        return {
            "clip_id": Path(result).stem,
            "video_id": req.video_id,
            "start_sec": req.start,
            "end_sec": req.end,
            "download_url": f"/files/clips/{Path(result).name}",
        }
    return JSONResponse({"error": result}, status_code=500)
