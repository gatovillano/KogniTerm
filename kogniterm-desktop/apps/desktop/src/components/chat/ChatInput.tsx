import React, { useState, useRef } from 'react';
import { Square, Plus, Mic, X, UploadCloud } from 'lucide-react';

interface ChatInputProps {
    onSendMessage: (message: string, images?: string[]) => void;
    isGenerating: boolean;
    onStopGeneration?: () => void;
    currentDir?: string;
    onChangeDir?: () => void;
    onOpenSettings?: () => void;
    messageQueue?: Array<string | { text: string; images?: string[] }>;
    onRemoveFromQueue?: (index: number) => void;
    onProcessNext?: () => void;
    isFloating?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ 
    onSendMessage, 
    isGenerating, 
    onStopGeneration,
}) => {
    const [input, setInput] = useState('');
    const [attachedImages, setAttachedImages] = useState<string[]>([]);
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const [isFocused, setIsFocused] = useState(false);

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

    const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
        const items = e.clipboardData?.items;
        if (!items) return;

        const imageFiles: File[] = [];
        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            if (item.type.startsWith('image/')) {
                const file = item.getAsFile();
                if (file) {
                    imageFiles.push(file);
                }
            }
        }

        if (imageFiles.length > 0) {
            imageFiles.forEach((file) => {
                const reader = new FileReader();
                reader.onload = (loadEvent) => {
                    if (loadEvent.target?.result) {
                        setAttachedImages((prev) => [...prev, loadEvent.target!.result as string]);
                    }
                };
                reader.readAsDataURL(file);
            });
        }
    };

    const handleRemoveImage = (indexToRemove: number) => {
        setAttachedImages((prev) => prev.filter((_, idx) => idx !== indexToRemove));
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (!isDragging) setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files);
        }
    };

    return (
        <div className="w-full max-w-3xl mx-auto px-4 pb-4">
            {/* Main Floating Input Form matching OpenClaw design */}
            <div 
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                className="relative transition-all duration-300"
            >
                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={(e) => {
                        if (e.target.files) {
                            handleFiles(e.target.files);
                            e.target.value = '';
                        }
                    }}
                    accept="image/*"
                    multiple
                    className="hidden"
                />

                {/* Drop indicator overlay */}
                {isDragging && (
                    <div className="absolute inset-0 z-20 flex items-center justify-center bg-indigo-50/90 dark:bg-indigo-950/90 border-2 border-dashed border-indigo-500 rounded-2xl backdrop-blur-xs pointer-events-none transition-all">
                        <div className="flex items-center gap-2 text-sm font-medium text-indigo-600 dark:text-indigo-300">
                            <UploadCloud size={20} className="animate-bounce" />
                            <span>Suelta las imágenes aquí</span>
                        </div>
                    </div>
                )}

                <form
                    onSubmit={handleSubmit}
                    className={`relative flex flex-col bg-white/95 dark:bg-zinc-900/90 border border-zinc-200/90 dark:border-zinc-800 rounded-2xl shadow-lg shadow-zinc-200/40 dark:shadow-none backdrop-blur-md transition-all ${
                        isFocused ? 'border-zinc-400 dark:border-zinc-600 shadow-xl' : ''
                    }`}
                >
                    {/* Attached Image Previews Bar */}
                    {attachedImages.length > 0 && (
                        <div className="flex flex-wrap items-center gap-2 px-3 pt-3 pb-1 border-b border-zinc-100 dark:border-zinc-800/80">
                            {attachedImages.map((imgSrc, idx) => (
                                <div 
                                    key={idx} 
                                    className="relative group w-14 h-14 rounded-xl overflow-hidden border border-zinc-200 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-800 shrink-0 shadow-xs"
                                >
                                    <img
                                        src={imgSrc}
                                        alt={`Adjunto ${idx + 1}`}
                                        className="w-full h-full object-cover"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => handleRemoveImage(idx)}
                                        className="absolute top-1 right-1 w-4 h-4 rounded-full bg-black/75 hover:bg-black text-white flex items-center justify-center transition-colors cursor-pointer opacity-90 group-hover:opacity-100"
                                        title="Eliminar imagen"
                                    >
                                        <X size={10} />
                                    </button>
                                </div>
                            ))}
                            <button
                                type="button"
                                onClick={() => fileInputRef.current?.click()}
                                className="h-14 px-3 flex flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-500 text-zinc-400 dark:text-zinc-500 hover:text-zinc-600 dark:hover:text-zinc-300 text-[10px] font-medium transition-colors cursor-pointer"
                                title="Agregar más imágenes"
                            >
                                <Plus size={14} />
                                <span>Agregar</span>
                            </button>
                        </div>
                    )}

                    <div className="flex items-center gap-3 px-3 py-2 w-full">
                        {/* Left Plus Attachment Icon */}
                        <button
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            className="p-1.5 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-xl transition-all cursor-pointer shrink-0"
                            title="Adjuntar imagen"
                        >
                            <Plus size={18} />
                        </button>

                        {/* Text Area */}
                        <textarea
                            ref={textareaRef}
                            value={input}
                            onChange={handleInputChange}
                            onKeyDown={handleKeyDown}
                            onPaste={handlePaste}
                            onFocus={() => setIsFocused(true)}
                            onBlur={() => setTimeout(() => setIsFocused(false), 200)}
                            placeholder={
                                attachedImages.length > 0 
                                    ? "¿Qué deseas consultar sobre la(s) imagen(es)? (o Enter para enviar)"
                                    : "What should we tackle?"
                            }
                            rows={1}
                            className="flex-1 bg-transparent text-zinc-800 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:outline-none resize-none text-sm leading-6 max-h-[120px]"
                        />

                        {/* Right Icon Actions */}
                        <div className="flex items-center gap-2 shrink-0">
                            <button
                                type="button"
                                className="p-1.5 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-xl transition-all cursor-pointer"
                                title="Voice Input"
                            >
                                <Mic size={18} />
                            </button>

                            {/* Send / Stop Generation Button */}
                            {isGenerating ? (
                                <button
                                    type="button"
                                    onClick={onStopGeneration}
                                    className="w-8 h-8 rounded-full bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 flex items-center justify-center transition-all cursor-pointer hover:opacity-90"
                                    title="Stop generation"
                                >
                                    <Square size={10} fill="currentColor" />
                                </button>
                            ) : (
                                <button
                                    type="submit"
                                    disabled={!input.trim() && attachedImages.length === 0}
                                    className={`w-8 h-8 rounded-full flex items-center justify-center transition-all ${
                                        input.trim() || attachedImages.length > 0
                                            ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 cursor-pointer hover:opacity-90'
                                            : 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 cursor-pointer hover:opacity-90'
                                    }`}
                                    title="Send message"
                                >
                                    <div className="w-3 h-3 rounded-full bg-current" />
                                </button>
                            )}
                        </div>
                    </div>
                </form>
            </div>
        </div>
    );
};


