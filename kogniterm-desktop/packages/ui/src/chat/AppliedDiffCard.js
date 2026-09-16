import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { ChevronRight, ChevronDown, Copy, Check, FileCheck } from 'lucide-react';
export const AppliedDiffCard = ({ diff, defaultExpanded = true, }) => {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);
    const [copied, setCopied] = useState(false);
    const totalChanges = diff.additions + diff.deletions;
    const additionsPercent = totalChanges > 0 ? (diff.additions / totalChanges) * 100 : 50;
    const deletionsPercent = totalChanges > 0 ? (diff.deletions / totalChanges) * 100 : 50;
    const handleCopy = (e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(diff.diffContent);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };
    return (_jsxs("div", { className: "w-full my-2 overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-900/50 shadow-sm transition-all duration-200 hover:border-zinc-700/80", children: [_jsxs("div", { onClick: () => setIsExpanded(!isExpanded), className: "flex items-center justify-between gap-3 border-b border-zinc-800/60 bg-zinc-900/80 px-3.5 py-2.5 cursor-pointer select-none hover:bg-zinc-900/90", children: [_jsxs("div", { className: "flex min-w-0 items-center gap-2.5", children: [_jsx("button", { className: "flex h-5 w-5 shrink-0 items-center justify-center rounded text-zinc-400 hover:text-zinc-200", title: isExpanded ? 'Colapsar diff' : 'Expandir diff', children: isExpanded ? _jsx(ChevronDown, { size: 14 }) : _jsx(ChevronRight, { size: 14 }) }), _jsx("div", { className: "flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400", children: _jsx(FileCheck, { size: 14 }) }), _jsxs("div", { className: "flex min-w-0 items-center gap-2", children: [_jsx("span", { className: "truncate font-mono text-[12px] font-medium text-zinc-200", title: diff.filePath, children: diff.filePath || 'archivo_modificado' }), diff.toolName && (_jsx("span", { className: "shrink-0 rounded-md bg-zinc-800/80 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400 border border-zinc-700/50", children: diff.toolName }))] })] }), _jsxs("div", { className: "flex items-center gap-2 shrink-0", children: [_jsxs("div", { className: "flex items-center gap-1.5 font-mono text-[11px] font-semibold", children: [_jsxs("span", { className: "rounded bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 text-emerald-400", children: ["+", diff.additions] }), _jsxs("span", { className: "rounded bg-rose-500/10 border border-rose-500/20 px-1.5 py-0.5 text-rose-400", children: ["-", diff.deletions] })] }), _jsx("button", { onClick: handleCopy, title: "Copiar diff", className: "flex h-7 w-7 items-center justify-center rounded-lg text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200", children: copied ? _jsx(Check, { size: 13, className: "text-emerald-400" }) : _jsx(Copy, { size: 13 }) })] })] }), totalChanges > 0 && (_jsxs("div", { className: "h-1 w-full bg-zinc-950 flex overflow-hidden", children: [_jsx("div", { style: { width: `${additionsPercent}%` }, className: "bg-emerald-500 h-full transition-all duration-300" }), _jsx("div", { style: { width: `${deletionsPercent}%` }, className: "bg-rose-500 h-full transition-all duration-300" })] })), isExpanded && (_jsx("div", { className: "overflow-x-auto bg-zinc-950/60 p-3", children: _jsx("pre", { className: "goose-scrollbar max-h-80 overflow-y-auto font-mono text-[12px] leading-relaxed", children: diff.diffContent ? (diff.diffContent.split('\n').map((line, i) => {
                        const trimmed = line.trim();
                        if (trimmed.startsWith('@@')) {
                            return (_jsx("div", { className: "text-cyan-400/80 bg-cyan-950/20 px-2 py-0.5 rounded my-0.5", children: line }, i));
                        }
                        if (line.startsWith('---') ||
                            line.startsWith('+++') ||
                            line.startsWith('Index:') ||
                            line.startsWith('diff --git')) {
                            return (_jsx("div", { className: "text-zinc-500 font-semibold px-2", children: line }, i));
                        }
                        if (line.startsWith('+')) {
                            return (_jsx("div", { className: "text-emerald-300 bg-emerald-950/30 px-2 py-0.2 rounded-sm", children: line }, i));
                        }
                        if (line.startsWith('-')) {
                            return (_jsx("div", { className: "text-rose-300 bg-rose-950/30 px-2 py-0.2 rounded-sm", children: line }, i));
                        }
                        return (_jsx("div", { className: "text-zinc-400 px-2", children: line }, i));
                    })) : (_jsx("span", { className: "text-zinc-500 italic", children: "Diff vac\u00EDo" })) }) }))] }));
};
