import { createSignal, type Accessor } from "solid-js"
import { createStore, produce, reconcile, type SetStoreFunction } from "solid-js/store"

export const KOGNITERM_DONE_MARKER = "##KOGNITERM_DONE_MARKER##"

export interface FilterTerminalOutputResult {
  filtered: string
  hasDoneMarker: boolean
  isFinished: boolean
}

/**
 * Filter terminal output respecting AGENTS.md rules:
 * - Compatible with ECHO disabled (do not assume terminal echoes commands)
 * - Strict differentiation between command echo and ##KOGNITERM_DONE_MARKER##
 * - Strips completion marker cleanly without dropping non-marker lines
 * - Does not block or freeze command execution
 */
export function filterTerminalOutput(
  raw: string,
  executedCommand?: string
): FilterTerminalOutputResult {
  const hasDoneMarker = raw.includes(KOGNITERM_DONE_MARKER)
  const lines = raw.split(/\r?\n/)
  const filteredLines: string[] = []

  const trimmedCmd = executedCommand?.trim()

  for (const line of lines) {
    const stripped = line.trim()

    // 1. Strict check: If line is identical to the clean done marker, it's the sentinel (not an echo)
    if (stripped === KOGNITERM_DONE_MARKER) {
      continue
    }

    // 2. Check for echo invocation of the marker (e.g. echo '##KOGNITERM_''DONE_MARKER##')
    if (stripped.includes("echo '##KOGNITERM_") || stripped.includes("echo '##KOGNI")) {
      continue
    }

    // 3. Filter command echo line if echoed, but ONLY if not identical to the done marker
    if (trimmedCmd && stripped === trimmedCmd && stripped !== KOGNITERM_DONE_MARKER) {
      continue
    }

    filteredLines.push(line)
  }

  return {
    filtered: filteredLines.join("\n"),
    hasDoneMarker,
    isFinished: hasDoneMarker,
  }
}

export interface KogniTermClientConfig {
  baseUrl: string
  fetch?: typeof globalThis.fetch
  headers?: Record<string, string>
  token?: string | null
}

export interface ServerHealth {
  healthy: boolean
  version?: string
  status?: string
  active_sessions?: number
  [key: string]: unknown
}

export interface ChatMessage {
  id: string
  sender: "user" | "agent" | "system"
  text: string
  timestamp: number
  images?: unknown[]
}

export interface TerminalEntry {
  id: string
  command: string
  tool: string
  output: string
  exitCode?: number
  isFinished: boolean
  timestamp: number
}

export interface ActiveTool {
  id: string
  name: string
  description: string
  skill?: string
  output?: string
  status: "running" | "completed" | "error"
}

export interface PendingApproval {
  id: string
  message: string
  title: string
  diff_content?: string
  file_path?: string
}

export interface PendingQuestion {
  id: string
  questions: unknown[]
}

export interface KogniTermSessionStore {
  // Signals
  connected: Accessor<boolean>
  status: Accessor<"connecting" | "connected" | "disconnected" | "error">
  isThinking: Accessor<boolean>
  thinking: Accessor<string>
  response: Accessor<string>
  error: Accessor<string | null>

  // Collections
  messages: Accessor<ChatMessage[]>
  terminalEntries: Accessor<TerminalEntry[]>
  activeTools: Accessor<ActiveTool[]>
  pendingApprovals: Accessor<PendingApproval[]>
  pendingQuestions: Accessor<PendingQuestion[]>
  taskPlans: Accessor<Record<string, unknown>>

  // Actions
  sendMessage: (text: string, images?: unknown[]) => void
  sendInterrupt: () => void
  sendTerminalInput: (text: string) => void
  sendApproval: (requestId: string, approved: boolean) => void
  sendQuestionResponse: (requestId: string, selected: string) => void
  startIndexing: () => void
  disconnect: () => void
}

export class KogniTermClient {
  public readonly baseUrl: string
  private readonly fetcher: typeof globalThis.fetch
  private readonly defaultHeaders: Record<string, string>
  private readonly token?: string | null

  public readonly health: {
    get: (opts?: { signal?: AbortSignal }) => Promise<ServerHealth>
  }

  public readonly session: {
    list: (opts?: { signal?: AbortSignal }) => Promise<{ sessions: unknown[] }>
    create: (data?: { session_id?: string; workspace_dir?: string }, opts?: { signal?: AbortSignal }) => Promise<{ session_id: string; created_at: string }>
    delete: (sessionId: string, opts?: { signal?: AbortSignal }) => Promise<{ deleted: string }>
    close: (sessionId: string, opts?: { signal?: AbortSignal }) => Promise<void>
  }

  public readonly global: {
    health: (opts?: { signal?: AbortSignal }) => Promise<{ data?: { healthy: boolean; version?: string }; error?: unknown }>
  }

