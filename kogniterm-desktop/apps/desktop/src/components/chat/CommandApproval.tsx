import React, { useEffect, useRef } from 'react';
import { X, Check, Terminal, FileCode } from 'lucide-react';

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
}

export const CommandApproval: React.FC<CommandApprovalProps> = ({
    request,
    onApprove,
    onReject,
}) => {
    const approveRef = useRef<HTMLButtonElement>(null);
    const isBash = request.file_path === 'bash';

    useEffect(() => {
        approveRef.current?.focus();
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                onApprove(request.id);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                onReject(request.id);
            }
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [request.id, onApprove, onReject]);

    const accentChip = isBash
        ? 'bg-amber-500/10 border border-amber-500/20'
        : 'bg-indigo-500/10 border border-indigo-500/20';
    const accentIcon = isBash ? 'text-amber-400' : 'text-indigo-400';

    return (
        <aside className="flex h-full flex-col">
            {/* Header */}
            <div className="flex items-center justify-between gap-3 border-b border-zinc-800/60 px-4 py-3">
                <div className="flex min-w-0 items-center gap-2.5">
                    <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${accentChip}`}>
                        {isBash
                            ? <Terminal size={15} className={accentIcon} />
                            : <FileCode size={15} className={accentIcon} />
                        }
                    </div>
                    <div className="min-w-0">
                        <p className="truncate text-[13px] font-semibold leading-tight text-zinc-100">
                            {request.title}
                        </p>
                        <p className="text-[11px] leading-tight text-zinc-500">
                            Requiere tu aprobación
                        </p>
                    </div>
                </div>
                <button
                    onClick={() => onReject(request.id)}
                    title="Rechazar (Esc)"
                    className="shrink-0 rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
                >
                    <X size={15} />
                </button>
            </div>

            {/* Body */}
            <div className="goose-scrollbar flex-1 space-y-4 overflow-y-auto px-4 py-4">
                {request.message && (
                    <p className="text-[13px] leading-relaxed text-zinc-300">
                        {request.message}
                    </p>
                )}

                {request.diff_content && (
                    <div className="overflow-hidden rounded-xl border border-zinc-800/60 bg-zinc-900/40">
                        {request.file_path && (
                            <div className="flex items-center gap-1.5 border-b border-zinc-800/60 bg-zinc-900/60 px-3 py-2">
                                <FileCode size={12} className="shrink-0 text-zinc-500" />
                                <span className="truncate font-mono text-[11px] text-zinc-400">
                                    {request.file_path}
                                </span>
                            </div>
                        )}
                        <pre className="goose-scrollbar max-h-64 overflow-y-auto whitespace-pre-wrap break-words p-3 font-mono text-[12px] leading-relaxed">
                            {request.diff_content.split('\n').map((line, i) => {
                                let lineClass = 'text-zinc-400';
                                if (line.startsWith('+')) lineClass = 'text-emerald-400';
                                else if (line.startsWith('-')) lineClass = 'text-red-400';
                                else if (line.startsWith('@')) lineClass = 'text-indigo-400';
                                return (
                                    <span key={i} className={lineClass}>
                                        {line}{'\n'}
                                    </span>
                                );
                            })}
                        </pre>
                    </div>
                )}
            </div>

            {/* Actions */}
            <div className="border-t border-zinc-800/60 px-4 py-3">
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => onReject(request.id)}
                        title="Rechazar (Esc)"
                        className="flex h-9 w-9 items-center justify-center rounded-xl text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
                    >
                        <X size={16} />
                    </button>
                    <button
                        ref={approveRef}
                        onClick={() => onApprove(request.id)}
                        title="Aprobar (Enter)"
                        className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm transition-colors hover:bg-indigo-500"
                    >
                        <Check size={16} />
                    </button>
                </div>
            </div>
        </aside>
    );
};
