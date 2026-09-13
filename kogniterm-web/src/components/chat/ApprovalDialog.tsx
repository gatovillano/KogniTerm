import React from 'react';
import { CheckCircle, XCircle, Terminal, FileEdit, Shield, AlertTriangle } from 'lucide-react';

interface ApprovalRequest {
  id: string;
  action: 'edit' | 'command' | 'other';
  title: string;
  description: string;
  content: string;
  tool_call_id: string;
}

interface ApprovalDialogProps {
  request: ApprovalRequest;
  onApprove: (id: string, tool_call_id: string) => void;
  onReject: (id: string, tool_call_id: string) => void;
}

const iconMap: Record<string, React.ElementType> = {
  edit: FileEdit,
  command: Terminal,
  other: AlertTriangle
};

export function ApprovalDialog({ request, onApprove, onReject }: ApprovalDialogProps) {
  const Icon = iconMap[request.action] || AlertTriangle;

  return (
    <div className="w-full my-4 overflow-hidden rounded-xl border border-amber-500/30 bg-amber-950/20 shadow-lg">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-amber-500/10 border-b border-amber-500/20">
        <div className="p-2 rounded-lg bg-amber-500/20 text-amber-400">
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <h3 className="font-semibold text-sm text-amber-300">{request.title}</h3>
          <p className="text-xs text-amber-500/80">{request.description}</p>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-3">
        {request.action === 'command' && (
          <div className="bg-black/40 rounded-lg p-3 font-mono text-xs overflow-x-auto border border-inherit">
            <div className="text-emerald-400">$ {request.content}</div>
          </div>
        )}

        {request.action === 'edit' && (
          <div className="bg-black/40 rounded-lg p-3 font-mono text-xs overflow-x-auto border border-inherit max-h-60 overflow-y-auto">
            <pre className="whitespace-pre-wrap text-emerald-300">{request.content}</pre>
          </div>
        )}

        {request.action === 'other' && (
          <div className="bg-black/40 rounded-lg p-3 font-mono text-xs border border-inherit">
            <pre className="whitespace-pre-wrap text-amber-300">{request.content}</pre>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-end gap-2 px-4 py-3 bg-black/20 border-t border-inherit">
        <button
          onClick={() => onReject(request.id, request.tool_call_id)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/20 transition-colors text-sm font-medium"
        >
          <XCircle className="w-4 h-4" />
          Rechazar
        </button>
        <button
          onClick={() => onApprove(request.id, request.tool_call_id)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20 transition-colors text-sm font-medium"
        >
          <CheckCircle className="w-4 h-4" />
          Aprobar
        </button>
      </div>
    </div>
  );
}