  public readonly permission: {
    reply: (input: { id: string; reply?: string | boolean; approved?: boolean }) => Promise<{ data: boolean }>
  }

  public readonly event: {
    subscribe: (opts?: { signal?: AbortSignal }) => AsyncIterable<unknown>
  }

  constructor(config: KogniTermClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, "")
    this.fetcher = config.fetch ?? globalThis.fetch
    this.defaultHeaders = config.headers ?? {}
    this.token = config.token

    this.health = {
      get: (opts) => this.checkHealth(opts),
    }

    this.session = {
      list: (opts) => this.fetchSessions(opts?.signal),
      create: (data, opts) => this.createSession(data, opts?.signal),
      delete: (sessionId, opts) => this.deleteSession(sessionId, opts?.signal),
      close: (sessionId, opts) => this.closeSession(sessionId, opts?.signal),
    }

    this.global = {
      health: async (opts) => {
        try {
          const res = await this.checkHealth(opts)
          return { data: { healthy: res.healthy, version: res.version } }
        } catch (error) {
          return { error }
        }
      },
    }

    this.permission = {
      reply: async (input) => {
        const approved = typeof input.approved === "boolean" ? input.approved : input.reply === true || input.reply === "true"
        await this.postJson(`/api/approval/${encodeURIComponent(input.id)}`, { approved })
        return { data: true }
      },
    }

