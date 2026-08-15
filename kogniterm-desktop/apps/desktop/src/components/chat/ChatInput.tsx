import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Folder, Sparkles, Paperclip, Square, ChevronDown, ChevronUp, X, ArrowUp, Zap, Box, FileText, Terminal } from 'lucide-react';

interface ChatInputProps {
    onSendMessage: (message: string, images?: string[]) => void;
    isGenerating: boolean;
    onStopGeneration?: () => void;
    currentDir: string;
    onChangeDir: () => void;
    onOpenSettings?: () => void;
    
    // Queue props
    messageQueue: string[];
    onRemoveFromQueue: (index: number) => void;
    onProcessNext: () => void;
    isFloating?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ 
    onSendMessage, 
    isGenerating, 
    onStopGeneration,
    currentDir, 
    onChangeDir,
    onOpenSettings,
    messageQueue,
    onRemoveFromQueue,
    onProcessNext,
    isFloating = false
}) => {
    const [input, setInput] = useState('');
    const [attachedImages, setAttachedImages] = useState<string[]>([]);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const [isFocused, setIsFocused] = useState(false);
    const [isQueueExpanded, setIsQueueExpanded] = useState(true);
    const [configuredModel, setConfiguredModel] = useState<string>('gemini/gemini-1.5-flash');

    useEffect(() => {
        const fetchConfiguredModel = async () => {
            try {
                const res = await fetch('http://localhost:8765/api/config/all');
                if (res.ok) {
                    const data = await res.json();
                    const model = data.merged?.default_model || 'gemini/gemini-1.5-flash';
                    setConfiguredModel(model);
                }
            } catch (err) {
                console.error("Error al obtener modelo configurado:", err);
            }
        };
        fetchConfiguredModel();

        const handleConfigUpdated = () => {
            fetchConfiguredModel();
        };
        window.addEventListener('kogniterm-config-updated', handleConfigUpdated);
        return () => {
            window.removeEventListener('kogniterm-config-updated', handleConfigUpdated);
        };
    }, []);

    interface SuggestionItem {
        id: string;
        label: string;
        desc: string;
        type: 'command' | 'skill' | 'file';
        scope?: string;
        meta?: string;
        insertValue: string;
    }

    const [showSuggestions, setShowSuggestions] = useState(false);
    const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [cursorOffset, setCursorOffset] = useState<{ top: number; left: number } | null>(null);
    const [activeTrigger, setActiveTrigger] = useState<'@' | '#' | '/' | '%' | null>(null);
    const [cachedSkills, setCachedSkills] = useState<SuggestionItem[]>([]);

    useEffect(() => {
        const fetchSkills = async () => {
            try {
                const res = await fetch('http://127.0.0.1:8765/api/skills');
                if (res.ok) {
                    const data = await res.json();
                    const items: SuggestionItem[] = (data.skills || []).map((s: any) => ({
                        id: `skill-${s.name}`,
                        label: `#${s.name}`,
                        desc: s.description || 'Skill personalizada',
                        type: 'skill',
                        scope: s.scope || 'global',
                        insertValue: `#${s.name} `
                    }));
                    setCachedSkills(items);
                }
            } catch (err) {
                console.error('Error cargando skills para autocompletado:', err);
            }
        };
        fetchSkills();
    }, []);

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

    const handleFiles = useCallback((files: FileList | File[]) => {
        Array.from(files).forEach((file) => {
            if (!file.type.startsWith('image/')) return;
            const reader = new FileReader();
            reader.onload = (e) => {
                const result = e.target?.result as string;
                if (result) {
                    setAttachedImages((prev) => [...prev, result]);
                }
            };
            reader.readAsDataURL(file);
        });
    }, []);

    const handlePaste = useCallback((e: React.ClipboardEvent<HTMLTextAreaElement>) => {
        const items = e.clipboardData.items;
        const imageFiles: File[] = [];
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.startsWith('image/')) {
                const file = items[i].getAsFile();
                if (file) imageFiles.push(file);
            }
        }
        if (imageFiles.length > 0) {
            handleFiles(imageFiles);
        }
    }, [handleFiles]);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files);
        }
    }, [handleFiles]);

    const handleSubmit = (e?: React.FormEvent) => {
        e?.preventDefault();
        if (input.trim() || attachedImages.length > 0) {
            onSendMessage(input.trim(), attachedImages);
            setInput('');
            setAttachedImages([]);
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
            }
            setShowSuggestions(false);
            setActiveTrigger(null);
        }
    };

    const COMMAND_DEFS = [
        { name: 'clear', desc: 'Limpiar conversación actual en pantalla' },
        { name: 'reset', desc: 'Reiniciar conversación (borrar memoria)' },
        { name: 'compact', desc: 'Comprimir historial de conversación' },
        { name: 'undo', desc: 'Deshacer última interacción' },
        { name: 'skills', desc: 'Ver habilidades (skills) disponibles' },
        { name: 'plan', desc: 'Ver o activar modo planificación' },
        { name: 'models', desc: 'Cambiar modelo de IA' },
        { name: 'provider', desc: 'Cambiar proveedor de LLM' },
        { name: 'help', desc: 'Mostrar menú de ayuda' },
        { name: 'session', desc: 'Gestión de hilos y sesiones (save/load/list)' },
        { name: 'resume', desc: 'Reanudar un hilo/sesión específico' },
        { name: 'init', desc: 'Inicializar contexto e indexar espacio de trabajo' },
        { name: 'theme', desc: 'Cambiar tema de la interfaz' },
        { name: 'keys', desc: 'Gestionar API Keys' },
        { name: 'param', desc: 'Ver/Editar parámetros de configuración' },
        { name: 'embeddings', desc: 'Configurar motor de embeddings' },
        { name: 'salir', desc: 'Salir de la aplicación' },
    ];

    const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        const value = e.target.value;
        setInput(value);

        const cursorPosition = e.target.selectionStart;
        const textBeforeCursor = value.substring(0, cursorPosition);

        // 1. Skill trigger: #
        const skillMatch = textBeforeCursor.match(/#([a-zA-Z0-9_-]*)$/);
        if (skillMatch) {
            const query = skillMatch[1].toLowerCase();
            const filtered = cachedSkills.filter(s =>
                s.label.toLowerCase().includes(query) || 
                s.desc.toLowerCase().includes(query)
            );
            if (filtered.length > 0) {
                setSuggestions(filtered);
                setShowSuggestions(true);
                setActiveTrigger('#');
                setSelectedIndex(0);
                requestAnimationFrame(updateCursorPosition);
                return;
            }
        }

        // 2. File trigger: @
        const fileMatch = textBeforeCursor.match(/@([^\s@]*)$/);
        if (fileMatch) {
            const query = fileMatch[1];
            setActiveTrigger('@');
            setShowSuggestions(true);
            setSelectedIndex(0);
            requestAnimationFrame(updateCursorPosition);

            fetch(`http://127.0.0.1:8765/api/workspace/files?query=${encodeURIComponent(query)}`)
                .then(res => res.ok ? res.json() : { results: [] })
                .then(data => {
                    const items: SuggestionItem[] = (data.results || []).map((f: any) => ({
                        id: `file-${f.path}`,
                        label: `@${f.path}`,
                        desc: f.is_dir ? 'Carpeta' : f.meta || 'Archivo',
                        type: 'file',
                        meta: f.meta,
                        insertValue: `@${f.path} `
                    }));
                    setSuggestions(items);
                    if (items.length === 0) {
                        setShowSuggestions(false);
                    }
                })
                .catch(err => {
                    console.error('Error buscando archivos:', err);
                    setSuggestions([]);
                });
            return;
        }

        // 3. Command trigger: % or /
        const cmdMatch = textBeforeCursor.match(/([%/])(\w*)$/);
        if (cmdMatch) {
            const triggerChar = cmdMatch[1];
            const query = cmdMatch[2].toLowerCase();
            const items: SuggestionItem[] = COMMAND_DEFS.map(c => {
                const fullCmd = `${triggerChar}${c.name}`;
                return {
                    id: `cmd-${fullCmd}`,
                    label: fullCmd,
                    desc: c.desc,
                    type: 'command' as const,
                    insertValue: `${fullCmd} `
                };
            }).filter(c =>
                c.label.toLowerCase().includes(query) || 
                c.desc.toLowerCase().includes(query)
            );

            if (items.length > 0) {
                setSuggestions(items);
                setShowSuggestions(true);
                setActiveTrigger(triggerChar as '%' | '/');
                setSelectedIndex(0);
                requestAnimationFrame(updateCursorPosition);
                return;
            }
        }

        setShowSuggestions(false);
        setActiveTrigger(null);
    };

    const handleSelectSuggestion = (item: SuggestionItem) => {
        const cursorPosition = textareaRef.current?.selectionStart || 0;
        const textBeforeCursor = input.substring(0, cursorPosition);
        const textAfterCursor = input.substring(cursorPosition);
        
        let regex: RegExp;
        if (activeTrigger === '#') {
            regex = /#([a-zA-Z0-9_-]*)$/;
        } else if (activeTrigger === '@') {
            regex = /@([^\s@]*)$/;
        } else {
            regex = /([%/])(\w*)$/;
        }

        const newTextBefore = textBeforeCursor.replace(regex, item.insertValue);
        const newValue = newTextBefore + textAfterCursor;
        setInput(newValue);
        setShowSuggestions(false);
        setActiveTrigger(null);
        
        setTimeout(() => {
            if (textareaRef.current) {
                textareaRef.current.focus();
                const newPos = newTextBefore.length;
                textareaRef.current.setSelectionRange(newPos, newPos);
            }
        }, 0);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (showSuggestions && suggestions.length > 0) {
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
                handleSelectSuggestion(suggestions[selectedIndex]);
                return;
            }
            if (e.key === 'Escape') {
                setShowSuggestions(false);
                setActiveTrigger(null);
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
        if (!path) return 'Contabilidad';
        const parts = path.split('/');
        const name = parts[parts.length - 1] || path;
        return name === '.' || name === '~' ? 'Contabilidad' : name;
    };

    const containerStyleClass = isFloating
        ? "w-full max-w-xl mx-auto flex flex-col gap-2 relative z-50"
        : "w-full max-w-3xl mx-auto px-4 pb-4 absolute bottom-0 left-0 right-0 z-50 flex flex-col gap-2";

    return (
        <div className={containerStyleClass}>
            
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

            {/* Command & Skills & Files Suggestions Menu */}
            {showSuggestions && suggestions.length > 0 && (
                <div
                    className="absolute z-[100] bg-[#16161a] border border-zinc-800 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.6)] overflow-hidden transition-all duration-200"
                    style={{
                        bottom: 'calc(100% + 12px)',
                        left: cursorOffset ? `${Math.min(Math.max(cursorOffset.left + 52, 16), 400)}px` : '50%',
                        transform: cursorOffset ? 'none' : 'translateX(-50%)',
                        width: 'min(380px, calc(100vw - 32px))',
                        opacity: 1,
                        visibility: 'visible',
                    }}
                >
                    <div className="max-h-64 overflow-y-auto custom-scrollbar p-1.5">
                        <div className="px-2 py-1 text-[10px] font-bold text-zinc-500 uppercase tracking-wider flex items-center justify-between">
                            <span>
                                {activeTrigger === '#' && '⚡ Skills Disponibles'}
                                {activeTrigger === '@' && '📁 Archivos del Workspace'}
                                {(activeTrigger === '/' || activeTrigger === '%') && '💻 Comandos del Sistema'}
                            </span>
                            <span className="text-[9px] text-zinc-600 font-mono">↑↓ para navegar</span>
                        </div>
                        {suggestions.map((item, index) => (
                            <button
                                key={item.id}
                                type="button"
                                onClick={() => handleSelectSuggestion(item)}
                                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-colors ${index === selectedIndex
                                    ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/30'
                                    : 'text-zinc-300 hover:bg-zinc-900 border border-transparent'
                                    }`}
                            >
                                <div className="flex items-center gap-2.5 min-w-0 pr-2">
                                    {item.type === 'skill' && <Zap size={13} className="text-yellow-400 shrink-0" />}
                                    {item.type === 'file' && <FileText size={13} className="text-blue-400 shrink-0" />}
                                    {item.type === 'command' && <Terminal size={13} className="text-emerald-400 shrink-0" />}
                                    <span className="font-mono font-medium truncate">{item.label}</span>
                                </div>

                                <div className="flex items-center gap-2 shrink-0">
                                    {item.scope && (
                                        <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-zinc-800 text-zinc-400 border border-zinc-700">
                                            {item.scope}
                                        </span>
                                    )}
                                    <span className="text-zinc-500 text-[10px] truncate max-w-[120px]">{item.desc}</span>
                                </div>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Main Input Form - Goose Capsule Style */}
            <div 
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                className={`relative transition-all duration-300 ${isFocused ? 'scale-[1.002]' : ''}`}
            >
                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={(e) => e.target.files && handleFiles(e.target.files)}
                    accept="image/*"
                    multiple
                    className="hidden"
                />

                <form
                    onSubmit={handleSubmit}
                    className={`relative flex flex-col bg-white dark:bg-[#18181b] border border-zinc-200 dark:border-zinc-800 rounded-2xl p-2.5 shadow-sm hover:border-zinc-300 dark:hover:border-zinc-700 transition-all ${isFocused ? 'border-zinc-400 dark:border-zinc-600 shadow-md' : ''}`}
                >
                    {/* Attached Image Thumbnails */}
                    {attachedImages.length > 0 && (
                        <div className="flex items-center gap-2 px-2 pt-1 pb-2 overflow-x-auto custom-scrollbar">
                            {attachedImages.map((imgUrl, idx) => (
                                <div key={idx} className="relative group shrink-0 rounded-lg overflow-hidden border border-zinc-700 bg-zinc-900 w-14 h-14">
                                    <img src={imgUrl} alt={`Adjunto ${idx + 1}`} className="w-full h-full object-cover" />
                                    <button
                                        type="button"
                                        onClick={() => setAttachedImages((prev) => prev.filter((_, i) => i !== idx))}
                                        className="absolute top-1 right-1 bg-black/70 hover:bg-red-600 text-white rounded-full p-0.5 transition-colors"
                                        title="Eliminar imagen"
                                    >
                                        <X size={10} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    <div className="flex items-start gap-1 px-1 pt-1 pb-2">
                        <textarea
                            ref={textareaRef}
                            value={input}
                            onChange={handleInputChange}
                            onKeyDown={handleKeyDown}
                            onPaste={handlePaste}
                            onFocus={() => setIsFocused(true)}
                            onBlur={() => {
                                setTimeout(() => setIsFocused(false), 200);
                            }}
                            placeholder="Ctrl+↑/Ctrl+↓ para navegar entre mensajes"
                            rows={1}
                            className="flex-1 bg-transparent text-zinc-800 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 px-2 py-1 focus:outline-none resize-none min-h-[36px] max-h-[140px] text-sm leading-6"
                        />
                    </div>

                    {/* Footer Inside Input Capsule (Goose layout) */}
                    <div className="flex items-center justify-between px-2 pt-2 border-t border-zinc-100 dark:border-zinc-800/80 text-xs">
                        <div className="flex items-center gap-2">
                            {/* Model selection pill */}
                            <button
                                type="button"
                                onClick={onOpenSettings}
                                className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 text-[11px] font-mono hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors select-none cursor-pointer"
                                title="Click para cambiar el modelo activo en Ajustes"
                            >
                                <Box size={12} className="text-zinc-500" />
                                <span>{configuredModel}</span>
                            </button>

                            {/* Active Directory Label */}
                            <button 
                                type="button"
                                onClick={onChangeDir}
                                className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 text-[11px] font-medium hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors max-w-[160px] truncate"
                                title="Cambiar directorio de trabajo"
                            >
                                <Folder size={12} className="text-zinc-500" />
                                <span className="truncate">{getFolderBasename(currentDir)}</span>
                            </button>
                        </div>

                        <div className="flex items-center gap-2.5">
                            {/* Cost/Tokens mock */}
                            <span className="flex items-center gap-1 font-mono text-[11px] text-zinc-500 dark:text-zinc-400 select-none">
                                <Sparkles size={11} className="text-zinc-400" />
                                0.0000 • 0 / 128k
                            </span>

                            {/* Skill badge */}
                            <span className="flex items-center gap-1 font-mono text-[11px] text-zinc-500 dark:text-zinc-400 select-none">
                                <Zap size={11} className="text-zinc-400" />
                                15
                            </span>

                            {/* Utility Buttons */}
                            <div className="flex items-center gap-1.5 pl-1 border-l border-zinc-200 dark:border-zinc-800">
                                <button
                                    type="button"
                                    onClick={() => fileInputRef.current?.click()}
                                    className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-all cursor-pointer"
                                    title="Adjuntar imagen"
                                >
                                    <Paperclip size={13} />
                                </button>
                                
                                {/* Send Button (Circle with Arrow Up) */}
                                {isGenerating ? (
                                    <button
                                        type="button"
                                        onClick={onStopGeneration}
                                        className="h-7 w-7 rounded-full bg-red-600 hover:bg-red-500 flex items-center justify-center text-white transition-all animate-pulse cursor-pointer"
                                        title="Detener respuesta"
                                    >
                                        <Square size={8} fill="white" className="text-white" />
                                    </button>
                                ) : (
                                    <button
                                        type="submit"
                                        disabled={!input.trim() && attachedImages.length === 0}
                                        className={`h-7 w-7 rounded-full flex items-center justify-center transition-all ${
                                            input.trim() || attachedImages.length > 0
                                                ? 'bg-zinc-800 dark:bg-zinc-100 text-white dark:text-zinc-900 hover:opacity-90 cursor-pointer'
                                                : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-600 cursor-not-allowed'
                                        }`}
                                    >
                                        <ArrowUp size={14} />
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    );
};

