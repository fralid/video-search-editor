import React, { useState } from 'react';

export default function AddVideo({ onAdded, compact = false }) {
    const [mode, setMode] = useState('youtube'); // 'youtube', 'single', 'bulk', 'channel'
    const [ytUrl, setYtUrl] = useState('');
    const [url, setUrl] = useState('');
    const [bulkUrls, setBulkUrls] = useState('');
    const [channelUrl, setChannelUrl] = useState('');
    const [channelLimit, setChannelLimit] = useState(20);
    const [tags, setTags] = useState('');
    const [loading, setLoading] = useState(false);
    const [msg, setMsg] = useState(null);
    const [showAdvanced, setShowAdvanced] = useState(false);

    // ... (logic remains same)
    const handleSingleSubmit = async (e) => {
        e.preventDefault();
        if (!url.trim()) return;

        setLoading(true);
        setMsg(null);
        try {
            const res = await fetch('/api/videos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, tags: tags.trim() }),
            });
            const data = await res.json();

            if (res.ok) {
                setMsg({ type: 'success', text: `✅ Added: ${data.title?.substring(0, 50) || data.video_id}...` });
                setUrl('');
                if (onAdded) onAdded();
            } else {
                setMsg({ type: 'error', text: data.detail || 'Failed to add video' });
            }
        } catch (err) {
            setMsg({ type: 'error', text: 'Network error' });
        } finally {
            setLoading(false);
        }
    };

    // ... (other handlers same as below, just render changes)
    const handleBulkDownload = async (quality) => {
        const urls = bulkUrls.split('\n').map(u => u.trim()).filter(u => u);
        if (urls.length === 0) return;

        setLoading(true);
        setMsg(null);
        let ok = 0, fail = 0;
        try {
            for (const u of urls) {
                try {
                    const res = await fetch('/api/download/youtube', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url: u, quality }),
                    });
                    if (res.ok) ok++; else fail++;
                } catch { fail++; }
            }
            setMsg({
                type: ok > 0 ? 'success' : 'error',
                text: `⬇️ ${ok} видео в очереди на скачивание (${quality})${fail > 0 ? `, ${fail} ошибок` : ''}`
            });
            if (ok > 0) { setBulkUrls(''); if (onAdded) onAdded(); }
        } catch (err) {
            setMsg({ type: 'error', text: 'Network error' });
        } finally {
            setLoading(false);
        }
    };

    const handleChannelSubmit = async (e) => {
        e.preventDefault();
        if (!channelUrl.trim()) return;

        setLoading(true);
        setMsg(null);
        try {
            const res = await fetch('/api/videos/import-channel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    channel_url: channelUrl.trim(),
                    limit: channelLimit,
                    tags: tags.trim()
                }),
            });
            const data = await res.json();

            if (res.ok) {
                setMsg({
                    type: 'success',
                    text: `✅ Importing ${data.videos_added} videos`
                });
                setChannelUrl('');
                if (onAdded) onAdded();
            } else {
                setMsg({ type: 'error', text: data.detail || 'Failed to import channel' });
            }
        } catch (err) {
            setMsg({ type: 'error', text: 'Network error' });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="h-full">
            {/* Mode tabs */}
            <div className={`flex gap-1 mb-4 bg-element p-1 rounded-lg ${compact ? 'flex-col' : ''}`}>
                <button
                    onClick={() => setMode('youtube')}
                    className={`flex-1 py-1.5 px-2 rounded-md text-[10px] font-semibold transition-all ${mode === 'youtube'
                        ? 'bg-emerald-600 text-white'
                        : 'text-muted hover:text-main hover:bg-black/10'
                        }`}
                >
                    YouTube
                </button>
                <button
                    onClick={() => setMode('single')}
                    className={`flex-1 py-1.5 px-2 rounded-md text-[10px] font-semibold transition-all ${mode === 'single'
                        ? 'bg-electric text-white'
                        : 'text-muted hover:text-main hover:bg-black/10'
                        }`}
                >
                    Single
                </button>
                <button
                    onClick={() => setMode('bulk')}
                    className={`flex-1 py-1.5 px-2 rounded-md text-[10px] font-semibold transition-all ${mode === 'bulk'
                        ? 'bg-electric text-white'
                        : 'text-muted hover:text-main hover:bg-black/10'
                        }`}
                >
                    Bulk
                </button>
                <button
                    onClick={() => setMode('channel')}
                    className={`flex-1 py-1.5 px-2 rounded-md text-[10px] font-semibold transition-all ${mode === 'channel'
                        ? 'bg-electric text-white'
                        : 'text-muted hover:text-main hover:bg-black/10'
                        }`}
                >
                    Channel
                </button>
            </div>

            {/* Forms */}
            {mode === 'youtube' && (
                <div className="flex flex-col gap-3">
                    <input
                        type="text"
                        className="bg-element border border-transparent text-main px-3 py-2 rounded-lg focus:ring-1 focus:ring-emerald-500 outline-none w-full transition-all placeholder:text-muted text-xs"
                        placeholder="https://www.youtube.com/watch?v=..."
                        value={ytUrl}
                        onChange={(e) => setYtUrl(e.target.value)}
                    />
                    <div className="flex gap-2">
                        <button
                            disabled={loading || !ytUrl.trim()}
                            onClick={async () => {
                                setLoading(true); setMsg(null);
                                try {
                                    const res = await fetch('/api/download/youtube', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ url: ytUrl.trim(), quality: '720p' }),
                                    });
                                    const data = await res.json();
                                    if (res.ok) {
                                        setMsg({ type: 'success', text: '⬇️ Скачиваю 720p... Видео появится в библиотеке' });
                                        setYtUrl('');
                                        if (onAdded) onAdded();
                                    } else {
                                        setMsg({ type: 'error', text: data.error || 'Ошибка' });
                                    }
                                } catch (err) { setMsg({ type: 'error', text: 'Network error' }); }
                                finally { setLoading(false); }
                            }}
                            className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2.5 rounded-lg font-bold transition-all disabled:opacity-40 text-xs"
                        >
                            {loading ? '⏳ Скачиваю...' : '⚡ 720p (быстро)'}
                        </button>
                        <button
                            disabled={loading || !ytUrl.trim()}
                            onClick={async () => {
                                setLoading(true); setMsg(null);
                                try {
                                    const res = await fetch('/api/download/youtube', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ url: ytUrl.trim(), quality: 'best' }),
                                    });
                                    const data = await res.json();
                                    if (res.ok) {
                                        setMsg({ type: 'success', text: '⬇️ Скачиваю в макс. качестве...' });
                                        setYtUrl('');
                                        if (onAdded) onAdded();
                                    } else {
                                        setMsg({ type: 'error', text: data.error || 'Ошибка' });
                                    }
                                } catch (err) { setMsg({ type: 'error', text: 'Network error' }); }
                                finally { setLoading(false); }
                            }}
                            className="flex-1 bg-purple-600 hover:bg-purple-500 text-white px-4 py-2.5 rounded-lg font-bold transition-all disabled:opacity-40 text-xs"
                        >
                            {loading ? '⏳...' : '🎬 Best'}
                        </button>
                    </div>
                    <p className="text-[10px] text-muted">Cookies: Firefox. Видео сохраняется в videos/ и автоматически транскрибируется.</p>
                </div>
            )}

            {mode === 'single' && (
                <form onSubmit={handleSingleSubmit} className="flex flex-col gap-3">
                    <input
                        type="text"
                        className="bg-element border border-transparent text-main px-3 py-2 rounded-lg focus:ring-1 focus:ring-electric outline-none w-full transition-all placeholder:text-muted text-xs"
                        placeholder="YouTube URL или путь к файлу..."
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                    />
                    {/* YouTube кнопки */}
                    {url.trim() && (url.includes('youtube.com') || url.includes('youtu.be')) ? (
                        <div className="flex gap-2">
                            <button
                                type="button"
                                disabled={loading}
                                onClick={async () => {
                                    setLoading(true); setMsg(null);
                                    try {
                                        const res = await fetch('/api/download/youtube', {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify({ url: url.trim(), quality: '720p' }),
                                        });
                                        const data = await res.json();
                                        if (res.ok) {
                                            setMsg({ type: 'success', text: '⬇️ Скачиваю 720p... Следите в библиотеке' });
                                            setUrl('');
                                            if (onAdded) onAdded();
                                        } else {
                                            setMsg({ type: 'error', text: data.error || 'Ошибка' });
                                        }
                                    } catch (err) { setMsg({ type: 'error', text: 'Network error' }); }
                                    finally { setLoading(false); }
                                }}
                                className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg font-bold transition-all disabled:opacity-50 text-xs"
                            >
                                {loading ? '⏳...' : '⚡ 720p (быстро)'}
                            </button>
                            <button
                                type="button"
                                disabled={loading}
                                onClick={async () => {
                                    setLoading(true); setMsg(null);
                                    try {
                                        const res = await fetch('/api/download/youtube', {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify({ url: url.trim(), quality: 'best' }),
                                        });
                                        const data = await res.json();
                                        if (res.ok) {
                                            setMsg({ type: 'success', text: '⬇️ Скачиваю в макс. качестве...' });
                                            setUrl('');
                                            if (onAdded) onAdded();
                                        } else {
                                            setMsg({ type: 'error', text: data.error || 'Ошибка' });
                                        }
                                    } catch (err) { setMsg({ type: 'error', text: 'Network error' }); }
                                    finally { setLoading(false); }
                                }}
                                className="flex-1 bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-lg font-bold transition-all disabled:opacity-50 text-xs"
                            >
                                {loading ? '⏳...' : '🎬 Лучшее'}
                            </button>
                        </div>
                    ) : (
                        <button
                            type="submit"
                            disabled={loading}
                            className="bg-electric hover:bg-electric/90 text-white px-4 py-2 rounded-lg font-bold transition-all disabled:opacity-50 w-full text-xs"
                        >
                            {loading ? '...' : 'Add Video'}
                        </button>
                    )}
                </form>
            )}

            {mode === 'bulk' && (
                <div className="flex flex-col gap-3">
                    <textarea
                        className="bg-element border border-transparent text-main px-3 py-2 rounded-lg focus:ring-1 focus:ring-electric outline-none w-full h-24 resize-none placeholder:text-muted text-xs"
                        placeholder="YouTube URLs (one per line)..."
                        value={bulkUrls}
                        onChange={(e) => setBulkUrls(e.target.value)}
                    />
                    <div className="flex gap-2">
                        <button
                            type="button"
                            disabled={loading}
                            onClick={() => handleBulkDownload('720p')}
                            className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg font-bold transition-all disabled:opacity-50 text-xs"
                        >
                            {loading ? '⏳...' : '⚡ 720p (быстро)'}
                        </button>
                        <button
                            type="button"
                            disabled={loading}
                            onClick={() => handleBulkDownload('best')}
                            className="flex-1 bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-lg font-bold transition-all disabled:opacity-50 text-xs"
                        >
                            {loading ? '⏳...' : '🎬 Лучшее'}
                        </button>
                    </div>
                </div>
            )}

            {/* Channel form simplified */}
            {mode === 'channel' && (
                <form onSubmit={handleChannelSubmit} className="flex flex-col gap-3">
                    <input
                        type="text"
                        className="bg-element border border-transparent text-main px-3 py-2 rounded-lg focus:ring-1 focus:ring-electric outline-none w-full placeholder:text-muted text-xs"
                        placeholder="Channel URL..."
                        value={channelUrl}
                        onChange={(e) => setChannelUrl(e.target.value)}
                    />
                    <div className="flex bg-element border border-border rounded-lg items-center px-2">
                        <span className="text-[10px] text-muted mr-2">Limit:</span>
                        <input
                            type="number"
                            className="bg-transparent text-main py-1 w-full outline-none text-xs"
                            value={channelLimit}
                            onChange={(e) => setChannelLimit(e.target.value)}
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={loading}
                        className="bg-electric hover:bg-electric/90 text-white px-4 py-2 rounded-lg font-bold transition-all disabled:opacity-50 w-full text-xs"
                    >
                        {loading ? '...' : 'Import'}
                    </button>
                </form>
            )}

            {msg && (
                <div className={`mt-3 text-[10px] p-2 rounded border font-mono break-all ${msg.type === 'success' ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'}`}>
                    {msg.text}
                </div>
            )}
        </div>
    );
}
