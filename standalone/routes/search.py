from fastapi import APIRouter

from .. import search as search_mod
from ..db import get_db
from ..schemas import SearchRequest

router = APIRouter(prefix="/api", tags=["search"])


def _video_ids_from_channels(channel_names: list[str]) -> list[str]:
    if not channel_names:
        return []
    conn = get_db()
    placeholders = ",".join("?" * len(channel_names))
    rows = conn.execute(
        f"SELECT video_id FROM videos WHERE channel_name IN ({placeholders})",
        channel_names,
    ).fetchall()
    conn.close()
    return [r["video_id"] for r in rows]


@router.post("/search")
def api_search(req: SearchRequest):
    video_ids = req.video_ids
    if req.filter_tags and req.filter_tags.strip():
        channel_names = [s.strip() for s in req.filter_tags.split(",") if s.strip()]
        channel_video_ids = _video_ids_from_channels(channel_names)
        if video_ids is not None:
            vid_set = set(video_ids)
            video_ids = [vid for vid in channel_video_ids if vid in vid_set]
        else:
            video_ids = channel_video_ids if channel_video_ids else None
    results = search_mod.search(req.query, req.top_k, video_ids=video_ids)
    return [
        {
            "segment_id": r["segment_id"],
            "video_id": r["video_id"],
            "start": r["start_sec"],
            "end": r["end_sec"],
            "text": r["text"],
            "score": r["score"],
        }
        for r in results
    ]
