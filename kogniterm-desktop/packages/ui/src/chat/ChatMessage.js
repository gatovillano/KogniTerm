import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import { ChevronRight } from 'lucide-react';
import { parseAppliedDiff } from '@kogniterm/types';
import { AppliedDiffCard } from './AppliedDiffCard';
const renderCodeBlock = (children, className, props) => {
    const match = /language-(\w+)/.exec(className || '');
    const codeString = String(children).replace(/\n$/, '');
    const isMultiLine = codeString.includes('\n');
    if (match || isMultiLine) {
        return (_jsx("div", { className: "my-3 rounded-xl overflow-hidden border border-slate-700/80 bg-[#0f172a] shadow-md text-left", children: _jsx(SyntaxHighlighter, { style: vscDarkPlus, language: match ? match[1] : 'text', PreTag: "div", customStyle: {
                    margin: 0,
                    padding: '1rem',
                    background: '#0f172a',
                    fontSize: '0.85rem',
                    lineHeight: '1.6',
                    fontFamily: 'var(--font-mono)',
                }, ...props, children: codeString }) }));
    }
    return (_jsx("code", { className: "bg-slate-800 text-pink-400 dark:text-pink-300 font-mono text-[0.85em] px-1.5 py-0.5 rounded-md border border-slate-700/50", ...props, children: children }));
};
export const ChatMessage = ({ message }) => {
    const [isReasoningExpanded, setIsReasoningExpanded] = useState(false);
    const isUser = message.role === 'user';
    // Extract thinking blocks (<thought>...</thought> or <thinking>...</thinking>)
    let reasoningContent = message.reasoning || '';
    let mainContent = message.content || '';
    const thoughtMatch = mainContent.match(/<(?:thought|thinking)>([\s\S]*?)<\/(?:thought|thinking)>/);
    if (thoughtMatch) {
        reasoningContent = (reasoningContent ? reasoningContent + '\n\n' : '') + thoughtMatch[1].trim();
        mainContent = mainContent.replace(/<(?:thought|thinking)>[\s\S]*?<\/(?:thought|thinking)>/, '').trim();
    }
    // Parse diff if applicable
    const appliedDiff = !isUser ? parseAppliedDiff(mainContent) : null;
    return (_jsx("div", { className: `group flex flex-col w-full px-4 py-4 transition-colors ${isUser ? 'bg-transparent' : 'bg-slate-900/40 border-y border-slate-800/40'}`, children: _jsxs("div", { className: "flex items-start gap-4 max-w-4xl mx-auto w-full", children: [_jsx("div", { className: `flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-xl font-medium text-xs shadow-sm ${isUser
                        ? 'bg-gradient-to-tr from-cyan-600 to-blue-600 text-white shadow-cyan-900/20'
                        : 'bg-gradient-to-tr from-purple-600 to-indigo-600 text-white shadow-purple-900/20'}`, children: isUser ? 'U' : 'K' }), _jsxs("div", { className: "flex flex-col min-w-0 flex-1 space-y-2", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: "font-semibold text-sm text-slate-200", children: isUser ? 'Tú' : 'KogniTerm' }), _jsx("span", { className: "text-[11px] text-slate-500", children: new Date(message.timestamp).toLocaleTimeString([], {
                                        hour: '2-digit',
                                        minute: '2-digit',
                                    }) })] }), reasoningContent && (_jsxs("div", { className: "rounded-xl border border-slate-800 bg-slate-950/40 overflow-hidden text-xs", children: [_jsxs("button", { onClick: () => setIsReasoningExpanded(!isReasoningExpanded), className: "flex items-center gap-2 w-full px-3 py-2 text-slate-400 hover:text-slate-200 bg-slate-900/50 hover:bg-slate-900 transition-colors", children: [_jsx(ChevronRight, { size: 14, className: `transition-transform duration-200 ${isReasoningExpanded ? 'rotate-90' : ''}` }), _jsx("span", { className: "font-mono font-medium", children: "Razonamiento (CoT)" })] }), isReasoningExpanded && (_jsx("div", { className: "p-3 text-slate-300 font-mono text-[11px] leading-relaxed border-t border-slate-800 whitespace-pre-wrap", children: reasoningContent }))] })), appliedDiff && _jsx(AppliedDiffCard, { diff: appliedDiff }), mainContent && (_jsx("div", { className: "prose prose-invert prose-slate max-w-none text-sm text-slate-300 leading-relaxed break-words", children: _jsx(ReactMarkdown, { remarkPlugins: [remarkGfm], components: {
                                    code({ className, children, ...props }) {
                                        return renderCodeBlock(children, className, props);
                                    },
                                }, children: mainContent }) })), message.tool_calls && message.tool_calls.length > 0 && (_jsx("div", { className: "flex flex-wrap gap-1.5 pt-2", children: message.tool_calls.map((tc) => (_jsxs("span", { className: "inline-flex items-center gap-1 rounded-md bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-purple-300 border border-slate-700/60", children: ["\u26A1 ", tc.name] }, tc.id))) }))] })] }) }));
};
