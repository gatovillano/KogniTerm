import React, { useEffect, useRef } from 'react';
import { ChevronDown } from 'lucide-react';

export interface ApprovalRequest {
    id: string;
    message: string;
    title: string;
    diff_content?: string;
    file_path?: string;
    timestamp: number;
}

interface CommandApprovalProps {
    request: ApprovalRequest;
    onApprove: (id: string) => void;
    onReject: (id: string) => void;
    isInline?: boolean;
}

export const CommandApproval: React.FC<CommandApprovalProps> = ({
    request,
    onApprove,
    onReject,
    isInline = false,
}) => {
    const approveRef = useRef<HTMLButtonElement>(null);

    const handleApproveAlways = async () => {
        try {
            await fetch('http://127.0.0.1:8765/api/config/set', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: 'auto_approve', value: true, scope: 'project' }),
            });
        } catch (e) {
            console.error("Error setting auto_approve:", e);
        }
        onApprove(request.id);
    };

    useEffect(() => {
        approveRef.current?.focus();
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                onApprove(request.id);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                onReject(request.id);
            } else if (e.key === 'a' || e.key === 'A') {
                e.preventDefault();
                handleApproveAlways();
            }
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [request.id, onApprove, onReject]);

    const displayTitle = request.message || request.title || 'Ejecutar comando';

    if (isInline) {
        return (
            <div className="w-full my-4 flex flex-col gap-2 font-sans select-none animate-fade-in">
                {/* Header Row: Running · <cmd>  27s */}
                <div className="flex items-center justify-between text-xs text-zinc-600 dark:text-zinc-400">
                    <div className="flex items-center gap-2 truncate max-w-[85%]">
                        {/* Matrix / Running Icon */}
                        <div className="grid grid-cols-2 gap-0.5 w-3.5 h-3.5 opacity-60">
                            <div className="bg-zinc-500 rounded-2xs animate-pulse" />
                            <div className="bg-zinc-400 rounded-2xs" />
                            <div className="bg-zinc-400 rounded-2xs" />
                            <div className="bg-zinc-500 rounded-2xs animate-pulse" />
                        </div>
                        <span className="truncate">
                            <span className="font-normal text-zinc-500 dark:text-zinc-400">Running</span>
                            <span className="mx-1.5 text-zinc-300 dark:text-zinc-600">·</span>
                            <span className="font-mono text-zinc-700 dark:text-zinc-300">{displayTitle}</span>
                        </span>
                    </div>
                    <span className="text-zinc-400 dark:text-zinc-500 font-mono text-xs shrink-0">
                        27s
                    </span>
                </div>

                {/* Inline Action Buttons matching OpenClaw screenshot */}
                <div className="flex items-center gap-2 pl-5 mt-1">
                    {/* Run Ctrl ↵ v */}
                    <div className="inline-flex items-center rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-2xs overflow-hidden">
                        <button
                            ref={approveRef}
                            onClick={() => onApprove(request.id)}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                        >
                            <span>Run</span>
                            <span className="kbd-badge">Ctrl ↵</span>
                        </button>
                        <button
                            onClick={handleApproveAlways}
                            title="Aceptar siempre (A)"
                            className="px-1.5 py-1.5 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 border-l border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                        >
                            <ChevronDown size={13} />
                        </button>
                    </div>

                    {/* Reject Esc */}
                    <button
                        onClick={() => onReject(request.id)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs font-medium text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-800 shadow-2xs transition-colors cursor-pointer"
                    >
                        <span>Reject</span>
                        <span className="kbd-badge">Esc</span>
                    </button>

                    {/* Command v */}
                    <button
                        onClick={() => {}}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs font-medium text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-800 shadow-2xs transition-colors cursor-pointer"
                    >
                        <span>Command</span>
                        <ChevronDown size={13} className="text-zinc-400" />
                    </button>
                </div>

                {/* Sub status row */}
                <div className="flex items-center gap-2 pl-5 mt-0.5 text-[11px] text-zinc-400 dark:text-zinc-500 font-mono">
                    <span className="w-2.5 h-2.5 rounded-xs bg-zinc-300 dark:bg-zinc-700 inline-block" />
                    <span>37s</span>
                </div>
            </div>
        );
    }

    return (
        <aside className="flex h-full flex-col bg-white dark:bg-zinc-900">
            {/* Header */}
            <div className="flex items-center justify-between gap-3 border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
                <div className="flex min-w-0 items-center gap-2.5">
                    <span className="tool-run-icon">&gt;_</span>
                    <div className="min-w-0">
                        <p className="truncate text-[13px] font-semibold leading-tight text-zinc-800 dark:text-zinc-100">
                            {request.title}
                        </p>
                        <p className="text-[11px] leading-tight text-zinc-500">
                            Requiere tu aprobación
                        </p>
                    </div>
                </div>
            </div>

            {/* Body */}
            <div className="goose-scrollbar flex-1 space-y-4 overflow-y-auto px-4 py-4">
                {request.message && (
                    <p className="text-[13px] leading-relaxed text-zinc-700 dark:text-zinc-300">
                        {request.message}
                    </p>
                )}
            </div>

            {/* Actions */}
            <div className="border-t border-zinc-200 dark:border-zinc-800 px-4 py-3">
                <div className="flex items-center justify-end gap-2">
                    <button
                        onClick={() => onReject(request.id)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-zinc-200 dark:border-zinc-800 text-xs font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                    >
                        <span>Reject</span>
                        <span className="kbd-badge">Esc</span>
                    </button>
                    <button
                        ref={approveRef}
                        onClick={() => onApprove(request.id)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 text-xs font-medium hover:bg-zinc-800 dark:hover:bg-white transition-colors"
                    >
                        <span>Run</span>
                        <span className="kbd-badge">Ctrl ↵</span>
                    </button>
                </div>
            </div>
        </aside>
    );
};

