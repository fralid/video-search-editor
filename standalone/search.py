"""Hybrid search: ChromaDB (vector) + FTS5 (BM25) + RRF fusion + дедупликация.

Паттерны портированы из app/query.py:
- Reciprocal Rank Fusion для объединения vector + FTS результатов
- Дедупликация перекрывающихся сегментов одного видео
- FTS5 BM25 поиск для точных совпадений слов
"""
import re
import logging
from typing import List, Dict, Any, Optional

from .config import SEARCH_TOP_K
from .models import get_embed_model
from .db import fts_search as _db_fts_search

logger = logging.getLogger("standalone.search")

_collection = None


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection
    import chromadb
    from .config import CHROMA_DIR
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _collection = client.get_or_create_collection(
        name="segments", metadata={"hnsw:space": "cosine"},
    )
    return _collection


# ─── Vector Search ──────────────────────────────────────────

def _vector_search(query: str, top_k: int, video_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Семантический поиск через ChromaDB. Если video_ids задан — только эти видео."""
    model = get_embed_model()
    collection = _get_collection()

    emb = model.encode([query], normalize_embeddings=True).tolist()
    kwargs = {"query_embeddings": emb, "n_results": top_k}
    if video_ids:
        kwargs["where"] = {"video_id": {"$in": video_ids}}
    results = collection.query(**kwargs)

    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    docs = results.get("documents", [[]])[0]

    out = []
    for sid, dist, meta, doc in zip(ids, distances, metas, docs):
        if len(doc) < 30:
            continue
        out.append({
            "segment_id": sid,
            "video_id": meta.get("video_id", ""),
            "start_sec": meta.get("start_sec", 0.0),
            "end_sec": meta.get("end_sec", 0.0),
            "text": doc,
            "score": round(1 - dist, 4),
            "source": "vector",
        })
    return out


# ─── FTS5 Search ────────────────────────────────────────────

def _fts_search(query: str, top_k: int, video_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """BM25 поиск через FTS5. Если video_ids задан — фильтруем по ним после запроса."""
    clean = re.sub(r'[^\w\s]', ' ', query).strip()
    if not clean:
        return []

    rows = _db_fts_search(clean, top_k * 3 if video_ids else top_k)
    if not rows:
        return []
    if video_ids:
        vid_set = set(video_ids)
        rows = [r for r in rows if r.get("video_id") in vid_set][:top_k]
    else:
        rows = rows[:top_k]

    # Подтягиваем timestamps из ChromaDB метаданных (если есть)
    # FTS хранит segment_id = chunk ID, timestamps можно получить из collection
    out = []
    try:
        collection = _get_collection()
        chunk_ids = [r["segment_id"] for r in rows if r.get("segment_id")]
        if chunk_ids:
            meta_results = collection.get(ids=chunk_ids)
            meta_map = {}
            if meta_results and meta_results.get("ids"):
                for i, cid in enumerate(meta_results["ids"]):
                    m = meta_results["metadatas"][i] if meta_results.get("metadatas") else {}
                    meta_map[cid] = m
    except Exception:
        meta_map = {}

    for r in rows:
        sid = r.get("segment_id", "")
        if not sid:
            continue
        
        # bm25: rank < 0, меньше (по модулю больше) = лучше
        rank = float(r.get("rank", 0))
        score = 1.0 / (1.0 + abs(rank))

        meta = meta_map.get(sid, {})
        out.append({
            "segment_id": sid,
            "video_id": r.get("video_id", "") or meta.get("video_id", ""),
            "start_sec": meta.get("start_sec", 0.0),
            "end_sec": meta.get("end_sec", 0.0),
            "text": r["text"],
            "score": round(score, 4),
            "source": "fts",
        })
    return out


# ─── RRF Fusion ─────────────────────────────────────────────

def _rrf_merge(
    lists: List[List[Dict[str, Any]]],
    k: float = 60.0,
) -> List[Dict[str, Any]]:
    """Reciprocal Rank Fusion: суммируем 1 / (k + rank).

    Объединяет результаты из разных источников (vector + FTS)
    в единый ранжированный список.
    """
    scores: Dict[str, float] = {}
    payloads: Dict[str, Dict[str, Any]] = {}

    for lst in lists:
        for rank, item in enumerate(lst, start=1):
            sid = item["segment_id"]
            scores[sid] = scores.get(sid, 0.0) + 1.0 / (k + rank)
            # Сохраняем лучший payload (vector предпочтительнее — имеет timestamps)
            if sid not in payloads or item.get("source") == "vector":
                payloads[sid] = item

    merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    out = []
    for sid, sc in merged:
        result = payloads[sid].copy()
        result["score"] = round(sc, 4)
        result["source"] = "hybrid"
        out.append(result)
    return out


# ─── Дедупликация ───────────────────────────────────────────

def _deduplicate_overlapping(
    results: List[Dict[str, Any]],
    overlap_threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """Убираем перекрывающиеся результаты из одного видео.

    Оставляем результат с лучшим score при значительном пересечении.
    """
    if not results:
        return results

    by_video: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        vid = r["video_id"]
        by_video.setdefault(vid, []).append(r)

    final = []
    for vid, items in by_video.items():
        sorted_items = sorted(items, key=lambda x: x["score"], reverse=True)
        kept = []

        for candidate in sorted_items:
            c_start = candidate["start_sec"]
            c_end = candidate["end_sec"]
            c_duration = max(c_end - c_start, 0.1)

            overlaps = False
            for k in kept:
                k_start = k["start_sec"]
                k_end = k["end_sec"]

                overlap_start = max(c_start, k_start)
                overlap_end = min(c_end, k_end)
                overlap_duration = max(0, overlap_end - overlap_start)

                if overlap_duration / c_duration >= overlap_threshold:
                    overlaps = True
                    break

            if not overlaps:
                kept.append(candidate)

        final.extend(kept)

    final.sort(key=lambda x: x["score"], reverse=True)
    return final


# ─── Main Search ────────────────────────────────────────────

def search(
    query: str,
    top_k: int = SEARCH_TOP_K,
    use_fts: bool = True,
    video_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Hybrid search: vector + FTS5 + RRF fusion + дедупликация.

    Args:
        query: поисковый запрос
        top_k: количество результатов
        use_fts: использовать ли FTS5 (BM25) дополнительно к vector
        video_ids: если задан — искать только в этих видео

    Returns:
        Отсортированный список результатов с полями:
        segment_id, video_id, start_sec, end_sec, text, score, source
    """
    if not query.strip():
        return []

    n_candidates = top_k * 3

    vec_results = _vector_search(query, n_candidates, video_ids=video_ids)

    if use_fts:
        fts_results = _fts_search(query, n_candidates, video_ids=video_ids)
    else:
        fts_results = []

    # 3. RRF fusion (если есть оба источника)
    if fts_results:
        fused = _rrf_merge([vec_results, fts_results])
    else:
        fused = vec_results

    # 4. Дедупликация перекрывающихся сегментов
    deduplicated = _deduplicate_overlapping(fused)

    return deduplicated[:top_k]
