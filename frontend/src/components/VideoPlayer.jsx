import React, { useRef, useEffect, useState } from 'react';
import ClipEditor from './ClipEditor';

export default function VideoPlayer({ segment, onClose }) {
    const videoRef = useRef(null);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [clipStart, setClipStart] = useState(null);
    const [clipEnd, setClipEnd] = useState(null);
    const [creating, setCreating] = useState(false);
    const [clipUrl, setClipUrl] = useState(null);
    const [showClipPanel, setShowClipPanel] = useState(false);
    const [showWordEditor, setShowWordEditor] = useState(false);

    useEffect(() => {
        if (videoRef.current && segment) {
            videoRef.current.currentTime = segment.start;
            videoRef.current.play().catch(e => console.log("Auto-play prevented", e));
            setClipStart(segment.start);
            setClipEnd(segment.end);
        }
    }, [segment]);

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

    const setMarkIn = () => {
        setClipStart(currentTime);
        if (clipEnd !== null && currentTime > clipEnd) {
            setClipEnd(null);
        }
    };

    const setMarkOut = () => {
        setClipEnd(currentTime);
        if (clipStart !== null && currentTime < clipStart) {
            setClipStart(currentTime);
        }
    };

    const seekTo = (time) => {
        if (videoRef.current) {
            videoRef.current.currentTime = time;
        }
    };

    const createClip = async () => {
        if (clipStart === null || clipEnd === null || clipStart >= clipEnd) {
            alert('Please set valid start and end marks');
            return;
        }

        setCreating(true);
        setClipUrl(null);

        try {
            const res = await fetch('/api/clips/manual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    video_id: segment.video_id,
                    start: clipStart,
                    end: clipEnd
                })
            });
            const data = await res.json();

            if (res.ok) {
                setClipUrl(data.download_url);
            } else {
                alert(data.detail || 'Failed to create clip');
            }
        } catch (err) {
            console.error("Clip creation failed", err);
            alert('Failed to create clip');
        } finally {
            setCreating(false);
        }
    };

    if (!segment) return null;

    if (showWordEditor) {
        return (
            <ClipEditor
                videoId={segment.video_id}
                initialTime={segment.start}
                initialEndTime={segment.end}
                initialSegmentId={segment.segment_id}
                onClose={() => setShowWordEditor(false)}
            />
        );
    }

    const srcUrl = `/files/videos/${segment.video_id}.mp4`;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <div className="bg-slate-900 rounded-xl shadow-2xl w-full max-w-5xl overflow-hidden flex flex-col">
                {/* Header */}
                <div className="flex justify-between items-center p-4 border-b border-slate-700 bg-slate-800">
                    <div>
                        <h3 className="text-white font-bold">{segment.video_id}</h3>
                        <p className="text-slate-400 text-sm">
                            Segment: {formatTime(segment.start)} - {formatTime(segment.end)}
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => setShowWordEditor(true)}
                            className="px-3 py-1 rounded text-sm bg-blue-600 hover:bg-blue-500 text-white"
                        >
                            📝 Word Editor
                        </button>
                        <button
                            onClick={() => setShowClipPanel(!showClipPanel)}
                            className={`px-3 py-1 rounded text-sm ${showClipPanel ? 'bg-purple-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}`}
                        >
                            ✂️ Clip
                        </button>
                        <button
                            onClick={onClose}
                            className="text-slate-400 hover:text-white text-2xl"
                        >
                            &times;
                        </button>
                    </div>
                </div>

                {/* Video */}
                <div className="relative bg-black aspect-video">
                    <video
                        ref={videoRef}
                        src={srcUrl}
                        controls
                        className="w-full h-full"
                        onTimeUpdate={handleTimeUpdate}
                        onLoadedMetadata={handleLoadedMetadata}
                    />
                </div>

                {/* Transcript — компактный фрагмент, не стена текста */}
                <div className="p-4 bg-slate-800 border-t border-slate-700">
                    <p className="text-gray-200 italic text-sm line-clamp-3">
                        "{segment.text}"
                    </p>
                    {segment.text && segment.text.length > 200 && (
                        <span className="text-slate-500 text-xs mt-1 block">
                            ...ещё {segment.text.length - 200} символов
                        </span>
                    )}
                </div>

                {/* Clip Panel */}
                {showClipPanel && (
                    <div className="p-4 bg-slate-800/50 border-t border-slate-700 space-y-4">
                        <div className="flex items-center justify-between">
                            <h4 className="text-white font-medium">✂️ Create Clip</h4>
                            <span className="text-slate-400 text-sm">
                                Current: {formatTime(currentTime)}
                            </span>
                        </div>

                        {/* Timeline with marks */}
                        <div className="relative h-8 bg-slate-700 rounded overflow-hidden">
                            {/* Progress */}
                            <div
                                className="absolute h-full bg-slate-600"
                                style={{ width: `${(currentTime / duration) * 100}%` }}
                            />

                            {/* Selection range */}
                            {clipStart !== null && clipEnd !== null && (
                                <div
                                    className="absolute h-full bg-purple-500/30"
                                    style={{
                                        left: `${(clipStart / duration) * 100}%`,
                                        width: `${((clipEnd - clipStart) / duration) * 100}%`
                                    }}
                                />
                            )}

                            {/* Start mark */}
                            {clipStart !== null && (
                                <div
                                    className="absolute h-full w-1 bg-green-500 cursor-pointer"
                                    style={{ left: `${(clipStart / duration) * 100}%` }}
                                    onClick={() => seekTo(clipStart)}
                                    title={`Start: ${formatTime(clipStart)}`}
                                />
                            )}

                            {/* End mark */}
                            {clipEnd !== null && (
                                <div
                                    className="absolute h-full w-1 bg-red-500 cursor-pointer"
                                    style={{ left: `${(clipEnd / duration) * 100}%` }}
                                    onClick={() => seekTo(clipEnd)}
                                    title={`End: ${formatTime(clipEnd)}`}
                                />
                            )}
                        </div>

                        {/* Controls */}
                        <div className="flex flex-wrap items-center gap-3">
                            <button
                                onClick={setMarkIn}
                                className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded text-sm"
                            >
                                [ Mark In
                            </button>
                            <span className="text-slate-400 text-sm">
                                {clipStart !== null ? formatTime(clipStart) : '--:--'}
                            </span>

                            <span className="text-slate-500">→</span>

                            <span className="text-slate-400 text-sm">
                                {clipEnd !== null ? formatTime(clipEnd) : '--:--'}
                            </span>
                            <button
                                onClick={setMarkOut}
                                className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded text-sm"
                            >
                                Mark Out ]
                            </button>

                            {clipStart !== null && clipEnd !== null && (
                                <span className="text-slate-400 text-sm ml-4">
                                    Duration: {formatTime(clipEnd - clipStart)}
                                </span>
                            )}
                        </div>

                        {/* Create/Download */}
                        <div className="flex items-center gap-3">
                            <button
                                onClick={createClip}
                                disabled={creating || clipStart === null || clipEnd === null || clipStart >= clipEnd}
                                className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-2 rounded font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {creating ? '⏳ Creating...' : '✂️ Create Clip'}
                            </button>

                            {clipUrl && (
                                <a
                                    href={clipUrl}
                                    download
                                    className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded font-medium inline-flex items-center gap-2"
                                >
                                    ⬇️ Download Clip
                                </a>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
