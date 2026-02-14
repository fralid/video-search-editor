"""Улучшенная версия chunking с исправлением критических багов.

Основные улучшения:
1. Принудительное разбиение сегментов > CHUNK_MAX_CHARS
2. Правильный порядок проверок (too_long ПЕРЕД too_short)
3. Использование Razdel для sentence segmentation (если доступен)
4. Защита от гигантских RAW сегментов
"""
import re
import json
import logging
from typing import List, Tuple, Dict, Any

from .config import (
    CHUNK_THRESHOLD, CHUNK_MIN_CHARS, CHUNK_MAX_CHARS,
    CHUNK_MIN_SECONDS, CHUNK_MAX_SECONDS,
)

logger = logging.getLogger("standalone.chunking_v2")

# Попытка импортировать Razdel для лучшего sentence segmentation
try:
    from razdel import sentenize
    HAS_RAZDEL = True
except ImportError:
    HAS_RAZDEL = False
    logger.warning("Razdel не установлен. Используется fallback sentence segmentation.")

# ---- Разбиение на предложения (русский) ----
_ABBREV = [
    (r'т\.е\.', 'Т_Е_'), (r'т\.д\.', 'Т_Д_'), (r'т\.п\.', 'Т_П_'),
    (r'и\.т\.д\.', 'И_Т_Д_'), (r'др\.', 'ДР_'), (r'г\.', 'Г_'),
    (r'руб\.', 'РУБ_'), (r'млн\.', 'МЛН_'), (r'млрд\.', 'МЛРД_'),
    (r'тыс\.', 'ТЫС_'),
]


def _split_sentences(text: str) -> List[str]:
    """
    Разбиение на предложения с учётом русских правил.
    Использует Razdel если доступен, иначе fallback regex.
    """
    if HAS_RAZDEL:
        # Используем Razdel для лучшего качества
        sentences = [s.text for s in sentenize(text)]
        return [s.strip() for s in sentences if s.strip() and len(s.strip()) >= 10]
    
    # Fallback: regex-based
    protected = text
    for pat, repl in _ABBREV:
        protected = re.sub(pat, repl, protected, flags=re.IGNORECASE)
    
    parts = re.split(r'(?<=[.!?])\s+(?=[А-ЯA-Z])|(?<=[.!?])\s*$', protected)
    
    result = []
    for p in parts:
        restored = p
        for pat, repl in _ABBREV:
            restored = restored.replace(repl, pat.replace('\\', ''))
        restored = restored.strip()
        if restored and len(restored) >= 10:
            if not restored[-1] in '.!?':
                restored += '.'
            result.append(restored)
    
    return result if result else [text]


