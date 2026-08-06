import React, { useState } from 'react';
import { History, MessageSquare, Trash2, Calendar, Search, ArrowRight, Sparkles } from 'lucide-react';

export interface ThreadItem {
  id: string;
  title?: string;
  updated_at?: string;
  created_at?: string;
  message_count?: number;
  last_message?: string;
}

interface SessionHistoryPanelProps {
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

  const filteredThreads = threads.filter(t => 
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
        minute: '2-digit'
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#fafafa] overflow-hidden select-none animate-fade-in">
      
      {/* Top Header Bar */}
      <div className="px-8 py-6 border-b border-slate-200/60 bg-white/60 backdrop-blur-md flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-2xl bg-indigo-50 border border-indigo-100 text-indigo-600 shadow-2xs">
            <History size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-slate-900 leading-none">Historial de Sesiones</h1>
              <span className="px-2 py-0.5 rounded-full bg-slate-100 border border-slate-200/80 text-xs font-semibold text-slate-500">
                {threads.length} {threads.length === 1 ? 'sesión' : 'sesiones'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">Explora y gestiona tus conversaciones anteriores de KogniTerm</p>
          </div>
        </div>

        {/* Search & Actions Header */}
        <div className="flex items-center gap-3">
          <div className="relative w-64">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white border border-slate-200/80 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition-all shadow-2xs"
              placeholder="Buscar por título o ID..."
            />
            <Search className="absolute left-3 top-2.5 text-slate-400" size={13} />
          </div>

          <button
            onClick={onNewSession}
            className="flex items-center gap-2 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-semibold shadow-card-light transition-all active:scale-[0.98]"
          >
            <Sparkles size={14} />
            <span>Nueva sesión</span>
          </button>
        </div>
      </div>

      {/* Main Grid Content Area - Three Columns */}
      <div className="flex-1 overflow-y-auto goose-scrollbar p-8">
        {filteredThreads.length === 0 ? (
          <div className="h-[60vh] flex flex-col items-center justify-center text-center">
            <div className="p-4 rounded-full bg-slate-100 text-slate-400 mb-3">
              <MessageSquare size={28} />
            </div>
            <p className="text-sm font-semibold text-slate-700 mb-1">No se encontraron sesiones</p>
            <p className="text-xs text-slate-400 max-w-sm">
              {searchQuery ? 'Intenta modificar el término de búsqueda.' : 'Crea una nueva sesión para empezar a interactuar con el asistente.'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 max-w-7xl mx-auto">
            {filteredThreads.map((thread) => {
              const isCurrent = currentThreadId === thread.id;
              const formattedDate = formatDate(thread.updated_at || thread.created_at);

              return (
                <div
                  key={thread.id}
                  onClick={() => onSelectThread(thread.id)}
                  className={`group bg-white border rounded-2xl p-5 transition-all duration-200 cursor-pointer flex flex-col justify-between hover:-translate-y-1 ${
                    isCurrent 
                      ? 'border-indigo-300 ring-2 ring-indigo-500/10 shadow-md' 
                      : 'border-slate-200/80 hover:border-slate-300 shadow-card-light hover:shadow-md'
                  }`}
                >
                  {/* Card Header */}
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <div className={`p-2 rounded-xl ${isCurrent ? 'bg-indigo-100/70 text-indigo-700' : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200/60 transition-colors'}`}>
                          <MessageSquare size={16} />
                        </div>
                        {isCurrent && (
                          <span className="px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-[10px] font-bold text-emerald-700 uppercase tracking-wide">
                            Activa
                          </span>
                        )}
                      </div>

                      <button
                        onClick={(e) => onDeleteThread(e, thread.id)}
                        className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-all"
                        title="Eliminar sesión"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>

                    {/* Card Title */}
                    <h3 className="text-sm font-semibold text-slate-800 group-hover:text-indigo-600 transition-colors line-clamp-2 leading-snug mb-1">
                      {thread.title || 'Conversación'}
                    </h3>

                    {/* ID Subtitle */}
                    <p className="text-[10px] font-mono text-slate-400 truncate mb-4">
                      ID: {thread.id}
                    </p>
                  </div>

                  {/* Card Footer with Date & CTA */}
                  <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
                    <div className="flex items-center gap-1.5">
                      <Calendar size={12} className="text-slate-400" />
                      <span className="text-[11px] text-slate-500">{formattedDate}</span>
                    </div>

                    <div className="flex items-center gap-1 text-[11px] font-semibold text-indigo-600 opacity-0 group-hover:opacity-100 transition-opacity">
                      <span>Abrir</span>
                      <ArrowRight size={12} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
