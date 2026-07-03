import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Folder, Sparkles, Paperclip, Settings2, Square, ChevronDown, ChevronUp, X } from 'lucide-react';

interface ChatInputProps {
    onSendMessage: (message: string) => void;
    isGenerating: boolean;
    currentDir: string;
    onChangeDir: () => void;
    
    // Queue props
    messageQueue: string[];
    onRemoveFromQueue: (index: number) => void;
    onProcessNext: () => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({ 
    onSendMessage, 
    isGenerating, 
    currentDir, 
    onChangeDir,
    messageQueue,
    onRemoveFromQueue,
    onProcessNext
}) => {
    const [input, setInput] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const [isFocused, setIsFocused] = useState(false);
    const [isQueueExpanded, setIsQueueExpanded] = useState(true);

    const [showSuggestions, setShowSuggestions] = useState(false);
    const [suggestions, setSuggestions] = useState<{ command: string; desc: string }[]>([]);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [cursorOffset, setCursorOffset] = useState<{ top: number; left: number } | null>(null);

    const getCursorOffset = useCallback(() => {
        const textarea = textareaRef.current;
        if (!textarea) return null;
        
        try {
            const selectionStart = textarea.selectionStart;
            const mirror = document.createElement('div');
            const style = window.getComputedStyle(textarea);

            mirror.style.position = 'absolute';
            mirror.style.visibility = 'hidden';
            mirror.style.whiteSpace = 'pre-wrap';
            mirror.style.wordWrap = 'break-word';
            mirror.style.width = style.width;
            mirror.style.fontSize = style.fontSize;
            mirror.style.fontFamily = style.fontFamily;
            mirror.style.lineHeight = style.lineHeight;
            mirror.style.padding = style.padding;
            mirror.style.boxSizing = style.boxSizing;

            const textBeforeCursor = textarea.value.substring(0, selectionStart);
            mirror.textContent = textBeforeCursor;

            const marker = document.createElement('span');
            marker.textContent = '|';
            mirror.appendChild(marker);

            document.body.appendChild(mirror);
            const markerRect = marker.getBoundingClientRect();
            const mirrorRect = mirror.getBoundingClientRect();
            document.body.removeChild(mirror);

            return {
                top: markerRect.top - mirrorRect.top,
                left: markerRect.left - mirrorRect.left,
            };
        } catch (e) {
            console.error("Error calculating cursor offset", e);
            return null;
        }
    }, []);

    const updateCursorPosition = useCallback(() => {
        const offset = getCursorOffset();
        if (offset) {
            setCursorOffset(offset);
        }
    }, [getCursorOffset]);

    const handleSubmit = (e?: React.FormEvent) => {
        e?.preventDefault();
        if (input.trim()) {
            onSendMessage(input.trim());
            setInput('');
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
            }
            setShowSuggestions(false);
        }
    };

    const COMMANDS = [
        { command: '%reset', desc: 'Reiniciar conversación (Borrar memoria)' },
        { command: '%undo', desc: 'Deshacer última interacción' },
        { command: '%models', desc: 'Cambiar modelo de IA' },
        { command: '%provider', desc: 'Cambiar proveedor de LLM' },
        { command: '%theme', desc: 'Cambiar tema de la terminal' },
        { command: '%help', desc: 'Mostrar menú de ayuda' },
        { command: '%keys', desc: 'Gestionar API Keys' },
        { command: '%session', desc: 'Gestión de sesiones (save/load/list)' },
        { command: '%param', desc: 'Ver/Editar parámetros de configuración (Global)' },
        { command: '%init', desc: 'Inicializar contexto del espacio de trabajo' },
        { command: '%compress', desc: 'Comprimir historial de conversación' },
        { command: '%embeddings', desc: 'Configurar motor de embeddings' },
        { command: '%salir', desc: 'Salir de la aplicación' },
    ];

    const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        const value = e.target.value;
        setInput(value);

        const cursorPosition = e.target.selectionStart;
        const textBeforeCursor = value.substring(0, cursorPosition);
        const match = textBeforeCursor.match(/([%/])(\w*)$/);

