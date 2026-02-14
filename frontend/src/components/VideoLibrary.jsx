import React, { useEffect, useState } from 'react';
import ClipEditor from './ClipEditor';
import { IconLogs, IconClose } from './Icons';
import { useToast, useConfirm } from '../contexts/UIContext';

export default function VideoLibrary({ refreshTrigger }) {
    const { addToast } = useToast();
    const { confirm } = useConfirm();
    const [videos, setVideos] = useState([]);
    const [channels, setChannels] = useState([]);
    const [selectedChannel, setSelectedChannel] = useState('');
    const [processing, setProcessing] = useState({});
    const [clipEditorVideoId, setClipEditorVideoId] = useState(null);
    const [logsData, setLogsData] = useState({ videoId: null, logs: [] });
    const [orphanedEmbeddings, setOrphanedEmbeddings] = useState(null);
    const [tabVisible, setTabVisible] = useState(() => typeof document !== 'undefined' ? !document.hidden : true);
    const [expandedIds, setExpandedIds] = useState(() => new Set());
    const [channelEdit, setChannelEdit] = useState({ videoId: null, channel_name: '', source_url: '' });

    const toggleExpanded = (videoId) => {
        setExpandedIds((prev) => {
            const next = new Set(prev);
            if (next.has(videoId)) next.delete(videoId);
            else next.add(videoId);
            return next;
        });
    };

    const fetchChannels = async () => {
        try {
            const res = await fetch('/api/channels');
            if (res.ok) {
                const data = await res.json();
                setChannels(data);
            }
        } catch (err) {
            console.error("Failed to load channels", err);
        }
    };

    const fetchVideos = async () => {
        try {
            const url = selectedChannel
                ? `/api/videos?channel=${encodeURIComponent(selectedChannel)}`
                : '/api/videos';
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                setVideos(data);
            }
        } catch (err) {
            console.error("Failed to load library", err);
        }
    };

    useEffect(() => {
        fetchChannels();
    }, []);

    useEffect(() => {
        const onVisibility = () => setTabVisible(!document.hidden);
        document.addEventListener('visibilitychange', onVisibility);
        return () => document.removeEventListener('visibilitychange', onVisibility);
    }, []);

    useEffect(() => {
        fetchVideos();
        const ms = tabVisible ? 15000 : 30000; // 15s в фокусе, 30s в фоне
        const interval = setInterval(fetchVideos, ms);
        return () => clearInterval(interval);
    }, [refreshTrigger, selectedChannel, tabVisible]);

    const handleTranscribe = async (videoId) => {
        if (processing[videoId]) return;
        setProcessing(p => ({ ...p, [videoId]: 'transcribe' }));
        try {
            await fetch(`/api/videos/${videoId}/transcribe`, { method: 'POST' });
            setTimeout(fetchVideos, 2000);
        } catch (err) {
            console.error("Transcribe failed", err);
            setProcessing(p => ({ ...p, [videoId]: null }));
        }
    };

    const handleIndex = async (videoId) => {
        if (processing[videoId]) return;
        setProcessing(p => ({ ...p, [videoId]: 'index' }));
        try {
            await fetch(`/api/videos/${videoId}/index`, { method: 'POST' });
            setTimeout(fetchVideos, 2000);
        } catch (err) {
            console.error("Index failed", err);
            setProcessing(p => ({ ...p, [videoId]: null }));
        }
    };

    const handleDelete = async (videoId) => {
        const ok = await confirm({ title: 'Удалить видео', message: 'Удалить это видео и все связанные данные?', danger: true, confirmLabel: 'Удалить' });
        if (!ok) return;
        try {
            const res = await fetch(`/api/videos/${videoId}`, { method: 'DELETE' });
            if (res.ok) {
                addToast('Видео удалено', 'success');
                fetchVideos();
                fetchChannels();
            } else {
                const data = await res.json().catch(() => ({}));
                addToast(data.error || 'Ошибка удаления', 'error');
            }
        } catch (err) {
            console.error("Delete failed", err);
            addToast('Ошибка сети', 'error');
        }
    };

    const handleReprocess = async (videoId) => {
        const ok = await confirm({ title: 'Перезапустить обработку', message: 'Запустить обработку видео заново? Это удалит старую транскрипцию и индекс.', danger: true, confirmLabel: 'Запустить' });
        if (!ok) return;
        setProcessing(p => ({ ...p, [videoId]: 'reprocess' }));
        try {
            const res = await fetch(`/api/videos/${videoId}/reprocess`, { method: 'POST' });
            if (res.ok) {
                addToast('Видео поставлено в очередь', 'success');
                setTimeout(fetchVideos, 2000);
            } else {
                setProcessing(p => ({ ...p, [videoId]: null }));
                addToast('Ошибка запроса', 'error');
            }
        } catch (err) {
            console.error("Reprocess failed", err);
            setProcessing(p => ({ ...p, [videoId]: null }));
            addToast('Ошибка сети', 'error');
        }
    };

    const fetchLogs = async (videoId) => {
        try {
            const res = await fetch(`/api/videos/${videoId}/logs`);
            if (res.ok) {
                const data = await res.json();
                setLogsData({ videoId, logs: data });
            }
        } catch (err) {
            console.error("Failed to fetch logs", err);
        }
    };

    const fetchOrphanedEmbeddings = async () => {
        try {
            const res = await fetch('/api/embeddings/orphaned');
            if (res.ok) {
                const data = await res.json();
                setOrphanedEmbeddings(data);
            }
        } catch (err) {
            console.error("Failed to fetch orphaned embeddings", err);
            addToast("Ошибка загрузки списка осиротевших эмбеддингов", 'error');
        }
    };

    const deleteEmbeddings = async (videoId) => {
        const ok = await confirm({ title: 'Удалить эмбеддинги', message: `Удалить эмбеддинги для видео "${videoId}"?`, danger: true, confirmLabel: 'Удалить' });
        if (!ok) return;
        try {
            const res = await fetch(`/api/embeddings/${encodeURIComponent(videoId)}`, { method: 'DELETE' });
            if (res.ok) {
                const data = await res.json();
                addToast(`Удалено ${data.deleted_count} эмбеддингов для видео "${videoId}"`, 'success');
                fetchOrphanedEmbeddings();
            } else {
                const error = await res.json().catch(() => ({}));
                addToast(error.message || 'Не удалось удалить эмбеддинги', 'error');
            }
        } catch (err) {
            console.error("Failed to delete embeddings", err);
            addToast("Ошибка удаления эмбеддингов", 'error');
        }
    };

    useEffect(() => {
        videos.forEach(vid => {
            if (processing[vid.video_id] === 'transcribe' &&
                (vid.status_transcribe === 'done' || vid.status_transcribe === 'failed')) {
                setProcessing(p => ({ ...p, [vid.video_id]: null }));
            }
            if (processing[vid.video_id] === 'index' &&
                (vid.status_index === 'done' || vid.status_index === 'failed')) {
                setProcessing(p => ({ ...p, [vid.video_id]: null }));
            }
        });
    }, [videos]);

    const formatDuration = (seconds) => {
        if (!seconds) return '';
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        return `${m}:${s.toString().padStart(2, '0')}`;
    };

    const saveVideoChannel = async (videoId, channel_name, source_url) => {
        try {
            const body = {};
            if (channel_name !== undefined && channel_name !== '') body.channel_name = channel_name;
            if (source_url !== undefined && source_url !== '') body.source_url = source_url;
            if (Object.keys(body).length === 0) return;
            const res = await fetch(`/api/videos/${videoId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (res.ok) {
                addToast('Канал сохранён', 'success');
                setChannelEdit({ videoId: null, channel_name: '', source_url: '' });
                fetchVideos();
            } else {
                const data = await res.json().catch(() => ({}));
                addToast(data.error || 'Ошибка сохранения', 'error');
            }
        } catch (err) {
            addToast('Ошибка сети', 'error');
        }
    };

    /** Из строки (URL или название) получаем подпись для показа: только @handle или как есть. */
    const channelNameToDisplay = (name) => {
        if (!name || typeof name !== 'string') return '—';
        const atMatch = name.match(/youtube\.com\/@([^/?]+)/i) || name.match(/youtu\.be\/@([^/?]+)/i) || name.match(/@([^/?\s]+)/);
        if (atMatch) return atMatch[1].startsWith('@') ? atMatch[1] : `@${atMatch[1]}`;
        return name;
    };
    /** Для карточки: приоритет source_url, иначе channel_name; всегда показываем только @handle или название. */
    const channelDisplayLabel = (vid) => {
        const fromUrl = vid.source_url || '';
        const atMatch = fromUrl.match(/youtube\.com\/@([^/?]+)/i) || fromUrl.match(/youtu\.be\/@([^/?]+)/i);
        if (atMatch) return `@${atMatch[1]}`;
        return channelNameToDisplay(vid.channel_name);
    };

    const getStatusBadge = (status) => {
        const normalizedStatus = status === 'downloaded' ? 'done' : status;
        const styles = {
            done: 'text-electric', // Blue for done
            processing: 'text-electric animate-spin',
            pending: 'text-muted/30',
            failed: 'text-red-500',
        };
        // Using much larger indicators
        const icons = {
            done: <div className="w-3 h-3 rounded-full bg-electric shadow-[0_0_10px_rgba(126,206,242,0.6)]"></div>,
            processing: <div className="w-3 h-3 border-2 border-electric border-t-transparent rounded-full animate-spin"></div>,
            pending: <div className="w-3 h-3 rounded-full bg-gray-300 dark:bg-gray-700"></div>,
            failed: <div className="w-3 h-3 rounded-full bg-red-500"></div>
        };

        return icons[normalizedStatus] || icons.pending;
    };

    return (
        <div className="h-full flex flex-col">
            <div className="flex justify-between items-center mb-4 px-1">
                <div className="flex items-center gap-3">
                    {/* Channel filter */}
                    {channels.length > 0 && (
                        <select
                            value={selectedChannel}
                            onChange={(e) => setSelectedChannel(e.target.value)}
                            className="bg-element text-main text-xs rounded-lg px-3 py-1.5 border border-border focus:border-plasma outline-none"
                        >
                            <option value="">All channels ({videos.length})</option>
                            {channels.map(ch => (
                                <option key={ch.name} value={ch.name}>
                                    {channelNameToDisplay(ch.name)} ({ch.count})
                                </option>
                            ))}
                        </select>
                    )}
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={fetchOrphanedEmbeddings}
                        className="text-muted hover:text-main text-xs transition-colors"
                        title="Показать осиротевшие эмбеддинги (видео удалены, но эмбеддинги остались)"
                    >
                        🧹 Очистить эмбеддинги
                    </button>
                    <button
                        onClick={async () => {
                            const res = await fetch('/api/videos/scan', { method: 'POST' });
                            const data = await res.json();
                            if (data.added > 0) {
                                addToast(`Найдено ${data.added} новых видео из ${data.total_files} файлов`, 'success');
                                fetchVideos();
                            } else {
                                addToast(`Все ${data.total_files} файлов уже в базе`, 'info');
                            }
                        }}
                        className="text-muted hover:text-emerald-400 text-xs transition-colors font-medium"
                        title="Сканировать папку videos/ и зарегистрировать новые файлы"
                    >
                        📂 Сканировать
                    </button>
                    <button
                        onClick={async () => {
                            const ok = await confirm({ title: 'Сканировать и обработать', message: 'Сканировать папку и поставить ВСЕ новые видео в очередь транскрипции?', danger: false, confirmLabel: 'Да' });
                            if (!ok) return;
                            const res = await fetch('/api/videos/scan?process=true', { method: 'POST' });
                            const data = await res.json();
                            if (data.added > 0) {
                                addToast(`Добавлено ${data.added} видео в очередь обработки`, 'success');
                                fetchVideos();
                            } else {
                                addToast(`Новых видео не найдено (${data.total_files} уже в базе)`, 'info');
                            }
                        }}
                        className="text-muted hover:text-emerald-400 text-xs transition-colors font-medium"
                        title="Сканировать + поставить в очередь транскрипции"
                    >
                        📂+▶
                    </button>
                    <button
                        onClick={async () => {
                            const res = await fetch('/api/videos/process-pending', { method: 'POST' });
                            const data = await res.json();
                            if (data.enqueued > 0) {
                                addToast(`${data.enqueued} видео поставлено в очередь (${data.skipped} пропущено)`, 'success');
                            } else {
                                addToast(`Все ${data.total} видео уже обработаны`, 'success');
                            }
                        }}
                        className="text-muted hover:text-amber-400 text-xs transition-colors font-medium"
                        title="Обработать все необработанные видео (транскрипция + индексация)"
                    >
                        ⚡ Обработать
                    </button>
                    <button
                        onClick={async () => {
                            const res = await fetch('/api/videos/refresh-all-metadata', { method: 'POST' });
                            const data = await res.json();
                            addToast(`Обновление метаданных: ${data.videos_to_update} видео`, 'info');
                            setTimeout(() => { fetchVideos(); fetchChannels(); }, 5000);
                        }}
                        className="text-muted hover:text-main text-xs transition-colors"
                        title="Fetch missing metadata from YouTube"
                    >
                        📡 Update
                    </button>
                    <button onClick={fetchVideos} className="text-muted hover:text-main text-xs transition-colors">
                        ↻ Refresh
                    </button>
                </div>
            </div>

            <div className="space-y-1 overflow-y-auto pr-2 custom-scrollbar flex-1 pb-6">
                {videos.map((vid) => {
                    const isExpanded = expandedIds.has(vid.video_id);
                    return (
                        <div key={vid.video_id} className="bg-element rounded-xl border border-border/50 hover:bg-white/5 transition-all group overflow-hidden">
                            {/* Полоска: название + стрелка */}
                            <button
                                type="button"
                                onClick={() => toggleExpanded(vid.video_id)}
                                className="w-full flex items-center gap-3 px-4 py-3 text-left"
                            >
                                <span
                                    className={`flex-shrink-0 w-6 h-6 flex items-center justify-center rounded transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                                    aria-hidden
                                >
                                    <svg className="w-4 h-4 text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M9 18l6-6-6-6" />
                                    </svg>
                                </span>
                                <span className="flex-1 min-w-0 font-medium text-main truncate" title={vid.title || vid.video_id}>
                                    {vid.title || vid.video_id}
                                </span>
                            </button>

                            {/* Развёрнутый блок */}
                            {isExpanded && (
                                <div className="px-4 pb-4 pt-0 border-t border-border/50">
                                    <div className="flex items-start gap-6 pt-4">
                                        <div className="w-56 h-32 bg-black rounded-xl overflow-hidden relative border border-white/5 flex-shrink-0 shadow-lg">
                                            {vid.thumbnail_url ? (
                                                <img src={vid.thumbnail_url} alt="" className="w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity" />
                                            ) : (
                                                <div className="w-full h-full flex items-center justify-center text-4xl opacity-30">📺</div>
                                            )}
                                            {vid.duration && (
                                                <span className="absolute bottom-2 right-2 bg-black/80 text-white text-xs px-2 py-0.5 rounded font-mono font-bold">
                                                    {formatDuration(vid.duration)}
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex-1 min-w-0 py-1">
                                            <div className="flex gap-3 items-center text-sm text-muted flex-wrap">
                                                <span className="truncate max-w-[200px] bg-white/5 px-2 py-1 rounded-md border border-white/5">{channelDisplayLabel(vid)}</span>
                                                {vid.source_url && (
                                                    <a
                                                        href={vid.source_url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="text-electric hover:underline truncate max-w-[320px]"
                                                        title={vid.source_url}
                                                        onClick={(e) => e.stopPropagation()}
                                                    >
                                                        {channelDisplayLabel(vid)}
                                                    </a>
                                                )}
                                            </div>
                                            <div className="mt-3 pt-3 border-t border-white/5">
                                                <div className="text-[10px] font-bold uppercase tracking-wider text-muted mb-2">Канал (откуда скачан)</div>
                                                {channelEdit.videoId === vid.video_id ? (
                                                    <div className="flex flex-wrap items-center gap-2" onClick={(e) => e.stopPropagation()}>
                                                        <input
                                                            type="text"
                                                            placeholder="Название или @ник (напр. Юлия Латынина или @yulialatynina71)"
                                                            value={channelEdit.channel_name}
                                                            onChange={(e) => setChannelEdit(prev => ({ ...prev, channel_name: e.target.value }))}
                                                            className="bg-element border border-border rounded px-2 py-1 text-xs w-56"
                                                        />
                                                        <input
                                                            type="text"
                                                            placeholder="youtube.com/... (опционально)"
                                                            value={channelEdit.source_url}
                                                            onChange={(e) => setChannelEdit(prev => ({ ...prev, source_url: e.target.value }))}
                                                            className="bg-element border border-border rounded px-2 py-1 text-xs flex-1 min-w-[180px]"
                                                        />
                                                        <button type="button" onClick={() => saveVideoChannel(vid.video_id, channelEdit.channel_name, channelEdit.source_url)} className="text-[10px] px-2 py-1 rounded bg-electric/20 text-electric font-medium">Сохранить</button>
                                                        <button type="button" onClick={() => setChannelEdit({ videoId: null, channel_name: '', source_url: '' })} className="text-[10px] px-2 py-1 rounded bg-white/5 text-muted">Отмена</button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        type="button"
                                                        onClick={(e) => { e.stopPropagation(); setChannelEdit({ videoId: vid.video_id, channel_name: vid.channel_name || '', source_url: vid.source_url || '' }); }}
                                                        className="text-[10px] px-2 py-1 rounded bg-white/5 text-muted hover:text-main border border-border/50"
                                                    >
                                                        {vid.channel_name ? 'Изменить канал' : 'Указать канал'}
                                                    </button>
                                                )}
                                            </div>
                                            <div className="flex gap-4 mt-4 pt-3">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted">Загрузка</span>
                                                    {getStatusBadge(vid.status_download)}
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted">Транскрипция</span>
                                                    {getStatusBadge(vid.status_transcribe)}
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted">Индекс</span>
                                                    {getStatusBadge(vid.status_index)}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex gap-3 mt-4 justify-end border-t border-white/5 pt-4 flex-wrap">
                                        {vid.status_transcribe !== 'done' && (
                                            <button onClick={() => handleTranscribe(vid.video_id)} disabled={!!processing[vid.video_id]} className="text-sm bg-electric/10 text-electric px-4 py-2 rounded-lg hover:bg-electric/20 transition-colors font-medium">
                                                Транскрибировать
                                            </button>
                                        )}
                                        {vid.status_transcribe === 'done' && vid.status_index !== 'done' && (
                                            <button onClick={() => handleIndex(vid.video_id)} disabled={!!processing[vid.video_id]} className="text-sm bg-electric/10 text-electric px-4 py-2 rounded-lg hover:bg-electric/20 transition-colors font-medium">
                                                Индексировать
                                            </button>
                                        )}
                                        <button
                                            onClick={() => handleReprocess(vid.video_id)}
                                            disabled={!!processing[vid.video_id]}
                                            className="text-sm bg-plasma/10 text-plasma px-3 py-2 rounded-lg hover:bg-plasma/20 transition-colors font-medium border border-plasma/20"
                                            title="Перезапустить обработку (ASR + Index)"
                                        >
                                            🔄 Заново
                                        </button>
                                        <button
                                            onClick={() => fetchLogs(vid.video_id)}
                                            className="text-sm bg-white/5 text-muted px-3 py-2 rounded-lg hover:text-main transition-colors border border-border/50 flex items-center gap-1"
                                            title="Посмотреть логи обработки"
                                        >
                                            <IconLogs className="w-4 h-4" /> Логи
                                        </button>
                                        <button
                                            onClick={() => handleDelete(vid.video_id)}
                                            className="text-sm bg-red-500/10 text-red-400 px-3 py-2 rounded-lg hover:bg-red-500/20 transition-colors font-medium border border-red-500/20"
                                            title="Удалить из базы"
                                        >
                                            🗑️
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
                {videos.length === 0 && (
                    <div className="text-center py-20 text-muted font-mono text-sm">
                        Index Empty. Init sequence required.
                    </div>
                )}
            </div>

            {/* ClipEditor Modal */}
            {
                clipEditorVideoId && (
                    <ClipEditor
                        videoId={clipEditorVideoId}
                        onClose={() => setClipEditorVideoId(null)}
                    />
                )
            }
            {/* Orphaned Embeddings Modal */}
            {orphanedEmbeddings !== null && (
                <div className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-center justify-center p-6">
                    <div className="bg-panel w-full max-w-3xl h-[70vh] rounded-2xl shadow-2xl border border-border flex flex-col overflow-hidden">
                        <div className="flex items-center justify-between p-4 border-b border-border bg-black/20">
                            <h3 className="font-bold flex items-center gap-2">
                                🧹 Осиротевшие эмбеддинги
                            </h3>
                            <button onClick={() => setOrphanedEmbeddings(null)} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                                <IconClose className="w-5 h-5" />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar">
                            {orphanedEmbeddings.orphaned_count === 0 ? (
                                <div className="text-muted italic opacity-50 text-center py-10">
                                    Осиротевших эмбеддингов не найдено. Всё чисто! ✨
                                </div>
                            ) : (
                                <>
                                    <div className="text-sm text-muted mb-4">
                                        Найдено {orphanedEmbeddings.orphaned_count} видео с осиротевшими эмбеддингами (видео удалены из БД, но эмбеддинги остались в ChromaDB)
                                    </div>
                                    <div className="space-y-2">
                                        {orphanedEmbeddings.orphaned.map((item, idx) => (
                                            <div key={idx} className="bg-element p-3 rounded-lg border border-border/50 flex items-center justify-between hover:bg-white/5 transition-colors">
                                                <div className="flex-1 min-w-0">
                                                    <div className="font-medium text-main truncate" title={item.video_id}>
                                                        {item.video_id}
                                                    </div>
                                                    <div className="text-xs text-muted mt-1">
                                                        {item.vectors_count} векторов
                                                    </div>
                                                </div>
                                                <button
                                                    onClick={() => deleteEmbeddings(item.video_id)}
                                                    className="ml-4 text-sm bg-red-500/10 text-red-400 px-3 py-1.5 rounded-lg hover:bg-red-500/20 transition-colors font-medium border border-red-500/20"
                                                >
                                                    Удалить
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                    {orphanedEmbeddings.orphaned_count > 5 && (
                                        <div className="mt-4 pt-4 border-t border-border">
                                            <button
                                                onClick={async () => {
                                                    const ok = await confirm({
                                                        title: 'Удалить все осиротевшие эмбеддинги',
                                                        message: `Удалить ВСЕ ${orphanedEmbeddings.orphaned_count} осиротевших эмбеддингов?`,
                                                        danger: true,
                                                        confirmLabel: 'Удалить все',
                                                    });
                                                    if (!ok) return;
                                                    let deleted = 0;
                                                    for (const item of orphanedEmbeddings.orphaned) {
                                                        try {
                                                            const res = await fetch(`/api/embeddings/${encodeURIComponent(item.video_id)}`, { method: 'DELETE' });
                                                            if (res.ok) deleted++;
                                                        } catch (err) {
                                                            console.error(`Failed to delete ${item.video_id}`, err);
                                                        }
                                                    }
                                                    addToast(`Удалено ${deleted} из ${orphanedEmbeddings.orphaned_count} эмбеддингов`, 'success');
                                                    fetchOrphanedEmbeddings();
                                                }}
                                                className="w-full text-sm bg-red-500/10 text-red-400 px-4 py-2 rounded-lg hover:bg-red-500/20 transition-colors font-medium border border-red-500/20"
                                            >
                                                Удалить все ({orphanedEmbeddings.orphaned_count})
                                            </button>
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                        <div className="p-4 border-t border-border bg-black/10 flex justify-end">
                            <button onClick={() => setOrphanedEmbeddings(null)} className="text-xs bg-electric text-white px-4 py-2 rounded-lg hover:bg-electric/80 transition-all font-bold">
                                Закрыть
                            </button>
                        </div>
                    </div>
                    <div className="absolute inset-0 -z-10" onClick={() => setOrphanedEmbeddings(null)}></div>
                </div>
            )}
            {/* Logs Modal */}
            {logsData.videoId && (
                <div className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-center justify-center p-6">
                    <div className="bg-panel w-full max-w-2xl h-[60vh] rounded-2xl shadow-2xl border border-border flex flex-col overflow-hidden">
                        <div className="flex items-center justify-between p-4 border-b border-border bg-black/20">
                            <h3 className="font-bold flex items-center gap-2">
                                <IconLogs className="w-5 h-5 text-electric" /> Логи: {logsData.videoId}
                            </h3>
                            <button onClick={() => setLogsData({ videoId: null, logs: [] })} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                                <IconClose className="w-5 h-5" />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-xs custom-scrollbar">
                            {logsData.logs.length === 0 && <div className="text-muted italic opacity-50">Логов пока нет...</div>}
                            {logsData.logs.map(log => (
                                <div key={log.id} className="border-l-2 border-white/5 pl-3 py-1 hover:bg-white/5 transition-colors">
                                    <div className="flex justify-between opacity-40 mb-1">
                                        <span className={log.level === 'ERROR' ? 'text-red-400' : 'text-electric'}>{log.level}</span>
                                        <span>{new Date(log.timestamp).toLocaleString()}</span>
                                    </div>
                                    <div className="text-main leading-relaxed">{log.message}</div>
                                </div>
                            ))}
                        </div>
                        <div className="p-4 border-t border-border bg-black/10 flex justify-end">
                            <button onClick={() => fetchLogs(logsData.videoId)} className="text-xs bg-electric text-white px-4 py-2 rounded-lg hover:bg-electric/80 transition-all font-bold">
                                Обновить
                            </button>
                        </div>
                    </div>
                    <div className="absolute inset-0 -z-10" onClick={() => setLogsData({ videoId: null, logs: [] })}></div>
                </div>
            )}
        </div>
    );
}
