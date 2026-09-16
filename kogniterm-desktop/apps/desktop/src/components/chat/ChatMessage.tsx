import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import { ChevronRight, Terminal, Copy, Check } from 'lucide-react';
import { Message } from '../../types/chat';
import { AppliedDiffCard } from './AppliedDiffCard';
import { parseAppliedDiff } from '../../hooks/useChat';

interface ChatMessageProps {
    message: Message;
}

const CodeBlock: React.FC<{ language?: string; codeString: string }> = ({ language, codeString }) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(codeString);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="my-3 rounded-lg overflow-hidden border border-slate-200/80 dark:border-zinc-800 bg-[#121214] text-left shadow-2xs">
            <div className="flex items-center justify-between px-3 py-1.5 bg-slate-100/90 dark:bg-[#18181b] border-b border-slate-200/60 dark:border-zinc-800/80 text-[11px] font-mono text-slate-500 dark:text-zinc-400 select-none">
                <span className="uppercase text-[10px] tracking-wider font-semibold">{language || 'code'}</span>
                <button
                    onClick={handleCopy}
                    className="flex items-center gap-1 text-slate-500 dark:text-zinc-400 hover:text-slate-800 dark:hover:text-zinc-200 transition-colors cursor-pointer py-0.5 px-1.5 rounded hover:bg-slate-200/60 dark:hover:bg-zinc-800"
                    title="Copiar código"
                >
                    {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                    <span className="text-[10px]">{copied ? 'Copiado' : 'Copiar'}</span>
                </button>
            </div>
            <SyntaxHighlighter
                style={vscDarkPlus}
                language={language || 'text'}
                PreTag="div"
                customStyle={{
                    margin: 0,
                    padding: '0.85rem 1rem',
                    background: '#121214',
                    fontSize: '0.8125rem',
                    lineHeight: '1.6',
                    fontFamily: 'var(--font-mono)',
                }}
            >
                {codeString}
            </SyntaxHighlighter>
        </div>
    );
};

