from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..queue_pipeline import get_queue_list, queue_remove, queue_clear

router = APIRouter(prefix="/api", tags=["queue"])


@router.get("/queue")
def api_queue():
    return get_queue_list()


@router.delete("/queue/{video_id}")
def api_queue_remove(video_id: str):
    ok, err = queue_remove(video_id)
    if not ok:
        return JSONResponse({"error": err}, status_code=404 if "Не найдено" in err else 409)
    return {"status": "removed", "video_id": video_id}


@router.post("/queue/clear")
def api_queue_clear():
    n = queue_clear()
    return {"cleared": n}
