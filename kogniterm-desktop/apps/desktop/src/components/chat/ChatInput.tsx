import React, { useState, useRef } from 'react';
import { Square, Plus, Mic } from 'lucide-react';

interface ChatInputProps {
    onSendMessage: (message: string, images?: string[]) => void;
    isGenerating: boolean;
    onStopGeneration?: () => void;
    currentDir?: string;
    onChangeDir?: () => void;
    onOpenSettings?: () => void;
    messageQueue?: string[];
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

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        if (e.dataTransfer.files) {
            handleFiles(e.dataTransfer.files);
        }
    };

    return (
        <div className="w-full max-w-3xl mx-auto px-4 pb-4">
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

                <form
                    onSubmit={handleSubmit}
                    className={`relative flex items-center gap-3 bg-white/95 dark:bg-zinc-900/90 border border-zinc-200/90 dark:border-zinc-800 rounded-2xl px-3 py-2 shadow-lg shadow-zinc-200/40 dark:shadow-none backdrop-blur-md transition-all ${
                        isFocused ? 'border-zinc-400 dark:border-zinc-600 shadow-xl' : ''
                    }`}
                >
                    {/* Left Plus Attachment Icon */}
                    <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="p-1.5 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-xl transition-all cursor-pointer shrink-0"
                        title="Add attachment"
                    >
                        <Plus size={18} />
                    </button>

                    {/* Text Area */}
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={handleInputChange}
                        onKeyDown={handleKeyDown}
                        onFocus={() => setIsFocused(true)}
                        onBlur={() => setTimeout(() => setIsFocused(false), 200)}
                        placeholder="What should we tackle?"
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
                </form>
            </div>
        </div>
    );
};


