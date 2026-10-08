import { createSignal, onCleanup } from "solid-js";
import { api, wsUrl } from "./api";
import { agents } from "./agents";
import { tabs, uid, isTerminalTool, type ChatAttachment } from "./tabs";
import { approvals } from "./approvals";
import { tasksStore } from "./tasks";

export type ConnState = "connecting" | "open" | "closed" | "error";

const sockets = new Map<string, WebSocket>();
const states = new Map<string, (s: ConnState) => void>();
const runningSetters = new Map<string, (r: boolean) => void>();
const runningMap = new Map<string, boolean>();

/** Buffer de deltas `stream`/`chunk` por pestaña: coalesce a ~1 flush por frame
 *  para no saturar el store de Solid (un setStore por token = re-render por token).
 *  Sin esto el chat se congela y parece que "llega todo al final". */
const streamBuffers = new Map<string, { buf: string; timer: number | undefined }>();
const STREAM_FLUSH_MS = 32;

/** Obtiene (creando si hace falta) el id del assistant en streaming. */
function streamingMsgId(tabId: string): string {
  const tab = tabs.store.tabs.find((t) => t.id === tabId);
  const last = tab?.messages[tab.messages.length - 1];
  if (last && last.role === "assistant" && last.pending) return last.id;
  tabs.finalizeAll(tabId);
  const id = uid("a");
  tabs.push(tabId, { id, role: "assistant", text: "", pending: true });
  return id;
}

function flushStreamBuffer(tabId: string) {
  const entry = streamBuffers.get(tabId);
  if (!entry || !entry.buf) {
    if (entry) entry.timer = undefined;
    return;
  }
  const chunk = entry.buf;
  entry.buf = "";
  entry.timer = undefined;
  tabs.appendTo(tabId, streamingMsgId(tabId), chunk);
}

/** Encola un delta de texto y lo pinta en el siguiente frame (tiempo real). */
function bufferStreamChunk(tabId: string, chunk: string) {
  if (!chunk) return;
  let entry = streamBuffers.get(tabId);
  if (!entry) {
    entry = { buf: "", timer: undefined };
    streamBuffers.set(tabId, entry);
  }
  entry.buf += chunk;
  if (entry.timer === undefined) {
    entry.timer = window.setTimeout(() => flushStreamBuffer(tabId), STREAM_FLUSH_MS);
  }
}

/** Vacía el buffer pendiente (al cerrar el turno no se pierde la cola). */
function drainStreamBuffer(tabId: string) {
  const entry = streamBuffers.get(tabId);
  if (entry?.timer !== undefined) {
    clearTimeout(entry.timer);
    entry.timer = undefined;
  }
  flushStreamBuffer(tabId);
}

/** Terminal inline actualmente abierta por pestaña/agente del backend. */
const activeAgentTerminals = new Map<string, { terminalId: string; agentId?: string }>();
/** El worker pidió cursor interactivo antes de que existiera la terminal inline. */
const interactiveAgentTerminals = new Set<string>();

export function setTabRunning(tabId: string, isRunning: boolean) {
  runningMap.set(tabId, isRunning);
  runningSetters.get(tabId)?.(isRunning);
}

function agentTerminalKey(tabId: string, agentId?: string): string {
  return `${encodeURIComponent(tabId)}::${encodeURIComponent(agentId ?? "main")}`;
}

export function closeStreaming(tabId: string, agentId?: string) {
  drainStreamBuffer(tabId);
  setTabRunning(tabId, false);
  tabs.finalizeAll(tabId);
  tabs.finalizeTools(tabId);
  tabs.closeAgentTerminals(tabId, agentId);
  for (const key of [...activeAgentTerminals.keys(), ...interactiveAgentTerminals]) {
    if (
      key.startsWith(`${encodeURIComponent(tabId)}::`) &&
      (agentId == null || key === agentTerminalKey(tabId, agentId))
    ) {
      activeAgentTerminals.delete(key);
      interactiveAgentTerminals.delete(key);
    }
  }
}

/** Responde aprobación por WS (como la TUI); fallback REST si el socket falla. */
export async function replyApproval(tabId: string, requestId: string, approved: boolean): Promise<void> {
  approvals.resolveApproval(requestId);
  try {
    const ws = sockets.get(tabId);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "approval_response", id: requestId, approved }));
      return;
    }
  } catch {
    /* cae al REST */
  }
  await api.replyPermission(tabId, requestId, approved);
}

