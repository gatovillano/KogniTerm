'use client'

import { createContext, useContext, useState, useEffect, useCallback } from 'react'

interface Session {
  id: string
  name: string
  created: string
  workspace?: string
}

interface SessionContextType {
  sessions: Session[]
  currentSession: Session | null
  createSession: (name?: string) => Promise<void>
  deleteSession: (id: string) => Promise<void>
  selectSession: (id: string) => Promise<void>
  loading: boolean
}

const SessionContext = createContext<SessionContextType | null>(null)

const API_BASE = 'http://localhost:8765'

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSession, setCurrentSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchSessions = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/sessions`)
      const data = await response.json()
      const sessionList = (data.sessions || []).map((s: any) => ({
        id: s.id,
        name: s.name || `Session ${s.id.slice(0, 8)}`,
        created: s.created,
        workspace: s.workspace,
      }))
      setSessions(sessionList)
      if (!currentSession && sessionList.length > 0) {
        setCurrentSession(sessionList[0])
      }
    } catch (error) {
      console.log('Backend not available, no sessions')
    } finally {
      setLoading(false)
    }
  }, [currentSession])

  const createSession = useCallback(async (name?: string): Promise<void> => {
    try {
      const response = await fetch(`${API_BASE}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      const data = await response.json()
      setSessions(prev => [data, ...prev])
      setCurrentSession(data)
    } catch (error) {
      if (sessions.length > 0) {
        setCurrentSession(sessions[0])
      }
    }
  }, [sessions])

  const deleteSession = useCallback(async (id: string): Promise<void> => {
    try {
      await fetch(`${API_BASE}/sessions/${id}`, { method: 'DELETE' })
      setSessions(prev => prev.filter(s => s.id !== id))
      if (currentSession?.id === id) setCurrentSession(null)
    } catch (error) {
      console.log('Cannot delete session')
    }
  }, [currentSession])

  const selectSession = useCallback(async (id: string): Promise<void> => {
    const session = sessions.find(s => s.id === id)
    if (session) setCurrentSession(session)
  }, [sessions])

  useEffect(() => {
    fetchSessions()
    const interval = setInterval(fetchSessions, 30000)
    return () => clearInterval(interval)
  }, [fetchSessions])

  return (
    <SessionContext.Provider value={{ sessions, currentSession, createSession, deleteSession, selectSession, loading }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSessions() {
  const context = useContext(SessionContext)
  if (!context) throw new Error('useSessions must be used within SessionProvider')
  return context
}
