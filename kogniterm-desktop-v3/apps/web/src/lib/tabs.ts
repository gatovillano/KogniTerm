import { createStore } from "solid-js/store";

export interface ChatMsg {
  id: string;
  role: "user" | "assistant" | "tool" | "system" | "terminal";
  text: string;
  agent?: string;
  /** Razonamiento del modelo (evento live_update.thinking), se muestra atenuado. */
  thinking?: string;
  /** Sigue llegando contenido: la burbuja muestra cursor y aún no se persiste. */
  pending?: boolean;
  /** Terminal interactiva vinculada a la ejecución worker del agente, no al PTY lateral. */
  terminalId?: string;
  terminalTool?: string;
  terminalCommand?: string;
  terminalOutput?: string;
  terminalActive?: boolean;
  terminalInteractive?: boolean;
  agentId?: string;
}

export interface Tab {
  id: string; // = session_id nativo
  title: string;
  messages: ChatMsg[];
  /** El historial ya se pidió al backend para esta pestaña. */
  historyLoaded?: boolean;
}

function uid(prefix = "id"): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36)}`;
}

function load(): Tab[] {
  try {
    const raw = localStorage.getItem("kogniterm-v3-tabs");
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) return arr;
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
    if (store.tabs.length === 1) return;
    const idx = store.tabs.findIndex((t) => t.id === id);
    setStore("tabs", (ts) => ts.filter((t) => t.id !== id));
    if (store.activeId === id) {
      const next = store.tabs[Math.max(0, idx - 1)];
      setStore("activeId", next.id);
    }
    persist();
  },
  push(tabId: string, msg: ChatMsg) {
    setStore("tabs", (t) => t.id === tabId, "messages", (ms) => [...ms, msg]);
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
  rename(id: string, title: string) {
    setStore("tabs", (t) => t.id === id, "title", title);
    persist();
  },
};

export { uid };
