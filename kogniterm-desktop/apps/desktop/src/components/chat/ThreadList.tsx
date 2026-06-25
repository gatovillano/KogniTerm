import React, { useState, useEffect } from 'react';
import { MessageSquare, Plus, Trash2 } from 'lucide-react';

interface Thread {
    id: string;
    title: string;
    updated_at: string;
}

interface ThreadListProps {
    currentThread: string | null;
    onSelectThread: (id: string) => void;
}

export function ThreadList({ currentThread, onSelectThread }: ThreadListProps) {
    const [threads, setThreads] = useState<Thread[]>([]);

    const fetchThreads = async () => {
        try {
            const res = await fetch('http://127.0.0.1:8765/api/threads');
            const data = await res.json();
            setThreads(data.threads || []);
        } catch (error) {
            console.error("Error fetching threads:", error);
        }
    };

    useEffect(() => {
        fetchThreads();
        
        // Listen to window events for thread updates if needed
        const handleThreadUpdate = () => fetchThreads();
        window.addEventListener('thread_update', handleThreadUpdate);
        return () => window.removeEventListener('thread_update', handleThreadUpdate);
    }, []);

    const createThread = async () => {
        try {
            const res = await fetch('http://127.0.0.1:8765/api/threads', { method: 'POST' });
            const data = await res.json();
            if (data.thread_id) {
                await fetchThreads();
                onSelectThread(data.thread_id);
            }
        } catch (error) {
            console.error("Error creating thread:", error);
        }
    };

    const deleteThread = async (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        try {
            await fetch(`http://127.0.0.1:8765/api/threads/${id}`, { method: 'DELETE' });
            await fetchThreads();
            if (currentThread === id) {
                onSelectThread(threads.find(t => t.id !== id)?.id || '');
            }
        } catch (error) {
            console.error("Error deleting thread:", error);
        }
    };

    return (
        <div className="flex flex-col h-full bg-[#0d0d0f] border-r border-[#27272a] w-full z-10 flex">
            <div className="p-4 border-b border-[#27272a]/50 flex justify-between items-center bg-[#09090b]">
                <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Hilos de Chat</h2>
                <button 
                    onClick={createThread}
                    className="p-1 hover:bg-[#27272a] rounded-md text-zinc-400 hover:text-white transition-colors"
                >
                    <Plus size={16} />
                </button>
            </div>
            <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
                {threads.map(thread => (
                    <div 
                        key={thread.id}
                        onClick={() => onSelectThread(thread.id)}
                        className={`group flex items-center justify-between p-2.5 rounded-lg cursor-pointer transition-all duration-200 ${
                            currentThread === thread.id 
                                ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' 
                                : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200 border border-transparent'
                        }`}
                    >
                        <div className="flex items-center space-x-3 overflow-hidden min-w-0 flex-1">
                            <MessageSquare size={14} className="shrink-0" />
                            <span className="text-sm truncate w-full" title={thread.title}>
                                {thread.title || 'Nueva conversación'}
                            </span>
                        </div>
                        <button 
                            onClick={(e) => deleteThread(e, thread.id)}
                            className="opacity-0 group-hover:opacity-100 p-1 text-zinc-500 hover:text-red-400 transition-opacity ml-2 shrink-0 rounded hover:bg-red-400/10"
                        >
                            <Trash2 size={14} />
                        </button>
                    </div>
                ))}
                {threads.length === 0 && (
                    <div className="p-4 text-center text-zinc-500 text-sm">
                        No hay hilos guardados.
                    </div>
                )}
            </div>
        </div>
    );
}
