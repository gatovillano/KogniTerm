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
    const panelRef = useRef<HTMLDivElement>(null);
    const isBash = request.file_path === 'bash';

    // Auto-focus the approve button and handle keyboard shortcuts
    useEffect(() => {
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

    return (
        <div className="approval-overlay">
            <div className="approval-panel" ref={panelRef}>
                {/* Header */}
                <div className="approval-header">
                    <div className="flex items-center gap-2.5">
                        <div className={`p-2 rounded-lg ${isBash ? 'bg-amber-500/10 border border-amber-500/20' : 'bg-indigo-500/10 border border-indigo-500/20'}`}>
                            {isBash
                                ? <Terminal size={16} className="text-amber-400" />
                                : <FileCode size={16} className="text-indigo-400" />
                            }
                        </div>
                        <div>
                            <h3 className="text-sm font-semibold text-zinc-100 tracking-tight">
                                {request.title}
                            </h3>
                            <p className="text-[11px] text-zinc-500 mt-0.5">
                                Aprobación requerida para continuar
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={() => onReject(request.id)}
                        className="p-1.5 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                    >
                        <X size={14} />
                    </button>
                </div>

                {/* Message */}
                <div className="approval-body">
                    <p className="text-sm text-zinc-300 leading-relaxed mb-3">
                        {request.message}
                    </p>

                    {/* Diff / Command Preview */}
                    {request.diff_content && (
                        <div className="approval-code-block">
                            <div className="flex items-center gap-2 mb-2">
                                {request.file_path && (
                                    <span className="text-[11px] font-mono text-zinc-500">
                                        {request.file_path}
                                    </span>
                                )}
                            </div>
                            <pre className="text-[12px] font-mono leading-relaxed whitespace-pre-wrap break-all">
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
                <div className="approval-actions">
                    <div className="flex items-center gap-2 text-[11px] text-zinc-600">
                        <span className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700/50 font-mono text-[10px]">Enter</span>
                        <span>aprobar</span>
                        <span className="mx-1 text-zinc-700">·</span>
                        <span className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700/50 font-mono text-[10px]">Esc</span>
                        <span>rechazar</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => onReject(request.id)}
                            className="approval-btn-reject"
                        >
                            <X size={14} />
                            Rechazar
                        </button>
                        <button
                            onClick={() => onApprove(request.id)}
                            className="approval-btn-approve"
                            autoFocus
                        >
                            <Check size={14} />
                            Aprobar
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};
