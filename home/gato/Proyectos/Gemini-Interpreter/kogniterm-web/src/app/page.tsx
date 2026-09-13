'use client'

import { useEffect, useRef, useState } from 'react'
import { useChat } from '../hooks/useChat'
import { useSessions } from '../hooks/useSessions'
import { LLMConfig } from '../components/settings/LLMConfig'
import { DiffViewer } from '../components/settings/DiffViewer'
import { ApprovalPanel } from '../components/settings/ApprovalPanel'
import { MessageSquare, Settings, Plus, Send, Terminal, Cpu, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function ChatPage() {
  const { sessions, currentSession, createSession, loading: sessionsLoading } = useSessions()
  const { messages, sendMessage, connectionState } = useChat({ sessionId: currentSession?.id || '' })
  const [input, setInput] = useState('')
  const [activeTab, setActiveTab] = useState<'chat' | 'settings'>('chat')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [autoCreatedSession, setAutoCreatedSession] = useState(false)

  useEffect(() => {
    if (sessions.length === 0 && !currentSession && !autoCreatedSession) {
      createSession('Chat').then(() => setAutoCreatedSession(true))
    }
  }, [sessions, currentSession, autoCreatedSession, createSession])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && currentSession) {
      sendMessage(input.trim())
      setInput('')
    }
  }

  return (
    <div className="flex h-screen bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 font-sans antialiased text-xs">
      {/* Sidebar minimalista */}
      <aside className="w-64 border-r border-zinc-200 dark:border-zinc-800/80 bg-zinc-50/50 dark:bg-zinc-900/20 flex flex-col justify-between">
        <div>
          {/* Header */}
          <div className="p-4 border-b border-zinc-200 dark:border-zinc-800/80 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 stroke-[1.5] text-zinc-700 dark:text-zinc-300" />
              <span className="font-medium tracking-tight">KogniTerm</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className={cn('w-1.5 h-1.5 rounded-full',
                connectionState.connected ? 'bg-emerald-500' : 'bg-zinc-400'
              )} />
            </div>
          </div>

          {/* Navegación */}
          <div className="p-3 space-y-1">
            <button
              onClick={() => setActiveTab('chat')}
              className={cn(
                "w-full flex items-center gap-2 px-3 py-1.5 rounded transition-colors text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100",
                activeTab === 'chat' && "bg-zinc-200/60 dark:bg-zinc-800/60 text-zinc-900 dark:text-zinc-100 font-medium"
              )}
            >
              <MessageSquare className="w-3.5 h-3.5 stroke-[1.5]" />
              <span>Chat</span>
            </button>
            <button
              onClick={() => setActiveTab('settings')}
              className={cn(
                "w-full flex items-center gap-2 px-3 py-1.5 rounded transition-colors text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100",
                activeTab === 'settings' && "bg-zinc-200/60 dark:bg-zinc-800/60 text-zinc-900 dark:text-zinc-100 font-medium"
              )}
            >
              <Settings className="w-3.5 h-3.5 stroke-[1.5]" />
              <span>Settings</span>
            </button>
          </div>

          {/* Sesiones (solo en chat) */}
          {activeTab === 'chat' && (
            <div className="p-3 border-t border-zinc-200 dark:border-zinc-800/80 space-y-1">
              <div className="flex items-center justify-between px-2 pb-1">
                <span className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider">Conversations</span>
                <button
                  onClick={() => createSession('New Chat')}
                  className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-800 rounded transition-colors"
                  title="New conversation"
                >
                  <Plus className="w-3.5 h-3.5 stroke-[1.5] text-zinc-500" />
                </button>
              </div>
              <div className="space-y-0.5 max-h-[calc(100vh-250px)] overflow-auto">
                {sessions.map((session) => (
                  <button
                    key={session.id}
                    className={cn(
                      "w-full text-left px-2.5 py-1.5 rounded truncate transition-colors text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200/40 dark:hover:bg-zinc-800/40",
                      currentSession?.id === session.id && "bg-zinc-200/80 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 font-medium"
                    )}
                  >
                    <span className="truncate">{session.name || `Session ${session.id.slice(0, 6)}`}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="p-3 border-t border-zinc-200 dark:border-zinc-800/80 text-[10px] font-mono text-zinc-400 text-center">
          v1.0.0-minimal
        </div>
      </aside>

      {/* Main Container */}
      <main className="flex-1 flex flex-col min-w-0">
        {activeTab === 'chat' ? (
          <>
            {/* Topbar minimalista */}
            <header className="h-12 border-b border-zinc-200 dark:border-zinc-800/80 px-6 flex items-center justify-between bg-white/50 dark:bg-zinc-950/50 backdrop-blur">
              <span className="font-medium text-zinc-700 dark:text-zinc-300">
                {currentSession?.name || 'Active Session'}
              </span>
              <span className="text-[10px] font-mono text-zinc-400">REST Stream</span>
            </header>

            {/* Mensajes */}
            <div className="flex-1 overflow-auto p-6 space-y-4">
              <div className="max-w-2xl mx-auto space-y-4">
                {messages.length === 0 && (
                  <div className="text-center py-16 text-zinc-400 font-mono">
                    Type a message to start interacting with KogniTerm.
                  </div>
                )}
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={cn(
                      "flex gap-3",
                      msg.role === 'user' ? 'flex-row-reverse' : ''
                    )}
                  >
                    <div className={cn(
                      "w-6 h-6 rounded-full border border-zinc-200 dark:border-zinc-800 flex items-center justify-center font-mono text-[10px]",
                      msg.role === 'user' ? 'bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400' : 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900'
                    )}>
                      {msg.role === 'user' ? 'U' : 'K'}
                    </div>
                    <div className={cn(
                      "max-w-[80%] rounded-lg px-3 py-2 leading-relaxed font-sans",
                      msg.role === 'user'
                        ? 'bg-zinc-100 dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200'
                        : 'bg-transparent text-zinc-800 dark:text-zinc-200 border border-zinc-200/60 dark:border-zinc-800/60'
                    )}>
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Input minimalista */}
            <div className="p-4 border-t border-zinc-200 dark:border-zinc-800/80 bg-white/50 dark:bg-zinc-950/50 backdrop-blur">
              <form onSubmit={handleSubmit} className="max-w-2xl mx-auto relative">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Message KogniTerm..."
                  className="w-full pl-3 pr-10 py-2 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs focus:outline-none focus:border-zinc-400 resize-none"
                  rows={2}
                  disabled={!currentSession}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSubmit(e)
                    }
                  }}
                />
                <button
                  type="submit"
                  disabled={!input.trim() || !currentSession}
                  className="absolute right-2.5 bottom-3.5 p-1 rounded bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 hover:opacity-90 disabled:opacity-30 transition-opacity"
                >
                  <Send className="w-3 h-3 stroke-[1.5]" />
                </button>
              </form>
            </div>
          </>
        ) : (
          /* Settings minimalista */
          <div className="flex-1 overflow-auto p-8">
            <div className="max-w-3xl mx-auto space-y-8">
              <LLMConfig />
              <ApprovalPanel />
              <div className="space-y-3">
                <div className="flex items-center gap-2 border-b border-zinc-200 dark:border-zinc-800 pb-3">
                  <ShieldCheck className="w-4 h-4 text-zinc-500 stroke-[1.5]" />
                  <h2 className="text-xs font-medium uppercase tracking-wider text-zinc-500">File Diff Inspection</h2>
                </div>
                <DiffViewer />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
ENDOFFILE