import React, { useState, useEffect } from 'react'
import VideoSearch from './components/VideoSearch'
import Sidebar from './components/Sidebar'
import VideoPlayer from './components/VideoPlayer'
import VideoLibrary from './components/VideoLibrary'
import AddVideo from './components/AddVideo'
import QueuePanel from './components/QueuePanel'
import { IconTheme, IconClose } from './components/Icons'

export default function App() {
    // Theme state
    const [theme, setTheme] = useState(() => {
        if (typeof window !== 'undefined') {
            return localStorage.getItem('theme') || 'dark';
        }
        return 'dark';
    });

    const [activeSegment, setActiveSegment] = useState(null);
    const [refreshTrigger, setRefreshTrigger] = useState(0);
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [activeModal, setActiveModal] = useState(null); // 'library', 'add', null
    const [wordSearchQuery, setWordSearchQuery] = useState('');

    // Apply theme
    useEffect(() => {
        const root = window.document.documentElement;
        if (theme === 'dark') {
            root.classList.add('dark');
        } else {
            root.classList.remove('dark');
        }
        localStorage.setItem('theme', theme);
    }, [theme]);

    const handleAdded = () => {
        setRefreshTrigger(prev => prev + 1);
    };

    const toggleTheme = () => {
        setTheme(prev => prev === 'dark' ? 'light' : 'dark');
    };

    const closeModal = () => setActiveModal(null);

    return (
        <div className="flex h-screen bg-app text-main font-sans selection:bg-electric/30 overflow-hidden relative">

            {/* Sidebar */}
            <Sidebar
                isOpen={sidebarOpen}
                setIsOpen={setSidebarOpen}
                onOpenLibrary={() => setActiveModal('library')}
                onOpenAdd={() => setActiveModal('add')}
                onWordSearch={(word) => setWordSearchQuery(word + '|' + Date.now())}
            />

            {/* Main Content */}
            <main className={`flex-1 flex flex-col transition-all duration-300 relative ${sidebarOpen ? 'ml-64' : 'ml-16'}`}>
                {/* Header / Top Bar */}
                <header className="h-16 flex items-center justify-between px-6 bg-app/80 backdrop-blur-md sticky top-0 z-40">
                    <div className="flex items-center gap-3">
                        <h1 className="text-xl font-bold tracking-tight">Поиск <span className="text-electric">Видео</span></h1>
                    </div>
                    <div>
                        <button
                            onClick={toggleTheme}
                            className="p-2 rounded-lg hover:bg-white/5 transition-colors text-muted hover:text-main"
                            title="Сменить тему"
                        >
                            <IconTheme className="w-5 h-5" isDark={theme === 'dark'} />
                        </button>
                    </div>
                </header>

                {/* Chat / Search Area */}
                <div className="flex-1 overflow-hidden relative">
                    <VideoSearch onPlay={setActiveSegment} externalQuery={wordSearchQuery ? wordSearchQuery.split('|')[0] : ''} />
                </div>
            </main>

            {/* Queue Panel — справа */}
            <QueuePanel />

            {/* Generic Modal Overlay */}
            {activeModal && (
                <div className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="bg-panel w-full max-w-4xl h-[80vh] rounded-2xl shadow-2xl flex flex-col border border-border overflow-hidden">
                        <div className="flex items-center justify-between p-4 border-b border-border">
                            <h2 className="text-lg font-bold">
                                {activeModal === 'library' ? 'Библиотека видео' : 'Добавить видео'}
                            </h2>
                            <button onClick={closeModal} className="text-muted hover:text-main transition-colors bg-white/5 p-2 rounded-lg">
                                <IconClose className="w-5 h-5" />
                            </button>
                        </div>
                        <div className="flex-1 overflow-hidden p-6 relative">
                            {activeModal === 'library' && (
                                <VideoLibrary refreshTrigger={refreshTrigger} />
                            )}
                            {activeModal === 'add' && (
                                <AddVideo onAdded={handleAdded} />
                            )}
                        </div>
                    </div>
                    {/* Click outside to close */}
                    <div className="absolute inset-0 -z-10" onClick={closeModal}></div>
                </div>
            )}

            {/* Modal Player */}
            <VideoPlayer
                segment={activeSegment}
                onClose={() => setActiveSegment(null)}
            />
        </div>
    )
}