const renderCodeBlock = (children: any, className?: string, props?: any) => {
    const match = /language-(\w+)/.exec(className || '');
    const codeString = String(children).replace(/\n$/, '');
    const isMultiLine = codeString.includes('\n');

    if (match || isMultiLine) {
        return <CodeBlock language={match ? match[1] : undefined} codeString={codeString} />;
    }

    return (
        <code
            className="font-mono text-[12px] bg-slate-100 dark:bg-zinc-800/80 border border-slate-200/80 dark:border-zinc-700/60 px-1.5 py-0.5 rounded text-slate-800 dark:text-zinc-200 font-normal"
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
                <div className="w-full my-2 animate-fade-in">
                    <AppliedDiffCard diff={parsedDiff} defaultExpanded={false} />
                </div>
            );
        }

        return (
            <div className="w-full my-1.5 animate-fade-in">
                <button 
                    onClick={() => setIsToolOpen(!isToolOpen)}
                    className="flex items-center gap-1.5 text-[11px] font-mono text-slate-500 dark:text-zinc-400 hover:text-slate-800 dark:hover:text-zinc-200 transition-colors cursor-pointer py-1"
                >
                    <ChevronRight size={12} className={`text-slate-400 dark:text-zinc-500 transition-transform duration-200 ${isToolOpen ? 'rotate-90' : ''}`} />
                    <Terminal size={12} className="text-emerald-500" />
                    <span>Salida de comando ({rawText.split('\n').length} líneas)</span>
                </button>
                {isToolOpen && (
                    <div className="mt-1.5 p-3 rounded-lg bg-[#121214] border border-slate-200/80 dark:border-zinc-800 font-mono text-[11.5px] text-zinc-300 whitespace-pre-wrap max-h-80 overflow-y-auto custom-scrollbar">
                        {rawText}
                    </div>
                )}
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
            <div className="flex w-full my-2 justify-center px-4 animate-fade-in">
                <div className="text-[11px] text-slate-500 dark:text-zinc-400 bg-slate-100/60 dark:bg-zinc-800/40 border border-slate-200/50 dark:border-zinc-800/50 rounded-full px-3 py-1 font-mono tracking-wide">
                    {message.content}
                </div>
            </div>
        );
    }

    const reasoningRaw = typeof message.reasoning === 'string' ? message.reasoning : JSON.stringify(message.reasoning || '');
    const reasoningSingleLine = reasoningRaw.replace(/[*#`_\n\r]/g, ' ').replace(/\s+/g, ' ').trim();

    return (
        <div className={`flex w-full mb-5 ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
            <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} w-full min-w-0`}>
                
                {/* Reasoning Block */}
                {!isUser && message.reasoning && (
                    <div className="w-full mb-2 max-w-full">
                        <button
                            onClick={() => setIsReasoningOpen(!isReasoningOpen)}
                            className="flex items-center gap-1.5 py-1 text-xs text-slate-500 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-zinc-200 transition-colors cursor-pointer select-none max-w-full truncate"
                        >
                            <ChevronRight
                                size={12}
                                className={`transition-transform duration-200 text-slate-400 dark:text-zinc-500 shrink-0 ${isReasoningOpen ? 'rotate-90' : ''}`}
                            />
                            <span className="font-medium text-[11.5px]">Pensamiento</span>
                            {!isReasoningOpen && reasoningSingleLine && (
                                <span className="truncate text-slate-400 dark:text-zinc-500 text-[11px] font-normal min-w-0">
                                    — {reasoningSingleLine}
                                </span>
                            )}
                        </button>

                        {isReasoningOpen && (
                            <div className="text-[12.5px] text-slate-600 dark:text-zinc-400 leading-relaxed pl-3.5 border-l-2 border-slate-200 dark:border-zinc-800 my-1.5">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                        p: ({ children }) => <p className="mb-1.5 last:mb-0 leading-relaxed">{children}</p>,
                                        code: ({ children }) => <code className="font-mono text-[11.5px] bg-slate-100 dark:bg-zinc-800 px-1 py-0.5 rounded">{children}</code>,
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
                    <div className="flex flex-col gap-1 w-full my-1.5">
                        {message.tool_calls.map((tool, idx) => {
                            const argStr = typeof tool.args === 'string' ? tool.args : JSON.stringify(tool.args || {});
                            const displayArgs = argStr
                                .replace(/^{"CommandLine":"|"}$/g, '')
                                .replace(/\\"/g, '"')
                                .replace(/\\n/g, ' ');
                            const shortCmd = displayArgs || tool.name;
                            const sampleTime = (tool as any).execution_time || `${Math.floor(Math.random() * 700 + 80)}ms`;

                            return (
                                <div key={tool.id || idx} className="flex items-center justify-between gap-2 py-1 px-2.5 rounded-md bg-slate-100/60 dark:bg-zinc-800/40 border border-slate-200/50 dark:border-zinc-800/60 text-xs my-0.5 select-none font-mono">
                                    <div className="flex items-center gap-2 truncate min-w-0">
                                        <Terminal size={12} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
                                        <span className="text-slate-500 dark:text-zinc-400 font-sans text-[11px] font-medium">Ejecutado</span>
                                        <span className="text-slate-300 dark:text-zinc-600">·</span>
                                        <span className="truncate text-slate-700 dark:text-zinc-300 text-[11.5px]">{shortCmd}</span>
                                    </div>
                                    <span className="text-slate-400 dark:text-zinc-500 text-[10px] shrink-0 font-mono">
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
                            <div key={index} className="relative group max-w-xs rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-zinc-900 shadow-2xs">
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
                        <div className="max-w-[85%] bg-slate-100/90 dark:bg-zinc-800/80 border border-slate-200/80 dark:border-zinc-700/60 rounded-2xl px-4 py-2.5 my-1 text-slate-800 dark:text-zinc-100 text-[13.5px] leading-relaxed shadow-2xs">
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={{
                                    pre: ({ children }) => <>{children}</>,
                                    code({ node, inline, className, children, ...props }: any) {
                                        return renderCodeBlock(children, className, props);
                                    },
                                    p: ({ children }) => <p className="mb-0 leading-relaxed text-slate-800 dark:text-zinc-100">{children}</p>,
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
                                <div className="w-full my-2">
                                    <AppliedDiffCard diff={parsedDiff} defaultExpanded={true} />
                                </div>
                            );
                        }
                        return (
                            <div className="assistant-msg-text w-full py-1 text-slate-800 dark:text-zinc-200 text-[14px] leading-relaxed select-text">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                        pre: ({ children }) => <>{children}</>,
                                        code({ node, inline, className, children, ...props }: any) {
                                            return renderCodeBlock(children, className, props);
                                        },
                                        p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
                                        ul: ({ children }) => <ul className="list-disc ml-5 mb-3 marker:text-slate-400 dark:marker:text-zinc-500 space-y-1">{children}</ul>,
                                        ol: ({ children }) => <ol className="list-decimal ml-5 mb-3 marker:text-slate-400 dark:marker:text-zinc-500 space-y-1">{children}</ol>,
                                        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                                        h1: ({ children }) => <h1 className="text-lg font-semibold text-slate-900 dark:text-zinc-100 mt-4 mb-2 first:mt-0">{children}</h1>,
                                        h2: ({ children }) => <h2 className="text-base font-semibold text-slate-900 dark:text-zinc-100 mt-3 mb-1.5 first:mt-0">{children}</h2>,
                                        h3: ({ children }) => <h3 className="text-sm font-semibold text-slate-900 dark:text-zinc-100 mt-2 mb-1 first:mt-0">{children}</h3>,
                                        blockquote: ({ children }) => <blockquote className="border-l-2 border-slate-300 dark:border-zinc-700 pl-3 my-2 text-slate-600 dark:text-zinc-400 italic">{children}</blockquote>,
                                        hr: () => <hr className="border-t border-slate-200 dark:border-zinc-800 my-4" />,
                                        a: ({ href, children }) => (
                                            <a href={href} target="_blank" rel="noopener noreferrer" className="text-indigo-600 dark:text-indigo-400 underline underline-offset-2 hover:opacity-80">
                                                {children}
                                            </a>
                                        ),
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
                    <span className={`text-[10px] text-slate-400 dark:text-zinc-500 mt-1 select-none font-mono ${isUser ? 'mr-1' : 'ml-0.5'}`}>
                        {formatTime(message.timestamp)}
                    </span>
                )}

            </div>
        </div>
    );
};
