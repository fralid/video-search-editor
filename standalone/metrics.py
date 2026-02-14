"""Метрики качества сегментации транскриптов.

Включает:
- Hallucination rate (на VAD-negative интервалах)
- Boundary F1 (точность границ сегментов)
- Word timestamp error (MAE и medianAE)
- 5-gram duplicates (прокси для looping)
"""
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter

logger = logging.getLogger("standalone.metrics")


def compute_hallucination_rate(segments: List[Dict[str, Any]], vad_chunks: Optional[List[Tuple[float, float]]] = None) -> float:
    """Вычислить hallucination rate на VAD-negative интервалах.
    
    HallucinationRate = (#VAD-negative секунд с текстом) / (#VAD-negative секунд)
    
    Args:
        segments: Список сегментов с полями start_sec, end_sec, text
        vad_chunks: Список (start, end) интервалов речи из VAD. Если None, метрика не вычисляется.
    
    Returns:
        Hallucination rate (0.0-1.0), или 0.0 если vad_chunks не предоставлены
    """
    if not vad_chunks:
        return 0.0
    
    total_vad_negative_sec = 0
    hallucinated_sec = 0
    
    # Строим маску VAD: где есть речь (с точностью до секунды)
    vad_mask = set()
    for start, end in vad_chunks:
        for t in range(int(start), int(end) + 1):
            vad_mask.add(t)
    
    # Проверяем каждый сегмент
    for seg in segments:
        seg_start = int(seg.get('start_sec', 0))
        seg_end = int(seg.get('end_sec', seg_start))
        text = seg.get('text', '').strip()
        
        if not text:
            continue
        
        for t in range(seg_start, seg_end + 1):
            if t not in vad_mask:
                total_vad_negative_sec += 1
                hallucinated_sec += 1
    
    if total_vad_negative_sec == 0:
        return 0.0
    
    return hallucinated_sec / total_vad_negative_sec


def compute_5gram_duplicates(segments: List[Dict[str, Any]]) -> float:
    """Вычислить долю 5-граммных повторов (прокси для looping).
    
    Returns:
        Доля дублирующихся 5-грамм (0.0-1.0)
    """
    all_5grams = []
    for seg in segments:
        text = seg.get('text', '').strip()
        if not text:
            continue
        words = text.split()
        for i in range(len(words) - 4):
            all_5grams.append(tuple(words[i:i+5]))
    
    if not all_5grams:
        return 0.0
    
    counts = Counter(all_5grams)
    duplicates = sum(1 for c in counts.values() if c > 1)
    return duplicates / len(all_5grams)


def compute_boundary_f1(
    predicted_boundaries: List[float],
    gold_boundaries: List[float],
    delta_ms: float = 500.0
) -> Dict[str, float]:
    """Вычислить Boundary F1 с допуском delta_ms.
    
    TP: предсказанная граница попадает в ±delta от gold
    Precision = TP / (TP + FP)
    Recall = TP / (TP + FN)
    F1 = 2 * Precision * Recall / (Precision + Recall)
    
    Args:
        predicted_boundaries: Список предсказанных границ (в секундах)
        gold_boundaries: Список эталонных границ (в секундах)
        delta_ms: Допуск в миллисекундах
    
    Returns:
        Словарь с метриками: precision, recall, f1, tp, fp, fn
    """
    delta_sec = delta_ms / 1000.0
    
    tp = 0
    fp = 0
    fn = 0
    
    # Для каждой gold границы ищем ближайшую predicted
    matched_predicted = set()
    for gold_boundary in gold_boundaries:
        closest_pred = None
        min_dist = float('inf')
        
        for i, pred_boundary in enumerate(predicted_boundaries):
            if i in matched_predicted:
                continue
            dist = abs(pred_boundary - gold_boundary)
            if dist < min_dist and dist <= delta_sec:
                min_dist = dist
                closest_pred = i
        
        if closest_pred is not None:
            tp += 1
            matched_predicted.add(closest_pred)
        else:
            fn += 1
    
    fp = len(predicted_boundaries) - len(matched_predicted)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def compute_word_timestamp_error(
    predicted_words: List[Dict[str, Any]],
    gold_words: List[Dict[str, Any]]
) -> Dict[str, float]:
    """Вычислить MAE и medianAE для word timestamps.
    
    Вычисляется только для слов с точным совпадением текста.
    
    Args:
        predicted_words: Список предсказанных слов с полями word, start, end
        gold_words: Список эталонных слов с полями word, start, end
    
    Returns:
        Словарь с метриками: mae_start, mae_end, median_ae
    """
    try:
        import numpy as np
    except ImportError:
        logger.warning("numpy не установлен, используем базовые вычисления")
        np = None
    
    errors_start = []
    errors_end = []
    
    # Строим словарь gold по тексту (нормализованному)
    gold_dict = {}
    for w in gold_words:
        word_text = w.get('word', '').strip().lower()
        if word_text:
            gold_dict[word_text] = (w.get('start', 0.0), w.get('end', 0.0))
    
    # Сравниваем predicted с gold
    for pred_word in predicted_words:
        word_lower = pred_word.get('word', '').strip().lower()
        if word_lower in gold_dict:
            gold_start, gold_end = gold_dict[word_lower]
            pred_start = pred_word.get('start', 0.0)
            pred_end = pred_word.get('end', pred_start)
            
            errors_start.append(abs(pred_start - gold_start))
            errors_end.append(abs(pred_end - gold_end))
    
    if not errors_start:
        return {
            "mae_start": 0.0,
            "mae_end": 0.0,
            "median_ae": 0.0,
        }
    
    if np:
        return {
            "mae_start": float(np.mean(errors_start)),
            "mae_end": float(np.mean(errors_end)),
            "median_ae": float(np.median(errors_start + errors_end)),
        }
    else:
        # Fallback без numpy
        all_errors = errors_start + errors_end
        all_errors.sort()
        median_idx = len(all_errors) // 2
        return {
            "mae_start": sum(errors_start) / len(errors_start),
            "mae_end": sum(errors_end) / len(errors_end),
            "median_ae": all_errors[median_idx] if all_errors else 0.0,
        }


