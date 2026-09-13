import React, { useState, useRef, useEffect } from 'react';
import { Terminal as TerminalIcon, Maximize2, Minimize2 } from 'lucide-react';

interface TerminalSession {
  session_id: string;
  output: string;
  interactive: boolean;
}

interface InteractiveTerminalProps {
  session_id: string;
  initialOutput?: string;
  onOutput: (output: string) => void;
  onClose?: () => void;
}

export function InteractiveTerminal({ session_id, initialOutput = '', onOutput, onClose }: InteractiveTerminalProps) {
  const [output, setOutput] = useState(initialOutput);
  const [input, setInput] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const terminalRef = useRef<HTMLDivElement>(null);

  // Connect to WebSocket for real-time terminal output
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/terminal/${session_id}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.output) {
          setOutput(prev => prev + data.output);
          onOutput(data.output);
        }
      } catch (e) {
        setOutput(prev => prev + event.data);
      }
    };

    ws.onerror = (error) => {
      console.error('Terminal WebSocket error:', error);
      setIsConnected(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [session_id, onOutput]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [output]);

  const handleInput = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    // Send command to backend
    wsRef.current.send(JSON.stringify({ input: input.trim() }));
    
    // Add command to output
    setOutput(prev => prev + `\n$ ${input}\n`);
    setInput('');
  };

  return (
    <div className={`w-full my-3 overflow-hidden rounded-xl border border-inherit chat-card shadow-sm transition-all ${isExpanded ? 'max-h-[70vh]' : 'max-h-96'}`}>
      {/* Header */}
      <div className="flex items-center justify-between gap-3 bg-black/20 px-3.5 py-2.5 border-b border-inherit">
        <div className="flex items-center gap-2.5">
          <TerminalIcon className="w-4 h-4 text-emerald-500" />
          <span className="font-mono text-xs">bash — {session_id.slice(0, 8)}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${isConnected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
            {isConnected ? 'Conectado' : 'Desconectado'}
          </span>
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="p-1.5 rounded-lg hover:opacity-100 opacity-70 transition-opacity"
          title={isExpanded ? 'Colapsar' : 'Expandir'}
        >
          {isExpanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Terminal Output */}
      <div 
        ref={terminalRef}
        className="overflow-y-auto bg-black/40 p-4 font-mono text-xs text-emerald-400 custom-scrollbar"
        style={{ height: isExpanded ? 'calc(70vh - 60px)' : '300px' }}
      >
        <div className="whitespace-pre-wrap break-words">
          {output}
        </div>

        {/* Input Line (only when connected) */}
        {isConnected && (
          <form onSubmit={handleInput} className="flex items-center gap-2 mt-2">
            <span className="text-indigo-400 font-medium">gato@gatoserv:~$</span>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="flex-1 bg-transparent border-none outline-none text-emerald-400 font-mono text-xs"
              autoFocus
              placeholder="Escribe un comando..."
            />
          </form>
        )}

        {!isConnected && (
          <div className="text-center py-4 text-rose-400 text-xs">
            Conexión perdida. Intenta reconectar más tarde.
          </div>
        )}
      </div>
    </div>
  );
}