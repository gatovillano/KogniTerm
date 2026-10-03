/* Cliente nativo KogniTerm — sin SDK opencode. Ver docs/API_NATIVA.md */

const BUILD_API = (import.meta as any).env?.VITE_KOGNITERM_API ?? "";

/** ¿Estamos dentro de Electron servido con file://? Entonces no hay proxy /kapi. */
function isFileProtocol(): boolean {
  return typeof location !== "undefined" && location.protocol === "file:";
}

/** URL que el proceso main de Electron resolvió (respeta KOGNITERM_PORT/HOST). */
function electronApiBase(): string {
  const b = (globalThis as any).kogniterm?.apiBase;
  return typeof b === "string" ? b.trim() : "";
}

/** URL del backend: override en runtime (Ajustes → Conexión) > Electron > build-time > defecto. */
export function apiRoot(): string {
  const custom = localStorage.getItem("kogniterm_api_url")?.trim();
  if (custom) return custom.replace(/\/$/, "");
  const fromMain = electronApiBase();
  if (fromMain) return fromMain.replace(/\/$/, "");
  if (BUILD_API) return BUILD_API.replace(/\/$/, "");
  // file:// → backend local directo (el proxy /kapi solo existe en el dev server)
  if (isFileProtocol()) return "http://127.0.0.1:8755";
  return "/kapi";
}

export function token(): string {
  return localStorage.getItem("kogniterm_token") ?? "";
}

export function setToken(v: string) {
  if (v.trim()) localStorage.setItem("kogniterm_token", v.trim());
  else localStorage.removeItem("kogniterm_token");
}

export function setApiUrl(v: string) {
  if (v.trim()) localStorage.setItem("kogniterm_api_url", v.trim().replace(/\/$/, ""));
  else localStorage.removeItem("kogniterm_api_url");
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json", ...extra };
  const t = token();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

export function wsUrl(sessionId: string): string {
  const explicit = (import.meta as any).env?.VITE_KOGNITERM_WS as string | undefined;
  const root0 = apiRoot();
  let root: string;
  if (explicit) {
    root = explicit.replace(/\/$/, "");
  } else if (root0.startsWith("http")) {
    root = root0.replace(/^http/, "ws");
  } else if (isFileProtocol() || (import.meta as any).env?.DEV) {
    // dev (el proxy no soporta WS) y Electron file:// → backend local directo
    root = "ws://127.0.0.1:8755";
  } else {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    root = `${proto}//${location.host}`;
  }
  const t = token();
  return `${root}/ws/${encodeURIComponent(sessionId)}?client_type=desktop${t ? `&token=${encodeURIComponent(t)}` : ""}`;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiRoot()}${path}`, { ...init, headers: headers(init?.headers as any) });
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} → ${res.status}`);
  return (await res.json()) as T;
}

export interface LLMConfig {
  provider: string;
  model: string;
  api_key_masked: string;
  has_key: boolean;
  reasoning_effort?: string;
}

export interface AvailableModels {
  providers: Array<{ id: string; name: string; models: string[] }>;
}

export interface MCPServerStatus {
  transport?: string;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
  disabled?: boolean;
  status?: string;
  tools?: string[];
  error?: string;
  [k: string]: any;
}

export type MCPScope = "project" | "global";

export interface Workspace {
  id: string;
  name: string;
  path: string;
}

export interface ThreadInfo {
  id: string;
  title: string;
  title_source?: string;
  created_at?: string;
  updated_at?: string;
  parent_thread_id?: string | null;
  workspace_dir?: string;
  message_count?: number;
  metadata?: Record<string, unknown>;
}

export interface ThreadMessage {
  id: string;
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  reasoning?: string;
  tool_calls?: Array<{ id: string; name: string; args: Record<string, unknown> }>;
  tool_call_id?: string | null;
  timestamp?: number;
  images?: string[];
}

export interface NativeAgent {
  id: string;
  name: string;
  description: string;
  engine: string;
}

export interface AgentCatalogResponse {
  agents: NativeAgent[];
  default: string;
}

