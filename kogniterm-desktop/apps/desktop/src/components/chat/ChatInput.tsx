import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Sparkles, StopCircle } from 'lucide-react';

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

        // Detect command trigger
        const match = value.match(/([%/])(\w*)$/);
        if (match) {
            const prefix = match[1];
            const query = match[2].toLowerCase();
            const filtered = COMMANDS.filter(c =>
                c.command.replace('%', '').toLowerCase().startsWith(query)
            );

            if (filtered.length > 0) {
                setSuggestions(filtered);
                setShowSuggestions(true);
                setSelectedIndex(0);
                return;
            }
        }
        setShowSuggestions(false);
    };

    const handleSelectCommand = (cmd: string) => {
        const newValue = input.replace(/([%/])(\w*)$/, cmd + ' ');
        setInput(newValue);
        setShowSuggestions(false);
        if (textareaRef.current) {
            textareaRef.current.focus();
        }
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
            textareaRef.current.style.height = 'inherit';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
        }
    }, [input]);

    return (
        <div className="w-full max-w-3xl mx-auto px-4 pb-6 absolute bottom-0 left-0 right-0 z-50">
            {/* Command Suggestions Menu */}
            {showSuggestions && (
                <div className="absolute bottom-full left-4 right-4 mb-2 bg-[#18181b] border border-zinc-700/50 rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-bottom-2 duration-200">
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
