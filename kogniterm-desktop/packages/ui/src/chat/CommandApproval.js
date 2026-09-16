import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useRef } from 'react';
import { ShieldCheck, Check, X } from 'lucide-react';
export const CommandApproval = ({ request, onApprove, onReject, isInline = false, }) => {
    const approveRef = useRef(null);
    const handleApproveAlways = async () => {
        try {
            await fetch('http://127.0.0.1:8765/api/config/set', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: 'auto_approve', value: true, scope: 'project' }),
            });
        }
        catch (e) {
            console.error('Error setting auto_approve:', e);
        }
        onApprove(request.id);
    };
    return (_jsx("div", { className: `w-full rounded-xl border border-amber-500/40 bg-amber-500/5 p-4 shadow-lg backdrop-blur-sm animate-fade-in ${isInline ? 'my-2' : 'my-4'}`, children: _jsxs("div", { className: "flex items-start gap-3", children: [_jsx("div", { className: "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30", children: _jsx(ShieldCheck, { size: 20 }) }), _jsxs("div", { className: "flex-1 min-w-0", children: [_jsx("h4", { className: "text-sm font-semibold text-amber-200", children: request.title || 'Aprobación requerida' }), _jsx("p", { className: "mt-1 text-xs text-slate-300 whitespace-pre-wrap", children: request.message }), request.diff_content && (_jsx("div", { className: "mt-3 overflow-hidden rounded-lg border border-slate-700 bg-slate-950 p-2 text-xs font-mono", children: _jsx("pre", { className: "max-h-48 overflow-y-auto text-slate-300", children: request.diff_content }) })), _jsxs("div", { className: "mt-4 flex flex-wrap items-center gap-2", children: [_jsxs("button", { ref: approveRef, onClick: () => onApprove(request.id), className: "flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 shadow-sm transition-colors", children: [_jsx(Check, { size: 14 }), " Aprobar"] }), _jsxs("button", { onClick: () => onReject(request.id), className: "flex items-center gap-1.5 rounded-lg bg-rose-600/80 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-rose-500 shadow-sm transition-colors", children: [_jsx(X, { size: 14 }), " Rechazar"] }), _jsx("button", { onClick: handleApproveAlways, className: "flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-amber-300 hover:bg-slate-700 border border-amber-500/30 transition-colors ml-auto", children: "Aprobar siempre para esta sesi\u00F3n" })] })] })] }) }));
};
