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
  BookOpen, Zap, Grid, Clock, Puzzle, History, PanelLeft, 
  ChevronDown, Trash2, Plus, Sparkles
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
    isConnected,
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
    // Fetch initial working directory from backend
    fetch('http://127.0.0.1:8765/api/files/list', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: '.' })
    })
      .then(res => res.json())
      .then(data => {
        if (data.currentPath) {
          setCurrentDir(data.currentPath);
        }
      })
      .catch(err => console.error("Failed to fetch initial CWD:", err));
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
    <div className="flex h-screen bg-[#0e0e11] text-zinc-300 font-sans overflow-hidden selection:bg-indigo-500/20">
      
      {/* Redesigned Sidebar (Unified style matching Goose screenshot) */}
      <aside 
        className={`${
          isSidebarCollapsed ? 'w-[68px]' : 'w-[260px]'
        } bg-[#151518] border-r border-[#27272a]/40 flex flex-col transition-all duration-300 z-30 select-none`}
      >
        {/* Sidebar Header */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-[#27272a]/20">
          {!isSidebarCollapsed && (
            <div className="flex items-center gap-2.5">
              <div className="h-6 w-6 rounded-md bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
                <Sparkles size={13} className="text-white" />
              </div>
              <span className="font-bold text-sm text-white tracking-wide">KogniTerm</span>
            </div>
          )}
          <button 
            onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            className="p-1.5 hover:bg-zinc-800/60 rounded-lg text-zinc-500 hover:text-zinc-300 transition-colors ml-auto"
            title={isSidebarCollapsed ? "Expandir barra lateral" : "Colapsar barra lateral"}
          >
            <PanelLeft size={16} />
          </button>
        </div>

        {/* Navigation / Actions */}
        <div className="p-3 flex flex-col gap-1.5">
          {/* New Chat Button */}
          <button 
            onClick={createThread}
            className={`flex items-center gap-3 px-3 py-2 bg-indigo-600/10 hover:bg-indigo-600 text-indigo-400 hover:text-white border border-indigo-500/20 rounded-lg text-xs font-semibold transition-all duration-200 justify-center`}
          >
            <Plus size={14} className="shrink-0" />
            {!isSidebarCollapsed && <span>New Chat</span>}
          </button>

          {/* Nav Items List */}
          <nav className="flex flex-col gap-0.5 mt-2">
            {[
              { id: 'recipes', icon: BookOpen, label: 'Recipes' },
              { id: 'skills', icon: Zap, label: 'Skills' },
              { id: 'apps', icon: Grid, label: 'Apps' },
              { id: 'scheduler', icon: Clock, label: 'Scheduler' },
              { id: 'extensions', icon: Puzzle, label: 'Extensions' },
              { id: 'session', icon: History, label: 'Session History' },
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
                className={`flex items-center gap-3.5 px-3 py-2.5 rounded-lg text-xs transition-all duration-150 ${
                  activeView === item.id
                    ? 'bg-zinc-800 text-white font-medium'
                    : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/40'
                }`}
              >
                <item.icon size={16} className="shrink-0 text-zinc-500 group-hover:text-zinc-300" />
                {!isSidebarCollapsed && <span>{item.label}</span>}
              </button>
            ))}
          </nav>
        </div>

        {/* Collapsible CHATS Section */}
        {!isSidebarCollapsed && (
          <div className="flex-1 flex flex-col min-h-0 border-t border-[#27272a]/20 mt-2">
            <button 
              onClick={() => setIsChatsExpanded(!isChatsExpanded)}
              className="flex items-center gap-1.5 px-4 py-3 text-[10px] font-bold text-zinc-500 hover:text-zinc-400 uppercase tracking-wider transition-colors text-left"
            >
              <ChevronDown size={12} className={`transition-transform duration-200 ${isChatsExpanded ? '' : '-rotate-90'}`} />
              <span>Chats</span>
            </button>

            {isChatsExpanded && (
              <div className="flex-1 overflow-y-auto custom-scrollbar px-2 pb-2 space-y-0.5">
                {threads.map(thread => {
                  const isCurrent = currentThreadId === thread.id;
                  return (
                    <div 
                      key={thread.id}
                      onClick={() => {
                        setCurrentThreadId(thread.id);
                        setActiveView('chat');
                      }}
                      className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-all duration-200 ${
                        isCurrent 
                          ? 'bg-zinc-800/60 text-white font-medium' 
                          : 'text-zinc-500 hover:bg-zinc-800/30 hover:text-zinc-300'
                      }`}
                    >
                      <div className="flex items-center space-x-2.5 overflow-hidden min-w-0 flex-1">
                        {/* Status dot representation */}
                        {isCurrent ? (
                          <div className="h-1.5 w-1.5 rounded-full bg-blue-500 shrink-0"></div>
                        ) : (
                          <div className="h-1.5 w-1.5 rounded-full bg-green-500/80 shrink-0"></div>
                        )}
                        <span className="text-xs truncate" title={thread.title}>
                          {thread.title || 'Nueva conversación'}
                        </span>
                      </div>
                      <button 
                        onClick={(e) => deleteThread(e, thread.id)}
                        className="opacity-0 group-hover:opacity-100 p-0.5 text-zinc-600 hover:text-red-400 transition-all rounded hover:bg-red-400/10 ml-2"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  );
                })}
                {threads.length === 0 && (
                  <div className="px-4 py-2 text-[11px] text-zinc-600 italic">
                    Sin hilos guardados.
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Sidebar Footer with Settings */}
        <div className="p-3 border-t border-[#27272a]/20 mt-auto">
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="w-full flex items-center gap-3.5 px-3 py-2.5 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/40 rounded-lg text-xs transition-colors"
          >
            <Settings size={16} />
            {!isSidebarCollapsed && <span>Settings</span>}
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 relative bg-[#0e0e11]">
        
        {/* Header Redesigned to support Center dropdown & Right status */}
        <header className="h-16 flex items-center justify-between px-6 border-b border-[#27272a]/20 z-20">
          <div className="flex items-center gap-3 select-none">
            {isSidebarCollapsed && (
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-white tracking-wide">KogniTerm</span>
                <span className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-[9px] text-zinc-500 font-bold uppercase">Desktop</span>
              </div>
            )}
          </div>

          {/* Central Directory Dropdown (Goose style) */}
          <button
            onClick={handleChangeDir}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-zinc-800/50 transition-all text-xs font-semibold text-zinc-400 hover:text-zinc-200 select-none border border-transparent hover:border-zinc-800/40"
            title="Cambiar directorio de trabajo"
          >
            <span>Current directory location</span>
            <ChevronDown size={12} className="text-zinc-500" />
          </button>

          {/* Right Status Panel */}
          <div className="flex items-center gap-4 select-none">
            <div className={`flex items-center gap-2 px-3 py-1 rounded-full border text-[10px] font-bold uppercase tracking-wider ${
              isConnected
                ? 'bg-emerald-500/5 border-emerald-500/10 text-emerald-400'
                : 'bg-red-500/5 border-red-500/10 text-red-400'
            }`}>
              <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
              <span>{isConnected ? 'kogniterm' : 'offline'}</span>
            </div>
          </div>
        </header>

        {/* Content Area */}
        {activeView === 'chat' && (
          <div className="flex flex-1 overflow-hidden">
            <div className="flex-1 flex flex-col relative min-w-0">
              
              <section className={`flex-1 overflow-y-auto custom-scrollbar px-4 lg:px-0 scroll-smooth ${isTerminalVisible ? 'pb-16' : 'pb-32'}`}>
                <div className="max-w-3xl mx-auto py-8">
                  {messages.length === 0 ? (
                    <div className="h-[60vh] flex flex-col items-center justify-center text-center px-4 animate-fade-in">
                      <div className="relative mb-8">
                        <div className="absolute -inset-4 bg-indigo-500/10 rounded-full blur-2xl"></div>
                        <div className="relative h-20 w-20 bg-gradient-to-tr from-zinc-900 to-zinc-950 rounded-2xl flex items-center justify-center border border-zinc-800/80 shadow-2xl rotate-3 transition-transform hover:rotate-0 duration-500">
                          <Sparkles size={36} className="text-indigo-500" />
                        </div>
                      </div>

                      <h2 className="text-2xl font-bold text-zinc-100 mb-2.5 tracking-tight">¿En qué trabajamos hoy?</h2>
                      <p className="text-zinc-500 max-w-sm text-xs leading-relaxed">
                        Tu asistente inteligente de terminal y código.<br />Comienza escribiendo un comando o haz una pregunta.
                      </p>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-10 w-full max-w-xl">
                        {[
                          { title: "Analiza la arquitectura", desc: "Explora la estructura del proyecto y dependencias.", prompt: "Analiza la arquitectura de este proyecto" },
                          { title: "¿Cómo desplegar?", desc: "Genera una guía de deployment paso a paso.", prompt: "Genera una guía de deployment para esta app" }
                        ].map((card, i) => (
                          <button
                            key={i}
                            onClick={() => handleSendMessage(card.prompt)}
                            className="group p-4 rounded-xl bg-[#151518]/60 border border-zinc-850 hover:border-indigo-500/20 hover:bg-[#151518] text-left transition-all hover:shadow-lg hover:shadow-indigo-500/2 hover:-translate-y-0.5"
                          >
                            <div className="flex justify-between items-start mb-1">
                              <p className="text-xs font-semibold text-zinc-300 group-hover:text-indigo-400 transition-colors">{card.title}</p>
                              <span className="opacity-0 group-hover:opacity-100 transition-opacity text-indigo-500 text-xs">→</span>
                            </div>
                            <p className="text-[10px] text-zinc-500 leading-normal">{card.desc}</p>
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
                    <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl mb-6 mx-4 text-xs flex items-center gap-2">
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

              <ChatInput 
                onSendMessage={handleSendMessage} 
                isGenerating={isGenerating} 
                currentDir={currentDir}
                onChangeDir={handleChangeDir}
                messageQueue={messageQueue}
                onRemoveFromQueue={handleRemoveFromQueue}
                onProcessNext={handleProcessNextQueueItem}
              />
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
