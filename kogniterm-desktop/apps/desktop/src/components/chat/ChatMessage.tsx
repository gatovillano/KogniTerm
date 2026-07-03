import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import { User, Bot, ChevronRight, Terminal } from 'lucide-react';
import { Message } from '../../types/chat';

interface ChatMessageProps {
    message: Message;
}

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
        return (
            <div className="flex w-full mb-4 justify-start pl-12 animate-fade-in">
                <div className="flex flex-col gap-1 w-full max-w-[90%]">
                    <button 
                        onClick={() => setIsToolOpen(!isToolOpen)}
                        className="flex items-center gap-2 text-[11px] font-bold text-zinc-500 uppercase tracking-widest ml-1 hover:text-zinc-300 transition-colors w-fit"
                    >
                        <ChevronRight size={12} className={`text-emerald-500 transition-transform duration-300 ${isToolOpen ? 'rotate-90' : ''}`} />
                        <span>Resultado de Herramienta</span>
                    </button>
                    {isToolOpen && (
                        <div className="output-code-card mt-1 whitespace-pre-wrap max-h-96 overflow-y-auto custom-scrollbar">
                            {typeof message.content === 'string' ? message.content : JSON.stringify(message.content, null, 2)}
                        </div>
                    )}
                </div>
            </div>
        );
    }

    if (isSystem) {
        return (
            <div className="flex w-full mb-4 justify-center px-4 animate-fade-in">
                <div className="text-xs text-zinc-600 bg-zinc-950/40 border border-zinc-900 rounded-full px-4 py-1.5 font-medium tracking-wide">
                    {message.content}
                </div>
            </div>
        );
    }

    return (
        <div className={`flex w-full mb-6 ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
            <div className={`flex max-w-[85%] ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start w-full`}>
                
                {/* Avatar Icon */}
                <div className={`flex-shrink-0 h-9 w-9 rounded-full flex items-center justify-center ${isUser ? 'bg-zinc-800 ml-3.5 border border-zinc-700' : 'bg-transparent mr-3.5 border-0'}`}>
                    {isUser ? (
                        <User size={18} className="text-zinc-200" />
                    ) : (
                        <div className="h-6 w-6 rounded-md bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
                            <Bot size={14} className="text-white" />
                        </div>
                    )}
                </div>

                <div className={`flex flex-col gap-1.5 ${isUser ? 'items-end' : 'items-start'} w-full min-w-0`}>
                    
                    {/* Username Header */}
                    <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-0.5 px-1">
                        {isUser ? 'Tú' : 'KogniTerm'}
                    </span>

                    {/* Reasoning Block */}
                    {!isUser && message.reasoning && (
                        <div className="w-full mb-2">
                            <button
                                onClick={() => setIsReasoningOpen(!isReasoningOpen)}
                                className="flex items-center gap-1.5 mb-1.5 text-xs font-medium text-zinc-500 italic hover:text-zinc-400 transition-colors"
                            >
                                <ChevronRight
                                    size={12}
                                    className={`transition-transform duration-300 text-zinc-500 ${isReasoningOpen ? 'rotate-90' : ''}`}
                                />
                                <span>Thinking</span>
                            </button>

                            {isReasoningOpen && (
                                <div className="text-[13px] text-zinc-500 italic leading-relaxed pl-3 border-l border-zinc-800/80 mb-2 markdown-content reasoning-text">
                                    <ReactMarkdown>
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
                                        <Terminal size={13} className="text-emerald-500 animate-pulse shrink-0" />
                                        <span className="truncate">
                                            running <span className="font-semibold text-white">{tool.name}</span>
                                            {displayArgs && ` ${displayArgs}`}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* Response body */}
                    {message.content && (
                        isUser ? (
                            <div className="user-msg-bubble">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                        code({ node, inline, className, children, ...props }: any) {
                                            const match = /language-(\w+)/.exec(className || '');
                                            return !inline && match ? (
                                                <SyntaxHighlighter
                                                    style={vscDarkPlus}
                                                    language={match[1]}
                                                    PreTag="div"
                                                    className="rounded-lg !mt-2 !mb-2 !bg-[#0c0c0e] border border-zinc-800"
                                                    {...props}
                                                >
                                                    {String(children).replace(/\n$/, '')}
                                                </SyntaxHighlighter>
                                            ) : (
                                                <code className={`${className} bg-zinc-200 px-1.5 py-0.5 rounded text-zinc-800 font-mono text-[13px]`} {...props}>
                                                    {children}
                                                </code>
                                            );
                                        },
                                        p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
                                        ul: ({ children }) => <ul className="list-disc ml-5 mb-2">{children}</ul>,
                                        ol: ({ children }) => <ol className="list-decimal ml-5 mb-2">{children}</ol>,
                                    }}
                                >
                                    {typeof message.content === 'string' ? message.content : JSON.stringify(message.content, null, 2)}
                                </ReactMarkdown>
                            </div>
                        ) : (
                            <div className="assistant-msg-text markdown-content w-full px-1">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                        code({ node, inline, className, children, ...props }: any) {
                                            const match = /language-(\w+)/.exec(className || '');
                                            return !inline && match ? (
                                                <SyntaxHighlighter
                                                    style={vscDarkPlus}
                                                    language={match[1]}
                                                    PreTag="div"
                                                    className="rounded-xl !mt-3 !mb-3 !bg-[#16161a] !border !border-zinc-800/80 p-4 shadow-inner"
                                                    {...props}
                                                >
                                                    {String(children).replace(/\n$/, '')}
                                                </SyntaxHighlighter>
                                            ) : (
                                                <code className={`${className} bg-zinc-900/80 border border-zinc-800/60 px-1.5 py-0.5 rounded text-indigo-300 font-mono text-[13px]`} {...props}>
                                                    {children}
                                                </code>
                                            );
                                        },
                                        p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed text-zinc-300">{children}</p>,
                                        ul: ({ children }) => <ul className="list-disc ml-5 mb-3 marker:text-indigo-500">{children}</ul>,
                                        ol: ({ children }) => <ol className="list-decimal ml-5 mb-3 marker:text-indigo-500">{children}</ol>,
                                        hr: () => <hr className="border-t border-zinc-800/60 my-6" />,
                                    }}
                                >
                                    {typeof message.content === 'string' ? message.content : JSON.stringify(message.content, null, 2)}
                                </ReactMarkdown>
                            </div>
                        )
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
