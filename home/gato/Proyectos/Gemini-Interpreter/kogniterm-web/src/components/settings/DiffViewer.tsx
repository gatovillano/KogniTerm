'use client'

import { useState } from 'react'
import { FileCode2, Check, X } from 'lucide-react'

interface DiffLine {
  type: 'add' | 'remove' | 'unchanged'
  content: string
  lineNumber?: number
}

interface DiffViewerProps {
  original?: string
  modified?: string
  path?: string
}

export function DiffViewer({ original = '', modified = '', path = 'example.ts' }: DiffViewerProps) {
  const [diff, setDiff] = useState<DiffLine[]>([
    { type: 'unchanged', content: 'import { useState } from \'react\'', lineNumber: 1 },
    { type: 'remove', content: 'const oldVal = 10;', lineNumber: 2 },
    { type: 'add', content: 'const newVal = 20;', lineNumber: 2 },
    { type: 'unchanged', content: 'export function Component() {', lineNumber: 3 },
    { type: 'unchanged', content: '  return <div />', lineNumber: 4 },
    { type: 'unchanged', content: '}', lineNumber: 5 },
  ])

  return (
    <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg overflow-hidden bg-zinc-50/50 dark:bg-zinc-900/30">
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
        <div className="flex items-center gap-2">
          <FileCode2 className="w-3.5 h-3.5 text-zinc-500 stroke-[1.5]" />
          <span className="text-xs font-mono text-zinc-600 dark:text-zinc-300">{path}</span>
        </div>
        <span className="text-[10px] font-mono text-zinc-400">DIFF PREVIEW</span>
      </div>
      
      <div className="max-h-64 overflow-auto font-mono text-[11px] leading-relaxed">
        {diff.map((line, idx) => (
          <div
            key={idx}
            className={`flex px-3 py-0.5 ${
              line.type === 'add' ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' :
              line.type === 'remove' ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400' :
              'text-zinc-600 dark:text-zinc-400'
            }`}
          >
            <span className="w-6 text-zinc-400 select-none text-right pr-2">
              {line.lineNumber || ' '}
            </span>
            <span className="w-4 select-none text-center">
              {line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' '}
            </span>
            <span className="flex-1 whitespace-pre">{line.content}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
ENDOFFILE