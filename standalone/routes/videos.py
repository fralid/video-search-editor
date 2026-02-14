"""Роуты /api/videos и /api/videos/..."""
import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from ..config import VIDEO_DIR, CLIPS_DIR, VIDEO_EXTENSIONS
from ..db import get_db
from .. import transcribe as transcribe_mod
from .. import index as index_mod
from ..queue_pipeline import enqueue_pipeline, is_in_queue, gpu_lock
from ..schemas import AddVideoRequest, BulkAddRequest, VideoPatchRequest
from ..metrics import compute_segmentation_metrics

logger = logging.getLogger("standalone.api")
router = APIRouter(prefix="/api", tags=["videos"])


@router.post("/videos/scan")
def api_scan_videos(bg: BackgroundTasks, process: bool = False):
    if not VIDEO_DIR.exists():
        return {"added": 0, "already": 0, "total_files": 0}

    conn = get_db()
    known_ids = set()
    known_paths = set()
    for row in conn.execute("SELECT video_id, local_path FROM videos").fetchall():
        known_ids.add(row["video_id"])
        if row["local_path"]:
            known_paths.add(str(Path(row["local_path"]).resolve()))

    added = []
    already = 0
    total_files = 0

    for f in VIDEO_DIR.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        total_files += 1
        resolved = str(f.resolve())
        video_id = f.stem
        if video_id in known_ids or resolved in known_paths:
            already += 1
            continue
        title = f.stem
        conn.execute(
            "INSERT INTO videos (video_id, title, local_path, status) VALUES (?,?,?,?)",
            (video_id, title, resolved, "added"),
        )
        added.append({"video_id": video_id, "title": title})

    conn.commit()
    conn.close()

    if process:
        for v in added:
            enqueue_pipeline(v["video_id"], v["title"])

    return {
        "added": len(added),
        "already": already,
        "total_files": total_files,
        "videos": added[:20],
    }


