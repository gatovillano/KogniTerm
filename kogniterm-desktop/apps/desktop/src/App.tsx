import { useRef, useEffect, useState } from 'react';
import { ChatMessage } from './components/chat/ChatMessage';
import { ChatInput } from './components/chat/ChatInput';
import { FileExplorer } from './components/files/FileExplorer';
import { SkillsPanel } from './components/skills/SkillsPanel';
import { SettingsModal } from './components/settings/SettingsModal';
import { HeartbeatsPanel } from './components/heartbeats/HeartbeatsPanel';
import { RightSidebar } from './components/chat/RightSidebar';
import { SessionHistoryPanel } from './components/session/SessionHistoryPanel';
import { useChat } from './hooks/useChat';
import { 
  Settings, Files, ShieldCheck, 
  Zap, History, PanelLeft, 
  Trash2, Plus, HeartPulse, Sparkles, PanelRightOpen
} from 'lucide-react';
import './App.css';

type ViewType = 'chat' | 'files' | 'skills' | 'heartbeat' | 'session';

function App() {
  const [currentThreadId, setCurrentThreadId] = useState<string>(() => {
    return `desktop-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  });
  
  const {
    messages,
    isGenerating,
    error,
    sendMessage,
    stopGeneration,
    taskPlans,
    pendingApproval,
    respondApproval,
    terminalEntries,
    sendTerminalInput,
    clearTerminal,
  } = useChat(currentThreadId);

  const hasActiveTasks = Object.values(taskPlans).some((plan) => plan.length > 0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // App views & parameters
  const [activeView, setActiveView] = useState<ViewType>('chat');
  const [currentDir, setCurrentDir] = useState<string>('~/Gemini-Interpreter'); 
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  
  // Sidebar state
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isChatsExpanded, setIsChatsExpanded] = useState(true);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(true);
  
  // Message queue state
  const [messageQueue, setMessageQueue] = useState<string[]>([]);
  
  // Threads list state (lifted from ThreadList.tsx)
  const [threads, setThreads] = useState<any[]>([]);

  // Derived: título del hilo activo para mostrar en el encabezado
  const activeThread = threads.find(t => t.id === currentThreadId);
  const activeTitle = activeThread?.title || 'Nueva conversación';

  // Live Clock & Greeting State (Goose UI)
  const [currentTime, setCurrentTime] = useState<string>('');
  const [greeting, setGreeting] = useState<string>('Buenas tardes');

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true });
      setCurrentTime(timeStr);

      const hour = now.getHours();
      if (hour < 12) {
        setGreeting('Buenos días');
      } else if (hour < 20) {
        setGreeting('Buenas tardes');
      } else {
        setGreeting('Buenas noches');
      }
    };

    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Fetch threads & working dir on load
  const fetchThreads = async (selectFirst = false) => {
    try {
      const res = await fetch('http://127.0.0.1:8765/api/threads');
      const data = await res.json();
      const list = data.threads || [];
      setThreads(list);
      if (selectFirst && list.length > 0) {
        setCurrentThreadId(list[0].id);
      }
    } catch (error) {
      console.error("Error fetching threads:", error);
    }
  };

  useEffect(() => {
    fetchThreads(true);
    const handleThreadUpdate = () => fetchThreads(false);
    window.addEventListener('thread_update', handleThreadUpdate);
    return () => window.removeEventListener('thread_update', handleThreadUpdate);
  }, []);

  useEffect(() => {
    const initWorkspace = async () => {
      let path = '.';
      try {
        const { invoke } = await import('@tauri-apps/api/core');
        path = await invoke<string>('get_cwd');
        console.log("CWD desde Tauri obtenido en App:", path);
      } catch (err) {
        console.warn("No se pudo obtener el CWD de Tauri, usando por defecto:", err);
      }

      // Fetch initial working directory from backend using resolved path
      fetch('http://127.0.0.1:8765/api/files/list', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      })
        .then(res => res.json())
        .then(data => {
          if (data.currentPath) {
            setCurrentDir(data.currentPath);
          }
        })
        .catch(err => console.error("Failed to fetch initial CWD:", err));
    };

    initWorkspace();
  }, []);

  // Handlers for Thread management
  const createThread = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8765/api/threads', { method: 'POST' });
      const data = await res.json();
      if (data.thread_id) {
        await fetchThreads();
        setCurrentThreadId(data.thread_id);
        setActiveView('chat');
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
      if (currentThreadId === id) {
        const remaining = threads.find(t => t.id !== id);
        setCurrentThreadId(remaining?.id || `desktop-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`);
      }
    } catch (error) {
      console.error("Error deleting thread:", error);
    }
  };

  const handleChangeDir = () => {
    const newDir = window.prompt("Introduce la ruta del directorio de trabajo:", currentDir);
    if (newDir && newDir !== currentDir) {
      setCurrentDir(newDir);
      sendMessage(`cd ${newDir}`);
    }
  };

  // Queue logic: if generating, buffer the messages
  const handleSendMessage = (text: string) => {
    if (isGenerating) {
      setMessageQueue(prev => [...prev, text]);
    } else {
      sendMessage(text);
    }
  };

  const handleProcessNextQueueItem = () => {
    if (messageQueue.length > 0) {
      const nextMessage = messageQueue[0];
      sendMessage(nextMessage);
      setMessageQueue(prev => prev.slice(1));
    }
  };

  const handleRemoveFromQueue = (index: number) => {
    setMessageQueue(prev => prev.filter((_, i) => i !== index));
  };


  return (
    <div className="flex h-screen bg-[#fafafa] text-slate-800 font-sans overflow-hidden selection:bg-indigo-100">
      
      {/* Redesigned Minimalist Sidebar */}
      {/* Redesigned Minimalist Sidebar */}
      <aside 
        className={`${
          isSidebarCollapsed ? 'w-[56px]' : 'w-[230px]'
        } bg-[#f7f8fa] border-r border-slate-200/60 flex flex-col transition-all duration-200 z-30 select-none`}
      >
        {/* Sidebar Header with Brand */}
        <div className="h-12 flex items-center justify-between px-3.5 border-b border-slate-200/50">
          {!isSidebarCollapsed && (
            <div className="flex items-center gap-2">
              <div className="h-5 w-5 rounded-md bg-slate-900 flex items-center justify-center">
                <Sparkles size={11} className="text-white" />
              </div>
              <span className="font-semibold text-[13px] text-slate-800 tracking-tight">KogniTerm</span>
              <span className="px-1.5 py-0.2 rounded bg-slate-200/50 text-[9px] text-slate-500 font-medium">Desktop</span>
            </div>
          )}
          <button 
            onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            className="p-1 hover:bg-slate-200/50 rounded-md text-slate-400 hover:text-slate-700 transition-colors ml-auto"
            title={isSidebarCollapsed ? "Expandir barra lateral" : "Colapsar barra lateral"}
          >
            <PanelLeft size={15} />
          </button>
        </div>

        {/* Navigation / Actions */}
        <div className="px-2.5 py-2 flex flex-col gap-1">
          {/* New Chat Item */}
          <div 
            onClick={createThread}
            className={`flex items-center gap-2.5 px-2 py-1.5 text-[13px] font-medium text-slate-700 hover:text-slate-900 cursor-pointer rounded-md hover:bg-slate-200/40 transition-colors ${isSidebarCollapsed ? 'justify-center px-0' : ''}`}
            title="Nuevo chat"
          >
            <Plus size={15} className="text-slate-500 shrink-0" />
            {!isSidebarCollapsed && <span>Nuevo chat</span>}
          </div>

          {/* Nav Items List */}
          <nav className="flex flex-col gap-0.5 mt-1">
            {[
              { id: 'skills', icon: Zap, label: 'Skills' },
              { id: 'heartbeat', icon: HeartPulse, label: 'Heartbeat' },
              { id: 'session', icon: History, label: 'Historial de sesiones' },
              { id: 'files', icon: Files, label: 'Archivos' }
            ].map((item) => {
              const isActive = activeView === item.id;
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    if (item.id === 'files') {
                      setActiveView('files');
                    } else if (item.id === 'skills') {
                      setActiveView('skills');
                    } else if (item.id === 'heartbeat') {
                      setActiveView('heartbeat');
                    } else if (item.id === 'session') {
                      setActiveView('session');
                    } else {
                      setActiveView('chat');
                    }
                  }}
                  className={`flex items-center gap-2.5 px-2 py-1.5 rounded-md text-[13px] cursor-pointer transition-colors ${
                    isActive
                      ? 'text-slate-900 font-semibold bg-slate-200/60'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/40'
                  } ${isSidebarCollapsed ? 'justify-center px-0' : ''}`}
                >
                  <item.icon size={15} className={`shrink-0 ${isActive ? 'text-indigo-600' : 'text-slate-400'}`} />
                  {!isSidebarCollapsed && <span>{item.label}</span>}
                </div>
              );
            })}
          </nav>
        </div>

        {/* Collapsible CHATS Section */}
        {!isSidebarCollapsed && (
          <div className="flex-1 flex flex-col min-h-0 border-t border-slate-200/40 mt-1 pt-2">
            <div 
              onClick={() => setIsChatsExpanded(!isChatsExpanded)}
              className="flex items-center justify-between px-4 py-1 text-[10px] font-semibold text-slate-400 hover:text-slate-600 uppercase tracking-wider transition-colors cursor-pointer"
            >
              <div className="flex items-center gap-1">
                <span className="text-[8px] text-slate-400">▾</span>
                <span>CHATS</span>
              </div>
              <span className="text-[10px] text-slate-400 font-mono">
                {threads.length}
              </span>
            </div>

            {isChatsExpanded && (
              <div className="flex-1 overflow-y-auto goose-scrollbar px-2 py-1 space-y-0.5">
                {threads.map(thread => {
                  const isCurrent = currentThreadId === thread.id;
                  return (
                    <div 
                      key={thread.id}
                      onClick={() => {
                        setCurrentThreadId(thread.id);
                        setActiveView('chat');
                      }}
                      className={`group flex items-center justify-between px-2 py-1.5 rounded-md cursor-pointer text-xs transition-colors ${
                        isCurrent 
                          ? 'text-slate-900 font-semibold bg-slate-200/60' 
                          : 'text-slate-600 hover:bg-slate-200/40 hover:text-slate-900'
                      }`}
                    >
                      <div className="flex items-center space-x-2 truncate flex-1 min-w-0 pr-1">
                        <span className="text-[12px] truncate" title={thread.title}>
                          {thread.title || 'Conversación'}
                        </span>
                      </div>
                      <button 
                        onClick={(e) => deleteThread(e, thread.id)}
                        className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-400 hover:text-rose-600 transition-all rounded hover:bg-slate-200/60"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  );
                })}
                {threads.length === 0 && (
                  <div className="px-2 py-1.5 text-[11px] text-slate-400 italic">
                    Sin hilos guardados.
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Sidebar Footer with Settings */}
        <div className="px-2.5 py-2 border-t border-slate-200/40 mt-auto">
          <div
            onClick={() => setIsSettingsOpen(true)}
            className={`flex items-center gap-2.5 px-2 py-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-200/40 rounded-md text-[13px] cursor-pointer transition-colors ${isSidebarCollapsed ? 'justify-center px-0' : ''}`}
          >
            <Settings size={15} className="text-slate-400 shrink-0" />
            {!isSidebarCollapsed && <span>Ajustes</span>}
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 relative bg-[#fafafa]">
        
        {/* Minimal Header */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-slate-200/60 bg-white/70 backdrop-blur-md z-20">
          <div className="flex items-center gap-3 select-none">
            {isSidebarCollapsed && (
              <div className="flex items-center gap-2">
                <span className="font-bold text-xs text-slate-800 tracking-tight">KogniTerm</span>
              </div>
            )}
            {!isSidebarCollapsed && (
              <span className="text-xs font-medium text-slate-500 truncate max-w-[180px]" title={activeTitle}>
                {activeTitle}
              </span>
            )}
          </div>

          {/* Central Directory Pill */}
          <button
            onClick={handleChangeDir}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-100/80 hover:bg-slate-200/80 border border-slate-200/60 transition-all text-xs font-medium text-slate-600 hover:text-slate-900 select-none"
            title="Cambiar directorio de trabajo"
          >
            <span>Ubicación actual</span>
            <span className="text-slate-400 font-mono text-[11px]">({currentDir})</span>
          </button>

          {/* Right Status Indicator */}
          <div className="flex items-center gap-3 select-none">
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200/60 text-[10px] font-bold uppercase tracking-wider text-emerald-700">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>kogniterm</span>
            </div>
          </div>
        </header>

        {/* Content Area */}
        {activeView === 'chat' && (
          <div className="flex flex-1 overflow-hidden relative">
            <div className="flex-1 flex flex-col relative min-w-0">
              
              <section className="flex-1 overflow-y-auto goose-scrollbar px-4 lg:px-0 scroll-smooth pb-32">
                <div className="max-w-3xl mx-auto py-8">
                  {messages.length === 0 ? (
                    <div className="h-[75vh] flex flex-col items-center justify-center text-center px-4 animate-fade-in">
                      {/* Ultra-Light Large Digital Clock */}
                      <div className="flex items-baseline mb-2">
                        <span className="text-7xl font-extralight tracking-tight text-slate-800 font-sans">
                          {currentTime.replace(/ AM| PM/i, '') || '4:51'}
                        </span>
                        <span className="text-xl font-normal text-slate-400 ml-2.5 uppercase tracking-wide">
                          {currentTime.includes('AM') ? 'AM' : 'PM'}
                        </span>
                      </div>
                      
                      {/* Dynamic Greeting */}
                      <p className="text-lg font-normal text-slate-500 mb-8 tracking-normal">
                        {greeting}, ¿en qué te puedo ayudar hoy?
                      </p>

                      {/* Centered Floating ChatInput Capsule */}
                      <ChatInput 
                        onSendMessage={handleSendMessage} 
                        isGenerating={isGenerating} 
                        onStopGeneration={stopGeneration}
                        currentDir={currentDir}
                        onChangeDir={handleChangeDir}
                        messageQueue={messageQueue}
                        onRemoveFromQueue={handleRemoveFromQueue}
                        onProcessNext={handleProcessNextQueueItem}
                        isFloating={true}
                      />

                      {/* Quick Suggestion Action Cards */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-8 w-full max-w-xl">
                        {[
                          { title: "Analizar código", desc: "Explora la estructura y componentes del proyecto.", prompt: "Analiza la estructura de este código" },
                          { title: "Guía de despliegue", desc: "Instrucciones de compilación y deployment.", prompt: "Genera una guía de deployment" }
                        ].map((card, i) => (
                          <button
                            key={i}
                            onClick={() => handleSendMessage(card.prompt)}
                            className="group p-3.5 rounded-2xl bg-white border border-slate-200/80 hover:border-slate-300 hover:shadow-card-light text-left transition-all hover:-translate-y-0.5"
                          >
                            <div className="flex justify-between items-start mb-1">
                              <p className="text-xs font-semibold text-slate-700 group-hover:text-indigo-600 transition-colors">{card.title}</p>
                              <span className="opacity-0 group-hover:opacity-100 transition-opacity text-indigo-600 text-xs">→</span>
                            </div>
                            <p className="text-[11px] text-slate-400 leading-normal">{card.desc}</p>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {messages.map((msg) => (
                        <ChatMessage key={msg.id} message={msg} />
                      ))}
                    </div>
                  )}

                  {error && (
                    <div className="bg-red-50 border border-red-200 text-red-600 p-4 rounded-2xl mb-6 mx-4 text-xs flex items-center gap-2 shadow-xs">
                      <ShieldCheck size={14} />
                      {error}
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              </section>

              {/* Bottom Fixed ChatInput when messages exist */}
              {messages.length > 0 && (
                <ChatInput 
                  onSendMessage={handleSendMessage} 
                  isGenerating={isGenerating} 
                  onStopGeneration={stopGeneration}
                  currentDir={currentDir}
                  onChangeDir={handleChangeDir}
                  messageQueue={messageQueue}
                  onRemoveFromQueue={handleRemoveFromQueue}
                  onProcessNext={handleProcessNextQueueItem}
                  isFloating={false}
                />
              )}
            </div>

            {/* Right Sidebar: Tareas | Terminal | Aprobación */}
            {isRightSidebarOpen && (
                <RightSidebar
                    taskPlans={taskPlans}
                    hasActiveTasks={hasActiveTasks}
                    pendingApproval={pendingApproval}
                    onApprove={(id) => respondApproval(id, true)}
                    onReject={(id) => respondApproval(id, false)}
                    terminalEntries={terminalEntries}
                    onTerminalInput={sendTerminalInput}
                    onClearTerminal={clearTerminal}
                    isOpen={isRightSidebarOpen}
                    onToggle={() => setIsRightSidebarOpen((prev) => !prev)}
                />
            )}
            {!isRightSidebarOpen && (
                <button
                    onClick={() => setIsRightSidebarOpen(true)}
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border-l border-zinc-800 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
                    title="Mostrar panel lateral"
                >
                    <PanelRightOpen size={16} />
                </button>
            )}
          </div>
          )}

          {activeView === 'files' && (
            <div className="flex-1 overflow-hidden">
              <FileExplorer workspacePath={currentDir} />
            </div>
          )}

          {activeView === 'skills' && (
            <div className="flex-1 overflow-hidden">
              <SkillsPanel />
            </div>
          )}

          {activeView === 'heartbeat' && (
            <div className="flex-1 overflow-y-auto bg-[#fafafa] text-slate-800">
              <HeartbeatsPanel />
            </div>
          )}

          {activeView === 'session' && (
            <div className="flex-1 overflow-hidden">
              <SessionHistoryPanel
                threads={threads}
                currentThreadId={currentThreadId}
                onSelectThread={(id) => {
                  setCurrentThreadId(id);
                  setActiveView('chat');
                }}
                onDeleteThread={deleteThread}
                onNewSession={createThread}
              />
            </div>
          )}
        </main>

        {/* Settings Modal */}
        <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
      </div>
  );
}

export default App;
