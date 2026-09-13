import React, { useState, useEffect, useRef } from 'react';
import { Terminal, X, Copy, ChevronDown, ChevronUp, BarChart3, Send } from 'lucide-react';
import { TaskTracker } from '../chat/TaskTracker';

interface TerminalState {
  isOpen: boolean;
  sessionLabel: string;
  toolName: string;
  command: string;
  output: string;
}

interface RightSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  terminalState: TerminalState;
  taskPlans: any;
  activeTab?: 'terminal' | 'tasks';
  onTabChange?: (tab: 'terminal' | 'tasks') => void;
  isDark?: boolean;
}

export function RightSidebar({
  isOpen,
  onClose,
  terminalState,
  taskPlans,
  activeTab,
  onTabChange,
  isDark = true,
}: RightSidebarProps) {
  const [internalTab, setInternalTab] = useState<'terminal' | 'tasks'>('terminal');
  const terminalRef = useRef<HTMLDivElement>(null);

  // Auto-scroll al bottom cuando cambia el output
  useEffect(() => {
    if (terminalRef.current && (activeTab || internalTab) === 'terminal') {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [terminalState.output, activeTab, internalTab]);

  // Pestaña actual seleccionada (soporta modo controlado y no controlado)
  const currentTab = activeTab !== undefined ? activeTab : internalTab;

  const handleTabChange = (tab: 'terminal' | 'tasks') => {
    setInternalTab(tab);
    if (onTabChange) {
      onTabChange(tab);
    }
  };

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-[1px] z-40 transition-opacity duration-300 opacity-100"
          onClick={onClose}
        />
      )}

      {/* Sidebar deslizante desde la derecha */}
      <aside
        className={`fixed top-0 right-0 h-full z-50 flex flex-col shadow-2xl transition-transform duration-[350ms] ease-[cubic-bezier(0.4,0,0.2,1)] ${
          isDark 
            ? 'bg-[#070a13] text-slate-100 border-l border-white/[0.08]' 
            : 'bg-slate-50 text-slate-900 border-l border-slate-200'
        } ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
        style={{ width: 'min(500px, 90vw)', maxWidth: '500px' }}
      >
        {/* Header con pestañas */}
        <div className={`flex items-center justify-between px-4 py-3 border-b shrink-0 ${
          isDark ? 'border-white/[0.07]' : 'border-slate-200'
        }`}>
          <div className={`flex items-center gap-1 rounded-lg p-1 ${
            isDark ? 'bg-black/20' : 'bg-slate-200/60'
          }`}>
            <button
              onClick={() => handleTabChange('terminal')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                currentTab === 'terminal'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : isDark
                    ? 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-black/5'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              Terminal
            </button>
            <button
              onClick={() => handleTabChange('tasks')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                currentTab === 'tasks'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : isDark
                    ? 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-black/5'
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              Tasks
            </button>
          </div>

          <button
            onClick={onClose}
            className={`p-1.5 rounded-lg transition-colors opacity-60 hover:opacity-100 ${
              isDark ? 'hover:bg-white/10' : 'hover:bg-black/10'
            }`}
            title="Cerrar panel"
          >
            <X className={`w-4 h-4 ${isDark ? 'text-slate-300' : 'text-slate-600'}`} />
          </button>
        </div>

        {/* Contenido de las pestañas */}
        <div className="flex-1 overflow-hidden">
          {currentTab === 'terminal' && (
            <div className="h-full flex flex-col">
              {/* Terminal Header */}
              <div className={`px-4 py-2.5 border-b shrink-0 ${
                isDark ? 'border-white/[0.07]' : 'border-slate-200 bg-slate-100/50'
              }`}>
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-6 h-6 rounded bg-emerald-500/10 border border-emerald-500/20">
                    <Terminal className="w-3 h-3 text-emerald-500" />
                  </div>
                  <div className="flex flex-col overflow-hidden">
                    <span className={`font-mono text-xs font-medium ${
                      isDark ? 'text-slate-200' : 'text-slate-800'
                    }`}>
                      {terminalState.toolName ? `${terminalState.toolName} — Shell` : terminalState.sessionLabel || 'Terminal'}
                    </span>
                    {terminalState.command && (
                      <span className={`font-mono text-[10px] truncate max-w-[400px] ${
                        isDark ? 'text-emerald-400/80' : 'text-emerald-600'
                      }`}>
                        $ {terminalState.command.slice(0, 80)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Terminal Output */}
              <div
                ref={terminalRef}
                className={`flex-1 overflow-y-auto p-4 font-mono text-xs custom-scrollbar ${
                  isDark ? 'bg-black/40 text-emerald-400' : 'bg-slate-900 text-emerald-400'
                }`}
              >
                <div className="whitespace-pre-wrap break-words">
                  {terminalState.output || (
                    <span className="opacity-50"># Sin salida disponible todavía...</span>
                  )}
                </div>
              </div>

              {/* Terminal Footer */}
              <div className={`px-4 py-2 border-t shrink-0 ${
                isDark ? 'border-white/[0.07]' : 'border-slate-200 bg-slate-100/50'
              }`}>
                <div className={`flex items-center justify-between text-[10px] font-mono ${
                  isDark ? 'text-slate-500' : 'text-slate-600'
                }`}>
                  <span>Terminal en vivo</span>
                  <span>· {terminalState.command || 'ejecutando comando'}</span>
                </div>
              </div>
            </div>
          )}

          {currentTab === 'tasks' && (
            <div className="h-full overflow-y-auto custom-scrollbar">
              <div className="p-4">
                <TaskTracker plans={taskPlans} isDark={isDark} />
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
