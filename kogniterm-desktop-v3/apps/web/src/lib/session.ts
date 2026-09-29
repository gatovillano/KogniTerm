import { createSignal, onCleanup } from "solid-js";
import { api, wsUrl } from "./api";
import { tabs, uid } from "./tabs";
import { approvals } from "./approvals";

export type ConnState = "connecting" | "open" | "closed" | "error";

const sockets = new Map<string, WebSocket>();
const states = new Map<string, (s: ConnState) => void>();

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

export function useSession(tabId: string) {
  const [conn, setConn] = createSignal<ConnState>("connecting");
  states.set(tabId, setConn);

  function ensureSocket(): WebSocket | null {
    const existing = sockets.get(tabId);
    if (existing && (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)) {
      return existing;
    }
    try {
      const ws = new WebSocket(wsUrl(tabId));
      sockets.set(tabId, ws);
      setConn("connecting");
      ws.onopen = () => setConn("open");
      ws.onerror = () => setConn("error");
      ws.onclose = () => setConn("closed");
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
    const data = msg?.data;
    const textOf = (d: any): string =>
      typeof d === "string" ? d : (d?.text ?? d?.content ?? d?.message ?? (d ? JSON.stringify(d) : ""));

    /** Devuelve el id del mensaje assistant que está en streaming, o lo crea. */
    function streamingMsg(): string {
      const tab = tabs.store.tabs.find((t) => t.id === tabId);
      const last = tab?.messages[tab.messages.length - 1];
      if (last && last.role === "assistant" && last.pending) return last.id;
      const id = uid("a");
      tabs.push(tabId, { id, role: "assistant", text: "", pending: true });
      return id;
    }

    function closeStreaming() {
      const tab = tabs.store.tabs.find((t) => t.id === tabId);
      const last = tab?.messages[tab.messages.length - 1];
      if (last && last.role === "assistant" && last.pending) {
        tabs.finalize(tabId, last.id);
        // si al final solo hubo razonamiento (sin respuesta), no dejamos burbuja vacía
        if (!last.text.trim() && !last.thinking?.trim()) tabs.dropIfEmpty(tabId, last.id);
      }
    }

    if (type === "stream") {
      const chunk = typeof data === "string" ? data : textOf(data);
      if (chunk) tabs.appendTo(tabId, streamingMsg(), chunk);
    } else if (type === "live_update") {
      if (data && typeof data === "object") {
        const special = data.special_type;
        if (special === "spinner" || special === "terminal") {
          // Estado de herramientas: no es texto de respuesta.
          // Para terminal ya existe el sidebar con el PTY real.
          if (special === "spinner" && data.text) {
            tabs.push(tabId, { id: uid("t"), role: "tool", text: `· ${data.text}` });
          }
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
      closeStreaming();
    } else if (type === "message") {
      const text = textOf(data);
      if (text) {
        const tab = tabs.store.tabs.find((t) => t.id === tabId);
        const last = tab?.messages[tab.messages.length - 1];
        // evita duplicar si ya veníamos mostrarándolo por streaming
        if (last && last.role === "assistant" && last.pending) {
          tabs.setText(tabId, last.id, text);
          tabs.finalize(tabId, last.id);
        } else {
          tabs.push(tabId, { id: uid("a"), role: "assistant", text });
        }
      }
    } else if (type === "tool_start") {
      tabs.push(tabId, { id: uid("t"), role: "tool", text: `▶ ${textOf(data)}` });
    } else if (type === "tool_output") {
      tabs.push(tabId, { id: uid("t"), role: "tool", text: textOf(data) });
    } else if (type === "terminal_output") {
      // El shell real vive en el sidebar (WS del PTY); no duplicamos la salida aquí.
      return;
    } else if (type === "task_tracker" || type === "todo.updated") {
      return;
    } else if (type === "done") {
      closeStreaming();
    } else if (type === "error") {
      closeStreaming();
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

  function send(text: string) {
    const clean = text.trim();
    if (!clean) return;
    tabs.push(tabId, { id: uid("u"), role: "user", text: clean });
    const ws = ensureSocket();
    const payload = JSON.stringify({ type: "message", text: clean });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
    } else if (ws) {
      ws.addEventListener("open", () => ws.send(payload), { once: true });
    }
    // No se crea la burbuja del asistente aquí a propósito: se abre en el
    // primer `stream`/`live_update` para no dejar un mensaje vacío si el
    // agente tarda o falla.
  }

  function interrupt() {
    const ws = sockets.get(tabId);
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "interrupt" }));
    else void api.interrupt(tabId).catch(() => {});
  }

  ensureSocket();
  onCleanup(() => {
    states.delete(tabId);
  });

  return { conn, send, interrupt, reconnect: ensureSocket };
}
