import { useRef, useEffect, useState } from 'react';
import { ChatMessage } from './components/chat/ChatMessage';
import { ChatInput } from './components/chat/ChatInput';
import { FileExplorer } from './components/files/FileExplorer';
import { SkillsPanel } from './components/skills/SkillsPanel';
import { SettingsModal } from './components/settings/SettingsModal';
import { TaskTracker } from './components/chat/TaskTracker';
import { TerminalPanel } from './components/chat/TerminalPanel';
import { CommandApproval } from './components/chat/CommandApproval';
import { useChat } from './hooks/useChat';
import { 
  Settings, Files, ShieldCheck, 
  Zap, History, PanelLeft, 
  Trash2, Plus, FileText, HeartPulse
} from 'lucide-react';
import './App.css';

type ViewType = 'chat' | 'files' | 'skills';

function App() {
  const [currentThreadId, setCurrentThreadId] = useState<string>(() => {
    return `desktop-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  });
  
  const {
    messages,
    isGenerating,
    error,
    sendMessage,
    taskPlans,
    pendingApproval,
    respondApproval,
    terminalEntries,
    isTerminalVisible,
    sendTerminalInput,
    closeTerminal,
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
  
  // Message queue state
  const [messageQueue, setMessageQueue] = useState<string[]>([]);
  
  // Threads list state (lifted from ThreadList.tsx)
  const [threads, setThreads] = useState<any[]>([]);

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
    <div className="flex flex-col h-screen bg-white text-zinc-800 font-sans overflow-hidden selection:bg-zinc-200">
      
      {/* Goose Top Window Menu Bar */}
      <div className="h-8 bg-[#f3f4f6] border-b border-[#e5e7eb] flex items-center justify-between px-3 text-xs text-zinc-600 select-none z-40">
        <div className="flex items-center gap-4">
          <span className="hover:text-zinc-900 cursor-pointer">File</span>
          <span className="hover:text-zinc-900 cursor-pointer">Edit</span>
          <span className="hover:text-zinc-900 cursor-pointer">View</span>
          <span className="hover:text-zinc-900 cursor-pointer">Window</span>
          <span className="hover:text-zinc-900 cursor-pointer">Help</span>
        </div>

        {/* Center Title */}
        <div className="font-semibold text-zinc-700 text-xs tracking-wide">
          Goose
        </div>

        {/* Window Control Buttons */}
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-orange-400"></div>
          <div className="w-3 h-3 rounded-full bg-red-500"></div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        
        {/* Redesigned Sidebar (Goose exact style) */}
        <aside 
          className={`${
            isSidebarCollapsed ? 'w-[60px]' : 'w-[240px]'
          } bg-[#f3f4f6] border-r border-[#e5e7eb] flex flex-col transition-all duration-200 z-30 select-none`}
        >
          {/* Top panel toggle icon */}
          <div className="h-10 flex items-center px-3 pt-2">
            <button 
              onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
              className="p-1 hover:bg-zinc-200 rounded text-zinc-600 hover:text-zinc-900 transition-colors"
              title={isSidebarCollapsed ? "Expandir barra lateral" : "Colapsar barra lateral"}
            >
              <PanelLeft size={16} />
            </button>
          </div>

          {/* Navigation / Actions */}
          <div className="p-3 flex flex-col gap-1.5">
            {/* New Chat Button (Pill matching Goose) */}
            <button 
              onClick={createThread}
              className={`flex items-center gap-2.5 px-3 py-2 bg-zinc-200/80 hover:bg-zinc-200 text-zinc-800 border border-zinc-300/60 rounded-xl text-xs font-medium transition-all duration-200 ${isSidebarCollapsed ? 'justify-center' : ''}`}
            >
              <div className="w-4 h-4 rounded-md border border-zinc-400 flex items-center justify-center">
                <Plus size={12} className="text-zinc-700" />
              </div>
              {!isSidebarCollapsed && <span>Nuevo chat</span>}
            </button>

            {/* Nav Items List */}
            <nav className="flex flex-col gap-0.5 mt-2">
              {[
                { id: 'recipes', icon: FileText, label: 'Recetas' },
                { id: 'skills', icon: Zap, label: 'Skills' },
                { id: 'heartbeat', icon: HeartPulse, label: 'Heartbeat' },
                { id: 'session', icon: History, label: 'Historial de sesiones' },
                { id: 'files', icon: Files, label: 'Archivos' }
              ].map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    if (item.id === 'files') {
                      setActiveView('files');
                    } else if (item.id === 'skills') {
                      setActiveView('skills');
                    } else {
                      setActiveView('chat');
                    }
                  }}
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs transition-all duration-150 ${
                    activeView === item.id
                      ? 'bg-zinc-200 text-zinc-900 font-medium'
                      : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-200/50'
                  }`}
                >
                  <item.icon size={15} className="shrink-0 text-zinc-500 group-hover:text-zinc-700" />
                  {!isSidebarCollapsed && <span>{item.label}</span>}
                </button>
              ))}
            </nav>
          </div>

          {/* Collapsible CHATS Section */}
          {!isSidebarCollapsed && (
            <div className="flex-1 flex flex-col min-h-0 border-t border-[#e5e7eb] mt-2 pt-1">
              <button 
                onClick={() => setIsChatsExpanded(!isChatsExpanded)}
                className="flex items-center gap-1.5 px-3 py-2 text-[10px] font-bold text-zinc-400 hover:text-zinc-600 uppercase tracking-wider transition-colors text-left"
              >
                <span className="text-[10px]">v</span>
                <span>CHATS</span>
              </button>

              {isChatsExpanded && (
                <div className="flex-1 overflow-y-auto goose-scrollbar px-2 pb-2 space-y-0.5">
                  {threads.map(thread => {
                    const isCurrent = currentThreadId === thread.id;
                    return (
                      <div 
                        key={thread.id}
                        onClick={() => {
                          setCurrentThreadId(thread.id);
                          setActiveView('chat');
                        }}
                        className={`group flex items-center justify-between px-2.5 py-1.5 rounded-lg cursor-pointer transition-all duration-200 ${
                          isCurrent 
                            ? 'bg-zinc-200/80 text-zinc-900 font-medium' 
                            : 'text-zinc-600 hover:bg-zinc-200/40 hover:text-zinc-900'
                        }`}
                      >
                        <span className="text-xs truncate flex-1 pr-2" title={thread.title}>
                          {thread.title || 'New Chat'}
                        </span>
                        <button 
                          onClick={(e) => deleteThread(e, thread.id)}
                          className="opacity-0 group-hover:opacity-100 p-0.5 text-zinc-400 hover:text-red-500 transition-all rounded hover:bg-red-100"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    );
                  })}
                  {threads.length === 0 && (
                    <div className="px-3 py-2 text-[11px] text-zinc-400 italic">
                      Sin hilos guardados.
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Sidebar Footer with Settings */}
          <div className="p-3 border-t border-[#e5e7eb] mt-auto">
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="w-full flex items-center gap-3 px-3 py-2 text-zinc-600 hover:text-zinc-900 hover:bg-zinc-200/60 rounded-lg text-xs transition-colors"
            >
              <Settings size={15} />
              {!isSidebarCollapsed && <span>Ajustes</span>}
            </button>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col min-w-0 relative bg-white">
          
          {/* Content Area */}
          {activeView === 'chat' && (
            <div className="flex flex-1 overflow-hidden relative">
              <div className="flex-1 flex flex-col relative min-w-0">
                
                <section className={`flex-1 overflow-y-auto goose-scrollbar px-4 lg:px-0 scroll-smooth ${isTerminalVisible ? 'pb-16' : 'pb-32'}`}>
                  <div className="max-w-3xl mx-auto py-8">
                    {messages.length === 0 ? (
                      <div className="h-[75vh] flex flex-col items-center justify-center text-center px-4 animate-fade-in">
                        {/* Clock display matching Goose */}
                        <div className="flex items-baseline mb-1">
                          <span className="text-6xl font-light tracking-tight text-zinc-800 font-sans">
                            {currentTime.replace(/ AM| PM/i, '') || '4:51'}
                          </span>
                          <span className="text-2xl font-normal text-zinc-400 ml-2 uppercase">
                            {currentTime.includes('AM') ? 'AM' : 'PM'}
                          </span>
                        </div>
                        <p className="text-xl font-normal text-zinc-500 mb-8">
                          {greeting}
                        </p>

                        {/* Floating Center ChatInput Capsule */}
                        <ChatInput 
                          onSendMessage={handleSendMessage} 
                          isGenerating={isGenerating} 
                          currentDir={currentDir}
                          onChangeDir={handleChangeDir}
                          messageQueue={messageQueue}
                          onRemoveFromQueue={handleRemoveFromQueue}
                          onProcessNext={handleProcessNextQueueItem}
                          isFloating={true}
                        />
                      </div>
                    ) : (
                      <div className="space-y-6">
                        {messages.map((msg) => (
                          <ChatMessage key={msg.id} message={msg} />
                        ))}
                      </div>
                    )}

                    {error && (
                      <div className="bg-red-50 border border-red-200 text-red-600 p-4 rounded-xl mb-6 mx-4 text-xs flex items-center gap-2">
                        <ShieldCheck size={14} />
                        {error}
                      </div>
                    )}

                    <div ref={messagesEndRef} />
                  </div>
                </section>

                {/* Terminal Panel — docked at bottom when visible */}
                <TerminalPanel
                  entries={terminalEntries}
                  isVisible={isTerminalVisible}
                  onClose={closeTerminal}
                  onTerminalInput={sendTerminalInput}
                />

                {/* Bottom Fixed ChatInput when messages exist */}
                {messages.length > 0 && (
                  <ChatInput 
                    onSendMessage={handleSendMessage} 
                    isGenerating={isGenerating} 
                    currentDir={currentDir}
                    onChangeDir={handleChangeDir}
                    messageQueue={messageQueue}
                    onRemoveFromQueue={handleRemoveFromQueue}
                    onProcessNext={handleProcessNextQueueItem}
                    isFloating={false}
                  />
                )}
              </div>

              {/* Task Tracker Panel */}
              {hasActiveTasks && (
                <TaskTracker taskPlans={taskPlans} />
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
        </main>
      </div>

      {/* Command Approval Modal */}
      {pendingApproval && (
        <CommandApproval
          request={pendingApproval}
          onApprove={(id) => respondApproval(id, true)}
          onReject={(id) => respondApproval(id, false)}
        />
      )}

      {/* Settings Modal */}
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </div>
  );
}

export default App;