def _force_split_large_segment(seg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Принудительно разбивает сегмент > CHUNK_MAX_CHARS на предложения.
    Используется когда RAW сегмент уже превышает лимиты.
    """
    text = seg["text"]
    start = seg["start_sec"]
    end = seg["end_sec"]
    duration = end - start
    
    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        # Не удалось разбить — возвращаем как есть с предупреждением
        logger.warning(f"Не удалось разбить сегмент {seg.get('segment_id')} ({len(text)} символов)")
        return [seg]
    
    # Пытаемся использовать word timestamps для точных границ
    words_data = None
    try:
        words_json = seg.get("words_json")
        if words_json:
            words_data = json.loads(words_json) if isinstance(words_json, str) else words_json
    except:
        pass
    
    result = []
    current_start = start
    
    if words_data:
        # Используем word timestamps для точных границ предложений
        full_text_with_words = " ".join(w.get("word", "") for w in words_data)
        word_idx = 0
        
        for i, sent in enumerate(sentences):
            sent_words = []
            sent_start = None
            sent_end = None
            
            # Находим слова, которые принадлежат этому предложению
            sent_clean = sent.strip()
            sent_start_in_full = full_text_with_words.find(sent_clean)
            
            if sent_start_in_full != -1:
                # Подсчитываем слова до начала предложения
                words_before = len(full_text_with_words[:sent_start_in_full].split())
                
                # Находим соответствующие word timestamps
                for j, w in enumerate(words_data):
                    if j >= words_before and j < words_before + len(sent_clean.split()):
                        if sent_start is None:
                            sent_start = w.get("start", current_start)
                        sent_end = w.get("end", current_start)
                        sent_words.append(w)
            
            if sent_start is None:
                # Fallback: пропорциональное распределение
                total_chars = sum(len(s) for s in sentences)
                sent_chars = len(sent)
                sent_duration = (sent_chars / total_chars) * duration if total_chars > 0 else duration / len(sentences)
                sent_start = current_start
                sent_end = current_start + sent_duration
            
            # Последнее предложение должно заканчиваться на end
            if i == len(sentences) - 1:
                sent_end = end
            
            # Сохраняем word timestamps для этого предложения
            words_json_result = json.dumps(sent_words, ensure_ascii=False) if sent_words else None
            
            result.append({
                "segment_id": f"{seg.get('segment_id', 'split')}-{i}",
                "start_sec": sent_start,
                "end_sec": sent_end,
                "text": sent,
                "words_json": words_json_result,
            })
            
            current_start = sent_end
    else:
        # Fallback: пропорциональное распределение без word timestamps
        total_chars = sum(len(s) for s in sentences)
        for i, sent in enumerate(sentences):
            sent_chars = len(sent)
            sent_duration = (sent_chars / total_chars) * duration if total_chars > 0 else duration / len(sentences)
            sent_end = current_start + sent_duration
            
            # Последнее предложение должно заканчиваться на end
            if i == len(sentences) - 1:
                sent_end = end
            
            result.append({
                "segment_id": f"{seg.get('segment_id', 'split')}-{i}",
                "start_sec": current_start,
                "end_sec": sent_end,
                "text": sent,
                "words_json": None,  # Word timestamps недоступны
            })
            
            current_start = sent_end
    
    logger.info(f"Разбит сегмент {seg.get('segment_id')} на {len(result)} предложений")
    return result


def semantic_chunk_v2(segments: List[Dict[str, Any]]) -> List[Tuple[str, float, float, str]]:
    """
    Улучшенная семантическая нарезка с исправлением багов.
    
    Ключевые исправления:
    1. Принудительное разбиение сегментов > CHUNK_MAX_CHARS ПЕРЕД обработкой
    2. Правильный порядок проверок: too_long проверяется ПЕРВЫМ
    3. Защита от гигантских финальных чанков
    """
    if not segments:
        return []

    # ШАГ 1: Принудительно разбиваем гигантские RAW сегменты
    processed_segments = []
    for seg in segments:
        seg_text_len = len(seg.get("text", ""))
        seg_duration = seg.get("end_sec", 0) - seg.get("start_sec", 0)
        
        # Если RAW сегмент уже превышает лимиты — разбиваем его
        if seg_text_len > CHUNK_MAX_CHARS or seg_duration > CHUNK_MAX_SECONDS:
            logger.warning(
                f"RAW сегмент {seg.get('segment_id')} превышает лимиты: "
                f"{seg_text_len} символов, {seg_duration:.1f} секунд. Разбиваю..."
            )
            split_segs = _force_split_large_segment(seg)
            processed_segments.extend(split_segs)
        else:
            processed_segments.append(seg)
    
    segs = sorted(processed_segments, key=lambda s: s["start_sec"])

    # ШАГ 2: Извлекаем слова с таймкодами
    all_words = []
    for s in segs:
        wj = s.get("words_json")
        if wj:
            try:
                wlist = json.loads(wj) if isinstance(wj, str) else wj
                for w in wlist:
                    all_words.append({
                        "word": w.get("word", ""),
                        "start": float(w.get("start", 0)),
                        "end": float(w.get("end", 0)),
                    })
            except Exception:
                pass

    if not all_words:
        return _fallback_chunk_v2(segs)

    # ШАГ 3: Полный текст + маппинг символ→время
    full_text = " ".join(w["word"] for w in all_words)
    word_spans = []
    cursor = 0
    for w in all_words:
        wlen = len(w["word"])
        word_spans.append({"sc": cursor, "ec": cursor + wlen, "st": w["start"], "et": w["end"]})
        cursor += wlen + 1

    # ШАГ 4: Предложения
    sentences = _split_sentences(full_text)
    if not sentences:
        return _fallback_chunk_v2(segs)
    
    # Объединяем короткие предложения
    sentences = _merge_short_sentences(sentences, min_len=40)  # Не уничтожаем границы предложений

    # ШАГ 5: Маппинг → таймкоды
    sent_objs = []
    search_cur = 0
    for sent in sentences:
        idx = full_text.find(sent.strip(), search_cur)
        if idx == -1:
            continue
        sc, ec = idx, idx + len(sent.strip())
        search_cur = ec
        st = next((ws["st"] for ws in word_spans if ws["sc"] <= sc < ws["ec"]), 0.0)
        et = next(
            (ws["et"] for ws in word_spans if ws["sc"] <= (ec - 1) < ws["ec"]),
            next((ws["et"] for ws in reversed(word_spans) if ws["ec"] <= ec), st),
        )
        sent_objs.append({"text": sent, "start": st, "end": et})

    if len(sent_objs) <= 2:
        txt = " ".join(s["text"] for s in sent_objs)
        return [("sem-0", sent_objs[0]["start"], sent_objs[-1]["end"], txt)]

    # ШАГ 6: Эмбеддинги + сходство
    import numpy as np
    from .models import get_chunk_model

    model = get_chunk_model()
    embs = model.encode([s["text"] for s in sent_objs], batch_size=32, show_progress_bar=False)
    sims = []
    if len(embs) > 1:
        A, B = embs[:-1], embs[1:]
        dot = (A * B).sum(axis=1)
        sims = (dot / (np.linalg.norm(A, axis=1) * np.linalg.norm(B, axis=1) + 1e-9)).tolist()

    # ШАГ 7: Группировка с ИСПРАВЛЕННЫМ порядком проверок
    chunks: List[Tuple[str, float, float, str]] = []
    group = [sent_objs[0]]
    glen = len(sent_objs[0]["text"])
    gstart = sent_objs[0]["start"]
    gend = sent_objs[0]["end"]

    for i, sim in enumerate(sims):
        ns = sent_objs[i + 1]
        gduration = gend - gstart
        
        # ИСПРАВЛЕНИЕ: Проверяем максимум ПЕРВЫМ
        too_long = glen >= CHUNK_MAX_CHARS or gduration >= CHUNK_MAX_SECONDS
        
        # Затем проверяем минимум
        too_short = glen < CHUNK_MIN_CHARS or gduration < CHUNK_MIN_SECONDS
        
        # ИСПРАВЛЕНИЕ: Приоритет too_long над too_short
        if too_long:
            # Превысили максимум — ОБЯЗАТЕЛЬНО завершаем чанк
            txt = " ".join(g["text"] for g in group)
            if txt and txt[-1] not in '.!?':
                txt += '.'
            chunks.append((f"sem-{len(chunks)}", gstart, gend, txt))
            # Начинаем новый чанк
            group = [ns]
            glen = len(ns["text"])
            gstart = ns["start"]
            gend = ns["end"]
        elif too_short:
            # Ещё слишком короткий — добавляем следующее предложение
            group.append(ns)
            glen += len(ns["text"]) + 1
            gend = ns["end"]
        elif sim < CHUNK_THRESHOLD:
            # Семантически разные — завершаем чанк
            txt = " ".join(g["text"] for g in group)
            if txt and txt[-1] not in '.!?':
                txt += '.'
            chunks.append((f"sem-{len(chunks)}", gstart, gend, txt))
            # Начинаем новый чанк
            group = [ns]
            glen = len(ns["text"])
            gstart = ns["start"]
            gend = ns["end"]
        else:
            # Всё ок — добавляем к текущему чанку
            group.append(ns)
            glen += len(ns["text"]) + 1
            gend = ns["end"]

    # Финальный чанк с проверкой максимума
    if group:
        txt = " ".join(g["text"] for g in group)
        if txt and txt[-1] not in '.!?':
            txt += '.'
        final_duration = gend - gstart
        
        # ИСПРАВЛЕНИЕ: Проверяем максимум для финального чанка
        if glen > CHUNK_MAX_CHARS or final_duration > CHUNK_MAX_SECONDS:
            # Финальный чанк слишком большой — разбиваем его
            logger.warning(f"Финальный чанк превышает лимиты: {glen} символов, {final_duration:.1f} секунд")
            # Разбиваем на предложения и создаём отдельные чанки
            final_sentences = _split_sentences(txt)
            current_start = gstart
            total_chars = sum(len(s) for s in final_sentences)
            
            for sent in final_sentences:
                sent_chars = len(sent)
                sent_duration = (sent_chars / total_chars) * final_duration if total_chars > 0 else final_duration / len(final_sentences)
                sent_end = current_start + sent_duration
                if sent_end > gend:
                    sent_end = gend
                
                chunks.append((f"sem-{len(chunks)}", current_start, sent_end, sent))
                current_start = sent_end
        elif glen >= CHUNK_MIN_CHARS and final_duration >= CHUNK_MIN_SECONDS:
            chunks.append((f"sem-{len(chunks)}", gstart, gend, txt))
        elif chunks:
            # Слишком короткий — добавляем к предыдущему
            prev_id, prev_start, prev_end, prev_txt = chunks[-1]
            merged_txt = prev_txt.rstrip('.!?') + " " + txt
            chunks[-1] = (prev_id, prev_start, gend, merged_txt)
        else:
            # Единственный чанк — сохраняем даже если короткий
            chunks.append((f"sem-{len(chunks)}", gstart, gend, txt))

    # Пост-обработка: объединяем короткие чанки
    chunks = _merge_short_chunks_v2(chunks, min_chars=60)  # Не склеиваем короткие чанки агрессивно
    chunks = [(f"sem-{i}", s, e, t) for i, (_, s, e, t) in enumerate(chunks)]
    
    logger.info("%d чанков из %d сегментов (v2)", len(chunks), len(segs))
    return chunks


def _merge_short_sentences(sentences: List[str], min_len: int = 40) -> List[str]:
    """Объединяет короткие предложения до минимального размера."""
    if not sentences:
        return sentences
    result, cur = [], sentences[0]
    for s in sentences[1:]:
        if len(cur) < min_len:
            cur = cur.rstrip('.!?') + " " + s
        else:
            if not cur[-1] in '.!?':
                cur += '.'
            result.append(cur)
            cur = s
    if cur:
        if not cur[-1] in '.!?':
            cur += '.'
        result.append(cur)
    return result


def _fallback_chunk_v2(segs: List[Dict[str, Any]]) -> List[Tuple[str, float, float, str]]:
    """
    Улучшенный fallback chunking с исправлением багов.
    
    Исправления:
    1. Принудительное разбиение сегментов > CHUNK_MAX_CHARS
    2. Правильный порядок проверок
    """
    if not segs:
        return []
    
    chunks = []
    texts, start, end, clen = [], segs[0]["start_sec"], segs[0]["end_sec"], 0
    
    for s in segs:
        slen = len(s["text"])
        seg_duration = s["end_sec"] - s["start_sec"]
        
        # ИСПРАВЛЕНИЕ: Если текущий сегмент уже превышает максимум — разбиваем его
        if slen > CHUNK_MAX_CHARS or seg_duration > CHUNK_MAX_SECONDS:
            # Сначала завершаем текущий чанк если он есть
            if texts and clen >= CHUNK_MIN_CHARS:
                txt = " ".join(texts)
                if txt and txt[-1] not in '.!?':
                    txt += '.'
                chunks.append((f"seg-{len(chunks)}", start, end, txt))
                texts, start, end, clen = [], s["start_sec"], s["end_sec"], 0
            
            # Разбиваем большой сегмент
            split_segs = _force_split_large_segment(s)
            for split_seg in split_segs:
                split_len = len(split_seg["text"])
                split_dur = split_seg["end_sec"] - split_seg["start_sec"]
                
                # Проверяем нужно ли завершить текущий чанк
                exceeds_max = (clen + split_len > CHUNK_MAX_CHARS) or ((split_seg["end_sec"] - start) >= CHUNK_MAX_SECONDS)
                meets_min = clen >= CHUNK_MIN_CHARS
                
                if exceeds_max and meets_min:
                    # Завершаем текущий чанк
                    txt = " ".join(texts)
                    if txt and txt[-1] not in '.!?':
                        txt += '.'
                    chunks.append((f"seg-{len(chunks)}", start, end, txt))
                    # Начинаем новый
                    texts, start, end, clen = [split_seg["text"]], split_seg["start_sec"], split_seg["end_sec"], split_len
                else:
                    # Добавляем к текущему
                    texts.append(split_seg["text"])
                    end = split_seg["end_sec"]
                    clen += split_len + 1
            continue
        
        # Обычная логика для нормальных сегментов
        exceeds_max = (clen + slen > CHUNK_MAX_CHARS) or ((s["end_sec"] - start) >= CHUNK_MAX_SECONDS)
        meets_min = clen >= CHUNK_MIN_CHARS
        
        if exceeds_max and meets_min:
            # Завершаем текущий чанк
            txt = " ".join(texts)
            if txt and txt[-1] not in '.!?':
                txt += '.'
            chunks.append((f"seg-{len(chunks)}", start, end, txt))
            # Начинаем новый
            texts, start, end, clen = [s["text"]], s["start_sec"], s["end_sec"], slen
        else:
            # Добавляем к текущему
            texts.append(s["text"])
            end = s["end_sec"]
            clen += slen + 1
    
    # Финальный чанк
    if texts:
        txt = " ".join(texts)
        if txt and txt[-1] not in '.!?':
            txt += '.'
        final_duration = end - start
        
        # ИСПРАВЛЕНИЕ: Проверяем максимум для финального чанка
        if clen > CHUNK_MAX_CHARS or final_duration > CHUNK_MAX_SECONDS:
            # Разбиваем финальный чанк
            logger.warning(f"Финальный fallback чанк превышает лимиты: {clen} символов, {final_duration:.1f} секунд")
            final_sentences = _split_sentences(txt)
            current_start = start
            total_chars = sum(len(s) for s in final_sentences)
            
            for sent in final_sentences:
                sent_chars = len(sent)
                sent_duration = (sent_chars / total_chars) * final_duration if total_chars > 0 else final_duration / len(final_sentences)
                sent_end = current_start + sent_duration
                if sent_end > end:
                    sent_end = end
                
                chunks.append((f"seg-{len(chunks)}", current_start, sent_end, sent))
                current_start = sent_end
        elif clen >= CHUNK_MIN_CHARS:
            chunks.append((f"seg-{len(chunks)}", start, end, txt))
        elif chunks:
            # Слишком короткий — объединяем с предыдущим
            prev_id, prev_start, prev_end, prev_txt = chunks[-1]
            merged_txt = prev_txt.rstrip('.!?') + " " + txt
            chunks[-1] = (prev_id, prev_start, end, merged_txt)
        else:
            # Единственный чанк — сохраняем даже если короткий
            chunks.append((f"seg-{len(chunks)}", start, end, txt))
    
    # Пост-обработка
    chunks = _merge_short_chunks_v2(chunks, min_chars=60)  # Не склеиваем короткие чанки агрессивно
    
    logger.info("Fallback v2: %d чанков из %d сегментов", len(chunks), len(segs))
    return chunks


def _merge_short_chunks_v2(
    chunks: List[Tuple[str, float, float, str]],
    min_chars: int = 200,
) -> List[Tuple[str, float, float, str]]:
    """Пост-обработка: объединяет чанки короче min_chars с соседними."""
    if len(chunks) <= 1:
        return chunks
    
    merged = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_id, prev_start, prev_end, prev_txt = merged[-1]
        cur_id, cur_start, cur_end, cur_txt = chunks[i]
        
        # Если предыдущий чанк слишком короткий — объединяем с текущим
        # НО проверяем что объединённый не превысит максимум
        merged_len = len(prev_txt) + len(cur_txt) + 1
        merged_dur = cur_end - prev_start
        
        if len(prev_txt) < min_chars and merged_len <= CHUNK_MAX_CHARS and merged_dur <= CHUNK_MAX_SECONDS:
            merged_txt = prev_txt.rstrip('.!?') + " " + cur_txt
            merged[-1] = (prev_id, prev_start, cur_end, merged_txt)
        else:
            merged.append(chunks[i])
    
    # Проверяем последний чанк
    if len(merged) > 1:
        last_id, last_start, last_end, last_txt = merged[-1]
        if len(last_txt) < min_chars:
            prev_id, prev_start, prev_end, prev_txt = merged[-2]
            merged_len = len(prev_txt) + len(last_txt) + 1
            merged_dur = last_end - prev_start
            
            if merged_len <= CHUNK_MAX_CHARS and merged_dur <= CHUNK_MAX_SECONDS:
                merged_txt = prev_txt.rstrip('.!?') + " " + last_txt
                merged[-2] = (prev_id, prev_start, last_end, merged_txt)
                merged.pop()
    
    return merged
