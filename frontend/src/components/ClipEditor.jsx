import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { useToast } from '../contexts/UIContext';

/**
 * ClipEditor — интерактивный транскрипт + видеоплеер.
 * 
 * Вдохновлён Mux CuePoints, Reduct.video, YouTube transcripts:
 * - Текст разбит на строки с таймкодами (как субтитры)
 * - Текущая строка подсвечивается при воспроизведении
 * - Клик по строке = перемотка видео
 * - Автопрокрутка к текущей позиции
 * - Выделение диапазона для вырезки клипа
 */
export default function ClipEditor({ videoId, initialTime, initialEndTime, initialSegmentId, onClose }) {
    const { addToast } = useToast();
    const videoRef = useRef(null);
    const transcriptRef = useRef(null);
    const activeLineRef = useRef(null);

    const [transcript, setTranscript] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Video state
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);

    // Selection for clip
    const [clipStart, setClipStart] = useState(null);
    const [clipEnd, setClipEnd] = useState(null);
    const [selectionMode, setSelectionMode] = useState('start'); // 'start' | 'end'

    // Clip creation
    const [creating, setCreating] = useState(false);
    const [clipUrl, setClipUrl] = useState(null);

    // Auto-scroll toggle
    const [autoScroll, setAutoScroll] = useState(true);

    // Load transcript
    useEffect(() => {
        async function loadTranscript() {
            try {
                const res = await fetch(`/api/videos/${videoId}/transcript`);
                if (!res.ok) throw new Error('Failed to load transcript');
                const data = await res.json();
                setTranscript(data);
            } catch (e) {
                setError(e.message);
            } finally {
                setLoading(false);
            }
        }
        loadTranscript();
    }, [videoId]);

    // Build lines from segments — каждый сегмент = одна строка с таймкодом
    const lines = useMemo(() => {
        if (!transcript?.segments) return [];
        return transcript.segments.map((seg, idx) => ({
            id: seg.segment_id,
            idx,
            start: seg.start,
            end: seg.end,
            text: seg.text,
            hasWords: seg.words?.length > 0,
            words: seg.words || [],
        }));
    }, [transcript]);

    // Find active line based on current playback time
    const activeLineIdx = useMemo(() => {
        for (let i = lines.length - 1; i >= 0; i--) {
            if (currentTime >= lines[i].start - 0.3) return i;
        }
        return 0;
    }, [lines, currentTime]);

    // Initial seek
    useEffect(() => {
        if (videoRef.current && initialTime !== undefined) {
            videoRef.current.currentTime = initialTime;
            setClipStart(initialTime);
            if (initialEndTime) setClipEnd(initialEndTime);
        }
    }, [initialTime, initialEndTime, loading]);

    // Auto-scroll to active line
    useEffect(() => {
        if (autoScroll && activeLineRef.current && transcriptRef.current) {
            activeLineRef.current.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
            });
        }
    }, [activeLineIdx, autoScroll]);

    const handleTimeUpdate = () => {
        if (videoRef.current) {
            setCurrentTime(videoRef.current.currentTime);
        }
    };

    const handleLoadedMetadata = () => {
        if (videoRef.current) {
            setDuration(videoRef.current.duration);
        }
    };

    const formatTime = (seconds) => {
        if (!seconds || isNaN(seconds)) return '00:00';
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    };

    // Click on a line — seek video + set clip boundary
    const handleLineClick = useCallback((line) => {
        // Seek video
        if (videoRef.current) {
            videoRef.current.currentTime = line.start;
        }

        // Set clip boundaries
        if (selectionMode === 'start') {
            setClipStart(line.start);
            setClipEnd(null);
            setClipUrl(null);
            setSelectionMode('end');
        } else {
            if (line.end >= (clipStart || 0)) {
                setClipEnd(line.end);
            } else {
                // Clicked before start — swap
                setClipEnd(clipStart);
                setClipStart(line.start);
            }
            setSelectionMode('start');
        }
    }, [selectionMode, clipStart]);

    // Check if a line is in the selected clip range
    const isLineInSelection = useCallback((line) => {
        if (clipStart === null) return false;
        if (clipEnd === null) return line.start >= clipStart && line.start <= clipStart + 0.5;
        return line.start >= clipStart - 0.1 && line.end <= clipEnd + 0.1;
    }, [clipStart, clipEnd]);

    const resetSelection = () => {
        setClipStart(null);
        setClipEnd(null);
        setSelectionMode('start');
        setClipUrl(null);
    };

    const previewSelection = () => {
        if (clipStart !== null && videoRef.current) {
            videoRef.current.currentTime = clipStart;
            videoRef.current.play();
        }
    };

    const createClip = async () => {
        if (clipStart === null || clipEnd === null || clipStart >= clipEnd) {
            addToast('Выберите начало и конец клипа', 'error');
            return;
        }

        setCreating(true);
        setClipUrl(null);

        try {
            const res = await fetch('/api/clips/manual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ video_id: videoId, start: clipStart, end: clipEnd }),
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok) {
                setClipUrl(data.download_url);
                addToast('Клип создан', 'success');
            } else {
                addToast(data.detail || data.error || 'Ошибка создания клипа', 'error');
            }
        } catch (err) {
            console.error("Clip creation failed", err);
            addToast('Ошибка создания клипа', 'error');
        } finally {
            setCreating(false);
        }
    };

    if (loading) {
        return (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
                <div className="text-white text-xl animate-pulse">Загрузка транскрипта...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
                <div className="bg-slate-900 p-6 rounded-lg">
                    <p className="text-red-400 mb-4">{error}</p>
                    <button onClick={onClose} className="bg-slate-700 text-white px-4 py-2 rounded">
                        Закрыть
                    </button>
                </div>
            </div>
        );
    }

    const srcUrl = `/files/videos/${videoId}.mp4`;

    return (
        <div className="fixed inset-0 z-50 flex bg-black/95 backdrop-blur-sm">
            {/* LEFT: Interactive Transcript */}
            <div className="w-1/2 flex flex-col border-r border-slate-700/50">
                {/* Header */}
                <div className="px-4 py-3 border-b border-slate-700/50 bg-slate-900/80 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <button onClick={onClose} className="text-slate-400 hover:text-white text-lg px-2">
                            &larr;
                        </button>
                        <div>
                            <h3 className="text-white font-semibold text-sm truncate max-w-[300px]">
                                {transcript?.title || videoId}
                            </h3>
                            <p className="text-slate-500 text-xs">{lines.length} строк</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setAutoScroll(!autoScroll)}
                            className={`text-xs px-2 py-1 rounded ${autoScroll ? 'bg-electric/20 text-electric' : 'bg-slate-800 text-slate-500'}`}
                            title="Автопрокрутка к текущей позиции"
                        >
                            {autoScroll ? 'Авто' : 'Ручн.'}
                        </button>
                    </div>
                </div>

                {/* Instructions */}
                <div className="px-4 py-2 bg-slate-800/50 border-b border-slate-700/30 text-xs text-slate-400">
                    <span className="text-green-400">1. Клик = начало</span>
                    {' → '}
                    <span className="text-red-400">2. Клик = конец</span>
                    {' → '}
                    <span className="text-purple-400">3. Вырезать!</span>
                </div>

                {/* Transcript Lines — YouTube-style */}
                <div
                    ref={transcriptRef}
                    className="flex-1 overflow-y-auto custom-scrollbar"
                    onMouseDown={() => setAutoScroll(false)}
                >
                    {lines.map((line, idx) => {
                        const isActive = idx === activeLineIdx;
                        const inSelection = isLineInSelection(line);
                        const isClipStart = clipStart !== null && Math.abs(line.start - clipStart) < 0.5;
                        const isClipEnd = clipEnd !== null && Math.abs(line.end - clipEnd) < 0.5;

                        return (
                            <div
                                key={line.id}
                                ref={isActive ? activeLineRef : null}
                                onClick={() => handleLineClick(line)}
                                className={`
                                    flex gap-3 px-4 py-2 cursor-pointer transition-all border-l-2
                                    ${isActive
                                        ? 'bg-electric/10 border-l-electric text-white'
                                        : inSelection
                                            ? 'bg-purple-500/10 border-l-purple-500 text-slate-200'
                                            : isClipStart
                                                ? 'bg-green-500/10 border-l-green-500 text-white'
                                                : isClipEnd
                                                    ? 'bg-red-500/10 border-l-red-500 text-white'
                                                    : 'border-l-transparent text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                                    }
                                `}
                            >
                                {/* Timestamp */}
                                <span className={`
                                    text-xs font-mono flex-shrink-0 w-12 pt-0.5
                                    ${isActive ? 'text-electric' : 'text-slate-600'}
                                `}>
                                    {formatTime(line.start)}
                                </span>

                                {/* Text */}
                                <span className="text-sm leading-relaxed flex-1">
                                    {line.text}
                                </span>
                            </div>
                        );
                    })}
                </div>

                {/* Selection Info */}
                <div className="px-4 py-3 bg-slate-900/80 border-t border-slate-700/50">
                    <div className="flex items-center gap-3 text-xs">
                        <span className="text-slate-500">Клип:</span>
                        <span className="text-green-400 font-mono">
                            {clipStart !== null ? formatTime(clipStart) : '--:--'}
                        </span>
                        <span className="text-slate-600">&rarr;</span>
                        <span className="text-red-400 font-mono">
                            {clipEnd !== null ? formatTime(clipEnd) : '--:--'}
                        </span>
                        {clipStart !== null && clipEnd !== null && (
                            <span className="text-purple-400 ml-auto">
                                {formatTime(clipEnd - clipStart)}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* RIGHT: Video + Controls */}
            <div className="w-1/2 flex flex-col">
                {/* Video */}
                <div className="flex-1 bg-black flex items-center justify-center">
                    <video
                        ref={videoRef}
                        src={srcUrl}
                        controls
                        className="max-w-full max-h-full"
                        onTimeUpdate={handleTimeUpdate}
                        onLoadedMetadata={handleLoadedMetadata}
                        onPlay={() => setIsPlaying(true)}
                        onPause={() => setIsPlaying(false)}
                    />
                </div>

                {/* Controls */}
                <div className="p-4 bg-slate-900/80 border-t border-slate-700/50 space-y-3">
                    {/* Timeline with selection */}
                    <div className="relative h-6 bg-slate-800 rounded overflow-hidden cursor-pointer"
                        onClick={(e) => {
                            const rect = e.currentTarget.getBoundingClientRect();
                            const pct = (e.clientX - rect.left) / rect.width;
                            if (videoRef.current) videoRef.current.currentTime = pct * duration;
                        }}
                    >
                        {/* Playback progress */}
                        <div
                            className="absolute h-full bg-slate-600/50"
                            style={{ width: `${(currentTime / duration) * 100}%` }}
                        />
                        {/* Selection range */}
                        {clipStart !== null && clipEnd !== null && (
                            <div
                                className="absolute h-full bg-purple-500/30"
                                style={{
                                    left: `${(clipStart / duration) * 100}%`,
                                    width: `${((clipEnd - clipStart) / duration) * 100}%`,
                                }}
                            />
                        )}
                        {/* Start marker */}
                        {clipStart !== null && (
                            <div
                                className="absolute h-full w-0.5 bg-green-500"
                                style={{ left: `${(clipStart / duration) * 100}%` }}
                            />
                        )}
                        {/* End marker */}
                        {clipEnd !== null && (
                            <div
                                className="absolute h-full w-0.5 bg-red-500"
                                style={{ left: `${(clipEnd / duration) * 100}%` }}
                            />
                        )}
                        {/* Playhead */}
                        <div
                            className="absolute h-full w-0.5 bg-white"
                            style={{ left: `${(currentTime / duration) * 100}%` }}
                        />
                    </div>

                    {/* Buttons */}
                    <div className="flex items-center gap-2">
                        <button
                            onClick={previewSelection}
                            disabled={clipStart === null}
                            className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded text-sm disabled:opacity-30"
                        >
                            ▶ Превью
                        </button>
                        <button
                            onClick={resetSelection}
                            className="bg-slate-700 hover:bg-slate-600 text-white px-3 py-1.5 rounded text-sm"
                        >
                            Сброс
                        </button>
                        <button
                            onClick={createClip}
                            disabled={creating || clipStart === null || clipEnd === null}
                            className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-1.5 rounded text-sm font-medium disabled:opacity-30 ml-auto"
                        >
                            {creating ? 'Создание...' : 'Вырезать клип'}
                        </button>
                    </div>

                    {/* Download */}
                    {clipUrl && (
                        <a
                            href={clipUrl}
                            download
                            className="block text-center bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded text-sm font-medium"
                        >
                            Скачать клип
                        </a>
                    )}
                </div>
            </div>
        </div>
    );
}
