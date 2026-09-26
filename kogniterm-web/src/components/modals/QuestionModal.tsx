import React, { useState, useEffect } from 'react';
import { HelpCircle, X, Send, CornerDownLeft } from 'lucide-react';
import { QuestionRequest } from '../../hooks/useChat';

interface QuestionModalProps {
    request: QuestionRequest | null;
    onRespond: (id: string, selected: string) => void;
    onCancel?: (id: string) => void;
}

export const QuestionModal: React.FC<QuestionModalProps> = ({
    request,
    onRespond,
    onCancel,
}) => {
    const [freeformText, setFreeformText] = useState('');
    const [isInputFocused, setIsInputFocused] = useState(false);

    useEffect(() => {
        setFreeformText('');
        setIsInputFocused(false);
    }, [request]);

    useEffect(() => {
        if (!request) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                if (onCancel) onCancel(request.id);
                else onRespond(request.id, 'Cancelado por el usuario.');
                return;
            }

            // Atajos numéricos (1-9) sólo si no se está escribiendo en el input libre
            if (!isInputFocused && /^[1-9]$/.test(e.key)) {
                const idx = parseInt(e.key, 10) - 1;
                if (idx >= 0 && idx < request.options.length) {
                    e.preventDefault();
                    onRespond(request.id, request.options[idx]);
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [request, isInputFocused, onRespond, onCancel]);

    if (!request) return null;

    const handleSelectOption = (option: string) => {
        onRespond(request.id, option);
    };

    const handleFreeformSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const trimmed = freeformText.trim();
        if (trimmed) {
            onRespond(request.id, trimmed);
        }
    };

    const optionColors = [
        'hover:border-purple-500 hover:bg-purple-950/30 text-purple-400',
        'hover:border-blue-500 hover:bg-blue-950/30 text-blue-400',
        'hover:border-cyan-500 hover:bg-cyan-950/30 text-cyan-400',
        'hover:border-emerald-500 hover:bg-emerald-950/30 text-emerald-400',
        'hover:border-amber-500 hover:bg-amber-950/30 text-amber-400',
        'hover:border-rose-500 hover:bg-rose-950/30 text-rose-400',
    ];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="w-full max-w-2xl overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl transition-all">
                {/* Header */}
                <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-4 bg-zinc-900/80">
                    <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400">
                            <HelpCircle className="h-5 w-5" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-zinc-100">
                                {request.title || 'Consulta del Agente'}
                            </h3>
                            <p className="text-xs text-zinc-400">Selecciona una alternativa para continuar</p>
                        </div>
                    </div>
                    <button
                        onClick={() => onRespond(request.id, 'Cancelado por el usuario.')}
                        className="rounded-lg p-1.5 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
                        title="Cancelar (Esc)"
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>

                {/* Question Content */}
                <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
                    <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4 text-sm leading-relaxed text-zinc-200 whitespace-pre-wrap">
                        {request.question}
                    </div>

                    {/* Predefined Options */}
                    <div className="space-y-2.5">
                        <label className="text-xs font-medium uppercase tracking-wider text-zinc-400">
                            Opciones Disponibles
                        </label>
                        <div className="grid gap-2">
                            {request.options.map((opt, i) => {
                                const colorClass = optionColors[i % optionColors.length];
                                return (
                                    <button
                                        key={i}
                                        onClick={() => handleSelectOption(opt)}
                                        className={`group relative flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/70 px-4 py-3 text-left transition-all duration-150 hover:scale-[1.005] ${colorClass}`}
                                    >
                                        <div className="flex items-center gap-3 pr-4">
                                            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-zinc-800 text-xs font-bold text-zinc-300 group-hover:bg-purple-600 group-hover:text-white transition-colors">
                                                {i + 1}
                                            </span>
                                            <span className="text-sm font-medium text-zinc-200 group-hover:text-white">
                                                {opt}
                                            </span>
                                        </div>
                                        <CornerDownLeft className="h-4 w-4 opacity-0 transition-opacity group-hover:opacity-100 text-zinc-400" />
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* Freeform input */}
                    {request.allow_freeform && (
                        <form onSubmit={handleFreeformSubmit} className="space-y-2 pt-2 border-t border-zinc-800/80">
                            <label className="text-xs font-medium text-zinc-400">
                                O escribe tu respuesta personalizada:
                            </label>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={freeformText}
                                    onChange={(e) => setFreeformText(e.target.value)}
                                    onFocus={() => setIsInputFocused(true)}
                                    onBlur={() => setIsInputFocused(false)}
                                    placeholder="Respuesta personalizada..."
                                    className="flex-1 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 transition-all"
                                />
                                <button
                                    type="submit"
                                    disabled={!freeformText.trim()}
                                    className="flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <span>Enviar</span>
                                    <Send className="h-4 w-4" />
                                </button>
                            </div>
                        </form>
                    )}
                </div>

                {/* Footer hint */}
                <div className="flex items-center justify-between border-t border-zinc-800 bg-zinc-950/80 px-6 py-3 text-xs text-zinc-500">
                    <span>
                        Pulsa <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">1-{Math.min(request.options.length, 9)}</kbd> para selección rápida
                    </span>
                    <span>
                        <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">Esc</kbd> cancelar
                    </span>
                </div>
            </div>
        </div>
    );
};
