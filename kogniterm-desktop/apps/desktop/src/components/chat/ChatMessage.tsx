import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import { User, Bot, Brain, ChevronRight, Wrench, Check } from 'lucide-react';
import { Message } from '../../types/chat';

interface ChatMessageProps {
    message: Message;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
    const isUser = message.role === 'user';
    const isTool = message.role === 'tool';
    const [isReasoningOpen, setIsReasoningOpen] = useState(true);

    if (isTool) {
        return (
            <div className="flex w-full mb-4 justify-start pl-12">
                <div className="flex flex-col gap-1 w-full max-w-[80%]">
                    <div className="flex items-center gap-2 text-[11px] font-bold text-zinc-500 uppercase tracking-widest ml-1">
                        <Check size={12} className="text-emerald-500" />
                        Resultado de Herramienta
                    </div>
                    <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-3 font-mono text-[12px] text-zinc-400 overflow-x-auto whitespace-pre-wrap">
                        {message.content}
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className={`flex w-full mb-6 ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div className={`flex max-w-[85%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
                <div className={`flex-shrink-0 h-10 w-10 rounded-full flex items-center justify-center ${isUser ? 'bg-indigo-600 ml-3 shadow-lg shadow-indigo-500/20' : 'bg-zinc-800 mr-3 border border-zinc-700'}`}>
                    {isUser ? <User size={20} className="text-white" /> : <Bot size={20} className="text-indigo-400" />}
                </div>

                <div className={`flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
                    {/* Reasoning Block */}
                    {!isUser && message.reasoning && (
                        <div className="w-full mb-1">
                            <button
                                onClick={() => setIsReasoningOpen(!isReasoningOpen)}
                                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-800/40 hover:bg-zinc-800/60 border border-zinc-700/50 transition-all group"
                            >
                                <Brain size={14} className="text-indigo-400" />
                                <span className="text-[12px] font-medium text-zinc-400 uppercase tracking-wider">Pensamiento</span>
                                <ChevronRight
                                    size={14}
                                    className={`text-zinc-500 transition-transform duration-300 ${isReasoningOpen ? 'rotate-90' : ''}`}
                                />
                            </button>

                            {isReasoningOpen && (
                                <div className="mt-2 p-3 rounded-xl bg-zinc-900/30 border-l-2 border-indigo-500/30 text-[13px] text-zinc-400 italic leading-relaxed backdrop-blur-sm animate-in fade-in slide-in-from-top-1 markdown-content">
                                    <ReactMarkdown>
                                        {message.reasoning}
                                    </ReactMarkdown>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Tool Calls */}
                    {!isUser && message.tool_calls && message.tool_calls.length > 0 && (
                        <div className="flex flex-col gap-2 w-full mb-2">
                            {message.tool_calls.map((tool, idx) => (
                                <div key={tool.id || idx} className="bg-indigo-500/5 border border-indigo-500/10 rounded-xl p-3 flex flex-col gap-2 border-l-2 border-l-indigo-500">
                                    <div className="flex items-center gap-2">
                                        <Wrench size={14} className="text-indigo-400" />
                                        <span className="text-[12px] font-bold text-indigo-300 font-mono">
                                            {tool.name}()
                                        </span>
                                    </div>
                                    <div className="bg-black/20 rounded-lg p-2 font-mono text-[11px] text-zinc-500">
                                        {typeof tool.args === 'string' ? tool.args : JSON.stringify(tool.args, null, 2)}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {message.content && (
                        <div className={`px-4 py-3 rounded-2xl shadow-sm ${isUser
                            ? 'bg-indigo-600/10 border border-indigo-500/20 text-zinc-100'
                            : 'bg-[#18181b] border border-zinc-800 text-zinc-200 markdown-content'
                            }`}>
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
                                                className="rounded-lg !mt-2 !mb-2 !bg-[#09090b] border border-zinc-800"
                                                {...props}
                                            >
                                                {String(children).replace(/\n$/, '')}
                                            </SyntaxHighlighter>
                                        ) : (
                                            <code className={`${className} bg-zinc-900 px-1.5 py-0.5 rounded text-indigo-300 font-mono text-[13px]`} {...props}>
                                                {children}
                                            </code>
                                        );
                                    },
                                    p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
                                    ul: ({ children }) => <ul className="list-disc ml-5 mb-2 marker:text-indigo-500">{children}</ul>,
                                    ol: ({ children }) => <ol className="list-decimal ml-5 mb-2 marker:text-indigo-500">{children}</ol>,
                                }}
                            >
                                {message.content}
                            </ReactMarkdown>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
