import React from 'react';
import { IconLibrary, IconAdd, IconMenu } from './Icons';

export default function Sidebar({ isOpen, setIsOpen, onOpenLibrary, onOpenAdd }) {
    return (
        <div className={`fixed inset-y-0 left-0 z-50 bg-panel border-r border-border transition-all duration-300 flex flex-col ${isOpen ? 'w-64' : 'w-16'}`}>
            {/* Header / Toggle */}
            <div className="p-4 flex items-center justify-between h-16">
                <button
                    onClick={() => setIsOpen(!isOpen)}
                    className="p-2 rounded-lg hover:bg-white/5 transition-colors text-muted hover:text-main"
                >
                    <IconMenu className="w-6 h-6" />
                </button>
            </div>

            {/* Navigation Buttons */}
            <div className="flex flex-col gap-2 p-2">
                <button
                    onClick={onOpenLibrary}
                    className="flex items-center gap-3 p-3 rounded-lg text-muted hover:text-main hover:bg-white/5 transition-all text-left"
                    title="Библиотека"
                >
                    <IconLibrary className="w-6 h-6 flex-shrink-0" />
                    {isOpen && <span className="font-medium text-sm">Библиотека</span>}
                </button>
                <button
                    onClick={onOpenAdd}
                    className="flex items-center gap-3 p-3 rounded-lg text-muted hover:text-main hover:bg-white/5 transition-all text-left"
                    title="Добавить видео"
                >
                    <IconAdd className="w-6 h-6 flex-shrink-0" />
                    {isOpen && <span className="font-medium text-sm">Добавить видео</span>}
                </button>
            </div>
        </div>
    );
}