        if (match) {
            const query = match[2].toLowerCase();
            const filtered = COMMANDS.filter(c =>
                c.command.toLowerCase().includes(query) || 
                c.desc.toLowerCase().includes(query)
            );

            if (filtered.length > 0) {
                setSuggestions(filtered);
                setShowSuggestions(true);
                setSelectedIndex(0);
                requestAnimationFrame(updateCursorPosition);
                return;
            }
        }
        setShowSuggestions(false);
    };

    const handleSelectCommand = (cmd: string) => {
        const cursorPosition = textareaRef.current?.selectionStart || 0;
        const textBeforeCursor = input.substring(0, cursorPosition);
        const textAfterCursor = input.substring(cursorPosition);
        
        const newValue = textBeforeCursor.replace(/([%/])(\w*)$/, cmd + ' ') + textAfterCursor;
        setInput(newValue);
        setShowSuggestions(false);
        
        setTimeout(() => {
            if (textareaRef.current) {
                textareaRef.current.focus();
                const newPos = textBeforeCursor.replace(/([%/])(\w*)$/, cmd + ' ').length;
                textareaRef.current.setSelectionRange(newPos, newPos);
            }
        }, 0);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (showSuggestions) {
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                setSelectedIndex(prev => (prev > 0 ? prev - 1 : suggestions.length - 1));
                return;
            }
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setSelectedIndex(prev => (prev < suggestions.length - 1 ? prev + 1 : 0));
                return;
            }
            if (e.key === 'Tab' || e.key === 'Enter') {
                e.preventDefault();
                handleSelectCommand(suggestions[selectedIndex].command);
                return;
            }
            if (e.key === 'Escape') {
                setShowSuggestions(false);
                return;
            }
        }

        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = '0px';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
        }
    }, [input]);

    // Folder basename
    const getFolderBasename = (path: string) => {
        if (!path) return 'workspace';
        const parts = path.split('/');
        return parts[parts.length - 1] || path;
    };

    return (
        <div className="w-full max-w-3xl mx-auto px-4 pb-4 absolute bottom-0 left-0 right-0 z-50 flex flex-col gap-2">
            
            {/* Message Queue Panel */}
            {messageQueue.length > 0 && (
                <div className="w-full bg-[#121214] border border-zinc-800/80 rounded-xl shadow-2xl overflow-hidden transition-all duration-300">
                    <button 
                        onClick={() => setIsQueueExpanded(!isQueueExpanded)}
                        className="w-full flex items-center justify-between px-4 py-2 bg-zinc-950/60 border-b border-zinc-900 text-xs font-semibold text-zinc-400 hover:text-zinc-300 transition-colors"
                    >
                        <div className="flex items-center gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
                            <span>Message Queue</span>
                            <span className="text-[10px] text-zinc-500 font-normal">
                                ({messageQueue.length} {messageQueue.length === 1 ? 'message' : 'messages'} queued)
                            </span>
                        </div>
                        {isQueueExpanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                    </button>

                    {isQueueExpanded && (
                        <div className="p-3 max-h-40 overflow-y-auto custom-scrollbar flex flex-col gap-2 bg-[#121214]/90">
                            {messageQueue.map((msg, index) => (
                                <div key={index} className="flex items-center justify-between bg-zinc-900/60 border border-zinc-800/40 rounded-lg p-2.5 text-xs text-zinc-300">
                                    <div className="flex items-center gap-3 min-w-0 flex-1">
                                        <div className="flex items-center justify-center h-5 w-5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 font-bold text-[10px]">
                                            {index + 1}
                                        </div>
                                        <span className="truncate pr-4">{msg}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {index === 0 && (
                                            <button 
                                                onClick={onProcessNext}
                                                className="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-[10px] font-bold transition-all"
                                            >
                                                Next
                                            </button>
                                        )}
                                        <button 
                                            onClick={() => onRemoveFromQueue(index)}
                                            className="p-1 hover:bg-zinc-800 rounded text-zinc-500 hover:text-red-400 transition-all"
                                        >
                                            <X size={12} />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Command Suggestions Menu */}
            {showSuggestions && (
                <div
                    className="absolute z-[100] bg-[#16161a] border border-zinc-800 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.6)] overflow-hidden transition-all duration-200"
                    style={{
                        bottom: 'calc(100% + 12px)',
                        left: cursorOffset ? `${Math.min(Math.max(cursorOffset.left + 52, 16), 400)}px` : '50%',
                        transform: cursorOffset ? 'none' : 'translateX(-50%)',
                        width: 'min(350px, calc(100vw - 32px))',
                        opacity: 1,
                        visibility: 'visible',
                    }}
                >
                    <div className="max-h-60 overflow-y-auto custom-scrollbar p-1.5">
                        <div className="px-2 py-1 text-[10px] font-bold text-zinc-500 uppercase tracking-wider">
                            Comandos Disponibles
                        </div>
                        {suggestions.map((cmd, index) => (
                            <button
                                key={cmd.command}
                                onClick={() => handleSelectCommand(cmd.command)}
                                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-colors ${index === selectedIndex
                                    ? 'bg-indigo-500/10 text-indigo-300'
                                    : 'text-zinc-400 hover:bg-zinc-900'
                                    }`}
                            >
                                <span className="font-mono font-medium">{cmd.command}</span>
                                <span className="text-zinc-500 text-[10px]">{cmd.desc}</span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Main Input Form */}
            <div className={`relative transition-all duration-300 ${isFocused ? 'scale-[1.005]' : ''}`}>
                <div className={`absolute -inset-0.5 bg-gradient-to-r from-indigo-500/10 via-purple-500/10 to-pink-500/10 rounded-2xl opacity-20 blur transition duration-500 ${isFocused ? 'opacity-40' : ''}`}></div>

                <form
                    onSubmit={handleSubmit}
                    className={`relative flex flex-col bg-[#16161a] border border-zinc-800/80 rounded-2xl p-1 px-1.5 shadow-2xl transition-all ${isFocused ? 'border-zinc-700/60' : ''}`}
                >
                    <div className="flex items-start gap-1 p-1">
                        <textarea
                            ref={textareaRef}
                            value={input}
                            onChange={handleInputChange}
                            onKeyDown={handleKeyDown}
                            onFocus={() => setIsFocused(true)}
                            onBlur={() => {
                                setTimeout(() => setIsFocused(false), 200);
                            }}
                            placeholder="Pregúntame algo sobre tu código... (Usa % para comandos)"
                            rows={1}
                            className="flex-1 bg-transparent text-zinc-100 placeholder-zinc-500 px-3 py-2 focus:outline-none resize-none min-h-[40px] max-h-[140px] text-sm leading-6"
                        />

                        {input.trim() && (
                            <button
                                type="submit"
                                className="h-8 w-8 rounded-lg flex items-center justify-center bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/25 transition-all mt-1"
                            >
                                <Send size={14} className="translate-x-0.5" />
                            </button>
                        )}
                    </div>

                    {/* Divider */}
                    <div className="border-t border-zinc-900/80 mx-2 my-0.5"></div>

                    {/* Status Bar */}
                    <div className="flex items-center justify-between px-3 py-1.5 text-xs text-zinc-500">
                        <div className="flex items-center gap-3">
                            {/* Model selection pill */}
                            <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-zinc-900/60 border border-zinc-800/40 text-[10px] text-zinc-400 font-mono hover:bg-zinc-900 hover:text-zinc-300 transition-colors cursor-pointer select-none">
                                <Sparkles size={10} className="text-indigo-400" />
                                gemini-3.5-flash
                            </span>

                            {/* Active Directory Label */}
                            <button 
                                type="button"
                                onClick={onChangeDir}
                                className="flex items-center gap-1.5 px-1 py-0.5 hover:text-zinc-300 transition-colors max-w-[180px] truncate"
                                title="Cambiar directorio de trabajo"
                            >
                                <Folder size={11} className="text-zinc-500" />
                                <span className="truncate">{getFolderBasename(currentDir)}</span>
                            </button>
                        </div>

                        <div className="flex items-center gap-3">
                            {/* Cost/Tokens mock/placeholder */}
                            <span className="font-mono text-[10px] tracking-wide select-none">
                                0.0000 • 51k / 128k
                            </span>

                            {/* Utility Buttons */}
                            <div className="flex items-center gap-1.5 border-l border-zinc-900 pl-3">
                                <button
                                    type="button"
                                    className="p-1 hover:bg-zinc-900 rounded text-zinc-500 hover:text-zinc-300 transition-all"
                                    title="Adjuntar archivo"
                                >
                                    <Paperclip size={13} />
                                </button>
                                <button
                                    type="button"
                                    className="p-1 hover:bg-zinc-900 rounded text-zinc-500 hover:text-zinc-300 transition-all"
                                    title="Configuración de agente"
                                >
                                    <Settings2 size={13} />
                                </button>
                                
                                {/* Processing State Indicator / Stop Button */}
                                {isGenerating ? (
                                    <button
                                        type="button"
                                        className="h-5 w-5 rounded bg-red-600 hover:bg-red-500 flex items-center justify-center text-white transition-all animate-pulse"
                                        title="Detener respuesta"
                                    >
                                        <Square size={8} fill="white" className="text-white" />
                                    </button>
                                ) : (
                                    <div className="w-5 h-5 flex items-center justify-center">
                                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </form>
            </div>
            
            <p className="text-center text-[10px] text-zinc-600 font-medium tracking-wide">
                KogniTerm AI puede cometer errores. Verifica el código generado.
            </p>
        </div>
    );
};
