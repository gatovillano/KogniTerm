import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, Sparkles } from 'lucide-react';

interface ChatInputProps {
    onSendMessage: (message: string) => void;
    isGenerating: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSendMessage, isGenerating }) => {
    const [input, setInput] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const [isFocused, setIsFocused] = useState(false);

    const [showSuggestions, setShowSuggestions] = useState(false);
    const [suggestions, setSuggestions] = useState<{ command: string; desc: string }[]>([]);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [cursorOffset, setCursorOffset] = useState<{ top: number; left: number } | null>(null);

    const getCursorOffset = useCallback(() => {
        const textarea = textareaRef.current;
        if (!textarea) return null;
        
        try {
            const selectionStart = textarea.selectionStart;

            // Create a hidden mirror div to measure text
            const mirror = document.createElement('div');
            const style = window.getComputedStyle(textarea);

            // Copy all relevant styles
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

            // Insert text up to cursor with a marker span
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
        if (input.trim() && !isGenerating) {
            onSendMessage(input.trim());
            setInput('');
            // Reset height
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

        // Detect command trigger at the current cursor position
        // We look for % or / followed by word characters until the cursor
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
                // Update position relative to the cursor if possible, 
                // but we'll use a more stable fallback
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
        
        // Focus back and set cursor position after the inserted command
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
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
        }
    }, [input]);

    return (
        <div className="w-full max-w-3xl mx-auto px-4 pb-6 absolute bottom-0 left-0 right-0 z-50">
            {/* Processing Indicator */}
            {isGenerating && (
                <div className="flex items-center gap-2 mb-3 px-2 animate-fade-in">
                    <div className="flex items-center justify-center h-5 w-5 rounded-full bg-indigo-500/10 border border-indigo-500/20 shadow-sm shadow-indigo-500/10">
                        <Loader2 className="animate-spin text-indigo-400" size={12} />
                    </div>
                    <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-[0.15em] drop-shadow-[0_0_8px_rgba(99,102,241,0.3)]">
                        Procesando
                    </span>
                    <div className="flex gap-1 ml-1">
                        <span className="w-1 h-1 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                        <span className="w-1 h-1 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                        <span className="w-1 h-1 bg-indigo-500 rounded-full animate-bounce"></span>
                    </div>
                </div>
            )}

            {/* Command Suggestions Menu */}
            {showSuggestions && (
                <div
                    className="absolute z-[100] bg-[#18181b] border border-zinc-700/50 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.6)] overflow-hidden transition-all duration-200"
                    style={{
                        bottom: 'calc(100% + 16px)',
                        left: cursorOffset ? `${Math.min(Math.max(cursorOffset.left + 52, 16), 400)}px` : '50%',
                        transform: cursorOffset ? 'none' : 'translateX(-50%)',
                        width: 'min(350px, calc(100vw - 32px))',
                        opacity: 1,
                        visibility: 'visible',
                    }}
                >
                    <div className="max-h-60 overflow-y-auto custom-scrollbar p-1.5">
                        <div className="px-2 py-1.5 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                            Comandos Disponibles
                        </div>
                        {suggestions.map((cmd, index) => (
                            <button
                                key={cmd.command}
                                onClick={() => handleSelectCommand(cmd.command)}
                                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm transition-colors ${index === selectedIndex
                                    ? 'bg-indigo-500/10 text-indigo-300'
                                    : 'text-zinc-300 hover:bg-zinc-800'
                                    }`}
                            >
                                <span className="font-mono font-medium">{cmd.command}</span>
                                <span className="text-zinc-500 text-xs">{cmd.desc}</span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            <div className={`relative transition-all duration-300 ${isFocused ? 'scale-[1.01]' : ''}`}>
                {/* Glow Effect */}
                <div className={`absolute -inset-0.5 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-2xl opacity-20 blur transition duration-500 ${isFocused ? 'opacity-50' : ''}`}></div>

                <form
                    onSubmit={handleSubmit}
                    className={`relative flex items-end gap-2 bg-[#18181b] border border-zinc-700/50 rounded-2xl p-2 shadow-2xl transition-all ${isFocused ? 'border-indigo-500/30' : ''}`}
                >
                    <div className="pl-3 pb-3 text-zinc-400">
                        <Sparkles size={18} className={isFocused ? 'text-indigo-400' : ''} />
                    </div>

                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={handleInputChange}
                        onKeyDown={handleKeyDown}
                        onFocus={() => setIsFocused(true)}
                        onBlur={() => {
                            // Delay hiding to allow click events on suggestions
                            setTimeout(() => setIsFocused(false), 200);
                        }}
                        placeholder="Pregúntame algo sobre tu código... (Usa % para comandos)"
                        rows={1}
                        className="flex-1 bg-transparent text-zinc-100 placeholder-zinc-500 px-3 py-2.5 focus:outline-none resize-none min-h-[44px] max-h-[200px] text-[15px] leading-6"
                        disabled={isGenerating}
                    />

                    <button
                        type="submit"
                        disabled={!input.trim() || isGenerating}
                        className={`h-10 w-10 rounded-xl flex items-center justify-center transition-all duration-300 ${input.trim() && !isGenerating
                            ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/25'
                            : 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                            }`}
                    >
                        {isGenerating ? (
                            <Loader2 className="animate-spin" size={18} />
                        ) : (
                            <Send size={18} className={input.trim() ? "translate-x-0.5 text-white" : ""} />
                        )}
                    </button>
                </form>
            </div>

            <p className="text-center text-[11px] text-zinc-600 mt-3 font-medium tracking-wide">
                KogniTerm AI puede cometer errores. Verifica el código generado.
            </p>
        </div>
    );
};
