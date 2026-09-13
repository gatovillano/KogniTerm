import React, { useState } from 'react';
import { Brain, ChevronDown, ChevronRight } from 'lucide-react';
import { MarkdownRenderer } from './MarkdownRenderer';

interface ThinkingBlockProps {
  thinking: string;
  isDark?: boolean;
}

export function ThinkingBlock({ thinking, isDark = true }: ThinkingBlockProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!thinking || !thinking.trim()) return null;

  return (
    <div className={`my-2 rounded-xl border text-xs overflow-hidden transition-all ${
      isDark 
        ? 'bg-indigo-950/20 border-indigo-500/20 text-indigo-200/90' 
        : 'bg-indigo-50/60 border-indigo-200/60 text-indigo-900/90'
    }`}>
      {/* Botón contraíble */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`w-full flex items-center justify-between px-3 py-2 text-left font-medium transition-colors ${
          isDark 
            ? 'hover:bg-indigo-500/10 text-indigo-300' 
            : 'hover:bg-indigo-100/50 text-indigo-700'
        }`}
      >
        <div className="flex items-center gap-2">
          <Brain className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
          <span className="font-mono text-[11px] uppercase tracking-wider opacity-90">Thinking...</span>
        </div>
        {isExpanded ? (
          <ChevronDown className="w-3.5 h-3.5 opacity-60" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 opacity-60" />
        )}
      </button>

      {/* Contenido expandible */}
      {isExpanded && (
        <div className={`px-3.5 py-2.5 border-t font-mono leading-relaxed whitespace-pre-wrap ${
          isDark 
            ? 'border-indigo-500/15 bg-black/20 text-indigo-200/80' 
            : 'border-indigo-200/50 bg-white/40 text-indigo-900/80'
        }`}>
          <MarkdownRenderer isDark={isDark}>
            {thinking}
          </MarkdownRenderer>
        </div>
      )}
    </div>
  );
}