/** Responde pregunta del agente por WS; fallback REST. */
export async function replyQuestion(tabId: string, requestId: string, selected: string): Promise<void> {
  approvals.resolveQuestion(requestId);
  try {
    const ws = sockets.get(tabId);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "question_response", id: requestId, selected }));
      return;
    }
  } catch {
    /* cae al REST */
  }
  await api.replyQuestion(tabId, requestId, selected);
}

/** Fija la preferencia de auto-aprobación: estado local + backend (fuente de verdad). */
export function setAutoApprove(tabId: string, value: boolean): void {
  approvals.setAuto(tabId, value);
  const ws = sockets.get(tabId);
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "set_auto_approve", value }));
  }
  // Sincronizar en la config global para que el backend lo persista
  void api
    .setConfig("auto_approve", value, "global")
    .catch(() => undefined);
}

export function useSession(tabId: string) {
  const [conn, setConn] = createSignal<ConnState>("connecting");
  const [running, setRunning] = createSignal<boolean>(runningMap.get(tabId) ?? false);
  states.set(tabId, setConn);
  runningSetters.set(tabId, setRunning);

  function ensureSocket(): WebSocket | null {
    const existing = sockets.get(tabId);
    if (existing && (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)) {
      return existing;
    }
    try {
      const ws = new WebSocket(wsUrl(tabId));
      sockets.set(tabId, ws);
      setConn("connecting");
      ws.onopen = () => {
        setConn("open");
        const currentAuto = approvals.isAuto(tabId);
        try {
          ws.send(JSON.stringify({ type: "set_auto_approve", value: currentAuto }));
        } catch {
          /* ignore */
        }
      };
      ws.onerror = () => {
        setConn("error");
        closeStreaming(tabId);
      };
      ws.onclose = () => {
        setConn("closed");
        closeStreaming(tabId);
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          handleServerEvent(tabId, msg);
        } catch {
          /* chunk no-JSON: ignorar */
        }
      };
      // keep-alive
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
      }, 25000);
      ws.addEventListener("close", () => clearInterval(ping));
      return ws;
    } catch {
      setConn("error");
      return null;
    }
  }

  /**
   * Streaming en tiempo real.
   *
   * Semántica real del backend (ver kogniterm/server/session_pool.py y el
   * acumulador de kogniterm/terminal/tui/ws_client.py):
   *  - `stream`      → DELTA: se añade al final.
   *  - `live_update` → SNAPSHOT: `data.response` es el texto ACUMULADO completo,
   *                    no un delta. Si se concatenara, el texto se duplicaría.
   *                    `data.thinking` es el razonamiento; `special_type` trae
   *                    spinner/terminal en vez de texto.
   *  - `live_stop` / `done` / `error` → cierra la respuesta en curso.
   *  - `message`     → mensaje completo ya cerrado (no sigue en streaming).
   */
  function handleServerEvent(tabId: string, msg: any) {
    const type = msg?.type;
    const data = msg?.data;    if (type === "connected") {
      const serverAgent = data?.config?.agent;
      if (typeof serverAgent === "string" && serverAgent) agents.applyServerAgent(tabId, serverAgent);
      // El backend es la fuente de verdad del auto-approve (config global/proyecto).
      const serverAuto = data?.config?.auto_approve;
      if (typeof serverAuto === "boolean") approvals.seedAuto(tabId, serverAuto);
      const isRunning = Boolean(data?.is_running ?? data?.config?.is_running ?? false);
      if (!isRunning) {
        closeStreaming(tabId);
      } else {
        setTabRunning(tabId, true);
      }
      return;
    }
    if (type === "auto_approve_changed") {
      if (typeof data?.value === "boolean") approvals.setAuto(tabId, data.value);
      return;
    }
    if (type === "agent_changed") {
      const serverAgent = data?.agent;
      if (typeof serverAgent === "string" && serverAgent) agents.applyServerAgent(tabId, serverAgent);
      return;
    }
    const textOf = (d: any): string =>
      typeof d === "string" ? d : (d?.text ?? d?.content ?? d?.message ?? (d ? JSON.stringify(d) : ""));

    /** Devuelve el id del mensaje assistant que está en streaming, o lo crea. */
    function streamingMsg(): string {
      const tab = tabs.store.tabs.find((t) => t.id === tabId);
      const last = tab?.messages[tab.messages.length - 1];
      if (last && last.role === "assistant" && last.pending) return last.id;
      tabs.finalizeAll(tabId);
      const id = uid("a");
      tabs.push(tabId, { id, role: "assistant", text: "", pending: true });
      return id;
    }

    /**
     * Crea o actualiza la terminal inline vinculada a la ejecución del agente.
     * Es una PTY distinta del shell lateral: su entrada debe ir al worker,
     * no al PTY de usuario.
     */
    function upsertAgentTerminal(
      agentId: string | undefined,
      input: { terminalId?: string; tool?: string; command?: string; snapshot?: string },
    ): string {
      const key = agentTerminalKey(tabId, agentId);
      const existing = activeAgentTerminals.get(key);
      let terminalId = input.terminalId;
      if (terminalId && existing && existing.terminalId !== terminalId) {
        tabs.setAgentTerminalState(tabId, existing.terminalId, {
          terminalActive: false,
          terminalInteractive: false,
        });
      }
      if (!terminalId) terminalId = existing?.terminalId;
      if (!terminalId) {
        terminalId = uid("term");
        tabs.pushAgentTerminal(tabId, {
          id: terminalId,
          terminalId,
          terminalTool: input.tool,
          terminalCommand: input.command,
          agentId,
          output: input.snapshot ?? "",
        });
        tabs.setAgentTerminalState(tabId, terminalId, {
          terminalActive: true,
          terminalInteractive: interactiveAgentTerminals.has(key),
        });
      } else {
        tabs.setAgentTerminalSnapshot(tabId, terminalId, input.snapshot ?? "");
        tabs.setAgentTerminalState(tabId, terminalId, {
          terminalActive: true,
          terminalInteractive: tabs.store.tabs
            .find((t) => t.id === tabId)
            ?.messages.find((m) => m.role === "terminal" && m.terminalId === terminalId)?.terminalInteractive,
        });
      }
      activeAgentTerminals.set(key, { terminalId, agentId });
      return terminalId;
    }

    function markAgentTerminalsInteractive(agentId: string | undefined, interactive: boolean) {
      if (agentId == null) {
        for (const [key, entry] of activeAgentTerminals) {
          if (key.startsWith(`${encodeURIComponent(tabId)}::`)) {
            tabs.setAgentTerminalState(tabId, entry.terminalId, {
              terminalActive: interactive,
              terminalInteractive: interactive,
            });
            if (!interactive) {
              activeAgentTerminals.delete(key);
              interactiveAgentTerminals.delete(key);
            } else {
              interactiveAgentTerminals.add(key);
            }
          }
        }
        return;
      }
      const key = agentTerminalKey(tabId, agentId);
      const entry = activeAgentTerminals.get(key);
      if (interactive) interactiveAgentTerminals.add(key);
      else interactiveAgentTerminals.delete(key);
      if (!entry) return;
      tabs.setAgentTerminalState(tabId, entry.terminalId, {
        terminalActive: interactive,
        terminalInteractive: interactive,
      });
      if (!interactive) activeAgentTerminals.delete(key);
    }

    if (type === "stream") {
      // ServerUI.print_stream emite "chunk" + "stream" con el mismo texto;
      // solo se pinta "stream" para no duplicar. ("chunk" se ignora abajo.)
      setTabRunning(tabId, true);
      const chunk = typeof data === "string" ? data : textOf(data);
      if (chunk) bufferStreamChunk(tabId, chunk);
    } else if (type === "chunk") {
      // Duplicado del `stream` gemelo: ignorar a propósito.
      setTabRunning(tabId, true);
      return;
    } else if (type === "live_update") {
      setTabRunning(tabId, true);
      if (data && typeof data === "object") {
        const special = data.special_type;
        if (special === "spinner") {
          if (data.text) {
            tabs.updateOrPushSpinner(tabId, data.text);
          }
          return;
        }
        if (special === "terminal") {
          // Snapshot acumulado del comando en ejecución. No pertenece al PTY lateral.
          upsertAgentTerminal(msg.agent_id, {
            tool: typeof data.tool === "string" ? data.tool : undefined,
            command: typeof data.command === "string" ? data.command : undefined,
            snapshot: typeof data.output === "string" ? data.output : "",
          });
          return;
        }
        const response = typeof data.response === "string" ? data.response : "";
        const thinking = typeof data.thinking === "string" ? data.thinking : "";
        if (!response && !thinking) return;
        const id = streamingMsg();
        if (response) tabs.setText(tabId, id, response);
        if (thinking) tabs.setThinking(tabId, id, thinking);
      } else {
        const t = textOf(data);
        if (t) tabs.setText(tabId, streamingMsg(), t);
      }
    } else if (type === "live_stop") {
      closeStreaming(tabId, msg.agent_id);
    } else if (type === "message") {
      // Vaciar deltas pendientes ANTES de fijar el texto final; si no, el
      // flush posterior añadiría chunks ya incluidos en `text`.
      drainStreamBuffer(tabId);
      const text = textOf(data);
      if (text) {
        const tab = tabs.store.tabs.find((t) => t.id === tabId);
        const last = tab?.messages[tab.messages.length - 1];
        // evita duplicar si ya veníamos mostrándolo por streaming
        if (last && last.role === "assistant" && last.pending) {
          tabs.setText(tabId, last.id, text);
          tabs.finalize(tabId, last.id);
        } else {
          tabs.push(tabId, { id: uid("a"), role: "assistant", text });
        }
      }
      closeStreaming(tabId, msg.agent_id);
    } else if (type === "tool_call" || type === "tool_start") {
      setTabRunning(tabId, true);
      const name = data?.name || data?.tool || (typeof data === "string" ? data : "herramienta");
      // execute_command y comandos de terminal usan la terminal interactiva (AgentTerminal), no el ToolIndicator
      if (isTerminalTool(name)) {
        return;
      }
      const toolCallId = data?.tool_call_id || data?.tool_id || data?.id || uid("tcall");
      const desc = data?.description || "";
      const args = data?.args || data?.tool_args || {};
      const cmd = data?.command || (typeof args === "object" ? args?.command || args?.cmd || args?.path : "") || "";
      const skill = data?.skill || "";
      tabs.pushToolCall(tabId, {
        toolCallId: String(toolCallId),
        toolName: String(name),
        toolArgs: args,
        toolCommand: cmd ? String(cmd) : undefined,
        toolDescription: desc ? String(desc) : undefined,
        toolSkill: skill ? String(skill) : undefined,
        agentId: msg.agent_id,
        status: "running",
      });
    } else if (type === "tool_result" || type === "tool_output") {
      const toolName = data?.tool || data?.name;
      if (isTerminalTool(toolName)) {
        return;
      }
      const output = typeof data === "string" ? data : (data?.content ?? data?.output ?? data?.result ?? (data ? JSON.stringify(data, null, 2) : ""));
      const toolCallId = data?.tool_call_id || data?.tool_id || data?.id;
      tabs.updateToolResult(tabId, {
        toolCallId: toolCallId ? String(toolCallId) : undefined,
        toolName: toolName ? String(toolName) : undefined,
        toolOutput: String(output),
        status: "completed",
      });
    } else if (type === "terminal_output") {
      setTabRunning(tabId, true);
      // El shell lateral es otro PTY. Esta salida pertenece al worker que está
      // ejecutando el comando aprobado y debe mostrarse aquí.
      if (data && typeof data === "object") {
        const toolCallId = typeof data.tool_call_id === "string" && data.tool_call_id ? data.tool_call_id : undefined;
        upsertAgentTerminal(msg.agent_id, {
          terminalId: toolCallId,
          tool: typeof data.tool === "string" ? data.tool : undefined,
          command: typeof data.command === "string" ? data.command : undefined,
          snapshot: typeof data.content === "string" ? data.content : typeof data.output === "string" ? data.output : "",
        });
      }
      return;
    } else if (type === "set_terminal_cursor") {
      const active = typeof data === "object" && data !== null ? Boolean(data.active) : Boolean(data);
      markAgentTerminalsInteractive(msg.agent_id, active);
      return;
    } else if (type === "task_tracker") {
      if (data && typeof data === "object") {
        tasksStore.setAgentPlans(tabId, data);
      }
      return;
    } else if (type === "todo.updated") {
      if (data && typeof data === "object" && Array.isArray(data.todos)) {
        tasksStore.setTodos(tabId, data.todos);
      }
      return;
    } else if (type === "done") {
      closeStreaming(tabId, msg.agent_id);
    } else if (type === "error") {
      tabs.finalizeTools(tabId, "error");
      closeStreaming(tabId, msg.agent_id);
      tabs.push(tabId, { id: uid("s"), role: "system", text: `Error: ${textOf(data)}` });
    } else if (type === "info") {
      // acks del servidor (p.ej. "Aprobación procesada") — no ensucian el chat
      return;
    } else if (type === "approval_required" && data && typeof data === "object") {
      const req = {
        id: String(data.id ?? ""),
        tabId,
        title: String(data.title ?? "Aprobación Requerida"),
        message: String(data.message ?? "Confirmar acción"),
        diff: String(data.diff_content ?? data.diff ?? ""),
        file_path: String(data.file_path ?? ""),
      };
      if (!req.id) return;
      // auto-aprobar si el usuario activó "aceptar siempre" en esta pestaña (como la TUI)
      if (approvals.isAuto(tabId)) {
        void replyApproval(tabId, req.id, true);
        return;
      }
      approvals.pushApproval(req);
      tabs.push(tabId, { id: uid("s"), role: "system", text: `⏳ ${req.title}: ${req.message}` });
    } else if (type === "question_required" && data && typeof data === "object") {
      const q = {
        id: String(data.id ?? ""),
        tabId,
        title: String(data.title ?? "Consulta del Agente"),
        question: String(data.question ?? ""),
        options: Array.isArray(data.options) ? data.options.map(String) : [],
        allow_freeform: data.allow_freeform !== false,
      };
      if (!q.id) return;
      approvals.pushQuestion(q);
    }
  }

  /** Envía raw por el WS de la pestaña (cola si aún conecta). */
  function sendRaw(payload: string): boolean {
    const ws = sockets.get(tabId) ?? ensureSocket();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
      return true;
    }
    if (ws) ws.addEventListener("open", () => ws.send(payload), { once: true });
    return false;
  }

  function send(text: string, agent?: string, images?: string[], attachments?: ChatAttachment[]) {
    const clean = text.trim();
    const imgs = (images ?? []).filter((u) => typeof u === "string" && u.length > 0);
    if (!clean && imgs.length === 0) return;
    setTabRunning(tabId, true);
    tabs.push(tabId, {
      id: uid("u"),
      role: "user",
      text: clean || (imgs.length ? "[imagen adjunta]" : ""),
      agent,
      ...(attachments?.length ? { attachments } : {}),
      ...(imgs.length ? { images: imgs } : {}),
    });
    const ws = ensureSocket();
    const payload = JSON.stringify({
      type: "message",
      text: clean,
      ...(imgs.length ? { images: imgs } : {}),
      ...(agent ? { agent } : {}),
    });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
    } else if (ws) {
      ws.addEventListener("open", () => ws.send(payload), { once: true });
    }
    // No se crea la burbuja del asistente aquí a propósito: se abre en el
    // primer `stream`/`live_update` para no dejar un mensaje vacío si el
    // agente tarda o falla.
  }

  /** Ejecuta un mensaje que ya estaba en la cola de la pestaña */
  function sendQueued(msgId: string, text: string, agent?: string) {
    const clean = text.trim();
    // La burbuja encolada guarda sus imágenes/adjuntos: se recuperan del store.
    const queued = tabs.store.tabs.find((t) => t.id === tabId)?.messages.find((m) => m.id === msgId);
    const imgs = (queued?.images ?? []).filter((u) => typeof u === "string" && u.length > 0);
    if (!clean && imgs.length === 0) return;
    tabs.unqueue(tabId, msgId);
    setTabRunning(tabId, true);
    const ws = ensureSocket();
    const payload = JSON.stringify({
      type: "message",
      text: clean,
      ...(imgs.length ? { images: imgs } : {}),
      ...(agent ? { agent } : {}),
    });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
    } else if (ws) {
      ws.addEventListener("open", () => ws.send(payload), { once: true });
    }
  }

  function interrupt() {
    const ws = sockets.get(tabId);
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "interrupt" }));
    else void api.interrupt(tabId).catch(() => {});
    closeStreaming(tabId);
  }

  /**
   * Envía teclas o texto a la ejecución interactiva del agente.
   * Va al worker de la sesión, no al PTY lateral.
   */
  function sendTerminalInput(text: string) {
    if (!text) return;
    sendRaw(JSON.stringify({ type: "terminal_input", text }));
  }

  ensureSocket();
  onCleanup(() => {
    states.delete(tabId);
    runningSetters.delete(tabId);
  });

  return { conn, running, send, sendQueued, sendTerminalInput, interrupt, reconnect: ensureSocket };
}
