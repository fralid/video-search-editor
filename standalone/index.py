"""Индексация: сегменты → семантические чанки → ChromaDB + FTS5."""
import time
import logging

from .config import CHROMA_DIR, USE_CHUNKING_V2
from .db import get_db, upsert_fts
from .models import get_embed_model
from .metrics import compute_segmentation_metrics, log_metrics

# Выбираем версию chunking на основе feature flag
if USE_CHUNKING_V2:
    from .chunking_v2 import semantic_chunk_v2 as semantic_chunk
else:
    from .chunking import semantic_chunk

logger = logging.getLogger("standalone.index")

_collection = None


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _collection = client.get_or_create_collection(
        name="segments", metadata={"hnsw:space": "cosine"},
    )
    logger.info("ChromaDB: %d vectors", _collection.count())
    return _collection


def _clean_old_fts(conn, video_id: str):
    """Удалить старые FTS записи для видео."""
    try:
        conn.execute(
            "DELETE FROM segments_fts WHERE video_id = ?", (video_id,)
        )
        conn.commit()
    except Exception as e:
        logger.warning("Не удалось очистить FTS для %s: %s", video_id, e)


def index_video(video_id: str) -> str:
    """Индексировать видео: сегменты → чанки → vector + FTS5. Одно соединение БД на всю операцию."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT segment_id, video_id, start_sec, end_sec, text, words_json "
            "FROM segments WHERE video_id=? ORDER BY start_sec",
            (video_id,),
        ).fetchall()

        if not rows:
            conn.close()
            return f"Нет сегментов для '{video_id}'."

        # Удаляем старые FTS записи (то же соединение)
        _clean_old_fts(conn, video_id)
    except Exception:
        conn.close()
        raise

    # Удаляем старые embeddings (ChromaDB) — БД не используем
    collection = _get_collection()
    try:
        existing = collection.get(where={"video_id": video_id})
        old_count = len(existing.get("ids", []))
        if old_count > 0:
            collection.delete(where={"video_id": video_id})
            logger.info("Удалено %d старых векторов для %s", old_count, video_id)
    except Exception as e:
        logger.warning("Не удалось удалить старые векторы: %s", e)

    segments = [dict(r) for r in rows]
    chunks = semantic_chunk(segments)

    # Метрики качества сегментации
    metrics = compute_segmentation_metrics(segments, chunks, vad_chunks=None)
    log_metrics(video_id, metrics)

    # Индексируем семантические чанки
    all_items = []
    for cid, start, end, text in chunks:
        all_items.append({"id": f"{video_id}-{cid}", "vid": video_id, "s": start, "e": end, "t": text})

    model = get_embed_model()

    t0 = time.time()
    batch_size = 64
    total = 0

    for i in range(0, len(all_items), batch_size):
        batch = all_items[i : i + batch_size]
        texts = [it["t"] for it in batch]
        embeddings = model.encode(texts, normalize_embeddings=True).tolist()

        # ChromaDB: vector embeddings
        collection.upsert(
            ids=[it["id"] for it in batch],
            embeddings=embeddings,
            documents=texts,
            metadatas=[{"video_id": it["vid"], "start_sec": it["s"], "end_sec": it["e"]} for it in batch],
        )

        # FTS5: полнотекстовый индекс
        for it in batch:
            upsert_fts(conn, it["id"], it["vid"], it["t"])

        total += len(batch)

    try:
        conn.commit()
        conn.execute("UPDATE videos SET status='indexed' WHERE video_id=?", (video_id,))
        conn.commit()
    finally:
        conn.close()

    elapsed = time.time() - t0
    return f"{total} vectors + FTS ({len(chunks)} чанков из {len(segments)} сегментов) за {elapsed:.1f}с"
