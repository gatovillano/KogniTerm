import { useCallback, useEffect, useRef, useState } from 'react'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
}

interface ConnectionState {
  connected: boolean
  connecting: boolean
  sending: boolean
  error: string | null
}

interface UseChatOptions {
  sessionId?: string
}

const API_BASE = 'http://localhost:8765'

export function useChat(options: UseChatOptions = {}) {
  const { sessionId = '' } = options
  
  const [messages, setMessages] = useState<Message[]>([])
  const [connectionState, setConnectionState] = useState<ConnectionState>({
    connected: !!sessionId,
    connecting: false,
    sending: false,
    error: null,
  })
  
  const messageIdRef = useRef(0)

  const sendMessage = useCallback(async (textContent: string) => {
    if (!sessionId) return

    const id = `msg-${Date.now()}-${messageIdRef.current++}`
    const userMessage: Message = { id, role: 'user', content: textContent, timestamp: new Date() }
    setMessages(prev => [...prev, userMessage])

    setConnectionState(prev => ({ ...prev, sending: true }))

    try {
      const res = await fetch(`${API_BASE}/chat/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: textContent }),
      })

      if (!res.ok) throw new Error('Failed to send message')
      
      const responseDataText = await res.text()
      
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last && last.role === 'assistant') {
          return [...prev.slice(0, -1), { ...last, content: last.content + responseDataText }]
        }
        return [...prev, {
          id: `${id}-assistant`,
          role: 'assistant',
          content: responseDataText,
          timestamp: new Date(),
        }]
      })

      setConnectionState(prev => ({ ...prev, sending: false }))
    } catch (error) {
      setMessages(prev => [...prev, {
        id: `${id}-error`,
        role: 'system',
        content: `Error: ${error}`,
        timestamp: new Date(),
      }])
      setConnectionState(prev => ({ ...prev, sending: false, error: 'Failed to send' }))
    }
  }, [sessionId])

  useEffect(() => {
    if (!sessionId) {
      setConnectionState(prev => ({ ...prev, connected: false, error: 'No session' }))
    } else {
      setConnectionState(prev => ({ ...prev, connected: true, error: null }))
    }
  }, [sessionId])

  return { messages, sendMessage, connectionState }
}
