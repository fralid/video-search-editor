import React, { useState, useCallback } from 'react';

const isYouTubeVideoUrl = (s) => /youtube\.com\/watch\?v=|youtu\.be\//i.test(s?.trim() || '');
const isYouTubeChannelUrl = (s) => /youtube\.com\/(@[^/?\s]+|channel\/[^/?\s]+|c\/[^/?\s]+)/i.test(s?.trim() || '');

export default function AddVideo({ onAdded, compact = false }) {
    const [input, setInput] = useState('');
    const [quality, setQuality] = useState('720p');
    const [loading, setLoading] = useState(false);
    const [msg, setMsg] = useState(null);

    const lines = input.split('\n').map((l) => l.trim()).filter(Boolean);
    const singleLine = lines.length === 1 ? lines[0] : '';
    const isChannel = singleLine && isYouTubeChannelUrl(singleLine) && !isYouTubeVideoUrl(singleLine);
    const isVideo = singleLine && isYouTubeVideoUrl(singleLine);
    const isList = lines.length > 1 && lines.every((l) => isYouTubeVideoUrl(l));
    const canSubmitVideo = singleLine && isYouTubeVideoUrl(singleLine);
    const canSubmitList = lines.length > 1 && lines.every((l) => isYouTubeVideoUrl(l));
    const canSubmitChannel = singleLine && isChannel;

    const submitYoutube = useCallback(
        async (url, q, clearAfter) => {
            if (!url?.trim()) return;
            setLoading(true);
            setMsg(null);
            try {
                const res = await fetch('/api/download/youtube', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url.trim(), quality: q, browser: 'firefox' }),
                });
                const data = await res.json();
                if (res.ok) {
                    setMsg({ type: 'success', text: '⬇️ Добавлено в очередь скачивания' });
                    if (typeof clearAfter === 'function') clearAfter();
                    if (onAdded) onAdded();
                } else {
                    setMsg({ type: 'error', text: data.error || 'Ошибка' });
                }
            } catch (err) {
                setMsg({ type: 'error', text: 'Ошибка сети' });
            } finally {
                setLoading(false);
            }
        },
        [onAdded]
    );

    const submitChannel = useCallback(
        async (url, q) => {
            if (!url?.trim()) return;
            setLoading(true);
            setMsg(null);
            try {
                const res = await fetch('/api/download/channel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url.trim(), quality: q, browser: 'firefox' }),
                });
                const data = await res.json();
                if (res.ok) {
                    setMsg({
                        type: 'success',
                        text: `⬇️ В очередь добавлено видео: ${data.enqueued}. Скачивание по одному.`,
                    });
                    setInput('');
                    if (onAdded) onAdded();
                } else {
                    setMsg({ type: 'error', text: data.error || 'Ошибка' });
                }
            } catch (err) {
                setMsg({ type: 'error', text: 'Ошибка сети' });
            } finally {
                setLoading(false);
            }
        },
        [onAdded]
    );

    const handleBulk = useCallback(
        async (q) => {
            if (lines.length === 0) return;
            setLoading(true);
            setMsg(null);
            let ok = 0,
                fail = 0;
            try {
                for (const u of lines) {
                    try {
                        const res = await fetch('/api/download/youtube', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ url: u, quality: q, browser: 'firefox' }),
                        });
                        if (res.ok) ok++;
                        else fail++;
                    } catch {
                        fail++;
                    }
                }
                setMsg({
                    type: ok > 0 ? 'success' : 'error',
                    text: `⬇️ В очередь: ${ok} видео${fail > 0 ? `, ошибок: ${fail}` : ''}`,
                });
                if (ok > 0) {
                    setInput('');
                    if (onAdded) onAdded();
                }
            } catch (err) {
                setMsg({ type: 'error', text: 'Ошибка сети' });
            } finally {
                setLoading(false);
            }
        },
        [lines, onAdded]
    );

    return (
        <div className="h-full">
            <div className="flex flex-col gap-3">
                <textarea
                    className="bg-element border border-border text-main px-3 py-2 rounded-lg focus:ring-1 focus:ring-electric outline-none w-full transition-all placeholder:text-muted text-xs min-h-[88px] resize-y"
                    placeholder={'Одно видео: https://www.youtube.com/watch?v=...\nСписок: несколько ссылок (каждая с новой строки)\nКанал: https://www.youtube.com/@канал или .../channel/...'}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    rows={4}
                />
                <div className="flex flex-wrap items-center gap-2">
                    {canSubmitVideo && !isChannel && (
                        <>
                            <button
                                type="button"
                                disabled={loading}
                                onClick={() => submitYoutube(singleLine, '720p', () => setInput(''))}
                                className="bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-lg font-semibold transition-all disabled:opacity-50 text-xs"
                            >
                                {loading ? '⏳' : '⚡ 720p'}
                            </button>
                            <button
                                type="button"
                                disabled={loading}
                                onClick={() => submitYoutube(singleLine, 'best', () => setInput(''))}
                                className="bg-purple-600 hover:bg-purple-500 text-white px-3 py-1.5 rounded-lg font-semibold transition-all disabled:opacity-50 text-xs"
                            >
                                {loading ? '⏳' : '🎬 Лучшее'}
                            </button>
                            <span className="text-[10px] text-muted">Одно видео</span>
                        </>
                    )}
                    {canSubmitChannel && (
                        <>
                            <button
                                type="button"
                                disabled={loading}
                                onClick={() => submitChannel(singleLine, '720p')}
                                className="bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-lg font-semibold transition-all disabled:opacity-50 text-xs"
                            >
                                {loading ? '⏳ Загрузка списка...' : '⚡ 720p — весь канал'}
                            </button>
                            <button
                                type="button"
                                disabled={loading}
                                onClick={() => submitChannel(singleLine, 'best')}
                                className="bg-purple-600 hover:bg-purple-500 text-white px-3 py-1.5 rounded-lg font-semibold transition-all disabled:opacity-50 text-xs"
                            >
                                {loading ? '⏳' : '🎬 Лучшее — весь канал'}
                            </button>
                            <span className="text-[10px] text-muted">Канал (до 500 видео)</span>
                        </>
                    )}
                    {canSubmitList && (
                        <>
                            <button
                                type="button"
                                disabled={loading}
                                onClick={() => handleBulk('720p')}
                                className="bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-lg font-semibold transition-all disabled:opacity-50 text-xs"
                            >
                                {loading ? '⏳' : `⚡ 720p — ${lines.length} шт.`}
                            </button>
                            <button
                                type="button"
                                disabled={loading}
                                onClick={() => handleBulk('best')}
                                className="bg-purple-600 hover:bg-purple-500 text-white px-3 py-1.5 rounded-lg font-semibold transition-all disabled:opacity-50 text-xs"
                            >
                                {loading ? '⏳' : `🎬 Лучшее — ${lines.length} шт.`}
                            </button>
                            <span className="text-[10px] text-muted">Список видео</span>
                        </>
                    )}
                </div>
                {!canSubmitVideo && !canSubmitList && !canSubmitChannel && input.trim() && (
                    <p className="text-[10px] text-muted">
                        Вставьте ссылку на видео YouTube, несколько ссылок (каждая с новой строки) или ссылку на канал (@канал или /channel/...).
                    </p>
                )}
                <p className="text-[10px] text-muted">
                    Cookies: Firefox. Видео сохраняются в videos/ и автоматически транскрибируются.
                </p>
            </div>

            {msg && (
                <div
                    className={`mt-3 text-[10px] p-2 rounded border font-mono break-all ${
                        msg.type === 'success'
                            ? 'bg-green-500/10 text-green-400 border-green-500/20'
                            : 'bg-red-500/10 text-red-400 border-red-500/20'
                    }`}
                >
                    {msg.text}
                </div>
            )}
        </div>
    );
}
