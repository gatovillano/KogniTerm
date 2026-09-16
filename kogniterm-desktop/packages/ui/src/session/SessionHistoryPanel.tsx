import React, { useState } from 'react';
import { History, MessageSquare, Trash2, Calendar, Search, ArrowRight, Sparkles } from 'lucide-react';
import { ThreadItem } from '@kogniterm/types';

export interface SessionHistoryPanelProps {
  threads: ThreadItem[];
  currentThreadId: string;
  onSelectThread: (threadId: string) => void;
  onDeleteThread: (e: React.MouseEvent, threadId: string) => void;
  onNewSession: () => void;
}

export const SessionHistoryPanel: React.FC<SessionHistoryPanelProps> = ({
  threads,
  currentThreadId,
  onSelectThread,
  onDeleteThread,
  onNewSession,
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredThreads = threads.filter(
    (t) =>
      (t.title && t.title.toLowerCase().includes(searchQuery.toLowerCase())) ||
      t.id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'Fecha reciente';
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return dateStr;
      return date.toLocaleDateString('es-ES', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-zinc-950 text-zinc-100 max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2 text-zinc-100">
            <History size={22} className="text-indigo-400" />
            Historial de Sesiones
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Explora y retoma conversaciones y tareas anteriores
          </p>
        </div>

        <button
          onClick={onNewSession}
          className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-medium text-white hover:bg-indigo-500 shadow-sm transition-colors"
        >
          <Sparkles size={14} />
          Nueva Conversación
        </button>
      </div>

      <div className="relative">
        <Search size={15} className="absolute left-3 top-2.5 text-zinc-500" />
        <input
          type="text"
          placeholder="Buscar por título o ID de sesión..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-zinc-900 border border-zinc-800 rounded-xl pl-9 pr-4 py-2 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
        />
      </div>

      <div className="flex-1 overflow-y-auto space-y-2">
        {filteredThreads.length === 0 ? (
          <div className="p-8 text-center text-xs text-zinc-500">No se encontraron sesiones</div>
        ) : (
          filteredThreads.map((thread) => {
            const isActive = thread.id === currentThreadId;
            return (
              <div
                key={thread.id}
                onClick={() => onSelectThread(thread.id)}
                className={`group flex items-center justify-between p-3.5 rounded-xl border transition-all cursor-pointer ${
                  isActive
                    ? 'bg-indigo-600/15 border-indigo-500/50 shadow-sm'
                    : 'bg-zinc-900/60 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900'
                }`}
              >
                <div className="flex items-start gap-3 min-w-0">
                  <div
                    className={`p-2 rounded-lg ${
                      isActive
                        ? 'bg-indigo-500/20 text-indigo-400'
                        : 'bg-zinc-800 text-zinc-400 group-hover:text-zinc-200'
                    }`}
                  >
                    <MessageSquare size={16} />
                  </div>

                  <div className="min-w-0">
                    <h4 className="text-xs font-semibold text-zinc-200 truncate">
                      {thread.title || 'Conversación sin título'}
                    </h4>
                    <div className="flex items-center gap-3 mt-1 text-[11px] text-zinc-500">
                      <span className="flex items-center gap-1">
                        <Calendar size={12} />
                        {formatDate(thread.updated_at || thread.created_at)}
                      </span>
                      {thread.message_count !== undefined && (
                        <span>{thread.message_count} mensajes</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => onDeleteThread(e, thread.id)}
                    className="p-1.5 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-rose-500/10 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Eliminar sesión"
                  >
                    <Trash2 size={14} />
                  </button>

                  <ArrowRight
                    size={15}
                    className={`text-zinc-600 group-hover:text-indigo-400 transition-colors ${
                      isActive ? 'text-indigo-400' : ''
                    }`}
                  />
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
