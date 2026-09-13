import React, { useState } from 'react';
import { ChevronRight, ChevronDown, Copy, Check, FileCheck } from 'lucide-react';

export interface AppliedDiff {
  id?: string;
  filePath: string;
  toolName?: string;
  additions: number;
  deletions: number;
  diffContent: string;
}

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
    <div className="w-full my-3 overflow-hidden rounded-xl border border-inherit chat-card shadow-sm transition-all duration-200">
      {/* Header */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between gap-3 bg-black/20 px-3.5 py-2.5 cursor-pointer select-none border-b border-inherit"
      >
        <div className="flex min-w-0 items-center gap-2.5">
          <button
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded opacity-70 hover:opacity-100"
            title={isExpanded ? "Colapsar diff" : "Expandir diff"}
          >
            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>

          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <FileCheck size={14} />
          </div>

          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate font-mono text-[12px] font-medium" title={diff.filePath}>
              {diff.filePath || 'archivo_modificado'}
            </span>
            {diff.toolName && (
              <span className="shrink-0 rounded-md bg-black/40 px-1.5 py-0.5 font-mono text-[10px] opacity-70 border border-inherit">
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
            className="flex h-7 w-7 items-center justify-center rounded-lg opacity-70 hover:opacity-100 transition-colors"
          >
            {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
          </button>
        </div>
      </div>

      {/* Visual Proportion Bar */}
      {totalChanges > 0 && (
        <div className="h-1 w-full bg-black/40 flex overflow-hidden">
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
        <div className="overflow-x-auto bg-black/40 p-3">
          <pre className="custom-scrollbar max-h-80 overflow-y-auto font-mono text-[12px] leading-relaxed">
            {diff.diffContent ? (
              diff.diffContent.split('\n').map((line, i) => {
                const trimmed = line.trim();
                let lineClass = 'opacity-70 py-[1px]';
                if (line.startsWith('+') && !line.startsWith('+++')) {
                  lineClass = 'bg-emerald-950/40 text-emerald-300 border-l-2 border-emerald-500/80 pl-2.5 my-[1px]';
                } else if (line.startsWith('-') && !line.startsWith('---')) {
                  lineClass = 'bg-rose-950/40 text-rose-300 border-l-2 border-rose-500/80 pl-2.5 my-[1px]';
                } else if (/^\d+(\s+\d+)?\s*\+/.test(trimmed)) {
                  lineClass = 'bg-emerald-950/40 text-emerald-300 border-l-2 border-emerald-500/80 pl-2.5 my-[1px]';
                } else if (/^\d+(\s+\d+)?\s*-/.test(trimmed)) {
                  lineClass = 'bg-rose-950/40 text-rose-300 border-l-2 border-rose-500/80 pl-2.5 my-[1px]';
                } else if (trimmed.startsWith('@@') || line.startsWith('@')) {
                  lineClass = 'bg-indigo-950/40 text-indigo-300 border-l-2 border-indigo-500/80 font-semibold pl-2.5 my-[2px]';
                } else if (line.startsWith('Index:') || line.startsWith('===') || line.startsWith('---') || line.startsWith('+++')) {
                  lineClass = 'opacity-50 font-semibold pl-2.5';
                } else {
                  lineClass = 'opacity-70 pl-3';
                }

                return (
                  <div key={i} className={`whitespace-pre-wrap break-words ${lineClass}`}>
                    {line}
                  </div>
                );
              })
            ) : (
              <div className="text-xs opacity-50 italic p-2">Sin cambios que mostrar</div>
            )}
          </pre>
        </div>
      )}
    </div>
  );
};
