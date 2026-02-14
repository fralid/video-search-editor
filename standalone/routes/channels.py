from fastapi import APIRouter

from ..db import get_db

router = APIRouter(prefix="/api", tags=["channels"])


@router.get("/channels")
def api_channels():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT channel_name AS name, COUNT(*) AS count
        FROM videos
        WHERE channel_name IS NOT NULL AND channel_name != ''
        GROUP BY channel_name
        ORDER BY count DESC
        """
    ).fetchall()
    conn.close()
    return [{"name": r["name"], "count": r["count"]} for r in rows]
