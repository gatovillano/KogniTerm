import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import { User, Bot, ChevronRight, Terminal } from 'lucide-react';
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
    const [isReasoningOpen, setIsReasoningOpen] = useState(true);
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

    return (
        <div className={`flex w-full mb-6 ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
            <div className={`flex max-w-[85%] ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start w-full`}>
                
                {/* Avatar Icon */}
                <div className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center ${isUser ? 'bg-zinc-200 ml-3 border border-zinc-300' : 'bg-transparent mr-3 border-0'}`}>
                    {isUser ? (
                        <User size={16} className="text-zinc-700" />
                    ) : (
                        <div className="h-6 w-6 rounded-md bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-sm">
                            <Bot size={13} className="text-white" />
                        </div>
                    )}
                </div>

                <div className={`flex flex-col gap-1.5 ${isUser ? 'items-end' : 'items-start'} w-full min-w-0`}>
                    
                    {/* Username Header */}
                    <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-0.5 px-1">
                        {isUser ? 'Tú' : 'KogniTerm'}
                    </span>

                    {/* Reasoning Block */}
                    {!isUser && message.reasoning && (
                        <div className="w-full mb-2">
                            <button
                                onClick={() => setIsReasoningOpen(!isReasoningOpen)}
                                className="flex items-center gap-1.5 mb-1.5 text-xs font-medium text-zinc-500 italic hover:text-zinc-700 transition-colors"
                            >
                                <ChevronRight
                                    size={12}
                                    className={`transition-transform duration-300 text-zinc-400 ${isReasoningOpen ? 'rotate-90' : ''}`}
                                />
                                <ThinkingSpinner compact text="KogniTerm está pensando..." />
                            </button>

                            {isReasoningOpen && (
                                <div className="text-[13px] text-zinc-600 italic leading-relaxed pl-3 border-l border-zinc-200 mb-2 markdown-content reasoning-text">
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                            pre: ({ children }) => <>{children}</>,
                                            code({ node, inline, className, children, ...props }: any) {
                                                return renderCodeBlock(children, className, props);
                                            },
                                            p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed text-zinc-500">{children}</p>,
                                            ul: ({ children }) => <ul className="list-disc ml-5 mb-2 marker:text-zinc-400">{children}</ul>,
                                            ol: ({ children }) => <ol className="list-decimal ml-5 mb-2 marker:text-zinc-400">{children}</ol>,
                                            li: ({ children }) => <li className="mb-1">{children}</li>,
                                            hr: () => <hr className="border-t border-zinc-200 my-4" />,
                                            h1: ({ children }) => <h1 className="text-sm font-bold text-zinc-700 mt-3 mb-1.5">{children}</h1>,
                                            h2: ({ children }) => <h2 className="text-xs font-bold text-zinc-700 mt-2.5 mb-1">{children}</h2>,
                                            h3: ({ children }) => <h3 className="text-[11px] font-bold text-zinc-700 mt-2 mb-1">{children}</h3>,
                                        }}
                                    >
                                        {typeof message.reasoning === 'string' ? message.reasoning : JSON.stringify(message.reasoning, null, 2)}
                                    </ReactMarkdown>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Tool Calls */}
                    {!isUser && message.tool_calls && message.tool_calls.length > 0 && (
                        <div className="flex flex-col gap-2 w-full mb-3">
                            {message.tool_calls.map((tool, idx) => {
                                const argStr = typeof tool.args === 'string' ? tool.args : JSON.stringify(tool.args);
                                const displayArgs = argStr.replace(/^{"CommandLine":"|"}$/g, '').replace(/\\"/g, '"');

                                return (
                                    <div key={tool.id || idx} className="tool-status-badge w-fit max-w-full">
                                        <Terminal size={13} className="text-emerald-600 animate-pulse shrink-0" />
                                        <span className="truncate">
                                            running <span className="font-semibold text-zinc-900">{tool.name}</span>
                                            {displayArgs && ` ${displayArgs}`}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* Attached Image Gallery */}
                    {message.images && message.images.length > 0 && (
                        <div className={`flex flex-wrap gap-2 my-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
                            {message.images.map((imgUrl, index) => (
                                <div key={index} className="relative group max-w-xs rounded-xl overflow-hidden border border-zinc-200 dark:border-zinc-800 bg-zinc-900 shadow-md">
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

                    {/* Response body */}
                    {message.content && (
                        isUser ? (
                            <div className="user-msg-bubble">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                        pre: ({ children }) => <>{children}</>,
                                        code({ node, inline, className, children, ...props }: any) {
                                            return renderCodeBlock(children, className, props);
                                        },
                                        p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed text-zinc-800">{children}</p>,
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
                                <div className="assistant-msg-text markdown-content w-full px-1">
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
        </div>
    );
};

