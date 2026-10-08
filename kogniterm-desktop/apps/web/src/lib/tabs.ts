import { createStore, produce } from "solid-js/store";

export interface ChatAttachment {
  id: string;
  name: string;
  mime: string;
  size: number;
  kind: "image" | "text";
  /** Imágenes: dataURL (preview + envío multimodal). */
  dataUrl?: string;
  /** Texto: contenido leído para inlinear en el mensaje. */
  textContent?: string;
}

export interface ChatMsg {
  id: string;
  role: "user" | "assistant" | "tool" | "system" | "terminal";
  text: string;
  agent?: string;
  /** Razonamiento del modelo (evento live_update.thinking), se muestra atenuado. */
  thinking?: string;
  /** Sigue llegando contenido: la burbuja muestra cursor y aún no se persiste. */
  pending?: boolean;
  /** Adjuntos enviados con el mensaje (preview local). */
  attachments?: ChatAttachment[];
  /** Imágenes en dataURL/URL para render y reenvío multimodal. */
  images?: string[];
  /** Terminal interactiva vinculada a la ejecución worker del agente, no al PTY lateral. */
  terminalId?: string;
  terminalTool?: string;
  terminalCommand?: string;
  terminalOutput?: string;
  terminalActive?: boolean;
  terminalInteractive?: boolean;
  agentId?: string;
  /** Mensaje en cola esperando que el agente termine su ejecución actual */
  queued?: boolean;
  queuedAt?: number;
  /** Metadatos de ejecución de herramienta */
  toolName?: string;
  toolArgs?: Record<string, any> | string;
  toolDescription?: string;
  toolCommand?: string;
  toolOutput?: string;
  toolStatus?: "running" | "completed" | "error";
  toolCallId?: string;
  toolSkill?: string;
  startedAt?: number;
  completedAt?: number;
}

export interface Tab {
  id: string; // = session_id nativo
  title: string;
  messages: ChatMsg[];
  /** El historial ya se pidió al backend para esta pestaña. */
  historyLoaded?: boolean;
}

export function isTerminalTool(name?: string): boolean {
  if (!name) return false;
  const n = name.toLowerCase().trim();
  return (
    n === "execute_command" ||
    n === "execute_command_tool" ||
    n === "run_command" ||
    n === "run_command_tool" ||
    n === "bash" ||
    n === "shell" ||
    n === "run_shell" ||
    n === "cmd_execution" ||
    n === "terminal" ||
    n.startsWith("execute_command")
  );
}

