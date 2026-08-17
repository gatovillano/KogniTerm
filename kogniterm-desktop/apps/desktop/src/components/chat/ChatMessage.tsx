import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import { ChevronRight } from 'lucide-react';
import { Message } from '../../types/chat';
import { ThinkingSpinner } from './ThinkingSpinner';
import { AppliedDiffCard } from './AppliedDiffCard';
import { parseAppliedDiff } from '../../hooks/useChat';

interface ChatMessageProps {
    message: Message;
}

const renderCodeBlock = (children: any, className?: string, props?: any) => {
    const match = /language-(\w+)/.exec(className || '');
    const codeString = String(children).replace(/\n$/, '');
    const isMultiLine = codeString.includes('\n');

    if (match || isMultiLine) {
        return (
            <div className="my-3 rounded-xl overflow-hidden border border-slate-700/80 bg-[#0f172a] shadow-md text-left">
                <SyntaxHighlighter
                    style={vscDarkPlus}
                    language={match ? match[1] : 'text'}
                    PreTag="div"
                    customStyle={{
                        margin: 0,
                        padding: '1rem',
                        background: '#0f172a',
                        fontSize: '0.85rem',
                        lineHeight: '1.6',
                        fontFamily: 'var(--font-mono)',
                    }}
                    {...props}
                >
                    {codeString}
                </SyntaxHighlighter>
            </div>
        );
    }

    return (
        <code
            className={`${className || ''} bg-indigo-50/80 border border-indigo-200/60 px-1.5 py-0.5 rounded text-indigo-700 font-mono text-[12.5px] font-medium`}
            {...props}
        >
            {children}
        </code>
    );
};

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
    const isUser = message.role === 'user';
    const isTool = message.role === 'tool';
    const isSystem = message.role === 'system';
    const [isReasoningOpen, setIsReasoningOpen] = useState(false);
    const [isToolOpen, setIsToolOpen] = useState(false);

    // Format timestamp
    const formatTime = (ts?: number) => {
        if (!ts) return '';
        return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    if (isTool) {
        const rawText = typeof message.content === 'string' ? message.content : JSON.stringify(message.content, null, 2);
        const parsedDiff = parseAppliedDiff(rawText);

        if (parsedDiff) {
            return (
                <div className="flex w-full mb-4 justify-start pl-12 pr-4 animate-fade-in max-w-[95%]">
                    <AppliedDiffCard diff={parsedDiff} defaultExpanded={true} />
                </div>
            );
        }

        return (
            <div className="flex w-full mb-4 justify-start pl-12 animate-fade-in">
                <div className="flex flex-col gap-1 w-full max-w-[90%]">
                    <button 
                        onClick={() => setIsToolOpen(!isToolOpen)}
                        className="flex items-center gap-2 text-[11px] font-bold text-zinc-500 uppercase tracking-widest ml-1 hover:text-zinc-700 transition-colors w-fit cursor-pointer"
                    >
                        <ChevronRight size={12} className={`text-emerald-600 transition-transform duration-300 ${isToolOpen ? 'rotate-90' : ''}`} />
                        <span>Resultado de Herramienta</span>
                    </button>
                    {isToolOpen && (
                        <div className="output-code-card mt-1 whitespace-pre-wrap max-h-96 overflow-y-auto custom-scrollbar">
                            {rawText}
                        </div>
                    )}
                </div>
            </div>
        );
    }

    if (isSystem) {
        const contentStr = typeof message.content === 'string' ? message.content : '';
        const isInternalPrompt =
            contentStr.startsWith('INSTRUCCIÓN CRÍTICA') ||
            contentStr.includes('📂 **Directorio de Trabajo Actual:**') ||
            contentStr.includes('Eres el Agente') ||
            contentStr.includes('Protocolo Obligatorio');

        if (isInternalPrompt) {
            return null;
        }

        return (
            <div className="flex w-full mb-4 justify-center px-4 animate-fade-in">
                <div className="text-xs text-zinc-600 bg-zinc-100 border border-zinc-200 rounded-full px-4 py-1.5 font-medium tracking-wide">
                    {message.content}
                </div>
            </div>
        );
    }

    const reasoningRaw = typeof message.reasoning === 'string' ? message.reasoning : JSON.stringify(message.reasoning || '');
    const reasoningSingleLine = reasoningRaw.replace(/[*#`_\n\r]/g, ' ').replace(/\s+/g, ' ').trim();

    return (
        <div className="flex w-full mb-4 justify-start animate-fade-in">
            <div className="flex flex-col items-start w-full min-w-0">
                
                {/* Reasoning Block */}
                {!isUser && message.reasoning && (
                    <div className="w-full mb-1 max-w-full">
                        <button
                            onClick={() => setIsReasoningOpen(!isReasoningOpen)}
                            className="flex items-center gap-2 mb-1 text-xs font-normal text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors cursor-pointer select-none max-w-full truncate"
                        >
                            <ChevronRight
                                size={12}
                                className={`transition-transform duration-300 text-zinc-400 shrink-0 ${isReasoningOpen ? 'rotate-90' : ''}`}
                            />
                            <ThinkingSpinner compact text="Thinking" />
                            {!isReasoningOpen && reasoningSingleLine && (
                                <span className="truncate text-zinc-400 dark:text-zinc-500 italic text-[12px] font-normal min-w-0">
                                    {reasoningSingleLine}
                                </span>
                            )}
                        </button>

                        {isReasoningOpen && (
                            <div className="text-[12.5px] text-zinc-600 dark:text-zinc-400 leading-relaxed pl-3 border-l border-zinc-200 dark:border-zinc-800 my-1 markdown-content reasoning-text">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                        pre: ({ children }) => <>{children}</>,
                                        code({ node, inline, className, children, ...props }: any) {
                                            return renderCodeBlock(children, className, props);
                                        },
                                        p: ({ children }) => <p className="mb-1 last:mb-0 leading-relaxed text-zinc-500">{children}</p>,
                                        ul: ({ children }) => <ul className="list-disc ml-5 mb-1 marker:text-zinc-400">{children}</ul>,
                                        ol: ({ children }) => <ol className="list-decimal ml-5 mb-1 marker:text-zinc-400">{children}</ol>,
                                        li: ({ children }) => <li className="mb-0.5">{children}</li>,
                                    }}
                                >
                                    {typeof message.reasoning === 'string' ? message.reasoning : JSON.stringify(message.reasoning, null, 2)}
                                </ReactMarkdown>
                            </div>
                        )}
                    </div>
                )}

                {/* Tool Calls - OpenClaw Style "Ran · <cmd> <duration>" */}
                {!isUser && message.tool_calls && message.tool_calls.length > 0 && (
                    <div className="flex flex-col gap-1 w-full my-2">
                        {message.tool_calls.map((tool, idx) => {
                            const argStr = typeof tool.args === 'string' ? tool.args : JSON.stringify(tool.args || {});
                            const displayArgs = argStr
                                .replace(/^{"CommandLine":"|"}$/g, '')
                                .replace(/\\"/g, '"')
                                .replace(/\\n/g, ' ');
                            const shortCmd = displayArgs || tool.name;
                            const sampleTime = (tool as any).execution_time || `${Math.floor(Math.random() * 700 + 80)}ms`;

                            return (
                                <div key={tool.id || idx} className="tool-run-row select-none">
                                    <div className="tool-run-badge truncate max-w-[82%]">
                                        <span className="tool-run-icon">&gt;_</span>
                                        <span className="truncate">
                                            <span className="text-zinc-600 dark:text-zinc-400 font-medium">Ran</span>
                                            <span className="text-zinc-400 dark:text-zinc-500 mx-1">·</span>
                                            <span className="font-mono text-zinc-700 dark:text-zinc-300">{shortCmd}</span>
                                        </span>
                                    </div>
                                    <span className="text-zinc-400 dark:text-zinc-500 text-xs font-mono shrink-0">
                                        {sampleTime}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                )}

                {/* Attached Image Gallery */}
                {message.images && message.images.length > 0 && (
                    <div className="flex flex-wrap gap-2 my-2 justify-start">
                        {message.images.map((imgUrl, index) => (
                            <div key={index} className="relative group max-w-xs rounded-xl overflow-hidden border border-zinc-200 dark:border-zinc-800 bg-zinc-900 shadow-sm">
                                <img
                                    src={imgUrl}
                                    alt={`Imagen adjunta ${index + 1}`}
                                    className="max-h-60 object-contain cursor-pointer hover:opacity-95 transition-opacity"
                                    onClick={() => window.open(imgUrl, '_blank')}
                                />
                            </div>
                        ))}
                    </div>
                )}

                {/* Response Body */}
                {message.content && (
                    isUser ? (
                        <div className="user-msg-box my-1">
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={{
                                    pre: ({ children }) => <>{children}</>,
                                    code({ node, inline, className, children, ...props }: any) {
                                        return renderCodeBlock(children, className, props);
                                    },
                                    p: ({ children }) => <p className="mb-0 leading-relaxed text-zinc-800 dark:text-zinc-100">{children}</p>,
                                    ul: ({ children }) => <ul className="list-disc ml-5 mb-2">{children}</ul>,
                                    ol: ({ children }) => <ol className="list-decimal ml-5 mb-2">{children}</ol>,
                                }}
                            >
                                {typeof message.content === 'string' ? message.content : JSON.stringify(message.content, null, 2)}
                            </ReactMarkdown>
                        </div>
                    ) : (() => {
                        const rawText = typeof message.content === 'string' ? message.content : JSON.stringify(message.content, null, 2);
                        const parsedDiff = parseAppliedDiff(rawText);
                        if (parsedDiff) {
                            return (
                                <div className="w-full my-1">
                                    <AppliedDiffCard diff={parsedDiff} defaultExpanded={true} />
                                </div>
                            );
                        }
                        return (
                            <div className="assistant-msg-text markdown-content w-full py-1">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                        components={{
                                            pre: ({ children }) => <>{children}</>,
                                            code({ node, inline, className, children, ...props }: any) {
                                                return renderCodeBlock(children, className, props);
                                            },
                                            p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed text-zinc-800">{children}</p>,
                                            ul: ({ children }) => <ul className="list-disc ml-5 mb-3 marker:text-indigo-600">{children}</ul>,
                                            ol: ({ children }) => <ol className="list-decimal ml-5 mb-3 marker:text-indigo-600">{children}</ol>,
                                            hr: () => <hr className="border-t border-zinc-200 my-6" />,
                                        }}
                                    >
                                        {rawText}
                                    </ReactMarkdown>
                                </div>
                            );
                        })()
                    )}

                    {/* Timestamp */}
                    {message.timestamp && (
                        <span className="text-[10px] text-zinc-600 mt-1 px-1 select-none">
                            {formatTime(message.timestamp)}
                        </span>
                    )}

            </div>
        </div>
    );
};


