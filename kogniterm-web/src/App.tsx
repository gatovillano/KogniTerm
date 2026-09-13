import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { 
  Terminal, Bot, Code, Cpu, Shield, Settings, 
  Send, Sparkles, Folder, CheckCircle2, Wrench, Plus, Trash2, 
  Copy, Check, MessageSquare, PanelLeft, PanelRight, Sun, Moon, Globe, 
  ChevronDown, ChevronRight, FolderPlus, Zap, HeartPulse, History, Files, Image as ImageIcon, X
} from 'lucide-react';
import { checkServerHealth, sendChatMessage } from './services/api';
import { LLMSettingsModal } from './components/settings/LLMSettingsModal';
import { AgentPanel } from './components/AgentPanel';
import { AppliedDiffCard } from './components/chat/AppliedDiffCard';
import { ApprovalDialog } from './components/chat/ApprovalDialog';
import { InteractiveTerminal } from './components/chat/InteractiveTerminal';
import { MarkdownRenderer } from './components/chat/MarkdownRenderer';
import { TaskTracker } from './components/chat/TaskTracker';
import { ToolIndicators } from './components/chat/ToolIndicator';
import { ThinkingBlock } from './components/chat/ThinkingBlock';
import { AutocompletePopup } from './components/chat/AutocompletePopup';
import { RightSidebar } from './components/terminal/RightSidebar';
import { useTerminalSidebar } from './hooks/useTerminalSidebar';
import { useChatWebSocket, parseAppliedDiff, stripAnsiAndControlCodes } from './hooks/useChatWebSocket';

interface Project {
  id: string;
  name: string;
  path: string;
  isExpanded: boolean;
}

interface Thread {
  id: string;
  title: string;
  updated_at?: string;
  created_at?: string;
  workspaceDir?: string;
  workspace_dir?: string;
  message_count?: number;
}

interface Message {
  id: string;
  sender: 'user' | 'assistant' | 'system';
  text: string;
  timestamp: string;
  agent?: string;
  thinking?: string;
  images?: string[];
  // Rich message types
  message_type?: 'text' | 'diff' | 'command' | 'approval_request' | 'terminal' | 'tool_execution';
  // For tool executions
  tool_execution?: {
    tool_name: string;
    action: string;
    status: 'pending' | 'running' | 'completed' | 'error';
    tool_call_id: string;
  };
  // For diff messages
  diff?: {
    filePath: string;
    toolName?: string;
    additions: number;
    deletions: number;
    diffContent: string;
    status?: 'pending' | 'approved' | 'rejected';
    tool_call_id?: string;
  };
  // For command messages
  command?: string;
  output?: string;
  error?: string;
  exit_code?: number;
  // For approval requests
  approval_request?: {
    id: string;
    action: 'edit' | 'command' | 'other';
    title: string;
    description: string;
    content: string;
    tool_call_id: string;
  };
  // For terminal messages
  terminal?: {
    session_id: string;
    output?: string;
    interactive?: boolean;
  };
}

