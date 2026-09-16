import { useState, useEffect } from 'react';
import { HelpCircle, X, Send } from 'lucide-react';
import { QuestionRequest } from '@kogniterm/types';

export interface QuestionModalProps {
  request: QuestionRequest | null;
  onRespond: (id: string, selected: string) => void;
  onCancel?: (id: string) => void;
}

export const QuestionModal: React.FC<QuestionModalProps> = ({
  request,
  onRespond,
  onCancel,
}) => {
  const [freeformText, setFreeformText] = useState('');
  const [isInputFocused, setIsInputFocused] = useState(false);

  useEffect(() => {
    setFreeformText('');
    setIsInputFocused(false);
  }, [request]);

  useEffect(() => {
    if (!request) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (onCancel) onCancel(request.id);
        else onRespond(request.id, 'Cancelado por el usuario.');
        return;
      }

      if (!isInputFocused && /^[1-9]$/.test(e.key)) {
        const idx = parseInt(e.key, 10) - 1;
        if (idx >= 0 && idx < request.options.length) {
          e.preventDefault();
          onRespond(request.id, request.options[idx]);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [request, isInputFocused, onRespond, onCancel]);

  if (!request) return null;

  const handleSelectOption = (option: string) => {
    onRespond(request.id, option);
  };

  const handleSendFreeform = (e: React.FormEvent) => {
    e.preventDefault();
    if (!freeformText.trim()) return;
    onRespond(request.id, freeformText.trim());
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-fade-in">
      <div className="w-full max-w-lg rounded-2xl border border-zinc-700/80 bg-zinc-900 shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4 bg-zinc-900/80">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400">
              <HelpCircle size={18} />
            </div>
            <h3 className="font-semibold text-sm text-zinc-100">KogniTerm necesita tu respuesta</h3>
          </div>
          {onCancel && (
            <button
              onClick={() => onCancel(request.id)}
              className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            >
              <X size={18} />
            </button>
          )}
        </div>

        {/* Question body */}
        <div className="p-5 space-y-4">
          <p className="text-sm text-zinc-200 leading-relaxed font-medium">{request.question}</p>

          {request.details && (
            <p className="text-xs text-zinc-400 leading-relaxed bg-zinc-950/60 p-3 rounded-xl border border-zinc-800">
              {request.details}
            </p>
          )}

          {/* Options */}
          <div className="space-y-2 pt-2">
            {request.options.map((option, idx) => (
              <button
                key={option}
                onClick={() => handleSelectOption(option)}
                className="w-full flex items-center justify-between p-3 rounded-xl border border-zinc-800 bg-zinc-950/40 hover:bg-indigo-600/10 hover:border-indigo-500/40 text-left text-xs text-zinc-200 transition-all group"
              >
                <span>{option}</span>
                <span className="font-mono text-[10px] text-zinc-500 group-hover:text-indigo-400 bg-zinc-800 px-1.5 py-0.5 rounded">
                  [{idx + 1}]
                </span>
              </button>
            ))}
          </div>

          {/* Custom text option */}
          <form onSubmit={handleSendFreeform} className="pt-2 flex gap-2">
            <input
              type="text"
              placeholder="O escribe otra respuesta..."
              value={freeformText}
              onChange={(e) => setFreeformText(e.target.value)}
              onFocus={() => setIsInputFocused(true)}
              onBlur={() => setIsInputFocused(false)}
              className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={!freeformText.trim()}
              className="flex items-center justify-center rounded-xl bg-indigo-600 px-3.5 py-2 text-white hover:bg-indigo-500 disabled:opacity-40 transition-colors"
            >
              <Send size={14} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
