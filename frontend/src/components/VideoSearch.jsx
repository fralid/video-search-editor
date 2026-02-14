import React, { useState, useEffect, useCallback } from 'react';

export default function VideoSearch({ onPlay }) {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [channels, setChannels] = useState([]);
    const [selectedChannels, setSelectedChannels] = useState([]);
    const [showFilters, setShowFilters] = useState(false);
    const [showChannelFilter, setShowChannelFilter] = useState(false);

    const [pageSize, setPageSize] = useState(10);
    const [allResults, setAllResults] = useState([]);
    const [visibleCount, setVisibleCount] = useState(10);
    const [searchError, setSearchError] = useState(null);

    useEffect(() => {
        fetch('/api/channels')
            .then(res => res.json())
            .then(data => setChannels(data))
            .catch(err => console.error("Failed to load channels", err));
    }, []);

    const toggleChannel = (channelName) => {
        setSelectedChannels(prev =>
            prev.includes(channelName)
                ? prev.filter(c => c !== channelName)
                : [...prev, channelName]
        );
    };

    /** Показ канала: из URL — только @handle, иначе как есть. */
    const channelNameToDisplay = (name) => {
        if (!name || typeof name !== 'string') return '—';
        const atMatch = name.match(/youtube\.com\/@([^/?]+)/i) || name.match(/youtu\.be\/@([^/?]+)/i) || name.match(/@([^/?\s]+)/);
        if (atMatch) return atMatch[1].startsWith('@') ? atMatch[1] : `@${atMatch[1]}`;
        return name;
    };

    const doSearch = useCallback(async (searchQuery) => {
        if (!searchQuery.trim()) return;

        setLoading(true);
        setSearchError(null);
        try {
            const filter_tags = selectedChannels.length > 0
                ? selectedChannels.join(',')
                : undefined;

            const res = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: searchQuery, top_k: 100, filter_tags }),
            });
            const data = await res.json();
            if (!res.ok) {
                setSearchError(data.detail || data.error || data.message || 'Ошибка поиска');
                setAllResults([]);
                setResults([]);
                return;
            }
            setAllResults(data);
            setVisibleCount(pageSize);
            setResults(data.slice(0, pageSize));
        } catch (err) {
            console.error("Search failed", err);
            setSearchError(err.message || 'Ошибка сети. Проверьте, что backend запущен.');
        } finally {
            setLoading(false);
        }
    }, [selectedChannels, pageSize]);

    const handleSearch = async (e) => {
        e.preventDefault();
        doSearch(query);
    };

    const handleShowMore = () => {
        const newCount = visibleCount + pageSize;
        setVisibleCount(newCount);
        setResults(allResults.slice(0, newCount));
    };

    // When pageSize changes, update visible results
    const handlePageSizeChange = (newSize) => {
        setPageSize(newSize);
        if (allResults.length > 0) {
            setVisibleCount(newSize);
            setResults(allResults.slice(0, newSize));
        }
    };

    const formatTime = (seconds) => {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        return `${m}:${s.toString().padStart(2, '0')}`;
    };

    const exportCsv = () => {
        if (allResults.length === 0) return;
        const escape = (v) => {
            const s = String(v ?? '');
            if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
            return s;
        };
        const header = 'video_id,start_sec,end_sec,score,text';
        const rows = allResults.map((r) => {
            const start = r.start_sec ?? r.start ?? 0;
            const end = r.end_sec ?? r.end ?? 0;
            return [r.video_id, start, end, (r.score ?? 0).toFixed(4), r.text ?? ''].map(escape).join(',');
        });
        const csv = [header, ...rows].join('\r\n');
        const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `search-results-${query.slice(0, 30).replace(/[^\w]/g, '-') || 'export'}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const hasMore = allResults.length > visibleCount;

    return (
        <div className="flex flex-col h-full bg-app">

            {/* Scrollable Content Area */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
                {!results.length && !loading && (
                    <div className="h-full flex flex-col items-center justify-center opacity-40">
                        <div className="w-20 h-20 bg-element rounded-3xl flex items-center justify-center text-4xl mb-6 shadow-2xl">
                            🎥
                        </div>
                        <h2 className="text-2xl font-bold text-main mb-2">Video Search Agent</h2>
                        <p className="text-sm text-center max-w-md">
                            Search through video transcripts instantly. Enter keywords below to find exact moments.
                        </p>
                    </div>
                )}

                {/* Results count & page size selector */}
                {allResults.length > 0 && (
                    <div className="flex items-center justify-between max-w-4xl mx-auto mb-3 flex-wrap gap-2">
                        <div className="text-xs text-muted">
                            Показано <span className="text-main font-bold">{results.length}</span> из <span className="text-main font-bold">{allResults.length}</span> результатов
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={exportCsv}
                                className="text-[10px] px-2 py-1 rounded-md bg-white/5 text-muted hover:text-main hover:bg-white/10 transition-colors"
                                title="Скачать результаты в CSV"
                            >
                                Экспорт CSV
                            </button>
                            <span className="text-[10px] text-muted">На странице:</span>
                            {[5, 10, 20, 50].map(n => (
                                <button
                                    key={n}
                                    onClick={() => handlePageSizeChange(n)}
                                    className={`text-[10px] px-2 py-0.5 rounded-md transition-all ${pageSize === n
                                            ? 'bg-electric text-white font-bold'
                                            : 'bg-white/5 text-muted hover:text-main hover:bg-white/10'
                                        }`}
                                >
                                    {n}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                <div className="space-y-3 max-w-4xl mx-auto">
                    {results.map((item, idx) => (
                        <div
                            key={item.segment_id}
                            onClick={() => onPlay(item)}
                            className="bg-panel p-4 rounded-xl cursor-pointer hover:bg-white/5 transition-all group border border-transparent hover:border-electric/30 relative"
                        >
                            <div className="flex items-start gap-4">
                                {/* Номер и score */}
                                <div className="flex flex-col items-center gap-1 pt-0.5 flex-shrink-0">
                                    <span className="text-lg font-bold text-electric/60">{idx + 1}</span>
                                    <span className="text-[10px] text-muted">{(item.score * 100).toFixed(0)}%</span>
                                </div>

                                {/* Контент */}
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1.5">
                                        <span className="text-[11px] font-medium text-electric bg-electric/10 px-2 py-0.5 rounded truncate max-w-[300px]" title={item.video_id}>
                                            {item.video_id.length > 40 ? item.video_id.slice(0, 40) + '...' : item.video_id}
                                        </span>
                                        <span className="text-[11px] font-mono text-muted flex-shrink-0">
                                            {formatTime(item.start_sec || item.start)} — {formatTime(item.end_sec || item.end)}
                                        </span>
                                    </div>
                                    <p className="text-main text-sm leading-relaxed line-clamp-3">{item.text}</p>
                                </div>

                                {/* Play */}
                                <div className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity self-center">
                                    <span className="text-electric text-xl">▶</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Show More Button */}
                {hasMore && !loading && (
                    <div className="flex justify-center mt-6 max-w-4xl mx-auto">
                        <button
                            onClick={handleShowMore}
                            className="px-8 py-3 bg-electric/10 text-electric rounded-xl hover:bg-electric/20 transition-all font-bold text-sm border border-electric/20 hover:border-electric/40 flex items-center gap-2"
                        >
                            <span>Показать ещё {Math.min(pageSize, allResults.length - visibleCount)}</span>
                            <span className="text-[10px] opacity-60">
                                (осталось {allResults.length - visibleCount})
                            </span>
                        </button>
                    </div>
                )}

                {/* All results shown */}
                {allResults.length > 0 && !hasMore && (
                    <div className="text-center mt-6 text-[10px] text-muted">
                        Все результаты показаны
                    </div>
                )}

                {loading && (
                    <div className="flex justify-center py-10">
                        <div className="flex gap-2">
                            <div className="w-2 h-2 bg-electric rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                            <div className="w-2 h-2 bg-electric rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                            <div className="w-2 h-2 bg-electric rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                        </div>
                    </div>
                )}
            </div>

            {/* Fixed Input Area — фильтры сверху, затем поле поиска */}
            <div className="p-6 bg-app/95 backdrop-blur-sm border-t border-border z-10 w-full max-w-4xl mx-auto">
                {/* Фильтры: Искать в — над полем ввода; один открытый dropdown */}
                <div className="mb-3 flex flex-wrap items-center justify-center gap-3">
                    <span className="text-[10px] text-muted">Искать в:</span>
                    <button
                        type="button"
                        onClick={() => { setShowChannelFilter(false); setSelectedChannels([]); }}
                        className={`text-[10px] px-2 py-1 rounded-md transition-all ${selectedChannels.length === 0 ? 'bg-electric/20 text-electric font-medium' : 'bg-white/5 text-muted hover:text-main'}`}
                    >
                        Все видео
                    </button>
                    <div className="relative inline-block">
                        <button
                            type="button"
                            onClick={() => setShowChannelFilter(!showChannelFilter)}
                            className={`text-[10px] px-2 py-1 rounded-md transition-all ${selectedChannels.length > 0 ? 'bg-electric/20 text-electric font-medium' : 'bg-white/5 text-muted hover:text-main'}`}
                        >
                            По каналам {selectedChannels.length > 0 ? `(${selectedChannels.length})` : ''} ▾
                        </button>
                        {showChannelFilter && (
                            <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 z-20 max-h-[min(280px,40vh)] overflow-y-auto overflow-x-hidden bg-panel border border-border rounded-xl shadow-xl p-2 min-w-[200px] max-w-[90vw]">
                                <div className="flex items-center justify-between gap-2 mb-2 sticky top-0 bg-panel py-1">
                                    <span className="text-[10px] text-muted">Фильтр по каналам:</span>
                                    <button type="button" onClick={() => setShowChannelFilter(false)} className="text-muted hover:text-main p-1 rounded" title="Закрыть">✕</button>
                                </div>
                                {channels.length === 0 ? (
                                    <div className="text-[10px] text-muted py-2">Нет каналов. Укажите канал у видео в библиотеке.</div>
                                ) : (
                                    channels.map((ch) => (
                                        <label key={ch.name} className="flex items-center gap-2 py-1 hover:bg-white/5 rounded px-1 cursor-pointer">
                                            <input type="checkbox" checked={selectedChannels.includes(ch.name)} onChange={() => toggleChannel(ch.name)} className="rounded border-border" />
                                            <span className="text-xs truncate" title={ch.name}>{channelNameToDisplay(ch.name)}</span>
                                            <span className="text-[10px] text-muted">({ch.count})</span>
                                        </label>
                                    ))
                                )}
                            </div>
                        )}
                    </div>
                </div>

                <form onSubmit={handleSearch} className="relative shadow-2xl rounded-2xl">
                    <input
                        type="text"
                        className="w-full bg-panel border border-border text-main pl-6 pr-32 py-5 rounded-2xl focus:ring-1 focus:ring-electric focus:border-electric outline-none transition-all placeholder:text-muted/50 text-lg shadow-inner"
                        placeholder="Спросите что-нибудь..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                    />
                    <div className="absolute right-2 top-2 bottom-2">
                        <button
                            type="submit"
                            disabled={loading || !query.trim()}
                            className="h-full px-6 bg-electric hover:bg-electric/90 text-white rounded-xl font-bold transition-all disabled:opacity-50 disabled:bg-panel disabled:text-muted flex items-center gap-2"
                        >
                            {loading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div> : <span>Поиск</span>}
                        </button>
                    </div>
                </form>
                {searchError && (
                    <p className="mt-3 text-center text-sm text-red-400" role="alert">
                        {searchError}
                    </p>
                )}
                <div className="text-center mt-3 text-[10px] text-muted font-mono">
                    ИИ может ошибаться. Проверяйте важную информацию.
                </div>
            </div>
        </div>
    );
}
