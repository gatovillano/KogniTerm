import React, { useState, useRef } from 'react';
import { 
    Square, 
    Plus, 
    Mic, 
    ArrowUp, 
    Loader2, 
    X, 
    Check, 
    AlertCircle, 
    Layers, 
    Pencil, 
    ListPlus, 
    Image as ImageIcon 
} from 'lucide-react';
import { useAudioTranscription } from '../../hooks/useAudioTranscription';
import { QueuedMessage } from '@kogniterm/types';

interface ChatInputProps {
    onSendMessage: (message: string, images?: string[]) => void;
    isGenerating: boolean;
    onStopGeneration?: () => void;
    currentDir?: string;
    onChangeDir?: () => void;
    onOpenSettings?: () => void;
    messageQueue?: QueuedMessage[];
    onRemoveFromQueue?: (id: string) => void;
    onClearQueue?: () => void;
    onProcessNext?: () => void;
    isFloating?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ 
    onSendMessage, 
    isGenerating, 
    onStopGeneration,
    messageQueue = [],
    onRemoveFromQueue,
    onClearQueue,
}) => {
    const [input, setInput] = useState('');
    const [attachedImages, setAttachedImages] = useState<string[]>([]);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const [isFocused, setIsFocused] = useState(false);

    const {
        isRecording,
        isTranscribing,
        recordingDuration,
        audioError,
        startRecording,
        stopRecording,
        cancelRecording,
        clearError,
    } = useAudioTranscription();

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        const value = e.target.value;
        setInput(value);

        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() && attachedImages.length === 0) return;
        onSendMessage(input, attachedImages);
        setInput('');
        setAttachedImages([]);
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
        }
    };

    const handleFiles = (files: FileList) => {
        Array.from(files).forEach((file) => {
            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    if (e.target?.result) {
                        setAttachedImages((prev) => [...prev, e.target!.result as string]);
                    }
                };
                reader.readAsDataURL(file);
            }
        });
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        if (e.dataTransfer.files) {
            handleFiles(e.dataTransfer.files);
        }
    };

    const handleMicClick = async () => {
        if (isTranscribing) return;
        if (isRecording) {
            const transcribed = await stopRecording();
            if (transcribed) {
                setInput((prev) => {
                    const nextVal = prev.trim() ? `${prev.trim()} ${transcribed}` : transcribed;
                    setTimeout(() => {
                        if (textareaRef.current) {
                            textareaRef.current.style.height = 'auto';
                            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
                            textareaRef.current.focus();
                        }
                    }, 50);
                    return nextVal;
                });
            }
        } else {
            await startRecording();
        }
    };

    const handleEditQueuedItem = (item: QueuedMessage) => {
        setInput(item.text);
        if (item.images && item.images.length > 0) {
            setAttachedImages(item.images);
        }
        if (onRemoveFromQueue) {
            onRemoveFromQueue(item.id);
        }
        setTimeout(() => {
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
                textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
                textareaRef.current.focus();
            }
        }, 50);
    };

    return (
        <div className="w-full max-w-3xl mx-auto px-6 sm:px-8 md:px-10 pb-4">
            {/* Error banner si falló la grabación o transcripción */}
            {audioError && (
                <div className="mb-2 flex items-center justify-between text-xs px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400">
                    <div className="flex items-center gap-1.5">
                        <AlertCircle size={14} className="shrink-0" />
                        <span>{audioError}</span>
                    </div>
                    <button
                        type="button"
                        onClick={clearError}
                        className="p-0.5 hover:opacity-75 cursor-pointer ml-2"
                        title="Descartar error"
                    >
                        <X size={13} />
                    </button>
                </div>
            )}

            {/* Panel de Cola de Mensajes */}
            {messageQueue.length > 0 && (
                <div className="mb-2.5 bg-white/95 dark:bg-zinc-900/95 border border-zinc-200/90 dark:border-zinc-800 rounded-xl p-2.5 shadow-sm backdrop-blur-md transition-all">
                    <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-zinc-100 dark:border-zinc-800/80 text-xs">
                        <div className="flex items-center gap-1.5 font-medium text-zinc-700 dark:text-zinc-300">
                            <Layers size={13} className="text-indigo-500 dark:text-indigo-400" />
                            <span>Cola de mensajes</span>
                            <span className="px-1.5 py-0.5 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 text-[10px] font-mono rounded-full border border-indigo-200/50 dark:border-indigo-800/40">
                                {messageQueue.length} {messageQueue.length === 1 ? 'pendiente' : 'pendientes'}
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-[10px] text-zinc-400 dark:text-zinc-500 font-mono hidden sm:inline">
                                {isGenerating ? 'Se despacharán secuencialmente' : 'Listo para procesar'}
                            </span>
                            {onClearQueue && (
                                <button
                                    type="button"
                                    onClick={onClearQueue}
                                    className="text-[11px] text-zinc-400 hover:text-red-500 dark:hover:text-red-400 transition-colors cursor-pointer px-1 py-0.5 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800"
                                    title="Vaciar toda la cola"
                                >
                                    Vaciar
                                </button>
                            )}
                        </div>
                    </div>
                    <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1 text-xs">
                        {messageQueue.map((item, index) => (
                            <div
                                key={item.id || index}
                                className="group flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700 transition-all text-zinc-700 dark:text-zinc-300"
                            >
                                <div className="flex items-center gap-2 min-w-0 flex-1">
                                    <span className="shrink-0 w-4 h-4 rounded-full bg-zinc-200/70 dark:bg-zinc-700/60 text-[10px] font-mono text-zinc-500 dark:text-zinc-400 flex items-center justify-center font-semibold">
                                        {index + 1}
                                    </span>
                                    <p className="truncate text-xs font-normal" title={item.text}>
                                        {item.text}
                                    </p>
                                    {item.images && item.images.length > 0 && (
                                        <span className="shrink-0 flex items-center gap-0.5 text-[10px] text-zinc-400 bg-zinc-200/50 dark:bg-zinc-700/40 px-1 py-0.5 rounded">
                                            <ImageIcon size={10} />
                                            {item.images.length}
                                        </span>
                                    )}
                                </div>
                                <div className="flex items-center gap-1 shrink-0 opacity-80 group-hover:opacity-100 transition-opacity">
                                    <button
                                        type="button"
                                        onClick={() => handleEditQueuedItem(item)}
                                        className="p-1 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-200/60 dark:hover:bg-zinc-700/60 rounded transition-colors cursor-pointer"
                                        title="Editar mensaje"
                                    >
                                        <Pencil size={11} />
                                    </button>
                                    {onRemoveFromQueue && (
                                        <button
                                            type="button"
                                            onClick={() => onRemoveFromQueue(item.id)}
                                            className="p-1 text-zinc-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 rounded transition-colors cursor-pointer"
                                            title="Eliminar de la cola"
                                        >
                                            <X size={12} />
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Main Floating Input Form matching OpenClaw design */}
            <div 
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                className="relative transition-all duration-300"
            >
                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={(e) => e.target.files && handleFiles(e.target.files)}
                    accept="image/*"
                    multiple
                    className="hidden"
                />

                {/* Previsualización de imágenes adjuntas en el input */}
                {attachedImages.length > 0 && (
                    <div className="flex items-center gap-2 mb-2 px-1 flex-wrap">
                        {attachedImages.map((img, idx) => (
                            <div key={idx} className="relative group w-12 h-12 rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-700 shadow-xs">
                                <img src={img} alt="Adjunto" className="w-full h-full object-cover" />
                                <button
                                    type="button"
                                    onClick={() => setAttachedImages(prev => prev.filter((_, i) => i !== idx))}
                                    className="absolute top-0.5 right-0.5 p-0.5 bg-black/60 hover:bg-black/80 text-white rounded-full transition-opacity opacity-0 group-hover:opacity-100 cursor-pointer"
                                    title="Eliminar imagen"
                                >
                                    <X size={10} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                <form
                    onSubmit={handleSubmit}
                    className={`relative flex items-center gap-2.5 bg-white/80 dark:bg-zinc-900/80 border border-zinc-200/90 dark:border-zinc-800 rounded-xl px-3 py-2 backdrop-blur-md transition-all ${
                        isRecording 
                            ? 'border-red-400/80 dark:border-red-500/60 ring-1 ring-red-400/20 shadow-sm'
                            : isFocused 
                            ? 'border-zinc-400 dark:border-zinc-600 ring-1 ring-zinc-400/20 dark:ring-zinc-600/20' 
                            : ''
                    }`}
                >
                    {/* Left Plus Attachment Icon */}
                    <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="p-1.5 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800/60 rounded-lg transition-colors cursor-pointer shrink-0"
                        title="Adjuntar archivo"
                    >
                        <Plus size={16} />
                    </button>

                    {/* Text Area or Recording HUD */}
                    {isRecording ? (
                        <div className="flex-1 flex items-center gap-3 py-1 px-1">
                            <div className="flex items-center gap-2 text-red-500 dark:text-red-400">
                                <span className="relative flex h-2.5 w-2.5">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
                                </span>
                                <span className="text-xs font-mono font-medium tracking-wide">
                                    Grabando audio ({formatTime(recordingDuration)})
                                </span>
                            </div>
                            <span className="text-xs text-zinc-400 dark:text-zinc-500 truncate">
                                Habla claramente para transcribir con Whisper...
                            </span>
                        </div>
                    ) : (
                        <textarea
                            ref={textareaRef}
                            value={input}
                            onChange={handleInputChange}
                            onKeyDown={handleKeyDown}
                            onFocus={() => setIsFocused(true)}
                            onBlur={() => setTimeout(() => setIsFocused(false), 200)}
                            placeholder={
                                isTranscribing 
                                    ? "Transcribiendo audio con Whisper..." 
                                    : isGenerating 
                                    ? "Escribe un mensaje para encolar..." 
                                    : "¿Qué deseas resolver o construir?"
                            }
                            disabled={isTranscribing}
                            rows={1}
                            className="flex-1 bg-transparent text-zinc-800 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:outline-none resize-none text-sm leading-6 max-h-[120px] disabled:opacity-60"
                        />
                    )}

                    {/* Right Icon Actions */}
                    <div className="flex items-center gap-1.5 shrink-0">
                        {isRecording ? (
                            <>
                                {/* Cancelar grabación */}
                                <button
                                    type="button"
                                    onClick={cancelRecording}
                                    className="p-1.5 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800/60 rounded-lg transition-colors cursor-pointer"
                                    title="Cancelar grabación"
                                >
                                    <X size={16} />
                                </button>

                                {/* Finalizar grabación y transcribir */}
                                <button
                                    type="button"
                                    onClick={handleMicClick}
                                    className="px-2.5 py-1 text-xs font-medium bg-red-500 hover:bg-red-600 text-white rounded-lg transition-all flex items-center gap-1 shadow-sm cursor-pointer"
                                    title="Finalizar y transcribir"
                                >
                                    <Check size={13} strokeWidth={2.5} />
                                    <span>Transcribir</span>
                                </button>
                            </>
                        ) : isTranscribing ? (
                            <div className="flex items-center gap-1.5 px-2 py-1 bg-zinc-100 dark:bg-zinc-800/80 rounded-lg text-xs text-zinc-600 dark:text-zinc-300">
                                <Loader2 size={14} className="animate-spin text-zinc-500 dark:text-zinc-400" />
                                <span className="font-mono text-[11px]">Whisper...</span>
                            </div>
                        ) : (
                            <button
                                type="button"
                                onClick={handleMicClick}
                                className="p-1.5 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800/60 rounded-lg transition-colors cursor-pointer"
                                title="Dictar por voz (Whisper)"
                            >
                                <Mic size={16} />
                            </button>
                        )}

                        {/* Send / Queue / Stop Generation Button */}
                        {isGenerating && (
                            <>
                                {(input.trim() || attachedImages.length > 0) && (
                                    <button
                                        type="submit"
                                        className="h-7 px-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-1 text-xs font-medium transition-all cursor-pointer shadow-xs shrink-0"
                                        title="Poner en cola para ejecutar después"
                                    >
                                        <ListPlus size={13} strokeWidth={2.2} />
                                        <span className="hidden sm:inline">Encolar</span>
                                    </button>
                                )}
                                <button
                                    type="button"
                                    onClick={onStopGeneration}
                                    className="w-7 h-7 rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 flex items-center justify-center transition-all cursor-pointer hover:opacity-85 shrink-0"
                                    title="Detener generación"
                                >
                                    <Square size={9} fill="currentColor" />
                                </button>
                            </>
                        )}

                        {!isGenerating && (
                            <button
                                type="submit"
                                disabled={(!input.trim() && attachedImages.length === 0) || isRecording || isTranscribing}
                                className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all shrink-0 ${
                                    (input.trim() || attachedImages.length > 0) && !isRecording && !isTranscribing
                                        ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 cursor-pointer hover:opacity-90 shadow-2xs'
                                        : 'bg-zinc-100 text-zinc-300 dark:bg-zinc-800/60 dark:text-zinc-600 cursor-not-allowed'
                                }`}
                                title="Enviar mensaje"
                            >
                                <ArrowUp size={14} strokeWidth={2.5} />
                            </button>
                        )}
                    </div>
                </form>
            </div>
        </div>
    );
};