    this.event = {
      subscribe: async function* () {
        // Yield empty placeholder stream if accessed directly; session WebSocket is the primary transport
      },
    }
  }

  static make(config: KogniTermClientConfig): KogniTermClient {
    return new KogniTermClient(config)
  }

  private async fetch(path: string, options?: RequestInit): Promise<Response> {
    const url = `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`
    const headers = new Headers(this.defaultHeaders)

    if (this.token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${this.token}`)
    }

    if (options?.headers) {
      new Headers(options.headers).forEach((value, key) => {
        headers.set(key, value)
      })
    }

    return this.fetcher(url, {
      ...options,
      headers,
    })
  }

  private async postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
    const res = await this.fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    })
    if (!res.ok) {
      throw new Error(`HTTP error ${res.status}: ${res.statusText}`)
    }
    return res.json() as Promise<T>
  }

  async checkHealth(options?: { signal?: AbortSignal }): Promise<ServerHealth> {
    try {
      const res = await this.fetch("/health", { signal: options?.signal })
      if (!res.ok) {
        const docs = await this.fetch("/docs", { signal: options?.signal })
        return { healthy: docs.ok, version: "2.0.0" }
      }
      const data = (await res.json()) as Record<string, unknown>
      return {
        healthy: data.status === "online" || res.status === 200,
        version: typeof data.version === "string" ? data.version : "2.0.0",
        status: typeof data.status === "string" ? data.status : "online",
        active_sessions: typeof data.active_sessions === "number" ? data.active_sessions : 0,
      }
    } catch {
      return { healthy: false }
    }
  }

  async fetchSessions(signal?: AbortSignal): Promise<{ sessions: unknown[] }> {
    const res = await this.fetch("/sessions", { signal })
    if (!res.ok) throw new Error(`Fetch sessions failed: ${res.statusText}`)
    return res.json()
  }

  async createSession(
    data?: { session_id?: string; workspace_dir?: string },
    signal?: AbortSignal
  ): Promise<{ session_id: string; created_at: string }> {
    return this.postJson<{ session_id: string; created_at: string }>("/sessions", data ?? {}, signal)
  }

  async deleteSession(sessionId: string, signal?: AbortSignal): Promise<{ deleted: string }> {
    const res = await this.fetch(`/sessions/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
      signal,
    })
    if (!res.ok) throw new Error(`Delete session failed: ${res.statusText}`)
    return res.json()
  }

  async closeSession(sessionId: string, signal?: AbortSignal): Promise<void> {
    await this.fetch(`/api/sessions/${encodeURIComponent(sessionId)}/close`, {
      method: "POST",
      signal,
    })
  }

  async getConfig(signal?: AbortSignal): Promise<unknown> {
    const res = await this.fetch("/api/config/all", { signal })
    if (!res.ok) throw new Error(`Get config failed: ${res.statusText}`)
    return res.json()
  }

  async getAvailableModels(signal?: AbortSignal): Promise<unknown> {
    const res = await this.fetch("/api/models/available", { signal })
    if (!res.ok) throw new Error(`Get available models failed: ${res.statusText}`)
    return res.json()
  }

  async listSkills(signal?: AbortSignal): Promise<unknown> {
    const res = await this.fetch("/api/skills", { signal })
    if (!res.ok) throw new Error(`List skills failed: ${res.statusText}`)
    return res.json()
  }

  async listWorkspaces(signal?: AbortSignal): Promise<unknown> {
    const res = await this.fetch("/api/workspaces", { signal })
    if (!res.ok) throw new Error(`List workspaces failed: ${res.statusText}`)
    return res.json()
  }

  async listThreads(signal?: AbortSignal): Promise<unknown> {
    const res = await this.fetch("/api/threads", { signal })
    if (!res.ok) throw new Error(`List threads failed: ${res.statusText}`)
    return res.json()
  }

  async executeCommand(
    data: { command: string; workspace_dir?: string },
    signal?: AbortSignal
  ): Promise<unknown> {
    return this.postJson("/api/execute", data, signal)
  }

  getWebSocketUrl(sessionId: string): string {
    const parsed = new URL(this.baseUrl)
    const protocol = parsed.protocol === "https:" ? "wss:" : "ws:"
    const wsUrl = new URL(`${protocol}//${parsed.host}/ws/${encodeURIComponent(sessionId)}`)
    if (this.token) {
      wsUrl.searchParams.set("token", this.token)
    }
    wsUrl.searchParams.set("client_type", "desktop")
    return wsUrl.toString()
  }

  /**
   * Connects to a KogniTerm agent session WebSocket, parsing streaming events into SolidJS Signals / Stores.
   */
  connectSessionWebSocket(sessionId: string): KogniTermSessionStore {
    const [connected, setConnected] = createSignal(false)
    const [status, setStatus] = createSignal<"connecting" | "connected" | "disconnected" | "error">("connecting")
    const [isThinking, setIsThinking] = createSignal(false)
    const [thinking, setThinking] = createSignal("")
    const [response, setResponse] = createSignal("")
    const [error, setError] = createSignal<string | null>(null)

    const [messages, setMessages] = createSignal<ChatMessage[]>([])
    const [terminalEntries, setTerminalEntries] = createSignal<TerminalEntry[]>([])
    const [activeTools, setActiveTools] = createSignal<ActiveTool[]>([])
    const [pendingApprovals, setPendingApprovals] = createSignal<PendingApproval[]>([])
    const [pendingQuestions, setPendingQuestions] = createSignal<PendingQuestion[]>([])
    const [taskPlans, setTaskPlans] = createSignal<Record<string, unknown>>({})

    let ws: WebSocket | null = null
    let pingInterval: ReturnType<typeof setInterval> | null = null
    let intentionalDisconnect = false

    const sendJson = (payload: unknown) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(payload))
      }
    }

    const connect = () => {
      const url = this.getWebSocketUrl(sessionId)
      setStatus("connecting")

      try {
        ws = new WebSocket(url)
      } catch (err) {
        setStatus("error")
        setError(err instanceof Error ? err.message : String(err))
        return
      }

      ws.onopen = () => {
        setConnected(true)
        setStatus("connected")
        setError(null)

        pingInterval = setInterval(() => {
          sendJson({ type: "ping" })
        }, 15000)
      }

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data)
          const msgType = parsed.type
          const data = parsed.data

          switch (msgType) {
            case "connected": {
              if (data && typeof data === "object") {
                if (data.live_state) {
                  if (typeof data.live_state.thinking === "string") {
                    setThinking(data.live_state.thinking)
                    setIsThinking(Boolean(data.live_state.thinking))
                  }
                  if (typeof data.live_state.response === "string") {
                    setResponse(data.live_state.response)
                  }
                }
                if (typeof data.is_running === "boolean") {
                  setIsThinking(data.is_running)
                }
              }
              break
            }

            case "live_update": {
              if (data && typeof data === "object") {
                if (typeof data.thinking === "string") {
                  setThinking(data.thinking)
                  setIsThinking(Boolean(data.thinking))
                }
                if (typeof data.response === "string") {
                  setResponse(data.response)
                }
              }
              break
            }

            case "live_stop": {
              setIsThinking(false)
              setThinking("")
              break
            }

            case "stream":
            case "chunk": {
              const text = typeof data === "string" ? data : (data?.content ?? "")
              if (text) {
                setResponse((prev) => prev + text)
              }
              break
            }

            case "message": {
              const text = typeof data === "string" ? data : (data?.text ?? data?.content ?? "")
              if (text) {
                setMessages((prev) => [
                  ...prev,
                  {
                    id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                    sender: "agent",
                    text,
                    timestamp: Date.now(),
                  },
                ])
              }
              break
            }

            case "tool_start":
            case "tool_call": {
              const toolName = data?.name ?? "tool"
              const desc = data?.description ?? ""
              const skill = data?.skill ?? ""
              const toolId = data?.tool_call_id ?? `tool-${Date.now()}`
              setActiveTools((prev) => [
                ...prev,
                {
                  id: toolId,
                  name: toolName,
                  description: desc,
                  skill,
                  status: "running",
                },
              ])
              break
            }

            case "tool_output":
            case "tool_result": {
              const toolId = data?.tool_call_id
              const content = typeof data === "string" ? data : (data?.content ?? JSON.stringify(data))
              if (toolId) {
                setActiveTools((prev) =>
                  prev.map((t) => (t.id === toolId ? { ...t, output: content, status: "completed" } : t))
                )
              }
              break
            }

            case "terminal_output": {
              const rawContent = data?.content ?? ""
              const toolName = data?.tool ?? "terminal"
              const commandStr = data?.command ?? toolName
              const toolCallId = data?.tool_call_id ?? `term-${Date.now()}`

              // Strict AGENTS.md filtering:
              const filterResult = filterTerminalOutput(rawContent, commandStr)

              setTerminalEntries((prev) => {
                const idx = prev.findIndex((e) => e.id === toolCallId)
                if (idx >= 0) {
                  const updated = [...prev]
                  updated[idx] = {
                    ...updated[idx],
                    output: filterResult.filtered,
                    isFinished: filterResult.isFinished || updated[idx].isFinished,
                  }
                  return updated
                }
                return [
                  ...prev,
                  {
                    id: toolCallId,
                    command: commandStr,
                    tool: toolName,
                    output: filterResult.filtered,
                    isFinished: filterResult.isFinished,
                    timestamp: Date.now(),
                  },
                ]
              })
              break
            }

            case "task_tracker": {
              if (data && typeof data === "object") {
                setTaskPlans(data as Record<string, unknown>)
              }
              break
            }

            case "approval_required": {
              if (data?.id) {
                setPendingApprovals((prev) => {
                  if (prev.some((a) => a.id === data.id)) return prev
                  return [
                    ...prev,
                    {
                      id: data.id,
                      message: data.message ?? "",
                      title: data.title ?? "Aprobación Requerida",
                      diff_content: data.diff_content,
                      file_path: data.file_path,
                    },
                  ]
                })
              }
              break
            }

            case "question_required":
            case "ask_question": {
              if (data?.id) {
                setPendingQuestions((prev) => {
                  if (prev.some((q) => q.id === data.id)) return prev
                  return [
                    ...prev,
                    {
                      id: data.id,
                      questions: data.questions ?? [],
                    },
                  ]
                })
              }
              break
            }

            case "done": {
              setIsThinking(false)
              setTerminalEntries((prev) =>
                prev.map((e) => ({ ...e, isFinished: true }))
              )
              break
            }

            case "error": {
              const errMsg = typeof data === "string" ? data : (data?.message ?? "Unknown error")
              setError(errMsg)
              break
            }

            case "pong": {
              break
            }
          }
        } catch {
          // Ignore json parse error for non-json frames
        }
      }

      ws.onerror = (evt) => {
        setStatus("error")
        setError("WebSocket encountered an error")
      }

      ws.onclose = () => {
        setConnected(false)
        setStatus("disconnected")
        if (pingInterval) {
          clearInterval(pingInterval)
          pingInterval = null
        }
        if (!intentionalDisconnect) {
          // Attempt reconnect after delay
          setTimeout(() => {
            if (!intentionalDisconnect) {
              connect()
            }
          }, 3000)
        }
      }
    }

    connect()

    return {
      connected,
      status,
      isThinking,
      thinking,
      response,
      error,
      messages,
      terminalEntries,
      activeTools,
      pendingApprovals,
      pendingQuestions,
      taskPlans,

      sendMessage: (text: string, images?: unknown[]) => {
        sendJson({ type: "message", text, images: images ?? [] })
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            sender: "user",
            text,
            timestamp: Date.now(),
            images,
          },
        ])
        setIsThinking(true)
      },

      sendInterrupt: () => {
        sendJson({ type: "interrupt" })
      },

      sendTerminalInput: (text: string) => {
        sendJson({ type: "terminal_input", text })
      },

      sendApproval: (requestId: string, approved: boolean) => {
        sendJson({ type: "approval_response", id: requestId, approved })
        setPendingApprovals((prev) => prev.filter((a) => a.id !== requestId))
      },

      sendQuestionResponse: (requestId: string, selected: string) => {
        sendJson({ type: "question_response", id: requestId, selected })
        setPendingQuestions((prev) => prev.filter((q) => q.id !== requestId))
      },

      startIndexing: () => {
        sendJson({ type: "start_indexing" })
      },

      disconnect: () => {
        intentionalDisconnect = true
        if (pingInterval) {
          clearInterval(pingInterval)
          pingInterval = null
        }
        if (ws) {
          ws.close()
          ws = null
        }
      },
    }
  }
}

export const KogniTerm = KogniTermClient
