import React, { createContext, useContext, useState, useCallback } from 'react';

const ToastContext = createContext(null);
const ConfirmContext = createContext(null);

const TOAST_TTL_MS = 5000;
const MAX_TOASTS = 5;

export function useToast() {
    const ctx = useContext(ToastContext);
    if (!ctx) throw new Error('useToast must be used within UIContextProvider');
    return ctx;
}

export function useConfirm() {
    const ctx = useContext(ConfirmContext);
    if (!ctx) throw new Error('useConfirm must be used within UIContextProvider');
    return ctx;
}

export function UIContextProvider({ children }) {
    const [toasts, setToasts] = useState([]);
    const [confirmState, setConfirmState] = useState(null);

    const addToast = useCallback((message, type = 'info') => {
        const id = Date.now() + Math.random();
        setToasts(prev => {
            const next = [...prev, { id, message, type }].slice(-MAX_TOASTS);
            return next;
        });
        setTimeout(() => {
            setToasts(prev => prev.filter(t => t.id !== id));
        }, TOAST_TTL_MS);
    }, []);

    const confirm = useCallback((options) => {
        return new Promise((resolve) => {
            setConfirmState({
                title: options.title || 'Подтверждение',
                message: options.message || '',
                confirmLabel: options.confirmLabel || 'OK',
                cancelLabel: options.cancelLabel || 'Отмена',
                danger: options.danger === true,
                onConfirm: () => {
                    setConfirmState(null);
                    resolve(true);
                },
                onCancel: () => {
                    setConfirmState(null);
                    resolve(false);
                },
            });
        });
    }, []);

    return (
        <ToastContext.Provider value={{ addToast }}>
            <ConfirmContext.Provider value={{ confirm }}>
                {children}
                <ToastContainer toasts={toasts} />
                {confirmState && <ConfirmModal {...confirmState} />}
            </ConfirmContext.Provider>
        </ToastContext.Provider>
    );
}

function ToastContainer({ toasts }) {
    if (toasts.length === 0) return null;
    return (
        <div className="fixed bottom-4 right-4 z-[70] flex flex-col gap-2 max-w-sm" role="region" aria-label="Уведомления">
            {toasts.map(t => (
                <div
                    key={t.id}
                    className={`px-4 py-3 rounded-lg shadow-lg border text-sm ${
                        t.type === 'success' ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' :
                        t.type === 'error' ? 'bg-red-500/15 text-red-300 border-red-500/30' :
                        'bg-panel text-main border-border'
                    }`}
                >
                    {t.message}
                </div>
            ))}
        </div>
    );
}

function ConfirmModal({ title, message, confirmLabel, cancelLabel, danger, onConfirm, onCancel }) {
    return (
        <div className="fixed inset-0 z-[70] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="confirm-title" onClick={onCancel}>
            <div className="bg-panel w-full max-w-md rounded-2xl border border-border shadow-2xl p-6" onClick={(e) => e.stopPropagation()}>
                <h2 id="confirm-title" className="text-lg font-bold text-main mb-2">{title}</h2>
                {message && <p className="text-muted text-sm mb-6">{message}</p>}
                <div className="flex gap-3 justify-end">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 rounded-lg bg-white/5 text-muted hover:text-main border border-border transition-colors"
                    >
                        {cancelLabel}
                    </button>
                    <button
                        onClick={onConfirm}
                        className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                            danger
                                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30'
                                : 'bg-electric text-white hover:bg-electric/90'
                        }`}
                    >
                        {confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
