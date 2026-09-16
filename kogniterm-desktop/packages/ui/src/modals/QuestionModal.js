import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
import { HelpCircle, X, Send } from 'lucide-react';
export const QuestionModal = ({ request, onRespond, onCancel, }) => {
    const [freeformText, setFreeformText] = useState('');
    const [isInputFocused, setIsInputFocused] = useState(false);
    useEffect(() => {
        setFreeformText('');
        setIsInputFocused(false);
    }, [request]);
    useEffect(() => {
        if (!request)
            return;
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                if (onCancel)
                    onCancel(request.id);
                else
                    onRespond(request.id, 'Cancelado por el usuario.');
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
    if (!request)
        return null;
    const handleSelectOption = (option) => {
        onRespond(request.id, option);
    };
    const handleSendFreeform = (e) => {
        e.preventDefault();
        if (!freeformText.trim())
            return;
        onRespond(request.id, freeformText.trim());
    };
    return (_jsx("div", { className: "fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-fade-in", children: _jsxs("div", { className: "w-full max-w-lg rounded-2xl border border-zinc-700/80 bg-zinc-900 shadow-2xl overflow-hidden flex flex-col", children: [_jsxs("div", { className: "flex items-center justify-between border-b border-zinc-800 px-5 py-4 bg-zinc-900/80", children: [_jsxs("div", { className: "flex items-center gap-2.5", children: [_jsx("div", { className: "flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400", children: _jsx(HelpCircle, { size: 18 }) }), _jsx("h3", { className: "font-semibold text-sm text-zinc-100", children: "KogniTerm necesita tu respuesta" })] }), onCancel && (_jsx("button", { onClick: () => onCancel(request.id), className: "rounded-lg p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200", children: _jsx(X, { size: 18 }) }))] }), _jsxs("div", { className: "p-5 space-y-4", children: [_jsx("p", { className: "text-sm text-zinc-200 leading-relaxed font-medium", children: request.question }), request.details && (_jsx("p", { className: "text-xs text-zinc-400 leading-relaxed bg-zinc-950/60 p-3 rounded-xl border border-zinc-800", children: request.details })), _jsx("div", { className: "space-y-2 pt-2", children: request.options.map((option, idx) => (_jsxs("button", { onClick: () => handleSelectOption(option), className: "w-full flex items-center justify-between p-3 rounded-xl border border-zinc-800 bg-zinc-950/40 hover:bg-indigo-600/10 hover:border-indigo-500/40 text-left text-xs text-zinc-200 transition-all group", children: [_jsx("span", { children: option }), _jsxs("span", { className: "font-mono text-[10px] text-zinc-500 group-hover:text-indigo-400 bg-zinc-800 px-1.5 py-0.5 rounded", children: ["[", idx + 1, "]"] })] }, option))) }), _jsxs("form", { onSubmit: handleSendFreeform, className: "pt-2 flex gap-2", children: [_jsx("input", { type: "text", placeholder: "O escribe otra respuesta...", value: freeformText, onChange: (e) => setFreeformText(e.target.value), onFocus: () => setIsInputFocused(true), onBlur: () => setIsInputFocused(false), className: "flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-indigo-500" }), _jsx("button", { type: "submit", disabled: !freeformText.trim(), className: "flex items-center justify-center rounded-xl bg-indigo-600 px-3.5 py-2 text-white hover:bg-indigo-500 disabled:opacity-40 transition-colors", children: _jsx(Send, { size: 14 }) })] })] })] }) }));
};