function uid(prefix = "id"): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36)}`;
}

function load(): Tab[] {
  try {
    const raw = localStorage.getItem("kogniterm-v3-tabs");
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) {
        return arr.map((tab) => ({
          ...tab,
          messages: (tab.messages || [])
            .filter((m: any) => !(m.role === "tool" && isTerminalTool(m.toolName || m.text)))
            .map((m: any) => ({
              ...m,
              pending: false,
              terminalActive: false,
              terminalInteractive: false,
              toolStatus: m.toolStatus === "running" ? "completed" : m.toolStatus,
            })),
        }));
      }
    }
  } catch {}
  return [];
}

const initial: Tab[] = load().length
  ? load()
  : [{ id: `desktop-${uid()}`, title: "Sesión 1", messages: [] }];

const [store, setStore] = createStore<{ tabs: Tab[]; activeId: string }>({
  tabs: initial,
  activeId: initial[0].id,
});

function persist() {
  try {
    const serializable = store.tabs.map((tab) => ({
      ...tab,
      messages: tab.messages.map((message) =>
        message.role === "terminal" && (message.terminalOutput?.length ?? 0) > 8000
          ? { ...message, terminalOutput: message.terminalOutput?.slice(-8000) }
          : message,
      ),
    }));
    localStorage.setItem("kogniterm-v3-tabs", JSON.stringify(serializable));
  } catch {}
}

export const tabs = {
  get store() {
    return store;
  },
  active(): Tab {
    return store.tabs.find((t) => t.id === store.activeId) ?? store.tabs[0];
  },
  select(id: string) {
    setStore("activeId", id);
  },
  newTab() {
    const id = `desktop-${uid()}`;
    const n = store.tabs.length + 1;
    setStore("tabs", (ts) => [...ts, { id, title: `Sesión ${n}`, messages: [] }]);
    setStore("activeId", id);
    persist();
  },
  /** Abre un hilo del backend en una pestaña (reutiliza la pestaña si ya existe). */
  openThread(id: string, title?: string) {
    const existing = store.tabs.find((t) => t.id === id);
    if (existing) {
      if (title) setStore("tabs", (t) => t.id === id, "title", title);
      setStore("activeId", id);
      persist();
      return id;
    }
    const name = title || "Conversación";
    setStore("tabs", (ts) => [...ts, { id, title: name, messages: [] }]);
    setStore("activeId", id);
    persist();
    return id;
  },
  isOpen(id: string): boolean {
    return store.tabs.some((t) => t.id === id);
  },
  /** Ya se pidió el historial de esta pestaña al backend (evita recargas). */
  wasHistoryLoaded(id: string): boolean {
    return store.tabs.some((t) => t.id === id && t.historyLoaded);
  },
  /** Sustituye los mensajes por el historial del hilo y marca la pestaña como cargada. */
  setHistory(id: string, msgs: ChatMsg[]) {
    setStore("tabs", (t) => t.id === id, "messages", msgs);
    setStore("tabs", (t) => t.id === id, "historyLoaded", true);
    persist();
  },
  markHistoryLoaded(id: string) {
    if (!store.tabs.some((t) => t.id === id && t.historyLoaded)) {
      setStore("tabs", (t) => t.id === id, "historyLoaded", true);
      persist();
    }
  },
  close(id: string) {
    const idx = store.tabs.findIndex((t) => t.id === id);
    if (idx < 0) return;
    // Mutación atómica: splice + activeId en un solo produce para que
    // Solid vea un único cambio y <For> reconcilie sin slots fantasma.
    if (store.tabs.length === 1) {
      const nid = `desktop-${uid()}`;
      setStore(
        produce((s) => {
          s.tabs.splice(0, 1, { id: nid, title: "Sesión 1", messages: [] });
          s.activeId = nid;
        }),
      );
      persist();
      return;
    }
    setStore(
      produce((s) => {
        s.tabs.splice(idx, 1);
        if (s.activeId === id) {
          // Tras el splice, el vecino ocupa idx (o el anterior si era la última).
          const next = s.tabs[Math.min(idx, s.tabs.length - 1)] ?? s.tabs[0];
          if (next) s.activeId = next.id;
        }
      }),
    );
    persist();
  },
  push(tabId: string, msg: ChatMsg) {
    setStore("tabs", (t) => t.id === tabId, "messages", (ms) => [...ms, msg]);
    persist();
  },
  /** Añade un mensaje en cola para ejecución diferida */
  enqueue(tabId: string, msg: ChatMsg) {
    setStore("tabs", (t) => t.id === tabId, "messages", (ms) => [
      ...ms,
      { ...msg, queued: true, queuedAt: Date.now() },
    ]);
    persist();
  },
  /** Elimina un mensaje específico de la cola */
  dequeue(tabId: string, msgId: string) {
    setStore("tabs", (t) => t.id === tabId, "messages", (ms) => ms.filter((m) => m.id !== msgId));
    persist();
  },
  /** Desmarca el mensaje de la cola al ser enviado para ejecución */
  unqueue(tabId: string, msgId: string) {
    setStore("tabs", (t) => t.id === tabId, "messages", (m) => m.id === msgId, "queued", false);
    persist();
  },
  /** Limpia todos los mensajes en cola de la pestaña */
  clearQueue(tabId: string) {
    setStore("tabs", (t) => t.id === tabId, "messages", (ms) => ms.filter((m) => !m.queued));
    persist();
  },
  /** Añade un delta al final del texto (evento `stream`). */
  appendTo(tabId: string, msgId: string, chunk: string) {
    setStore("tabs", (t) => t.id === tabId, "messages", (m) => m.id === msgId, "text", (t) => t + chunk);
  },
  /** Reemplaza el texto completo (evento `live_update`, que es snapshot y no delta). */
  setText(tabId: string, msgId: string, text: string) {
    setStore("tabs", (t) => t.id === tabId, "messages", (m) => m.id === msgId, "text", text);
  },
  setThinking(tabId: string, msgId: string, thinking: string) {
    setStore("tabs", (t) => t.id === tabId, "messages", (m) => m.id === msgId, "thinking", thinking);
  },
  finalize(tabId: string, msgId: string) {
    setStore("tabs", (t) => t.id === tabId, "messages", (m) => m.id === msgId, "pending", false);
    persist();
  },
  /** Finaliza todos los mensajes de asistente pendientes y descarta burbujas vacías */
  finalizeAll(tabId: string) {
    setStore(
      "tabs",
      (t) => t.id === tabId,
      "messages",
      (m) => m.role === "assistant" && Boolean(m.pending),
      "pending",
      false,
    );
    setStore("tabs", (t) => t.id === tabId, "messages", (ms) =>
      ms.filter((m) => !(m.role === "assistant" && !m.text.trim() && !m.thinking?.trim())),
    );
    persist();
  },
  /** Quita la burbuja si quedó vacía (p.ej. solo hubo razonamiento). */
  dropIfEmpty(tabId: string, msgId: string) {
    setStore("tabs", (t) => t.id === tabId, "messages", (ms) =>
      ms.filter((m) => !(m.id === msgId && m.role === "assistant" && !m.text.trim() && !m.thinking?.trim())),
    );
    persist();
  },
  /** Crea una terminal inline vinculada a la ejecución del agente. */
  pushAgentTerminal(
    tabId: string,
    terminal: Pick<ChatMsg, "id" | "terminalId" | "terminalTool" | "terminalCommand" | "agentId"> & {
      output?: string;
    },
  ) {
    const message: ChatMsg = {
      id: terminal.id,
      role: "terminal",
      text: "",
      terminalId: terminal.terminalId,
      terminalTool: terminal.terminalTool,
      terminalCommand: terminal.terminalCommand,
      terminalOutput: terminal.output ?? "",
      terminalActive: true,
      terminalInteractive: false,
      agentId: terminal.agentId,
    };
    setStore("tabs", (t) => t.id === tabId, "messages", (ms) => [...ms, message]);
  },
  /** Actualiza el snapshot de salida sin persistir cada fragmento intermedio. */
  setAgentTerminalSnapshot(tabId: string, terminalId: string, output: string) {
    setStore(
      "tabs",
      (t) => t.id === tabId,
      "messages",
      (m) => m.role === "terminal" && m.terminalId === terminalId,
      "terminalOutput",
      output,
    );
  },
  setAgentTerminalState(
    tabId: string,
    terminalId: string,
    state: Pick<ChatMsg, "terminalActive" | "terminalInteractive">,
  ) {
    setStore(
      "tabs",
      (t) => t.id === tabId,
      "messages",
      (m) => m.role === "terminal" && m.terminalId === terminalId,
      (m) => ({ ...m, ...state }),
    );
  },
  closeAgentTerminals(tabId: string, agentId?: string) {
    setStore(
      "tabs",
      (t) => t.id === tabId,
      "messages",
      (m) => m.role === "terminal" && (agentId == null || m.agentId === agentId),
      (m) => ({ ...m, terminalActive: false, terminalInteractive: false }),
    );
    persist();
  },
  /** Registra el inicio o invocación de una herramienta */
  pushToolCall(
    tabId: string,
    tool: {
      id?: string;
      toolCallId?: string;
      toolName: string;
      toolArgs?: any;
      toolCommand?: string;
      toolDescription?: string;
      toolSkill?: string;
      agentId?: string;
      status?: "running" | "completed" | "error";
    },
  ) {
    if (isTerminalTool(tool.toolName)) {
      return;
    }
    const callId = tool.toolCallId || tool.id || uid("tcall");
    const existing = store.tabs.find((t) => t.id === tabId)?.messages.find(
      (m) => m.role === "tool" && m.toolCallId === callId,
    );
    if (existing) {
      setStore(
        "tabs",
        (t) => t.id === tabId,
        "messages",
        (m) => m.id === existing.id,
        (prev) => ({
          ...prev,
          toolName: tool.toolName || prev.toolName,
          toolArgs: tool.toolArgs !== undefined ? tool.toolArgs : prev.toolArgs,
          toolCommand: tool.toolCommand || prev.toolCommand,
          toolDescription: tool.toolDescription || prev.toolDescription,
          toolSkill: tool.toolSkill || prev.toolSkill,
          toolStatus: tool.status ?? prev.toolStatus ?? "running",
        }),
      );
      return;
    }

    const msg: ChatMsg = {
      id: tool.id || uid("t"),
      role: "tool",
      text: tool.toolDescription || tool.toolName,
      toolName: tool.toolName,
      toolArgs: tool.toolArgs,
      toolCommand: tool.toolCommand,
      toolDescription: tool.toolDescription,
      toolSkill: tool.toolSkill,
      toolStatus: tool.status ?? "running",
      toolCallId: callId,
      agentId: tool.agentId,
      startedAt: Date.now(),
    };
    setStore("tabs", (t) => t.id === tabId, "messages", (ms) => [...ms, msg]);
    persist();
  },
  /** Actualiza el resultado o salida de una herramienta */
  updateToolResult(
    tabId: string,
    result: {
      toolCallId?: string;
      toolName?: string;
      toolOutput: string;
      status?: "completed" | "error";
    },
  ) {
    if (isTerminalTool(result.toolName)) {
      return;
    }
    const tab = store.tabs.find((t) => t.id === tabId);
    if (!tab) return;

    let target = result.toolCallId
      ? tab.messages.find((m) => m.role === "tool" && m.toolCallId === result.toolCallId)
      : undefined;

    if (!target) {
      const tools = tab.messages.filter((m) => m.role === "tool");
      target = tools.slice().reverse().find((m) => m.toolStatus === "running") || tools[tools.length - 1];
    }

    if (target) {
      setStore(
        "tabs",
        (t) => t.id === tabId,
        "messages",
        (m) => m.id === target!.id,
        (prev) => ({
          ...prev,
          toolOutput: result.toolOutput,
          toolStatus: result.status ?? "completed",
          completedAt: Date.now(),
        }),
      );
    } else {
      const msg: ChatMsg = {
        id: uid("t"),
        role: "tool",
        text: result.toolOutput,
        toolName: result.toolName || "herramienta",
        toolOutput: result.toolOutput,
        toolStatus: result.status ?? "completed",
        toolCallId: result.toolCallId,
        completedAt: Date.now(),
      };
      setStore("tabs", (t) => t.id === tabId, "messages", (ms) => [...ms, msg]);
    }
    persist();
  },
  /** Actualiza o añade un indicador spinner/actividad para el agente */
  updateOrPushSpinner(tabId: string, text: string) {
    const tab = store.tabs.find((t) => t.id === tabId);
    if (!tab) return;
    const last = tab.messages[tab.messages.length - 1];
    if (last && last.role === "tool" && last.toolStatus === "running") {
      setStore(
        "tabs",
        (t) => t.id === tabId,
        "messages",
        (m) => m.id === last.id,
        (prev) => ({ ...prev, toolDescription: text, text }),
      );
      return;
    }
    const msg: ChatMsg = {
      id: uid("t"),
      role: "tool",
      text,
      toolName: "ejecutando",
      toolDescription: text,
      toolStatus: "running",
      startedAt: Date.now(),
    };
    setStore("tabs", (t) => t.id === tabId, "messages", (ms) => [...ms, msg]);
    persist();
  },
  /** Finaliza todas las herramientas activas marcándolas como completadas */
  finalizeTools(tabId: string, status: "completed" | "error" = "completed") {
    setStore(
      "tabs",
      (t) => t.id === tabId,
      "messages",
      (m) => m.role === "tool" && m.toolStatus === "running",
      (prev) => ({
        ...prev,
        toolStatus: status,
        completedAt: prev.completedAt || Date.now(),
      }),
    );
    persist();
  },
  rename(id: string, title: string) {
    setStore("tabs", (t) => t.id === id, "title", title);
    persist();
  },
};

export { uid };
