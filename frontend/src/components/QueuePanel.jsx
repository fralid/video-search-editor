import React, { useState, useEffect, useRef } from 'react';
import { useToast } from '../contexts/UIContext';

const STATUS_CONFIG = {
    downloading: { label: 'Загрузка', icon: '⬇️', color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
    waiting: { label: 'Ожидание', icon: '⏳', color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20' },
    processing: { label: 'Обработка', icon: '⚙️', color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
    done: { label: 'Готово', icon: '✅', color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/20' },
    error: { label: 'Ошибка', icon: '❌', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
};

const POLL_INTERVAL_VISIBLE = 2000;   // 2s когда вкладка активна
const POLL_INTERVAL_HIDDEN = 5000;    // 5s когда вкладка в фоне

export default function QueuePanel() {
    const { addToast } = useToast();
    const [queue, setQueue] = useState([]);
    const [collapsed, setCollapsed] = useState(true);
    const [tabVisible, setTabVisible] = useState(() => typeof document !== 'undefined' ? !document.hidden : true);
    const intervalRef = useRef(null);

    const fetchQueue = async () => {
        try {
            const res = await fetch('/api/queue');
            if (res.ok) {
                const data = await res.json();
                setQueue(data);
            }
        } catch (e) {
            // ignore
        }
    };

    useEffect(() => {
        const onVisibility = () => setTabVisible(!document.hidden);
        document.addEventListener('visibilitychange', onVisibility);
        return () => document.removeEventListener('visibilitychange', onVisibility);
    }, []);

    useEffect(() => {
        fetchQueue();
        const ms = tabVisible ? POLL_INTERVAL_VISIBLE : POLL_INTERVAL_HIDDEN;
        intervalRef.current = setInterval(fetchQueue, ms);
        return () => clearInterval(intervalRef.current);
    }, [tabVisible]);

    const handleRemove = async (videoId) => {
        try {
            const res = await fetch(`/api/queue/${encodeURIComponent(videoId)}`, { method: 'DELETE' });
            if (res.ok) {
                setQueue(prev => prev.filter(item => item.video_id !== videoId));
            } else {
                const data = await res.json().catch(() => ({}));
                addToast(data.error || 'Не удалось удалить', 'error');
            }
        } catch (e) {
            addToast('Ошибка сети', 'error');
        }
    };

    const handleClear = async () => {
        try {
            await fetch('/api/queue/clear', { method: 'POST' });
            fetchQueue();
        } catch (e) { }
    };

    const downloadingCount = queue.filter(q => q.status === 'downloading').length;
    const activeCount = queue.filter(q => q.status === 'processing').length;
    const waitingCount = queue.filter(q => q.status === 'waiting').length;
    const doneCount = queue.filter(q => q.status === 'done' || q.status === 'error').length;

    return (
        <div className={`bg-panel border-l border-border flex flex-col h-full transition-all duration-300 flex-shrink-0 ${collapsed ? 'w-16' : 'w-72'}`}>
            {collapsed ? (
                /* Свёрнутая полоска — как левый сайдбар */
                <div className="flex flex-col items-center py-4">
                    <button
                        onClick={() => setCollapsed(false)}
                        className="p-2 rounded-lg hover:bg-white/5 transition-colors text-muted hover:text-main"
                        title="Развернуть очередь"
                    >
                        <span className="text-lg">▸</span>
                    </button>
                    {queue.length > 0 && (
                        <span className="mt-2 px-1.5 py-0.5 rounded-full bg-electric/20 text-electric text-[9px] font-bold">
                            {queue.length}
                        </span>
                    )}
                </div>
            ) : (
                <>
            {/* Header */}
            <div className="p-3 border-b border-border flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-muted">Очередь</h3>
                    {downloadingCount > 0 && (
                        <span className="px-1.5 py-0.5 rounded-full bg-orange-500/20 text-orange-400 text-[9px] font-bold animate-pulse">
                            {downloadingCount} ⬇️
                        </span>
                    )}
                    {activeCount > 0 && (
                        <span className="px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-400 text-[9px] font-bold animate-pulse">
                            {activeCount} ⚙️
                        </span>
                    )}
                    {waitingCount > 0 && (
                        <span className="px-1.5 py-0.5 rounded-full bg-yellow-500/20 text-yellow-400 text-[9px] font-bold">
                            {waitingCount} ⏳
                        </span>
                    )}
                </div>
                <div className="flex gap-1">
                    {doneCount > 0 && (
                        <button
                            onClick={handleClear}
                            className="text-[9px] text-muted hover:text-main px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/10 transition-colors"
                            title="Очистить завершённые"
                        >
                            🧹
                        </button>
                    )}
                    <button
                        onClick={() => setCollapsed(true)}
                        className="text-[9px] text-muted hover:text-main px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/10 transition-colors"
                        title="Свернуть"
                    >
                        ▾
                    </button>
                </div>
            </div>

            {/* Queue items */}
                <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
                    {queue.length === 0 ? (
                        <p className="text-[10px] text-muted text-center py-8">Очередь пуста</p>
                    ) : (
                        queue.map((item) => {
                            const cfg = STATUS_CONFIG[item.status] || STATUS_CONFIG.waiting;
                            return (
                                <div
                                    key={item.video_id}
                                    className={`${cfg.bg} border ${cfg.border} rounded-lg p-2.5 group transition-all`}
                                >
                                    <div className="flex items-start justify-between gap-1.5">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-1.5 mb-1">
                                                <span className="text-xs">{cfg.icon}</span>
                                                <span className={`text-[9px] font-semibold uppercase ${cfg.color}`}>
                                                    {cfg.label}
                                                </span>
                                            </div>
                                            <p className="text-[11px] text-main truncate font-medium" title={item.title || item.video_id}>
                                                {item.title || item.video_id}
                                            </p>
                                            {item.error && (
                                                <p className="text-[9px] text-red-400 mt-1 truncate" title={item.error}>
                                                    {item.error}
                                                </p>
                                            )}
                                        </div>

                                        {/* Delete button — only for waiting/done/error */}
                                        {item.status !== 'processing' && (
                                            <button
                                                onClick={() => handleRemove(item.video_id)}
                                                className="opacity-0 group-hover:opacity-100 text-muted hover:text-red-400 transition-all p-0.5 rounded hover:bg-red-500/10 flex-shrink-0"
                                                title="Удалить из очереди"
                                            >
                                                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                    <path d="M18 6L6 18M6 6l12 12" />
                                                </svg>
                                            </button>
                                        )}

                                        {/* Spinner for processing/downloading */}
                                        {(item.status === 'processing' || item.status === 'downloading') && (
                                            <div className={`w-3.5 h-3.5 border-2 rounded-full animate-spin flex-shrink-0 mt-0.5 ${item.status === 'downloading'
                                                    ? 'border-orange-400/30 border-t-orange-400'
                                                    : 'border-blue-400/30 border-t-blue-400'
                                                }`} />
                                        )}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
                </>
            )}
        </div>
    );
}
