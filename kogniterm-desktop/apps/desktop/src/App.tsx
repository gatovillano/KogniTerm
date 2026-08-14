import { useRef, useEffect, useState } from 'react';
import { ChatMessage } from './components/chat/ChatMessage';
import { ChatInput } from './components/chat/ChatInput';
import { ThinkingSpinner } from './components/chat/ThinkingSpinner';
import { FileExplorer } from './components/files/FileExplorer';
import { SkillsPanel } from './components/skills/SkillsPanel';
import { SettingsModal } from './components/settings/SettingsModal';
import { HeartbeatsPanel } from './components/heartbeats/HeartbeatsPanel';
import { RightSidebar } from './components/chat/RightSidebar';
import { SessionHistoryPanel } from './components/session/SessionHistoryPanel';
import { ProjectsSidebar } from './components/sidebar/ProjectsSidebar';
import { AddProjectModal } from './components/modals/AddProjectModal';
import { useProjects } from './hooks/useProjects';
import { useChat } from './hooks/useChat';
import { 
  ShieldCheck, Zap, PanelRightOpen
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
    appliedDiffs,
    scrollPosition,
    isUserNearBottom,
    setThreadScrollPosition,
  } = useChat(currentThreadId);

  const hasActiveTasks = Object.values(taskPlans).some((plan) => plan.length > 0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLElement>(null);
  
  // App views & parameters
  const [activeView, setActiveView] = useState<ViewType>('chat');
  const [currentDir, setCurrentDir] = useState<string>('~/Gemini-Interpreter'); 
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isAddProjectModalOpen, setIsAddProjectModalOpen] = useState(false);

  // Projects hook for sidebar folder management
  const { projects, addProject, removeProject, toggleProjectExpand } = useProjects(currentDir);
  
  // Sidebar state
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
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
  const [autoApprove, setAutoApprove] = useState<boolean>(false);

  useEffect(() => {
    fetch('http://127.0.0.1:8765/api/config/all')
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data?.merged?.auto_approve !== undefined) {
          setAutoApprove(Boolean(data.merged.auto_approve));
        }
      })
      .catch(err => console.error("Error fetching config auto_approve:", err));
  }, [isSettingsOpen]);

  const toggleAutoApprove = async () => {
    const nextVal = !autoApprove;
    setAutoApprove(nextVal);
    try {
      await fetch('http://127.0.0.1:8765/api/config/set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'auto_approve', value: nextVal, scope: 'project' }),
      });
    } catch (err) {
      console.error('Error toggling auto_approve:', err);
    }
  };

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

  const handleChatScroll = () => {
    if (!chatContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    setThreadScrollPosition(scrollTop, isNearBottom);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Restore scroll position when thread or active view changes
  useEffect(() => {
    if (activeView === 'chat' && chatContainerRef.current) {
      chatContainerRef.current.scrollTop = scrollPosition;
    }
  }, [currentThreadId, activeView]);

  // Auto scroll only when user is near bottom
  useEffect(() => {
    if (isUserNearBottom) {
      scrollToBottom();
    }
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
  const createThread = async (workspaceDir?: string) => {
    try {
      const targetDir = workspaceDir || currentDir;
      const res = await fetch('http://127.0.0.1:8765/api/threads', { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_dir: targetDir })
      });
      const data = await res.json();
      if (data.thread_id) {
        await fetchThreads();
        setCurrentThreadId(data.thread_id);
        if (targetDir && targetDir !== currentDir) {
          setCurrentDir(targetDir);
        }
        setActiveView('chat');
      }
    } catch (error) {
      console.error("Error creating thread:", error);
    }
  };

  const handleSelectThread = (threadId: string, workspaceDir?: string) => {
    setCurrentThreadId(threadId);
    if (workspaceDir && workspaceDir !== currentDir) {
      setCurrentDir(workspaceDir);
    }
    setActiveView('chat');
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
  const handleSendMessage = (text: string, images?: string[]) => {
    if (isGenerating) {
      setMessageQueue(prev => [...prev, text]);
    } else {
      sendMessage(text, images);
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
      
      {/* Redesigned Projects Sidebar */}
      <ProjectsSidebar
        isSidebarCollapsed={isSidebarCollapsed}
        setIsSidebarCollapsed={setIsSidebarCollapsed}
        projects={projects}
        onOpenAddProjectModal={() => setIsAddProjectModalOpen(true)}
        onToggleProjectExpand={toggleProjectExpand}
        onDeleteProject={removeProject}
        threads={threads}
        currentThreadId={currentThreadId}
        onSelectThread={handleSelectThread}
        onCreateThread={createThread}
        onDeleteThread={deleteThread}
        activeView={activeView}
        setActiveView={setActiveView}
        onOpenSettings={() => setIsSettingsOpen(true)}
        executingThreadIds={{ [currentThreadId]: isGenerating }}
      />

      {/* Modal para añadir nueva carpeta/proyecto */}
      <AddProjectModal
        isOpen={isAddProjectModalOpen}
        onClose={() => setIsAddProjectModalOpen(false)}
        onAddProject={(path) => addProject(path)}
      />

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
          <div className="flex items-center gap-2 select-none">
            <button
              type="button"
              onClick={toggleAutoApprove}
              title={autoApprove ? "Auto-aprobación activa (Clic para desactivar)" : "Auto-aprobación inactiva (Clic para activar)"}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium transition-all cursor-pointer ${
                autoApprove 
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100' 
                  : 'bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200 hover:text-slate-800'
              }`}
            >
              {autoApprove ? <Zap size={13} className="text-emerald-600 fill-emerald-600/20" /> : <ShieldCheck size={13} />}
              <span>{autoApprove ? "Auto-aprobación ON" : "Auto-aprobación OFF"}</span>
            </button>
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
              
              <section 
                ref={chatContainerRef}
                onScroll={handleChatScroll}
                className="flex-1 overflow-y-auto goose-scrollbar px-4 lg:px-0 scroll-smooth pb-32"
              >
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
                      {isGenerating && (messages.length === 0 || messages[messages.length - 1]?.role === 'user' || (messages[messages.length - 1]?.role === 'assistant' && !messages[messages.length - 1]?.content && !messages[messages.length - 1]?.reasoning && (!messages[messages.length - 1]?.tool_calls || messages[messages.length - 1]?.tool_calls?.length === 0))) && (
                        <ThinkingSpinner />
                      )}
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

            {/* Right Sidebar: Tareas | Terminal | Aprobación | Diffs */}
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
                    appliedDiffs={appliedDiffs}
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