def compute_segmentation_metrics(
    segments: List[Dict[str, Any]],
    chunks: List[Tuple[str, float, float, str]],
    vad_chunks: Optional[List[Tuple[float, float]]] = None
) -> Dict[str, Any]:
    """Вычислить все метрики сегментации.
    
    Args:
        segments: RAW сегменты из транскрибации
        chunks: Семантические чанки (chunk_id, start, end, text)
        vad_chunks: VAD интервалы (если доступны)
    
    Returns:
        Словарь со всеми метриками
    """
    metrics = {
        "num_raw_segments": len(segments),
        "num_chunks": len(chunks),
    }
    
    # Метрики длительности чанков
    if chunks:
        chunk_durations = [c[2] - c[1] for c in chunks]
        chunk_lengths = [len(c[3]) for c in chunks]
        
        metrics.update({
            "avg_chunk_duration": sum(chunk_durations) / len(chunk_durations),
            "max_chunk_duration": max(chunk_durations),
            "min_chunk_duration": min(chunk_durations),
            "avg_chunk_length": sum(chunk_lengths) / len(chunk_lengths),
            "max_chunk_length": max(chunk_lengths),
            "min_chunk_length": min(chunk_lengths),
        })
        
        # Проверка на гигантские чанки
        metrics["chunks_over_5min"] = sum(1 for d in chunk_durations if d > 300)
        metrics["chunks_over_max_chars"] = sum(1 for l in chunk_lengths if l > 2000)
        metrics["chunks_over_max_sec"] = sum(1 for d in chunk_durations if d > 120)
    
    # Метрики RAW сегментов
    if segments:
        seg_durations = [s.get('end_sec', 0) - s.get('start_sec', 0) for s in segments]
        seg_lengths = [len(s.get('text', '')) for s in segments]
        
        metrics.update({
            "avg_segment_duration": sum(seg_durations) / len(seg_durations),
            "max_segment_duration": max(seg_durations),
            "segments_over_5min": sum(1 for d in seg_durations if d > 300),
        })
    
    # Hallucination rate
    if vad_chunks:
        metrics["hallucination_rate"] = compute_hallucination_rate(segments, vad_chunks)
    
    # 5-gram duplicates
    metrics["5gram_duplicates"] = compute_5gram_duplicates(segments)
    
    return metrics


def log_metrics(video_id: str, metrics: Dict[str, Any]):
    """Логировать метрики в структурированном формате."""
    logger.info(
        "METRICS",
        extra={
            "video_id": video_id,
            "metrics": metrics,
        }
    )
    # Также выводим в консоль для удобства
    print(f"[METRICS] {video_id}: {json.dumps(metrics, indent=2, ensure_ascii=False)}", flush=True)
