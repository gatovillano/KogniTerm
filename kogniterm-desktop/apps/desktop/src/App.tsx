import { useRef, useEffect, useState } from 'react';
import { ChatMessage } from './components/chat/ChatMessage';
import { ThinkingSpinner } from './components/chat/ThinkingSpinner';
import { CommandApproval } from './components/chat/CommandApproval';
import { FileExplorer } from './components/files/FileExplorer';
import { SkillsPanel } from './components/skills/SkillsPanel';
import { HeartbeatsPanel } from './components/heartbeats/HeartbeatsPanel';
import { SessionHistoryPanel } from './components/session/SessionHistoryPanel';
import { QuestionModal } from './components/modals/QuestionModal';
import { ChatInput } from './components/chat/ChatInput';
import { SettingsModal } from './components/settings/SettingsModal';
import { RightSidebar } from './components/chat/RightSidebar';
import { ProjectsSidebar } from './components/sidebar/ProjectsSidebar';
import { AddProjectModal } from './components/modals/AddProjectModal';
import { useProjects } from './hooks/useProjects';
import { useChat } from './hooks/useChat';
import { API_BASE_URL, isTauriApp } from './config/api';
import { 
  ShieldCheck, Zap, PanelRightOpen, Folder
} from 'lucide-react';
import './App.css';

type ViewType = 'chat' | 'files' | 'skills' | 'heartbeat' | 'session';

