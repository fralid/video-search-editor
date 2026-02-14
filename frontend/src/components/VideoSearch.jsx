import React, { useState, useEffect, useCallback } from 'react';

export default function VideoSearch({ onPlay, externalQuery }) {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [channels, setChannels] = useState([]);
    const [selectedChannels, setSelectedChannels] = useState([]);
    const [showFilters, setShowFilters] = useState(false);

    // Pagination
    const [pageSize, setPageSize] = useState(10);
    const [allResults, setAllResults] = useState([]);
    const [visibleCount, setVisibleCount] = useState(10);

    useEffect(() => {
        // Fetch channels for filter
        fetch('/api/channels')
            .then(res => res.json())
            .then(data => setChannels(data))
            .catch(err => console.error("Failed to load channels", err));
    }, []);

    // Handle external search (from PopularWords)
    useEffect(() => {
        if (externalQuery && externalQuery !== query) {
            setQuery(externalQuery);
            doSearch(externalQuery);
        }
    }, [externalQuery]);

    const toggleChannel = (channelName) => {
        setSelectedChannels(prev =>
            prev.includes(channelName)
                ? prev.filter(c => c !== channelName)
                : [...prev, channelName]
        );
    };

    const doSearch = useCallback(async (searchQuery) => {
        if (!searchQuery.trim()) return;

        setLoading(true);
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
            setAllResults(data);
            setVisibleCount(pageSize);
            setResults(data.slice(0, pageSize));
        } catch (err) {
            console.error("Search failed", err);
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
                    <div className="flex items-center justify-between max-w-4xl mx-auto mb-3">
                        <div className="text-xs text-muted">
                            Показано <span className="text-main font-bold">{results.length}</span> из <span className="text-main font-bold">{allResults.length}</span> результатов
                        </div>
                        <div className="flex items-center gap-2">
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

            {/* Fixed Input Area */}
            <div className="p-6 bg-app/95 backdrop-blur-sm border-t border-border z-10 w-full max-w-4xl mx-auto">
                <form onSubmit={handleSearch} className="relative shadow-2xl rounded-2xl">
                    <input
                        type="text"
                        className="w-full bg-panel border border-border text-main pl-6 pr-32 py-5 rounded-2xl focus:ring-1 focus:ring-electric focus:border-electric outline-none transition-all placeholder:text-muted/50 text-lg shadow-inner"
                        placeholder="Спросите что-нибудь о видео..."
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
                <div className="text-center mt-3 text-[10px] text-muted font-mono">
                    ИИ может ошибаться. Проверяйте важную информацию.
                </div>
            </div>
        </div>
    );
}
