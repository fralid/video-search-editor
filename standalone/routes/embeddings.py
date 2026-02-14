import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..db import get_db

logger = logging.getLogger("standalone.api")
router = APIRouter(prefix="/api", tags=["embeddings"])


@router.delete("/embeddings/{video_id}")
def api_delete_embeddings(video_id: str):
    """Удалить эмбеддинги из ChromaDB по video_id (даже если видео уже удалено из БД)."""
    try:
        from ..index import _get_collection
        collection = _get_collection()

        results = collection.get(where={"video_id": video_id})
        count_before = len(results.get("ids", [])) if results else 0

        if count_before == 0:
            return {"status": "not_found", "message": f"Эмбеддинги для видео '{video_id}' не найдены в ChromaDB"}

        collection.delete(where={"video_id": video_id})

        logger.info("Удалены эмбеддинги из ChromaDB для видео %s (удалено векторов: %d)", video_id, count_before)
        return {"status": "deleted", "video_id": video_id, "deleted_count": count_before}
    except Exception as e:
        logger.error("Ошибка удаления эмбеддингов для %s: %s", video_id, e, exc_info=True)
        return JSONResponse(
            {"status": "error", "message": f"Ошибка удаления эмбеддингов: {str(e)}"},
            status_code=500,
        )


@router.get("/embeddings/orphaned")
def api_list_orphaned_embeddings():
    """Список всех video_id в ChromaDB, которых нет в БД (осиротевшие эмбеддинги)."""
    try:
        from ..index import _get_collection
        collection = _get_collection()

        all_results = collection.get()
        all_video_ids = set()

        if all_results and "metadatas" in all_results:
            for meta in all_results["metadatas"]:
                if meta and "video_id" in meta:
                    all_video_ids.add(meta["video_id"])

        conn = get_db()
        db_video_ids = set(row[0] for row in conn.execute("SELECT video_id FROM videos").fetchall())
        conn.close()

        orphaned = sorted(all_video_ids - db_video_ids)

        orphaned_stats = []
        for vid in orphaned:
            results = collection.get(where={"video_id": vid})
            count = len(results.get("ids", [])) if results else 0
            orphaned_stats.append({"video_id": vid, "vectors_count": count})

        return {
            "status": "ok",
            "orphaned_count": len(orphaned),
            "orphaned": orphaned_stats,
        }
    except Exception as e:
        logger.error("Ошибка получения списка осиротевших эмбеддингов: %s", e, exc_info=True)
        return JSONResponse(
            {"status": "error", "message": f"Ошибка: {str(e)}"},
            status_code=500,
        )
