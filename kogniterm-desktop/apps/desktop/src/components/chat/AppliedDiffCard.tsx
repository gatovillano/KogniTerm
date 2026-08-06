import React, { useState } from 'react';
import { ChevronRight, ChevronDown, Copy, Check, FileCheck } from 'lucide-react';
import { AppliedDiff } from '../../types/chat';

interface AppliedDiffCardProps {
    diff: AppliedDiff;
    defaultExpanded?: boolean;
}

export const AppliedDiffCard: React.FC<AppliedDiffCardProps> = ({
    diff,
    defaultExpanded = true,
}) => {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);
    const [copied, setCopied] = useState(false);

    const totalChanges = diff.additions + diff.deletions;
    const additionsPercent = totalChanges > 0 ? (diff.additions / totalChanges) * 100 : 50;
    const deletionsPercent = totalChanges > 0 ? (diff.deletions / totalChanges) * 100 : 50;

    const handleCopy = (e: React.MouseEvent) => {
        e.stopPropagation();
        navigator.clipboard.writeText(diff.diffContent);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="w-full my-2 overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-900/50 shadow-sm transition-all duration-200 hover:border-zinc-700/80">
            {/* Header */}
            <div
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center justify-between gap-3 border-b border-zinc-800/60 bg-zinc-900/80 px-3.5 py-2.5 cursor-pointer select-none hover:bg-zinc-900/90"
            >
                <div className="flex min-w-0 items-center gap-2.5">
                    <button
                        className="flex h-5 w-5 shrink-0 items-center justify-center rounded text-zinc-400 hover:text-zinc-200"
                        title={isExpanded ? "Colapsar diff" : "Expandir diff"}
                    >
                        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>

                    <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                        <FileCheck size={14} />
                    </div>

                    <div className="flex min-w-0 items-center gap-2">
                        <span className="truncate font-mono text-[12px] font-medium text-zinc-200" title={diff.filePath}>
                            {diff.filePath || 'archivo_modificado'}
                        </span>
                        {diff.toolName && (
                            <span className="shrink-0 rounded-md bg-zinc-800/80 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400 border border-zinc-700/50">
                                {diff.toolName}
                            </span>
                        )}
                    </div>
                </div>

                {/* Stats & Actions */}
                <div className="flex items-center gap-2 shrink-0">
                    <div className="flex items-center gap-1.5 font-mono text-[11px] font-semibold">
                        <span className="rounded bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 text-emerald-400">
                            +{diff.additions}
                        </span>
                        <span className="rounded bg-rose-500/10 border border-rose-500/20 px-1.5 py-0.5 text-rose-400">
                            -{diff.deletions}
                        </span>
                    </div>

                    <button
                        onClick={handleCopy}
                        title="Copiar diff"
                        className="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
                    >
                        {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                    </button>
                </div>
            </div>

            {/* Visual Proportion Bar */}
            {totalChanges > 0 && (
                <div className="h-1 w-full bg-zinc-950 flex overflow-hidden">
                    <div
                        style={{ width: `${additionsPercent}%` }}
                        className="bg-emerald-500 h-full transition-all duration-300"
                    />
                    <div
                        style={{ width: `${deletionsPercent}%` }}
                        className="bg-rose-500 h-full transition-all duration-300"
                    />
                </div>
            )}

            {/* Expanded Diff Viewer */}
            {isExpanded && (
                <div className="overflow-x-auto bg-zinc-950/60 p-3">
                    <pre className="goose-scrollbar max-h-80 overflow-y-auto font-mono text-[12px] leading-relaxed">
                        {diff.diffContent ? (
                            diff.diffContent.split('\n').map((line, i) => {
                                let lineClass = 'text-zinc-400 py-[1px]';
                                if (line.startsWith('+')) {
                                    lineClass = 'bg-emerald-950/30 text-emerald-300 border-l-2 border-emerald-500/80 pl-2.5 my-[1px]';
                                } else if (line.startsWith('-')) {
                                    lineClass = 'bg-rose-950/30 text-rose-300 border-l-2 border-rose-500/80 pl-2.5 my-[1px]';
                                } else if (line.startsWith('@')) {
                                    lineClass = 'bg-indigo-950/40 text-indigo-300 border-l-2 border-indigo-500/80 font-semibold pl-2.5 my-[2px]';
                                } else if (line.startsWith('Index:') || line.startsWith('===')) {
                                    lineClass = 'text-zinc-500 font-semibold pl-2.5';
                                } else {
                                    lineClass = 'text-zinc-400 pl-3';
                                }

                                return (
                                    <div key={i} className={`whitespace-pre-wrap break-words ${lineClass}`}>
                                        {line}
                                    </div>
                                );
                            })
                        ) : (
                            <div className="text-xs text-zinc-500 italic p-2">Sin cambios que mostrar</div>
                        )}
                    </pre>
                </div>
            )}
        </div>
    );
};