function App() {
  const [currentThreadId, setCurrentThreadId] = useState<string>(() => {
    return `desktop-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  });

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
  
  // Threads list state
  const [threads, setThreads] = useState<any[]>([]);

  // Derived: título e workspace del hilo activo
  const activeThread = threads.find(t => t.id === currentThreadId);
  const activeTitle = activeThread?.title || 'Nueva conversación';
  const activeWorkspace = activeThread?.workspaceDir || activeThread?.workspace_dir || currentDir;

  const {
    messages,
    isGenerating,
    error,
    sendMessage,
    stopGeneration,
    taskPlans,
    pendingApproval,
    respondApproval,
    pendingQuestion,
    respondQuestion,
    terminalEntries,
    sendTerminalInput,
    clearTerminal,
    appliedDiffs,
    scrollPosition,
    isUserNearBottom,
    setThreadScrollPosition,
    messageQueue,
    removeFromQueue,
    clearQueue,
    processNextQueueItem,
  } = useChat(currentThreadId, activeWorkspace);

  const hasActiveTasks = Object.values(taskPlans).some((plan) => plan.length > 0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLElement>(null);

  const [autoApprove, setAutoApprove] = useState<boolean>(false);

  useEffect(() => {
    document.title = isTauriApp() ? 'KogniTerm Desktop' : 'KogniTerm Web';
  }, []);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/config/all`)
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
      await fetch(`${API_BASE_URL}/api/config/set`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'auto_approve', value: nextVal, scope: 'project' }),
      });
    } catch (err) {
      console.error('Error toggling auto_approve:', err);
    }
  };

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
      const projectPaths = projects.map(p => p.path).filter(Boolean).join(',');
      const url = projectPaths 
        ? `${API_BASE_URL}/api/threads?workspace_dirs=${encodeURIComponent(projectPaths)}`
        : `${API_BASE_URL}/api/threads`;
      const res = await fetch(url);
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
    if (projects.length > 0) {
      fetchThreads(false);
    }
  }, [projects]);

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
      fetch(`${API_BASE_URL}/api/files/list`, {
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
      const res = await fetch(`${API_BASE_URL}/api/threads`, { 
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
      await fetch(`${API_BASE_URL}/api/threads/${id}`, { method: 'DELETE' });
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


  return (
    <div className="flex h-screen bg-[#fafafa] dark:bg-[#09090b] text-slate-800 dark:text-zinc-100 font-sans overflow-hidden selection:bg-indigo-100 dark:selection:bg-indigo-900">
      
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
      <main className="flex-1 flex flex-col min-w-0 relative bg-topo-pattern">
        
        {/* Content Area */}
        {activeView === 'chat' && (
          <div className="flex flex-1 overflow-hidden relative">
            <div className="flex-1 flex flex-col relative min-w-0">

              {/* Top-Right Floating Micro-HUD (Cursor / Zed style) */}
              <div className="absolute top-3 right-4 z-30 flex items-center gap-1.5 opacity-40 hover:opacity-100 transition-opacity duration-150 bg-white/60 dark:bg-zinc-900/60 backdrop-blur-md px-2 py-1 rounded-lg border border-slate-200/50 dark:border-zinc-800/60 select-none shadow-xs">
                {/* Workspace Directory Switcher */}
                <button
                  onClick={handleChangeDir}
                  className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 hover:bg-slate-200/50 dark:hover:bg-zinc-800/60 transition-colors cursor-pointer"
                  title={`Directorio actual: ${currentDir}. Clic para cambiar.`}
                >
                  <Folder size={12} className="text-slate-400 dark:text-zinc-500" />
                  <span className="max-w-[150px] truncate">{currentDir.split('/').pop() || currentDir}</span>
                </button>

                <div className="w-[1px] h-3 bg-slate-200 dark:bg-zinc-800" />

                {/* Auto-Approve Quick Toggle */}
                <button
                  type="button"
                  onClick={toggleAutoApprove}
                  title={autoApprove ? "Auto-aprobación activa (Clic para desactivar)" : "Auto-aprobación inactiva (Clic para activar)"}
                  className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium transition-colors cursor-pointer ${
                    autoApprove
                      ? 'text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10'
                      : 'text-slate-500 dark:text-zinc-500 hover:text-slate-800 dark:hover:text-zinc-200 hover:bg-slate-200/50 dark:hover:bg-zinc-800/60'
                  }`}
                >
                  {autoApprove ? <Zap size={12} className="fill-emerald-500/20" /> : <ShieldCheck size={12} />}
                  <span>{autoApprove ? "Auto ON" : "Manual"}</span>
                </button>

                <div className="w-[1px] h-3 bg-slate-200 dark:bg-zinc-800" />

                {/* Right Panel Toggle */}
                <button
                  type="button"
                  onClick={() => setIsRightSidebarOpen(prev => !prev)}
                  title={isRightSidebarOpen ? "Ocultar panel lateral (Terminal/Tareas)" : "Mostrar panel lateral (Terminal/Tareas)"}
                  className={`p-1 rounded text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 hover:bg-slate-200/50 dark:hover:bg-zinc-800/60 transition-colors cursor-pointer ${
                    isRightSidebarOpen ? 'text-slate-800 dark:text-zinc-200' : ''
                  }`}
                >
                  <PanelRightOpen size={13} />
                </button>
              </div>
              
              <section 
                ref={chatContainerRef}
                onScroll={handleChatScroll}
                className="flex-1 overflow-y-auto goose-scrollbar scroll-smooth pb-32"
              >
                <div className="max-w-3xl mx-auto pt-14 pb-8 px-6 sm:px-8 md:px-10">
                  {messages.length === 0 ? (
                    <div className="h-[75vh] flex flex-col items-center justify-center text-center px-4 animate-fade-in">
                      <div className="w-full max-w-2xl flex flex-col items-center">
                        <ChatInput 
                          onSendMessage={sendMessage} 
                          isGenerating={isGenerating} 
                          onStopGeneration={stopGeneration}
                          currentDir={currentDir}
                          onChangeDir={handleChangeDir}
                          messageQueue={messageQueue}
                          onRemoveFromQueue={removeFromQueue}
                          onClearQueue={clearQueue}
                          onProcessNext={processNextQueueItem}
                          isFloating={true}
                        />
                        <div className="mt-4 flex items-center gap-3 text-[11px] text-slate-400 dark:text-zinc-600 font-mono select-none">
                          <span>↵ enviar</span>
                          <span>·</span>
                          <span>⇧↵ nueva línea</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {messages.map((msg) => (
                        <ChatMessage key={msg.id} message={msg} />
                      ))}

                      {/* Inline Pending Command Approval matching OpenClaw screenshot */}
                      {pendingApproval && (
                        <CommandApproval
                          request={pendingApproval}
                          onApprove={(id) => respondApproval(id, true)}
                          onReject={(id) => respondApproval(id, false)}
                          isInline={true}
                        />
                      )}

                      {isGenerating && (messages.length === 0 || messages[messages.length - 1]?.role === 'user' || (messages[messages.length - 1]?.role === 'assistant' && !messages[messages.length - 1]?.content && !messages[messages.length - 1]?.reasoning && (!messages[messages.length - 1]?.tool_calls || messages[messages.length - 1]?.tool_calls?.length === 0))) && (
                        <ThinkingSpinner text="Thinking" />
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
                <div className="relative">
                  <ChatInput 
                    onSendMessage={sendMessage} 
                    isGenerating={isGenerating} 
                    onStopGeneration={stopGeneration}
                    currentDir={currentDir}
                    onChangeDir={handleChangeDir}
                    messageQueue={messageQueue}
                    onRemoveFromQueue={removeFromQueue}
                    onClearQueue={clearQueue}
                    onProcessNext={processNextQueueItem}
                    isFloating={false}
                  />

                  {/* Bottom Footer Status Bar */}
                  <div className="flex items-center justify-between px-6 sm:px-8 md:px-10 py-1.5 text-[11px] text-zinc-400 dark:text-zinc-500 font-mono border-t border-slate-200/40 dark:border-zinc-800/40 bg-transparent select-none">
                    <div className="flex items-center gap-3">
                      <span className="truncate max-w-[280px]">{activeTitle}</span>
                    </div>
                    <div className="flex items-center gap-3 text-[10px]">
                      <span>KogniTerm Engine</span>
                    </div>
                  </div>
                </div>
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

        {/* Question Modal */}
        <QuestionModal request={pendingQuestion} onRespond={respondQuestion} />

        {/* Settings Modal */}
        <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
      </div>
  );
}

export default App;
