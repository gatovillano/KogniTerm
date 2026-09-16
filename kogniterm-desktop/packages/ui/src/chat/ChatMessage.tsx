import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import { ChevronRight } from 'lucide-react';
import { Message, parseAppliedDiff } from '@kogniterm/types';
import { AppliedDiffCard } from './AppliedDiffCard';

export interface ChatMessageProps {
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
      className="bg-slate-800 text-pink-400 dark:text-pink-300 font-mono text-[0.85em] px-1.5 py-0.5 rounded-md border border-slate-700/50"
      {...props}
    >
      {children}
    </code>
  );
};

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
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

  return (
    <div
      className={`group flex flex-col w-full px-4 py-4 transition-colors ${
        isUser ? 'bg-transparent' : 'bg-slate-900/40 border-y border-slate-800/40'
      }`}
    >
      <div className="flex items-start gap-4 max-w-4xl mx-auto w-full">
        {/* Avatar */}
        <div
          className={`flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-xl font-medium text-xs shadow-sm ${
            isUser
              ? 'bg-gradient-to-tr from-cyan-600 to-blue-600 text-white shadow-cyan-900/20'
              : 'bg-gradient-to-tr from-purple-600 to-indigo-600 text-white shadow-purple-900/20'
          }`}
        >
          {isUser ? 'U' : 'K'}
        </div>

        {/* Content Body */}
        <div className="flex flex-col min-w-0 flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-slate-200">
              {isUser ? 'Tú' : 'KogniTerm'}
            </span>
            <span className="text-[11px] text-slate-500">
              {new Date(message.timestamp).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>

          {/* Reasoning / CoT accordion */}
          {reasoningContent && (
            <div className="rounded-xl border border-slate-800 bg-slate-950/40 overflow-hidden text-xs">
              <button
                onClick={() => setIsReasoningExpanded(!isReasoningExpanded)}
                className="flex items-center gap-2 w-full px-3 py-2 text-slate-400 hover:text-slate-200 bg-slate-900/50 hover:bg-slate-900 transition-colors"
              >
                <ChevronRight
                  size={14}
                  className={`transition-transform duration-200 ${
                    isReasoningExpanded ? 'rotate-90' : ''
                  }`}
                />
                <span className="font-mono font-medium">Razonamiento (CoT)</span>
              </button>
              {isReasoningExpanded && (
                <div className="p-3 text-slate-300 font-mono text-[11px] leading-relaxed border-t border-slate-800 whitespace-pre-wrap">
                  {reasoningContent}
                </div>
              )}
            </div>
          )}

          {/* Diff card if present */}
          {appliedDiff && <AppliedDiffCard diff={appliedDiff} />}

          {/* Main message markdown */}
          {mainContent && (
            <div className="prose prose-invert prose-slate max-w-none text-sm text-slate-300 leading-relaxed break-words">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ className, children, ...props }) {
                    return renderCodeBlock(children, className, props);
                  },
                }}
              >
                {mainContent}
              </ReactMarkdown>
            </div>
          )}

          {/* Tool Calls badge list if any */}
          {message.tool_calls && message.tool_calls.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-2">
              {message.tool_calls.map((tc) => (
                <span
                  key={tc.id}
                  className="inline-flex items-center gap-1 rounded-md bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-purple-300 border border-slate-700/60"
                >
                  ⚡ {tc.name}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