export const api = {
  health: () => req<{ status: string }>("/health"),
  listAgents: () => req<AgentCatalogResponse>("/api/agents"),
  getModels: () => req<AvailableModels>("/models/available"),
  getLLM: () => req<LLMConfig>("/config/llm"),
  setLLM: (body: { model?: string; provider?: string; api_key?: string }) =>
    req<{ status: string; model: string; provider: string }>("/config/llm", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listSessions: () => req<any[]>("/sessions"),
  createSession: (workspace_dir?: string) =>
    req<any>("/sessions", { method: "POST", body: JSON.stringify({ workspace_dir }) }),
  deleteSession: (id: string) => req<any>(`/sessions/${encodeURIComponent(id)}`, { method: "DELETE" }),
  interrupt: (id: string) =>
    req<any>(`/session/${encodeURIComponent(id)}/interrupt`, { method: "POST", body: JSON.stringify({}) }),
  /** Estado del workspace de una sesión: {indexed, path}. */
  workspaceStatus: (sessionId?: string) =>
    req<{ indexed: boolean; path: string; error?: string }>(
      `/api/workspace/status${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`,
    ),
  // Fallback REST para aprobaciones/preguntas (la vía principal es el WS).
  // approved=true ↔ reply "once"; approved=false ↔ reply "denied".
  replyPermission: (sessionId: string, requestId: string, approved: boolean) =>
    req<any>(`/session/${encodeURIComponent(sessionId)}/permission/${encodeURIComponent(requestId)}/reply`, {
      method: "POST",
      body: JSON.stringify({ reply: approved ? "once" : "denied" }),
    }),
  replyQuestion: (sessionId: string, requestId: string, selected: string) =>
    req<any>(`/session/${encodeURIComponent(sessionId)}/question/${encodeURIComponent(requestId)}/reply`, {
      method: "POST",
      body: JSON.stringify({ reply: selected }),
    }),
  // ── MCP (paridad con /mcp de la TUI) ──
  listMCP: () => req<Record<string, MCPServerStatus>>("/api/mcp/servers"),
  saveMCP: (name: string, config: Record<string, any>, scope: MCPScope = "project") =>
    req<{ status: string; name: string }>("/api/mcp/servers", {
      method: "POST",
      body: JSON.stringify({ name, config, scope }),
    }),
  deleteMCP: (name: string, scope: MCPScope = "project") =>
    req<{ status: string; name: string }>(`/api/mcp/servers/${encodeURIComponent(name)}?scope=${scope}`, {
      method: "DELETE",
    }),
  toggleMCP: (name: string, scope: MCPScope = "project") =>
    req<{ status: string; name: string; disabled: boolean }>(
      `/api/mcp/servers/${encodeURIComponent(name)}/toggle?scope=${scope}`,
      { method: "POST", body: JSON.stringify({}) },
    ),
  testMCP: (config: Record<string, any>) =>
    req<{ status: string; message?: string; tools?: string[] } & Record<string, any>>("/api/mcp/test-connection", {
      method: "POST",
      body: JSON.stringify(config),
    }),
  // ── Workspaces e hilos (conversaciones persistidas) ──
  listWorkspaces: () => req<{ workspaces: Workspace[] }>("/api/workspaces"),
  listThreads: (workspaceDirs?: string[]) =>
    req<{ threads: ThreadInfo[] }>(
      `/api/threads${workspaceDirs?.length ? `?workspace_dirs=${encodeURIComponent(workspaceDirs.join(","))}` : ""}`,
    ),
  createThread: (workspaceDir?: string) =>
    req<{ thread_id: string; metadata?: any }>("/api/threads", {
      method: "POST",
      body: JSON.stringify({ workspace_dir: workspaceDir }),
    }),
  deleteThread: (id: string) => req<{ deleted: string }>(`/api/threads/${encodeURIComponent(id)}`, { method: "DELETE" }),
  renameThread: (id: string, title: string) =>
    req<any>(`/api/threads/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  /** Historial persistido de un hilo. */
  threadMessages: (id: string) =>
    req<{ messages: ThreadMessage[] }>(`/api/threads/${encodeURIComponent(id)}/messages`),
};

/** Proveedores canónicos TUI (command_processor._handle_provider + multi_provider_manager). */
export const PROVIDERS: Array<{ id: string; label: string; defaultModel: string }> = [
  { id: "google", label: "Google AI (Gemini)", defaultModel: "google/gemini-1.5-flash" },
  { id: "openai", label: "OpenAI (GPT)", defaultModel: "openai/gpt-4o" },
  { id: "anthropic", label: "Anthropic (Claude)", defaultModel: "anthropic/claude-3-5-sonnet-20240620" },
  { id: "openrouter", label: "OpenRouter", defaultModel: "openrouter/google/gemini-2.5-flash" },
  { id: "ollama", label: "Ollama Local", defaultModel: "ollama/llama3" },
  { id: "ollama_cloud", label: "Ollama Cloud", defaultModel: "ollama_cloud/llama3:70b" },
  { id: "kilocode", label: "KiloCode Gateway", defaultModel: "kilocode/kilo/auto" },
  { id: "inception", label: "Inception Labs", defaultModel: "inception/mercury-2" },
  { id: "antigravity", label: "Google Antigravity (Session OAuth2)", defaultModel: "antigravity/gemini-3-flash" },
];

export const KEY_PROVIDERS = [
  { id: "google", env: "GOOGLE_API_KEY" },
  { id: "openai", env: "OPENAI_API_KEY" },
  { id: "anthropic", env: "ANTHROPIC_API_KEY" },
  { id: "openrouter", env: "OPENROUTER_API_KEY" },
  { id: "kilocode", env: "KILOCODE_API_KEY" },
  { id: "inception", env: "INCEPTION_API_KEY" },
];
