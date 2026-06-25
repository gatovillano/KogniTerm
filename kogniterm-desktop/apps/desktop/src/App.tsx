import { useRef, useEffect, useState } from 'react';
import { ChatMessage } from './components/chat/ChatMessage';
import { ChatInput } from './components/chat/ChatInput';
import { FileExplorer } from './components/files/FileExplorer';
import { SettingsModal } from './components/settings/SettingsModal';
import { ThreadList } from './components/chat/ThreadList';
import { TaskTracker } from './components/chat/TaskTracker';
import { TerminalPanel } from './components/chat/TerminalPanel';
import { CommandApproval } from './components/chat/CommandApproval';
import { useChat } from './hooks/useChat';
import { Settings, Files, MessageSquare, ShieldCheck, Command, Folder, MessageCircle, Terminal } from 'lucide-react';
import './App.css';

type ViewType = 'chat' | 'files' | 'threads';

function App() {
  const [currentThreadId, setCurrentThreadId] = useState<string>(() => {
    // Generar un ID único para esta instancia del cliente
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
  const [activeView, setActiveView] = useState<ViewType>('chat');
  const [currentDir, setCurrentDir] = useState<string>('~/Gemini-Interpreter'); // Default fallback
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Fetch initial working directory from backend to ensure UI matches reality
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

  const handleChangeDir = () => {
    const newDir = window.prompt("Introduce la ruta del directorio de trabajo:", currentDir);
    if (newDir && newDir !== currentDir) {
      setCurrentDir(newDir);
      sendMessage(`cd ${newDir}`);
    }
  };

  return (
    <div className="flex h-screen bg-[var(--bg-app)] text-slate-200 font-sans overflow-hidden selection:bg-indigo-500/30">
      {/* Sidebar */}
      <aside className="w-[80px] glass-panel flex flex-col items-center py-6 z-30">
        <div className="h-12 w-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center mb-10 shadow-lg shadow-indigo-500/20 ring-1 ring-white/10">
          <Command size={24} className="text-white" />
        </div>

        <nav className="flex flex-col gap-4 flex-1 w-full px-3">
          {[
            { id: 'chat', icon: MessageSquare, label: 'Chat' },
            { id: 'threads', icon: MessageCircle, label: 'Hilos' },
            { id: 'files', icon: Files, label: 'Archivos' }
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id as ViewType)}
              className={`group relative p-3 rounded-xl transition-all duration-300 flex justify-center ${activeView === item.id
                ? 'bg-indigo-500/10 text-indigo-400'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
                }`}
            >
              <item.icon size={28} strokeWidth={activeView === item.id ? 2.5 : 1.8} />

              {/* Tooltip hint */}
              <div className="absolute left-14 bg-zinc-800 text-zinc-200 text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap border border-zinc-700/50">
                {item.label}
              </div>

              {activeView === item.id && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-indigo-500 rounded-r-full shadow-[0_0_12px_rgba(99,102,241,0.5)]" />
              )}
            </button>
          ))}
        </nav>

        {/* Terminal toggle button */}
        {terminalEntries.length > 0 && (
          <button
            onClick={() => closeTerminal()}
            className={`p-3 rounded-xl transition-all mb-2 relative ${
              isTerminalVisible
                ? 'bg-emerald-500/10 text-emerald-400'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
            }`}
            title="Terminal"
          >
            <Terminal size={28} strokeWidth={isTerminalVisible ? 2.5 : 1.8} />
            <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          </button>
        )}

        <button
          onClick={() => setIsSettingsOpen(true)}
          className="p-3 rounded-xl text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 transition-all mt-auto mb-2"
        >
          <Settings size={28} />
        </button>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 relative bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-indigo-900/10 via-zinc-950/0 to-zinc-950/0">
        {/* Header */}
        <header className="h-16 flex items-center justify-between px-8 z-20 sticky top-0">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-zinc-100 tracking-tight">
              KogniTerm <span className="text-zinc-500 font-normal">Desktop</span>
            </h1>
            <span className="px-2 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-[10px] text-indigo-400 font-medium uppercase tracking-wider">
              Beta
            </span>
          </div>

          <div className="flex items-center gap-4">

            <button
              onClick={handleChangeDir}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-800/50 border border-zinc-700/50 hover:bg-zinc-800 hover:border-zinc-600 transition-all text-xs text-zinc-400 hover:text-zinc-200 max-w-[200px]"
              title="Cambiar directorio de trabajo"
            >
              <Folder size={14} className="min-w-[14px]" />
              <span className="truncate">{currentDir}</span>
            </button>
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-medium ${isConnected
              ? 'bg-emerald-500/5 border-emerald-500/10 text-emerald-400'
              : 'bg-red-500/5 border-red-500/10 text-red-400'
              }`}>
              <div className={`w-1.5 h-1.5 rounded-full shadow-[0_0_8px_rgba(52,211,153,0.6)] ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'
                }`} />
              <span>{isConnected ? 'Conectado' : 'Desconectado'}</span>
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
                      <div className="absolute -inset-4 bg-indigo-500/20 rounded-full blur-2xl"></div>
                      <div className="relative h-24 w-24 bg-gradient-to-tr from-zinc-800 to-zinc-900 rounded-2xl flex items-center justify-center border border-zinc-700 shadow-2xl rotate-3 transition-transform hover:rotate-0 duration-500">
                        <Command size={48} className="text-indigo-500" />
                      </div>
                    </div>

                    <h2 className="text-3xl font-bold text-zinc-100 mb-3 tracking-tight">¿En qué trabajamos hoy?</h2>
                    <p className="text-zinc-500 max-w-md text-base leading-relaxed">
                      Tu asistente agéntico inteligente. <br />Investigación profunda, depuración y arquitectura.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-12 w-full max-w-2xl">
                      {[
                        { title: "Analiza la arquitectura", desc: "Explora la estructura del proyecto y dependencias.", prompt: "Analiza la arquitectura de este proyecto" },
                        { title: "¿Cómo desplegar?", desc: "Genera una guía de deployment paso a paso.", prompt: "Genera una guía de deployment para esta app" }
                      ].map((card, i) => (
                        <button
                          key={i}
                          onClick={() => sendMessage(card.prompt)}
                          className="group p-5 rounded-2xl bg-zinc-900/50 border border-zinc-800/80 hover:border-indigo-500/30 hover:bg-zinc-900 text-left transition-all hover:shadow-lg hover:shadow-indigo-500/5 hover:-translate-y-1"
                        >
                          <div className="flex justify-between items-start mb-2">
                            <p className="text-sm font-semibold text-zinc-200 group-hover:text-indigo-400 transition-colors">{card.title}</p>
                            <span className="opacity-0 group-hover:opacity-100 transition-opacity text-indigo-500">→</span>
                          </div>
                          <p className="text-xs text-zinc-500 leading-relaxed">{card.desc}</p>
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
                  <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl mb-6 mx-4 text-sm flex items-center gap-2">
                    <ShieldCheck size={16} />
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

            <ChatInput onSendMessage={sendMessage} isGenerating={isGenerating} />
            </div>

            {/* Task Tracker Panel — slides in when agent has active tasks */}
            {hasActiveTasks && (
              <TaskTracker taskPlans={taskPlans} />
            )}
          </div>
        )}

        {activeView === 'threads' && (
          <div className="flex-1 overflow-hidden flex bg-slate-950">
            <ThreadList 
              currentThread={currentThreadId} 
              onSelectThread={(id) => {
                setCurrentThreadId(id || `desktop-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`);
                setActiveView('chat');
              }} 
            />
          </div>
        )}

        {activeView === 'files' && (
          <div className="flex-1 overflow-hidden">
            <FileExplorer workspacePath={currentDir} />
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

      {/* Modals */}
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </div>
  );
}

export default App;