export default function App() {
  const normalizePath = (p?: string) => p ? p.replace(/\\/g, '/').replace(/\/$/, '') : '';
  const [activeTab, setActiveTab] = useState<'chat' | 'terminal' | 'agents' | 'tasks' | 'skills'>('chat');
  const [isLLMModalOpen, setIsLLMModalOpen] = useState<boolean>(false);
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');

  const [selectedAgent, setSelectedAgent] = useState<string>('super_agent');
  const [selectedModel, setSelectedModel] = useState<string>('gemini-2.5-pro');
  const [inputQuery, setInputQuery] = useState<string>('');
  const [attachedImages, setAttachedImages] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [serverOnline, setServerOnline] = useState<boolean>(false);
  const [workspaceFiles, setWorkspaceFiles] = useState<string[]>([]);
  const [skillsList, setSkillsList] = useState<Array<{ name: string; description?: string }>>([]);
  const [rightSidebarOpen, setRightSidebarOpen] = useState<boolean>(false);

  // Task tracker state
  const [taskPlans, setTaskPlans] = useState<any>([]);

  // Proyectos / Workspaces State
  const [projects, setProjects] = useState<Project[]>(() => {
    try {
      const saved = localStorage.getItem('kogniterm_web_projects');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (e) {}
    return [{
      id: 'proj-default',
      name: 'Gemini-Interpreter',
      path: '/home/gato/Proyectos/Gemini-Interpreter',
      isExpanded: true
    }];
  });

  // Threads State recuperados del servidor
  const [threads, setThreads] = useState<Thread[]>([]);
  const [currentThread, setCurrentThread] = useState<string>('');

  // Messages por hilo
  const [threadMessages, setThreadMessages] = useState<Record<string, Message[]>>({});

  const currentMessages = currentThread ? (threadMessages[currentThread] || []) : [];

  // WebSocket hook alineado con KogniTerm Desktop / TUI
  const { sendMessage, isGenerating, activeToolExecutions } = useChatWebSocket(
    currentThread || null,
    useCallback((updater: (prev: Message[]) => Message[]) => {
      if (!currentThread) return;
      setThreadMessages((prev) => ({
        ...prev,
        [currentThread]: updater(prev[currentThread] || [])
      }));
    }, [currentThread])
  );

  // Terminal PTY Sidebar State
  const { isTerminalOpen, terminalState, openTerminal: openTerm, appendOutput, closeTerminal: closeTerm } = useTerminalSidebar();

  // Control manual del sidebar derecho
  const [userOpenedRightSidebar, setUserOpenedRightSidebar] = useState<boolean>(false);
  const [rightSidebarTab, setRightSidebarTab] = useState<'terminal' | 'tasks'>('terminal');

  const openRightSidebar = useCallback((tab: 'terminal' | 'tasks' = 'terminal') => {
    setRightSidebarTab(tab);
    setUserOpenedRightSidebar(true);
  }, []);

  const closeRightSidebar = useCallback(() => {
    setUserOpenedRightSidebar(false);
    closeTerm();
  }, [closeTerm]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Manejador de paste (portapapeles) para imágenes
  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.type.indexOf('image') !== -1) {
        const file = item.getAsFile();
        if (file) {
          const reader = new FileReader();
          reader.onload = (uploadEvent) => {
            const result = uploadEvent.target?.result as string;
            if (result) {
              setAttachedImages(prev => [...prev, result]);
            }
          };
          reader.readAsDataURL(file);
        }
      }
    }
  }, []);

  // Manejador de selección de imágenes vía input tipo file
  const handleImageFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    Array.from(files).forEach(file => {
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (uploadEvent) => {
          const result = uploadEvent.target?.result as string;
          if (result) {
            setAttachedImages(prev => [...prev, result]);
          }
        };
        reader.readAsDataURL(file);
      }
    });
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  useEffect(() => {
    localStorage.setItem('kogniterm_web_projects', JSON.stringify(projects));
  }, [projects]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentMessages]);

  useEffect(() => {
    checkServerHealth().then((online) => {
      setServerOnline(online);
      fetchThreads();
    });

  // Listen for task tracker, tool, and terminal events from WebSocket
  const handleKognitermEvent = (event: CustomEvent) => {
    const data = event.detail;
    console.log('[DEBUG] Listener recibió evento:', data.type, JSON.stringify(data.data).slice(0, 100));
    const eventData = data.data || data;

    if (data.type === 'task_tracker' && data.data) {
      const rawData = data.data;
      console.log('[TASK_TRACKER] Received data:', JSON.stringify(rawData, null, 2));
      setTaskPlans(rawData);
      // Auto-abrir sidebar derecho en la pestaña de Tasks al recibir un plan de tareas
      openRightSidebar('tasks');
    }

    if (data.type === 'tool_call' || data.type === 'tool_execution') {
      const toolEvent = data.data || {};
      const toolName = toolEvent.name || toolEvent.tool_name || 'Tool';
      const actionDesc = toolEvent.description || toolEvent.action || '';
      const toolCallId = toolEvent.tool_call_id || `tool-${Date.now()}`;
    }

    // Detectar herramientas de terminal del agente: tool_call con tool de comando
    const TERMINAL_TOOL_KEYWORDS = ['bash', 'shell', 'terminal', 'command', 'cmd_execution', 'python_exec', 'execute_command'];

    // Evento tool_call: detectar cuando el agente inicia una herramienta de terminal
    if (data.type === 'tool_call' && eventData) {
      const toolName = eventData.name || eventData.tool_name || '';
      const isTerminalTool = TERMINAL_TOOL_KEYWORDS.some((kw) => toolName.toLowerCase().includes(kw));

      if (isTerminalTool) {
        const toolArgs = eventData.args || {};
        const commandVal = toolArgs.command || toolArgs.cmd || toolArgs.script || toolArgs.input || '';
        const cmdLabel = typeof commandVal === 'string' ? commandVal.slice(0, 80) : '';

        openTerm(toolName || 'Terminal', toolName, cmdLabel);
      }
    }

    // Evento terminal_output: acumular la salida del comando en el sidebar
    if (data.type === 'terminal_output' && eventData) {
      const content = eventData.content || eventData.output || '';
      const toolName = eventData.tool || eventData.name || '';
      const command = eventData.command || '';

      const cleanContent = stripAnsiAndControlCodes(content);

      if (cleanContent) {
        // Si ya está abierto, acumular el output limpio
        if (isTerminalOpen || userOpenedRightSidebar) {
          appendOutput(cleanContent);
        } else {
          // Abrilo si detectamos output de terminal
          if (command) {
            openTerm(command, toolName || 'Tool', command);
            appendOutput(cleanContent);
          } else if (toolName) {
            openTerm(toolName, toolName, '');
            appendOutput(cleanContent);
          }
        }
      }
    }

    // Evento applied_diff
    if (data.type === 'applied_diff' && data.data) {
        const diffData = data.data;
        if (currentThread) {
          const diffMsg: Message = {
            id: `diff-${Date.now()}`,
            sender: 'assistant',
            text: '',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            message_type: 'diff',
            diff: {
              filePath: diffData.file_path || diffData.path || 'archivo_modificado',
              toolName: diffData.tool_name || diffData.tool || 'file_editor',
              additions: diffData.additions || 0,
              deletions: diffData.deletions || 0,
              diffContent: diffData.diff_content || diffData.diff || ''
            }
          };
          setThreadMessages(prev => ({
            ...prev,
            [currentThread]: [...(prev[currentThread] || []), diffMsg]
          }));
        }
      }
    };

    window.addEventListener('kogniterm_event' as any, handleKognitermEvent as any);
    return () => {
      window.removeEventListener('kogniterm_event' as any, handleKognitermEvent as any);
    };
  }, []);

  // Cargar mensajes cuando cambia el hilo seleccionado
  useEffect(() => {
    if (currentThread) {
      fetchThreadMessages(currentThread);
    }
  }, [currentThread]);

  // Cargar archivos y skills del espacio de trabajo para autocompletado (@ y #)
  useEffect(() => {
    // Archivos vía /api/workspace/files
    fetch('/api/workspace/files?max_results=200')
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data && data.results && Array.isArray(data.results)) {
          setWorkspaceFiles(data.results.map((r: any) => r.path));
        } else if (data && data.items && Array.isArray(data.items)) {
          setWorkspaceFiles(data.items);
        }
      })
      .catch(() => {});

    // Skills procedimentales vía /api/skills?procedural_only=true (tal como en la TUI con #)
    fetch('/api/skills?procedural_only=true')
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data && data.skills && Array.isArray(data.skills)) {
          setSkillsList(data.skills.map((s: any) => ({ name: s.name, description: s.description, scope: s.scope })));
        }
      })
      .catch(() => {});
  }, []);

  const fetchThreads = async () => {
    try {
      const res = await fetch('/api/threads');
      if (res.ok) {
        const data = await res.json();
        const fetchedThreads: Thread[] = data.threads || [];
        setThreads(fetchedThreads);

        // Auto-descubrir workspaces a partir de los hilos preexistentes
        setProjects(prevProjects => {
          const existingPaths = new Set(prevProjects.map(p => normalizePath(p.path).toLowerCase()));
          const newProjects = [...prevProjects];

          fetchedThreads.forEach(t => {
            const wsPath = t.workspace_dir || t.workspaceDir;
            if (wsPath) {
              const normWs = normalizePath(wsPath);
              if (normWs && !existingPaths.has(normWs.toLowerCase())) {
                existingPaths.add(normWs.toLowerCase());
                const folderName = normWs.split('/').filter(Boolean).pop() || 'Workspace';
                newProjects.push({
                  id: `proj-auto-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                  name: folderName,
                  path: normWs,
                  isExpanded: true
                });
              }
            }
          });
          return newProjects;
        });

        if (fetchedThreads.length > 0 && !currentThread) {
          setCurrentThread(fetchedThreads[0].id);
        }
      }
    } catch (err) {
      console.warn('Error al obtener hilos del servidor:', err);
    }
  };

  const fetchThreadMessages = async (threadId: string) => {
    try {
      const res = await fetch(`/api/threads/${threadId}/messages`);
      if (res.ok) {
        const data = await res.json();
        if (data.messages && Array.isArray(data.messages)) {
          const formatted: Message[] = data.messages
            .map((m: any, idx: number) => {
              const role = m.role || m.sender || 'assistant';
              const sender = role === 'user' ? 'user' : 'assistant';
              let text = typeof m.content === 'string' ? m.content : (m.text || m.message || '');
              
              // Omitir ToolMessages de LangChain (role === 'tool') que vienen del backend
              if (role === 'tool') {
                const parsedDiff = parseAppliedDiff(text);
                if (parsedDiff) {
                  return {
                    id: m.id || `${threadId}-${idx}`,
                    sender: 'assistant',
                    text: '',
                    timestamp: m.timestamp ? new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    agent: m.agent || 'SuperAgent',
                    message_type: 'diff',
                    diff: parsedDiff
                  };
                }
                return null; // Omitir tool messages crudos
              }

              // Limpiar texto para omitir ruidos de consola o JSON sin formatear
              text = stripAnsiAndControlCodes(text);

              // Extraer pensamiento (thinking/reasoning) si existe en el mensaje guardado
              const rawThinking = m.thinking || m.reasoning || m.additional_kwargs?.reasoning_content || m.additional_kwargs?.thought || '';
              const thinking = stripAnsiAndControlCodes(rawThinking);

              // Si es un JSON de tool result o diff no formateado, analizarlo como diff
              const parsedDiff = parseAppliedDiff(text);
              if (parsedDiff) {
                return {
                  id: m.id || `${threadId}-${idx}`,
                  sender: sender as 'user' | 'assistant' | 'system',
                  text: '',
                  thinking: thinking || undefined,
                  timestamp: m.timestamp ? new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                  agent: m.agent || 'SuperAgent',
                  message_type: 'diff',
                  diff: parsedDiff
                };
              }

              // Si el mensaje del historial trae llamadas a herramientas grabadas (tool_calls)
              const toolCalls = m.tool_calls || [];
              if (toolCalls && toolCalls.length > 0) {
                // Generar indicadores de herramienta persistentes en el historial
                const toolExecutionMsgs: Message[] = toolCalls.map((tc: any, tcIdx: number) => ({
                  id: `${m.id || threadId}-${idx}-tool-${tcIdx}`,
                  sender: 'assistant',
                  text: '',
                  timestamp: m.timestamp ? new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                  agent: m.agent || 'SuperAgent',
                  message_type: 'tool_execution',
                  tool_execution: {
                    tool_name: tc.name || tc.tool || 'Tool',
                    action: tc.args ? (typeof tc.args === 'string' ? tc.args : JSON.stringify(tc.args)) : '',
                    status: 'completed',
                    tool_call_id: tc.id || `tc-${tcIdx}`
                  }
                }));

                // Devolver tanto las herramientas como el mensaje de texto si existe
                const mainMsg: Message = {
                  id: m.id || `${threadId}-${idx}`,
                  sender: sender as 'user' | 'assistant' | 'system',
                  text: text,
                  thinking: thinking || undefined,
                  timestamp: m.timestamp ? new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                  agent: m.agent || 'SuperAgent',
                  command: m.command,
                  output: m.output
                };

                return [...toolExecutionMsgs, mainMsg];
              }

              return {
                id: m.id || `${threadId}-${idx}`,
                sender: sender as 'user' | 'assistant' | 'system',
                text: text,
                thinking: thinking || undefined,
                timestamp: m.timestamp ? new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                agent: m.agent || 'SuperAgent',
                command: m.command,
                output: m.output
              };
            })
            .filter((m: any) => m !== null && ((m.text && m.text.trim() !== '') || m.thinking || m.message_type === 'diff' || m.message_type === 'tool_execution'));

          setThreadMessages(prev => ({ ...prev, [threadId]: formatted.flat() }));
        }
      }
    } catch (err) {
      console.warn(`No se pudieron cargar mensajes del hilo ${threadId}`);
    }
  };

  const createNewThread = async (workspaceDir?: string): Promise<string> => {
    const targetWs = workspaceDir || (projects[0]?.path || '/home/gato/Proyectos/Gemini-Interpreter');
    let newId = 'thread-' + Date.now();
    let newTitle = `Nuevo Chat ${threads.length + 1}`;

    if (serverOnline) {
      try {
        const res = await fetch('/api/threads', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ workspace_dir: targetWs })
        });
        if (res.ok) {
          const data = await res.json();
          newId = data.thread_id;
          newTitle = data.metadata?.title || 'Nuevo chat';
        }
      } catch (e) {
        console.error('Error al crear hilo en servidor:', e);
      }
    }

    const newThread: Thread = {
      id: newId,
      title: newTitle,
      workspace_dir: targetWs
    };
    setThreads(prev => [newThread, ...prev]);
    setCurrentThread(newId);
    setThreadMessages(prev => ({ ...prev, [newId]: prev[newId] || [] }));
    return newId;
  };

  const deleteThread = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (serverOnline) {
      try {
        await fetch(`/api/threads/${id}`, { method: 'DELETE' });
      } catch (err) {
        console.error('Error al eliminar hilo en backend:', err);
      }
    }
    const updated = threads.filter(t => t.id !== id);
    setThreads(updated);
    if (currentThread === id) {
      setCurrentThread(updated[0]?.id || '');
    }
  };

  const toggleProjectExpand = (id: string) => {
    setProjects(prev => prev.map(p => p.id === id ? { ...p, isExpanded: !p.isExpanded } : p));
  };

  const addProject = () => {
    const pPath = prompt('Ruta absoluta del proyecto:', '/home/gato/Proyectos/');
    if (!pPath) return;
    const folderName = pPath.split('/').filter(Boolean).pop() || 'Proyecto';
    const newProj = {
      id: `proj-${Date.now()}`,
      name: folderName,
      path: pPath,
      isExpanded: true
    };
    setProjects(prev => [...prev, newProj]);
    fetchThreads();
  };

  const threadsByProject = useMemo(() => {
    const map: Record<string, Thread[]> = {};
    projects.forEach(p => { map[normalizePath(p.path)] = []; });
    const unmapped: Thread[] = [];

    threads.forEach(t => {
      const threadWorkspace = normalizePath(t.workspaceDir || t.workspace_dir);
      let matchedKey: string | undefined = undefined;

      if (threadWorkspace) {
        const normTW = threadWorkspace.toLowerCase();
        matchedKey = Object.keys(map).find(pPath => {
          if (!pPath) return false;
          const normPP = pPath.toLowerCase();
          return normPP === normTW || normTW.startsWith(normPP + '/');
        });
      }

      if (matchedKey && map[matchedKey]) {
        map[matchedKey].push(t);
      } else if (projects.length > 0) {
        const firstKey = normalizePath(projects[0].path);
        if (map[firstKey]) map[firstKey].push(t);
        else unmapped.push(t);
      } else {
        unmapped.push(t);
      }
    });

    return { map, unmapped };
  }, [projects, threads]);

  const handleSendMessage = async (textToSend?: string) => {
    const query = textToSend !== undefined ? textToSend : inputQuery;
    if ((!query.trim() && attachedImages.length === 0) || isGenerating) return;

    let activeThreadId = currentThread;
    if (!activeThreadId) {
      activeThreadId = await createNewThread();
    }

    const currentImages = textToSend !== undefined ? [] : [...attachedImages];

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: query,
      images: currentImages.length > 0 ? currentImages : undefined,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setThreadMessages(prev => ({
      ...prev,
      [activeThreadId]: [...(prev[activeThreadId] || []), userMsg]
    }));

    if (textToSend === undefined) {
      setInputQuery('');
      setAttachedImages([]);
    }

    // Enviar a través del socket persistente usando el protocolo oficial con imágenes
    sendMessage(query, selectedAgent, selectedModel, currentImages.length > 0 ? currentImages : undefined);
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className={`flex h-screen w-screen overflow-hidden font-sans ${theme === 'dark' ? 'theme-dark' : 'theme-light'}`}>
      
      {/* Modal Configuración LLM (Réplica Desktop) */}
      <LLMSettingsModal isOpen={isLLMModalOpen} onClose={() => setIsLLMModalOpen(false)} />

      {/* ── SIDEBAR LIMPIO SIN LÍNEAS SEPARADORAS HORIZONTALES ── */}
      <aside className={`chat-sidebar flex flex-col transition-all duration-300 z-30 select-none ${sidebarOpen ? 'w-64' : 'w-0 overflow-hidden'}`}>
        
        {/* Brand & Botón Colapsar */}
        <div className="p-3 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-5 h-5 rounded-md bg-indigo-600 flex items-center justify-center text-white font-bold text-xs">
              <Sparkles className="w-3 h-3" />
            </div>
            <span className="font-bold text-xs tracking-tight">Kogniterm</span>
            <span className="text-[9px] opacity-60 bg-black/20 px-1 py-0.5 rounded font-mono">Web</span>
          </div>
          <button onClick={() => setSidebarOpen(false)} className="p-1 opacity-70 hover:opacity-100 rounded">
            <PanelLeft className="w-4 h-4" />
          </button>
        </div>

        {/* Nuevo Chat Botón */}
        <div className="p-2">
          <button 
            onClick={() => createNewThread()}
            className="flex items-center space-x-2 px-3 py-2 rounded-lg chat-card hover:opacity-95 transition-all text-xs w-full justify-between font-medium shadow-sm"
          >
            <span className="flex items-center gap-2"><Plus className="w-3.5 h-3.5" /> Nuevo chat</span>
            <span className="text-[10px] opacity-60 font-mono">⌘K</span>
          </button>
        </div>

        {/* Proyectos & Acordeones de Hilos */}
        <div className="flex-1 px-2 py-2 space-y-3 overflow-y-auto custom-scrollbar text-xs">
          
          <div className="flex items-center justify-between px-2 text-[10px] font-semibold opacity-50 uppercase tracking-wider">
            <span>Workspaces</span>
            <button onClick={addProject} className="p-0.5 hover:opacity-100 opacity-60 rounded" title="Agregar Proyecto">
              <FolderPlus className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Renderizado de Proyectos y sus hilos asociados */}
          {projects.map(project => {
            const normPath = normalizePath(project.path);
            const projectThreads = threadsByProject.map[normPath] || [];
            return (
              <div key={project.id} className="space-y-0.5">
                <div 
                  onClick={() => toggleProjectExpand(project.id)}
                  className="group flex items-center justify-between px-2 py-1.5 rounded-lg cursor-pointer hover:bg-black/5 transition-colors font-medium"
                >
                  <div className="flex items-center space-x-2 truncate min-w-0">
                    {project.isExpanded ? <ChevronDown className="w-3.5 h-3.5 opacity-60" /> : <ChevronRight className="w-3.5 h-3.5 opacity-60" />}
                    <Folder className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                    <span className="truncate text-xs">{project.name}</span>
                  </div>
                  <button 
                    onClick={(e) => { e.stopPropagation(); createNewThread(project.path); }}
                    className="opacity-0 group-hover:opacity-100 p-0.5 hover:text-indigo-400 transition-opacity"
                    title="Nuevo chat en este workspace"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>

                {project.isExpanded && (
                  <div className="pl-4 space-y-0.5 ml-3">
                    {projectThreads.map(thread => (
                      <div
                        key={thread.id}
                        onClick={() => { setCurrentThread(thread.id); setActiveTab('chat'); }}
                        className={`group flex items-center justify-between px-2 py-1.5 rounded-lg cursor-pointer transition-colors ${currentThread === thread.id ? 'chat-card font-medium' : 'opacity-75 hover:opacity-100'}`}
                      >
                        <span className="truncate text-[11px]">{thread.title || 'Conversación sin título'}</span>
                        <button 
                          onClick={(e) => deleteThread(e, thread.id)}
                          className="opacity-0 group-hover:opacity-100 p-0.5 hover:text-red-400 transition-opacity"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                    {projectThreads.length === 0 && (
                      <div className="px-2 py-1 text-[10px] opacity-40 italic">Sin conversaciones</div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* Otros Hilos sin mapeo explícito */}
          {threadsByProject.unmapped.length > 0 && (
            <div className="space-y-0.5 pt-2">
              <div className="px-2 text-[10px] font-semibold opacity-50 uppercase tracking-wider">Otros Hilos</div>
              {threadsByProject.unmapped.map(thread => (
                <div
                  key={thread.id}
                  onClick={() => { setCurrentThread(thread.id); setActiveTab('chat'); }}
                  className={`group flex items-center justify-between px-2 py-1.5 rounded-lg cursor-pointer transition-colors ${currentThread === thread.id ? 'chat-card font-medium' : 'opacity-75 hover:opacity-100'}`}
                >
                  <span className="truncate text-[11px]">{thread.title || 'Conversación sin título'}</span>
                  <button 
                    onClick={(e) => deleteThread(e, thread.id)}
                    className="opacity-0 group-hover:opacity-100 p-0.5 hover:text-red-400 transition-opacity"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Vistas de Navegación */}
          <div className="pt-2 text-[10px] font-semibold opacity-50 uppercase tracking-wider px-2">Vistas</div>
          <button 
            onClick={() => setActiveTab('chat')}
            className={`w-full flex items-center space-x-2.5 px-2.5 py-1.5 rounded-lg transition-colors ${activeTab === 'chat' ? 'chat-card font-medium' : 'opacity-75 hover:opacity-100'}`}
          >
            <Bot className="w-4 h-4 text-emerald-500" />
            <span>Chat Multi-Agente</span>
          </button>
          <button 
            onClick={() => setActiveTab('terminal')}
            className={`w-full flex items-center space-x-2.5 px-2.5 py-1.5 rounded-lg transition-colors ${activeTab === 'terminal' ? 'chat-card font-medium' : 'opacity-75 hover:opacity-100'}`}
          >
            <Terminal className="w-4 h-4 text-indigo-500" />
            <span>Terminal Shell</span>
          </button>
          <button 
            onClick={() => setActiveTab('agents')}
            className={`w-full flex items-center space-x-2.5 px-2.5 py-1.5 rounded-lg transition-colors ${activeTab === 'agents' ? 'chat-card font-medium' : 'opacity-75 hover:opacity-100'}`}
          >
            <Cpu className="w-4 h-4 text-violet-500" />
            <span>Panel de Agentes</span>
          </button>
          <button 
            onClick={() => {
              setActiveTab('tasks');
              openRightSidebar('tasks');
            }}
            className={`w-full flex items-center space-x-2.5 px-2.5 py-1.5 rounded-lg transition-colors ${activeTab === 'tasks' ? 'chat-card font-medium' : 'opacity-75 hover:opacity-100'}`}
          >
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            <span>Task Tracker</span>
          </button>
          <button 
            onClick={() => setActiveTab('skills')}
            className={`w-full flex items-center space-x-2.5 px-2.5 py-1.5 rounded-lg transition-colors ${activeTab === 'skills' ? 'chat-card font-medium' : 'opacity-75 hover:opacity-100'}`}
          >
            <Wrench className="w-4 h-4 text-amber-500" />
            <span>Skills Marketplace</span>
          </button>

        </div>

        {/* Footer Sidebar */}
        <div className="p-3 flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2 truncate">
            <div className={`w-2 h-2 rounded-full ${serverOnline ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            <span className="truncate text-[11px] font-mono opacity-80">{serverOnline ? 'Daemon Online' : 'Standalone'}</span>
          </div>
          <div className="flex items-center space-x-1">
            <button 
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="p-1.5 rounded hover:opacity-100 opacity-70 transition-opacity"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            <button onClick={() => setIsLLMModalOpen(true)} className="p-1.5 rounded hover:opacity-100 opacity-70 transition-opacity">
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Sidebar Footer */}
      </aside>

      {/* Botón flotante para reabrir el sidebar si está colapsado */}
      {!sidebarOpen && (
        <button 
          onClick={() => setSidebarOpen(true)}
          className="absolute top-3 left-3 z-40 p-2 rounded-xl chat-card border shadow-lg hover:opacity-100 opacity-80"
          title="Abrir Sidebar"
        >
          <PanelLeft className="w-4 h-4" />
        </button>
      )}

      {/* Botón flotante para abrir el panel derecho (Siempre visible cuando el panel está cerrado) */}
      {!(userOpenedRightSidebar || isTerminalOpen) && (
        <button
          onClick={() => openRightSidebar('terminal')}
          className="fixed top-3 right-3 z-40 p-2 rounded-xl chat-card border shadow-lg hover:opacity-100 opacity-80 bg-[#111827] text-white"
          title="Abrir Panel Derecho (Terminal / Tasks)"
        >
          <PanelRight className="w-4 h-4 text-slate-300" />
        </button>
      )}

      {/* ── CONTENIDO PRINCIPAL (SIN BARRA SUPERIOR) ── */}
      <main className="chat-main flex-1 flex flex-col relative overflow-hidden">
        
        {/* ── VISTA CHAT ── */}
        {activeTab === 'chat' && (
          <div className="flex-1 flex flex-col overflow-hidden relative">
            {(!currentThread || (currentMessages.length === 0)) ? (
              /* PANTALLA DE BIENVENIDA MINIMALISTA TIPO CHATGPT CENTRADA */
              <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center text-white shadow-xl mb-6">
                  <Sparkles className="w-6 h-6" />
                </div>
                <h1 className="text-2xl font-bold mb-2 tracking-tight">¿En qué puedo ayudarte hoy?</h1>
                <p className="text-sm opacity-60 max-w-md mb-8">
                  Escribe una instrucción para tu workspace o selecciona una sugerencia rápida.
                </p>

                {/* Input Central Premium */}
                <div className="w-full max-w-2xl relative">
                  {/* Previsualización de imágenes adjuntas */}
                  {attachedImages.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-2.5 px-2">
                      {attachedImages.map((img, idx) => (
                        <div key={idx} className="relative group">
                          <img src={img} alt={`adjunto-${idx}`} className="w-16 h-16 object-cover rounded-xl border border-indigo-500/30 shadow-md" />
                          <button
                            type="button"
                            onClick={() => setAttachedImages(prev => prev.filter((_, i) => i !== idx))}
                            className="absolute -top-1.5 -right-1.5 p-0.5 rounded-full bg-rose-600 text-white shadow-md hover:bg-rose-500 transition-colors"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} className="relative">
                    <input 
                      type="file"
                      ref={fileInputRef}
                      onChange={handleImageFileSelect}
                      accept="image/*"
                      multiple
                      className="hidden"
                    />
                    <AutocompletePopup
                      inputValue={inputQuery}
                      workspaceFiles={workspaceFiles}
                      skillsList={skillsList}
                      isDark={theme === 'dark'}
                      onSelect={(completedText) => {
                        const words = inputQuery.split(/\s+/);
                        const last = words[words.length - 1] || '';
                        if (last.includes('@')) {
                          const prefix = last.substring(0, last.lastIndexOf('@'));
                          words[words.length - 1] = prefix + completedText;
                        } else if (last.includes('#')) {
                          const prefix = last.substring(0, last.lastIndexOf('#'));
                          words[words.length - 1] = prefix + completedText;
                        } else {
                          words[words.length - 1] = completedText;
                        }
                        setInputQuery(words.join(' ') + ' ');
                      }}
                      onClose={() => {}}
                    />
                    <input 
                      type="text"
                      value={inputQuery}
                      onChange={(e) => setInputQuery(e.target.value)}
                      onPaste={handlePaste}
                      placeholder="Escribe tu instrucción, / para comandos, @ para archivos o pega una imagen..."
                      className="w-full chat-input-box rounded-2xl pl-12 pr-14 py-4 text-sm focus:outline-none transition-all shadow-2xl"
                    />
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="absolute left-3 top-3.5 p-1.5 rounded-lg text-slate-400 hover:text-indigo-400 hover:bg-white/5 transition-all"
                      title="Adjuntar Imagen"
                    >
                      <ImageIcon className="w-4 h-4" />
                    </button>
                    <button 
                      type="submit"
                      disabled={(!inputQuery.trim() && attachedImages.length === 0) || isGenerating}
                      className="absolute right-3 top-3 p-2.5 rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-30 transition-colors shadow"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </form>

                  {/* Sugerencias Rápidas */}
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5 mt-6 text-xs">
                    {[
                      'Ejecuta pytest y verifica tests',
                      'Refactoriza código con CodeAgent',
                      'Busca una skill con npx skills',
                      'Audita vulnerabilidades Bandit'
                    ].map((sug, i) => (
                      <button 
                        key={i}
                        onClick={() => handleSendMessage(sug)}
                        className="chat-card p-3 rounded-xl opacity-80 hover:opacity-100 hover:scale-[1.01] transition-all text-left truncate shadow-sm border"
                      >
                        {sug}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              /* HISTORIAL DE CHAT CON MENSAJES */
              <div className="flex-1 flex flex-col overflow-hidden">
                <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6 custom-scrollbar">
                  <div className="max-w-3xl mx-auto space-y-6">
                    {currentMessages.map((msg) => (
                      <div key={msg.id} className={`flex space-x-4 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                        {msg.sender !== 'user' && (
                          <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-white shrink-0 font-bold text-xs shadow-md">
                            K
                          </div>
                        )}
                        <div className={`max-w-2xl space-y-3 ${
                          msg.sender === 'user' 
                            ? 'justify-end' 
                            : 'justify-start'
                        }`}>
                          {/* Tool Execution Persistente en el Historial */}
                          {msg.tool_execution && (
                            <ToolIndicators
                              executions={[{
                                tool_name: msg.tool_execution.tool_name,
                                action: msg.tool_execution.action,
                                status: msg.tool_execution.status,
                                tool_call_id: msg.tool_execution.tool_call_id
                              }]}
                            />
                          )}

                          {/* Bloque de Pensamiento (Thinking...) contraíble */}
                          {msg.thinking && (
                            <ThinkingBlock thinking={msg.thinking} isDark={theme === 'dark'} />
                          )}

                          {/* Text content */}
                          {msg.text && (
                            <div className={`text-sm leading-relaxed ${
                              msg.sender === 'user' 
                                ? theme === 'dark'
                                  ? 'bg-slate-800/90 text-slate-100 rounded-2xl rounded-br-xs px-4 py-3 shadow-md border border-slate-700/60' 
                                  : 'bg-slate-200/90 text-slate-800 rounded-2xl rounded-br-xs px-4 py-3 shadow-sm border border-slate-300/60'
                                : 'bg-transparent py-1'
                            }`}>
                              {/* Render de imágenes adjuntas en el mensaje */}
                              {msg.images && msg.images.length > 0 && (
                                <div className="flex flex-wrap gap-2 mb-2">
                                  {msg.images.map((imgUrl, imgIdx) => (
                                    <img 
                                      key={imgIdx} 
                                      src={imgUrl} 
                                      alt={`adjunto-${imgIdx}`}
                                      className="max-h-56 max-w-full rounded-lg object-contain border border-white/20 shadow-sm" 
                                    />
                                  ))}
                                </div>
                              )}
                              <MarkdownRenderer isDark={theme === 'dark'}>
                                {msg.text}
                              </MarkdownRenderer>
                            </div>
                          )}

                          {/* Approval Request */}
                          {msg.approval_request && (
                            <ApprovalDialog
                              request={msg.approval_request}
                              onApprove={async (id, tool_call_id) => {
                                try {
                                  await fetch(`/api/approval/${tool_call_id}`, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ tool_call_id, action: 'approve', status: 'approved' })
                                  });
                                } catch (err) {
                                  console.error('Error al aprobar:', err);
                                }
                              }}
                              onReject={async (id, tool_call_id) => {
                                try {
                                  await fetch(`/api/approval/${tool_call_id}`, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ tool_call_id, action: 'reject', status: 'rejected' })
                                  });
                                } catch (err) {
                                  console.error('Error al rechazar:', err);
                                }
                              }}
                            />
                          )}

                          {/* Diff Card */}
                          {msg.diff && (
                            <AppliedDiffCard 
                              diff={{
                                filePath: msg.diff.filePath,
                                toolName: msg.diff.toolName,
                                additions: msg.diff.additions,
                                deletions: msg.diff.deletions,
                                diffContent: msg.diff.diffContent
                              }}
                              defaultExpanded={true}
                            />
                          )}

                          {/* Command Output */}
                          {msg.command && (
                            <div className="mt-3 rounded-xl chat-card font-mono text-xs overflow-hidden border">
                              <div className="px-3 py-1.5 opacity-80 border-b border-inherit flex justify-between items-center">
                                <span>$ {msg.command}</span>
                                <button onClick={() => copyToClipboard(msg.command!, msg.id)} className="text-[10px] hover:underline">
                                  {copiedId === msg.id ? 'Copiado' : 'Copiar'}
                                </button>
                              </div>
                              {msg.output && (
                                <div className="p-3 text-emerald-400 bg-black/30 whitespace-pre-wrap">{msg.output}</div>
                              )}
                              {msg.error && (
                                <div className="p-3 text-rose-400 bg-black/30 whitespace-pre-wrap">{msg.error}</div>
                              )}
                            </div>
                          )}

                          {/* Interactive Terminal */}
                          {msg.terminal && (
                            <InteractiveTerminal
                              session_id={msg.terminal.session_id}
                              initialOutput={msg.terminal.output}
                              onOutput={(output) => console.log('Terminal output:', output)}
                            />
                          )}
                        </div>
                      </div>
                    ))}
                    {isGenerating && (
                      <div className="flex space-x-4">
                        <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-white shrink-0 font-bold text-xs animate-pulse">
                          K
                        </div>
                        <div className="flex flex-col space-y-2">
                          {/* Tool Execution Indicators insertados directamente en el flujo del chat */}
                          {Object.keys(activeToolExecutions).length > 0 && (
                            <ToolIndicators
                              executions={Object.values(activeToolExecutions)}
                            />
                          )}
                          <div className="flex items-center space-x-2 opacity-55 text-xs py-2">
                            <div className="w-2 h-2 rounded-full bg-current animate-bounce" />
                            <div className="w-2 h-2 rounded-full bg-current animate-bounce delay-100" />
                            <div className="w-2 h-2 rounded-full bg-current animate-bounce delay-200" />
                          </div>
                        </div>
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </div>
                </div>

                {/* Input Inferior en Chat Activo */}
                <div className="p-4 bg-inherit">
                  {/* Previsualización de imágenes en chat activo */}
                  {attachedImages.length > 0 && (
                    <div className="max-w-3xl mx-auto flex flex-wrap gap-2 mb-2 px-2">
                      {attachedImages.map((img, idx) => (
                        <div key={idx} className="relative group">
                          <img src={img} alt={`adjunto-${idx}`} className="w-14 h-14 object-cover rounded-xl border border-indigo-500/30 shadow-md" />
                          <button
                            type="button"
                            onClick={() => setAttachedImages(prev => prev.filter((_, i) => i !== idx))}
                            className="absolute -top-1.5 -right-1.5 p-0.5 rounded-full bg-rose-600 text-white shadow-md hover:bg-rose-500 transition-colors"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} className="max-w-3xl mx-auto relative">
                    <input 
                      type="file"
                      ref={fileInputRef}
                      onChange={handleImageFileSelect}
                      accept="image/*"
                      multiple
                      className="hidden"
                    />
                    <AutocompletePopup
                      inputValue={inputQuery}
                      workspaceFiles={workspaceFiles}
                      skillsList={skillsList}
                      isDark={theme === 'dark'}
                      onSelect={(completedText) => {
                        const words = inputQuery.split(/\s+/);
                        const last = words[words.length - 1] || '';
                        if (last.includes('@')) {
                          const prefix = last.substring(0, last.lastIndexOf('@'));
                          words[words.length - 1] = prefix + completedText;
                        } else if (last.includes('#')) {
                          const prefix = last.substring(0, last.lastIndexOf('#'));
                          words[words.length - 1] = prefix + completedText;
                        } else {
                          words[words.length - 1] = completedText;
                        }
                        setInputQuery(words.join(' ') + ' ');
                      }}
                      onClose={() => {}}
                    />
                    <input 
                      type="text"
                      value={inputQuery}
                      onChange={(e) => setInputQuery(e.target.value)}
                      onPaste={handlePaste}
                      placeholder={`Mensaje a ${selectedAgent} (/ comandos, @ archivos, pega una imagen)...`}
                      className="w-full chat-input-box rounded-2xl pl-11 pr-12 py-3.5 text-sm focus:outline-none transition-all shadow-lg"
                    />
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="absolute left-3 top-3 p-1 rounded-lg text-slate-400 hover:text-indigo-400 hover:bg-white/5 transition-all"
                      title="Adjuntar Imagen"
                    >
                      <ImageIcon className="w-4 h-4" />
                    </button>
                    <button 
                      type="submit"
                      disabled={(!inputQuery.trim() && attachedImages.length === 0) || isGenerating}
                      className="absolute right-2.5 top-2.5 p-2 rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-30 transition-colors shadow"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </form>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── VISTA TERMINAL ── */}
        {activeTab === 'terminal' && (
          <div className="flex-1 p-6 flex flex-col overflow-hidden">
            <div className="chat-card flex-1 rounded-2xl flex flex-col overflow-hidden shadow-xl">
              <div className="px-4 py-2.5 border-b border-inherit flex items-center justify-between text-xs font-mono opacity-80">
                <span>bash — kogniterm-daemon</span>
                <span className="text-emerald-500">● Conectado</span>
              </div>
              <div className="flex-1 bg-black/40 p-4 font-mono text-xs text-emerald-400 overflow-y-auto custom-scrollbar space-y-1">
                <p className="opacity-50"># Kogniterm Shell Emulator</p>
                <div className="flex items-center space-x-2 pt-2">
                  <span className="text-indigo-400">gato@gatoserv:~$</span>
                  <span className="animate-pulse bg-emerald-400 w-2 h-4 inline-block" />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── VISTA AGENTS ── */}
        {activeTab === 'agents' && (
          <AgentPanel 
            selectedAgent={selectedAgent}
            setSelectedAgent={setSelectedAgent}
          />
        )}

        {/* ── VISTA SKILLS ── */}
        {activeTab === 'skills' && (
          <div className="flex-1 p-8 overflow-y-auto custom-scrollbar">
            <div className="max-w-4xl mx-auto space-y-6">
              <h2 className="text-lg font-semibold">Skills Marketplace (`npx skills`)</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                  { name: 'frontend-design', author: 'anthropics/skills', installs: '875.1K' },
                  { name: 'design-taste-frontend', author: 'leonxlnx/taste-skill', installs: '465.9K' },
                  { name: 'react-best-practices', author: 'vercel-labs/agent-skills', installs: '185K' }
                ].map((s, idx) => (
                  <div key={idx} className="chat-card p-5 rounded-2xl flex flex-col justify-between space-y-4 text-xs">
                    <div>
                      <span className="text-[10px] font-mono text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded">{s.installs} installs</span>
                      <h3 className="font-bold mt-2 font-mono">{s.name}</h3>
                      <p className="opacity-70">{s.author}</p>
                    </div>
                    <button onClick={() => alert(`Instalando ${s.name}...`)} className="w-full py-2 chat-card rounded-lg font-medium hover:opacity-90 transition-all">
                      Instalar
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── VISTA TASKS ── */}
        {activeTab === 'tasks' && (
          <div className="flex-1 p-8 overflow-y-auto custom-scrollbar">
            <div className="max-w-4xl mx-auto space-y-6">
              <h2 className="text-lg font-semibold">Task Tracker - Planes de Trabajo</h2>
              <TaskTracker plans={taskPlans} isDark={theme === 'dark'} />
            </div>
          </div>
        )}

      </main>

      {/* Right Sidebar con pestañas Terminal / Task Tracker */}
      <RightSidebar
        isOpen={userOpenedRightSidebar || isTerminalOpen}
        onClose={closeRightSidebar}
        terminalState={terminalState}
        taskPlans={taskPlans}
        activeTab={rightSidebarTab}
        onTabChange={(tab) => setRightSidebarTab(tab)}
        isDark={theme === 'dark'}
      />

    </div>
  );
}
