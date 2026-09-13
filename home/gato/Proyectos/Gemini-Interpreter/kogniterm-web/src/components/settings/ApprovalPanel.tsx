'use client'

import { useState } from 'react'
import { ShieldCheck, Check, X } from 'lucide-react'

interface ApprovalRequest {
  id: string
  action: string
  description: string
  tool_type?: string
  path?: string
}

export function ApprovalPanel() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([
    {
      id: '1',
      action: 'edit_file',
      description: 'Modify src/app/page.tsx for minimal UI update',
      tool_type: 'file_edit',
      path: 'src/app/page.tsx'
    }
  ])

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-zinc-500 stroke-[1.5]" />
          <h2 className="text-xs font-medium uppercase tracking-wider text-zinc-500">Pending Approvals</h2>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-zinc-200 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">
          {approvals.length}
        </span>
      </div>

      {approvals.length === 0 ? (
        <div className="text-center py-6 text-xs text-zinc-400 font-mono">
          No pending approvals
        </div>
      ) : (
        <div className="space-y-2">
          {approvals.map((approval) => (
            <div key={approval.id} className="border border-zinc-200 dark:border-zinc-800/80 rounded-lg p-3 bg-zinc-50/50 dark:bg-zinc-900/30 flex items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-zinc-800 dark:text-zinc-200">{approval.action}</span>
                  {approval.path && (
                    <span className="text-[10px] font-mono text-zinc-400">({approval.path})</span>
                  )}
                </div>
                <p className="text-xs text-zinc-500">{approval.description}</p>
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => setApprovals(prev => prev.filter(a => a.id !== approval.id))}
                  className="p-1.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                  title="Approve"
                >
                  <Check className="w-3.5 h-3.5 stroke-[1.5]" />
                </button>
                <button
                  onClick={() => setApprovals(prev => prev.filter(a => a.id !== approval.id))}
                  className="p-1.5 rounded border border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400 hover:bg-rose-500/20 transition-colors"
                  title="Reject"
                >
                  <X className="w-3.5 h-3.5 stroke-[1.5]" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
ENDOFFILE