import React, { useState, useEffect } from 'react';

export default function PopularWords({ onSearch, isOpen }) {
    const [words, setWords] = useState([]);
    const [loading, setLoading] = useState(false);
    const [minCount, setMinCount] = useState(5);
    const [minLength, setMinLength] = useState(4);
    const [limit, setLimit] = useState(80);
    const [totalUnique, setTotalUnique] = useState(0);

    const fetchWords = async () => {
        setLoading(true);
        try {
            const res = await fetch(`/api/words/popular?min_count=${minCount}&limit=${limit}&min_length=${minLength}`);
            if (res.ok) {
                const data = await res.json();
                setWords(data.words || []);
                setTotalUnique(data.total_unique || 0);
            }
        } catch (e) {
            console.error("Failed to load popular words", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (isOpen) fetchWords();
    }, [isOpen]);

    if (!isOpen) return null;

    const maxCount = words.length > 0 ? words[0].count : 1;

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="p-3 border-b border-border">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted mb-3">
                    🔤 Популярные слова
                </h3>

                {/* Filters */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <label className="text-[9px] text-muted w-16 flex-shrink-0">Мин. раз:</label>
                        <input
                            type="number"
                            value={minCount}
                            onChange={(e) => setMinCount(Math.max(1, parseInt(e.target.value) || 1))}
                            className="flex-1 bg-element text-main text-[11px] px-2 py-1 rounded border border-border focus:border-electric outline-none w-full"
                            min="1"
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        <label className="text-[9px] text-muted w-16 flex-shrink-0">Мин. букв:</label>
                        <input
                            type="number"
                            value={minLength}
                            onChange={(e) => setMinLength(Math.max(1, parseInt(e.target.value) || 1))}
                            className="flex-1 bg-element text-main text-[11px] px-2 py-1 rounded border border-border focus:border-electric outline-none w-full"
                            min="1"
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        <label className="text-[9px] text-muted w-16 flex-shrink-0">Лимит:</label>
                        <input
                            type="number"
                            value={limit}
                            onChange={(e) => setLimit(Math.max(10, parseInt(e.target.value) || 10))}
                            className="flex-1 bg-element text-main text-[11px] px-2 py-1 rounded border border-border focus:border-electric outline-none w-full"
                            min="10"
                        />
                    </div>
                    <button
                        onClick={fetchWords}
                        disabled={loading}
                        className="w-full text-[10px] font-bold bg-electric/10 text-electric py-1.5 rounded-lg hover:bg-electric/20 transition-colors disabled:opacity-50"
                    >
                        {loading ? '⏳ Загрузка...' : '🔄 Обновить'}
                    </button>
                </div>

                {totalUnique > 0 && (
                    <div className="text-[9px] text-muted mt-2">
                        Уникальных слов: {totalUnique.toLocaleString()} · Показано: {words.length}
                    </div>
                )}
            </div>

            {/* Word Cloud List */}
            <div className="flex-1 overflow-y-auto p-2 custom-scrollbar">
                {words.length === 0 && !loading ? (
                    <p className="text-[10px] text-muted text-center py-8">
                        Нет данных. Нажмите «Обновить».
                    </p>
                ) : (
                    <div className="flex flex-wrap gap-1 p-1">
                        {words.map((item) => {
                            const ratio = item.count / maxCount;
                            // Scale font size from 10px to 18px based on frequency
                            const fontSize = 10 + Math.round(ratio * 8);
                            // Opacity from 0.5 to 1
                            const opacity = 0.5 + ratio * 0.5;

                            return (
                                <button
                                    key={item.word}
                                    onClick={() => onSearch(item.word)}
                                    className="px-1.5 py-0.5 rounded-md bg-white/5 hover:bg-electric/20 hover:text-electric text-main transition-all cursor-pointer border border-transparent hover:border-electric/30"
                                    style={{ fontSize: `${fontSize}px`, opacity }}
                                    title={`«${item.word}» — ${item.count} раз`}
                                >
                                    {item.word}
                                    <span className="text-[8px] text-muted ml-0.5 opacity-70">{item.count}</span>
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