@router.post("/videos/process-pending")
def api_process_pending():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT v.video_id, v.title, COALESCE(seg.cnt, 0) AS seg_count
        FROM videos v
        LEFT JOIN (
            SELECT video_id, COUNT(*) AS cnt FROM segments GROUP BY video_id
        ) seg ON v.video_id = seg.video_id
        """
    ).fetchall()
    conn.close()

    enqueued = []
    skipped = 0

    for row in rows:
        video_id = row["video_id"]
        title = row["title"] or video_id
        if row["seg_count"] > 0:
            skipped += 1
            continue
        if is_in_queue(video_id):
            skipped += 1
            continue
        enqueue_pipeline(video_id, title)
        enqueued.append({"video_id": video_id, "title": title})

    return {
        "enqueued": len(enqueued),
        "skipped": skipped,
        "total": len(rows),
        "videos": enqueued[:20],
    }


@router.get("/videos")
def api_list_videos(
    channel: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
):
    conn = get_db()
    sql = """
        SELECT v.video_id, v.title, v.status, v.local_path, v.created_at,
               v.channel_name, v.duration, v.thumbnail_url, v.uploaded_at, v.source_url,
               COALESCE(seg.cnt, 0) AS seg_count
        FROM videos v
        LEFT JOIN (
            SELECT video_id, COUNT(*) AS cnt FROM segments GROUP BY video_id
        ) seg ON v.video_id = seg.video_id
        WHERE 1=1
    """
    params = []
    if channel:
        sql += " AND v.channel_name = ?"
        params.append(channel)
    sql += " ORDER BY v.created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        seg_count = r["seg_count"]
        st = r["status"]
        result.append({
            "video_id": r["video_id"],
            "title": r["title"],
            "channel_id": "standalone",
            "channel_name": (r["channel_name"] if r["channel_name"] else "Local"),
            "description": f"{seg_count} сегментов",
            "tags": "",
            "duration": r["duration"],
            "thumbnail_url": r["thumbnail_url"],
            "uploaded_at": r["uploaded_at"],
            "source_url": r["source_url"],
            "url": f"file://{r['local_path']}" if r["local_path"] else "",
            "local_path": r["local_path"],
            "status_download": "done" if r["local_path"] else "pending",
            "status_transcribe": "done" if st in ("transcribed", "indexed") else ("pending" if st == "added" else st),
            "status_index": "done" if st == "indexed" else "pending",
            "created_at": r["created_at"],
        })

    return result[offset : offset + limit]


@router.post("/videos")
def api_add_video(req: AddVideoRequest, bg: BackgroundTasks):
    src = Path(req.url.replace("file://", ""))
    if not src.exists():
        return JSONResponse({"error": f"Файл не найден: {req.url}"}, status_code=400)

    video_id = src.stem
    dst = VIDEO_DIR / src.name
    if not dst.exists():
        shutil.copy2(src, dst)

    conn = get_db()
    exists = conn.execute("SELECT video_id FROM videos WHERE video_id=?", (video_id,)).fetchone()
    if exists:
        conn.close()
        return {"status": "already_exists", "video_id": video_id}

    conn.execute(
        "INSERT INTO videos (video_id, title, local_path, status) VALUES (?,?,?,?)",
        (video_id, req.tags or video_id, str(dst), "added"),
    )
    conn.commit()
    conn.close()

    enqueue_pipeline(video_id, req.tags or video_id)
    return {"status": "processing_started", "video_id": video_id}


@router.patch("/videos/{video_id}")
def api_patch_video(video_id: str, req: VideoPatchRequest):
    """Обновить метаданные видео (канал, ссылка на источник)."""
    conn = get_db()
    row = conn.execute("SELECT video_id FROM videos WHERE video_id=?", (video_id,)).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "not found"}, status_code=404)
    updates = []
    params = []
    if req.channel_name is not None:
        updates.append("channel_name = ?")
        params.append(req.channel_name)
    if req.source_url is not None:
        updates.append("source_url = ?")
        params.append(req.source_url)
    if updates:
        params.append(video_id)
        conn.execute(f"UPDATE videos SET {', '.join(updates)} WHERE video_id=?", params)
        conn.commit()
    conn.close()
    return {"status": "ok", "video_id": video_id}


@router.post("/videos/{video_id}/transcribe")
def api_transcribe(video_id: str, bg: BackgroundTasks, force: bool = False):
    if force:
        conn = get_db()
        conn.execute("DELETE FROM segments WHERE video_id=?", (video_id,))
        conn.commit()
        conn.close()

    def _do():
        with gpu_lock:
            transcribe_mod.transcribe(video_id)

    bg.add_task(_do)
    return {"status": "transcription_started", "video_id": video_id}


@router.post("/videos/{video_id}/index")
def api_index(video_id: str, bg: BackgroundTasks):
    def _do():
        with gpu_lock:
            index_mod.index_video(video_id)

    bg.add_task(_do)
    return {"status": "indexing_started", "video_id": video_id}


@router.post("/videos/{video_id}/reprocess")
def api_reprocess(video_id: str, bg: BackgroundTasks):
    conn = get_db()
    conn.execute("DELETE FROM segments WHERE video_id=?", (video_id,))
    conn.execute("UPDATE videos SET status='added' WHERE video_id=?", (video_id,))
    conn.commit()
    conn.close()

    enqueue_pipeline(video_id)
    return {"status": "reprocessing_started", "video_id": video_id}


@router.delete("/videos/{video_id}")
def api_delete_video(video_id: str):
    conn = get_db()
    row = conn.execute("SELECT local_path FROM videos WHERE video_id=?", (video_id,)).fetchone()

    segments_count = conn.execute("SELECT COUNT(*) FROM segments WHERE video_id=?", (video_id,)).fetchone()[0]
    clips_count = conn.execute("SELECT COUNT(*) FROM clips WHERE video_id=?", (video_id,)).fetchone()[0]

    conn.execute("DELETE FROM segments WHERE video_id=?", (video_id,))
    conn.execute("DELETE FROM clips WHERE video_id=?", (video_id,))
    conn.execute("DELETE FROM videos WHERE video_id=?", (video_id,))
    conn.commit()
    conn.close()

    try:
        from ..index import _get_collection
        collection = _get_collection()
        deleted_count = collection.delete(where={"video_id": video_id})
        logger.info("Удалены эмбеддинги из ChromaDB для видео %s (удалено векторов: %s)", video_id, deleted_count)
    except Exception as e:
        logger.warning("Не удалось удалить эмбеддинги из ChromaDB для %s: %s", video_id, e)

    if row and row["local_path"]:
        p = Path(row["local_path"])
        if p.exists():
            try:
                p.unlink()
            except Exception as e:
                logger.warning("Не удалось удалить файл %s: %s", p, e)

    return {"status": "deleted", "stats": {"segments": segments_count, "clips": clips_count}}


@router.get("/videos/{video_id}/transcript")
def api_transcript(video_id: str):
    conn = get_db()
    video = conn.execute("SELECT video_id, title FROM videos WHERE video_id=?", (video_id,)).fetchone()
    if not video:
        conn.close()
        return JSONResponse({"error": "not found"}, status_code=404)

    rows = conn.execute(
        "SELECT segment_id, start_sec, end_sec, text, words_json FROM segments WHERE video_id=? ORDER BY start_sec",
        (video_id,),
    ).fetchall()
    conn.close()

    segments = []
    for r in rows:
        words = []
        if r["words_json"]:
            try:
                words = json.loads(r["words_json"])
            except Exception:
                pass
        segments.append({
            "segment_id": r["segment_id"],
            "start": r["start_sec"],
            "end": r["end_sec"],
            "text": r["text"],
            "words": words,
        })

    return {
        "video_id": video["video_id"],
        "title": video["title"],
        "duration": segments[-1]["end"] if segments else 0,
        "segments": segments,
    }


@router.get("/videos/{video_id}/logs")
def api_logs(video_id: str):
    return []


@router.get("/videos/{video_id}/metrics")
def api_get_metrics(video_id: str):
    conn = get_db()
    seg_rows = conn.execute(
        "SELECT segment_id, video_id, start_sec, end_sec, text, words_json "
        "FROM segments WHERE video_id=? ORDER BY start_sec",
        (video_id,),
    ).fetchall()

    if not seg_rows:
        conn.close()
        return {"error": "Нет сегментов для этого видео"}

    segments = [dict(r) for r in seg_rows]

    try:
        from ..index import _get_collection
        collection = _get_collection()
        chunk_results = collection.get(where={"video_id": video_id})
        chunks = []
        if chunk_results.get("metadatas"):
            for i, metadata in enumerate(chunk_results["metadatas"]):
                doc = chunk_results["documents"][i] if chunk_results.get("documents") else ""
                chunk_id = chunk_results["ids"][i] if chunk_results.get("ids") else f"chunk-{i}"
                chunks.append((
                    chunk_id,
                    metadata.get("start_sec", 0.0),
                    metadata.get("end_sec", 0.0),
                    doc,
                ))
    except Exception as e:
        logger.warning("Не удалось получить чанки из ChromaDB: %s", e)
        chunks = []

    conn.close()
    metrics = compute_segmentation_metrics(segments, chunks, vad_chunks=None)
    return metrics


@router.post("/videos/bulk")
def api_bulk_add(req: BulkAddRequest, bg: BackgroundTasks):
    added = []
    for url in req.urls:
        src = Path(url.replace("file://", ""))
        if not src.exists():
            continue
        video_id = src.stem
        dst = VIDEO_DIR / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        conn = get_db()
        exists = conn.execute("SELECT video_id FROM videos WHERE video_id=?", (video_id,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO videos (video_id, title, local_path, status) VALUES (?,?,?,?)",
                (video_id, video_id, str(dst), "added"),
            )
            conn.commit()
            added.append({"video_id": video_id, "title": video_id})
            enqueue_pipeline(video_id)
        conn.close()
    return {"status": "processing_started", "added": len(added), "errors": 0, "videos": added, "failed": []}


@router.post("/videos/import-channel")
def api_import_channel():
    return JSONResponse({"error": "Channel import not available in standalone mode"}, status_code=400)


@router.post("/videos/refresh-all-metadata")
def api_refresh_metadata():
    return {"status": "not_needed", "videos_to_update": 0}
