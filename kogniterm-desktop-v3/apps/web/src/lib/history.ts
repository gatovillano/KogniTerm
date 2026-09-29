import { api, type ThreadMessage } from "./api";
import { tabs, uid, type ChatMsg } from "./tabs";

/** Convierte el historial del backend al formato de burbuja de la UI. */
function toChatMsg(m: ThreadMessage): ChatMsg {
  // El backend ya normaliza a user/assistant/tool/system, pero por si llega
  // un nombre de tipo de LangChain sin mapear.
  const raw = String(m.role ?? "");
  const role: ChatMsg["role"] =
    raw === "human" ? "user" : raw === "ai" ? "assistant" : raw === "tool" ? "tool" : (raw as ChatMsg["role"]) || "system";
  let text = typeof m.content === "string" ? m.content : "";
  // Si el mensaje de IA solo trae tool_calls, mostramos qué herramienta invocó.
  if (role === "assistant" && !text && m.tool_calls?.length) {
    text = m.tool_calls.map((t) => `⚙ ${t.name}(${summarize(t.args)})`).join("\n");
  }
  if (role === "tool" && !text) text = "⚙ herramienta";
  return {
    id: m.id || uid("h"),
    role,
    text,
    thinking: m.reasoning || undefined,
  };
}

function summarize(args: Record<string, unknown>): string {
  const s = JSON.stringify(args ?? {});
  return s.length > 120 ? `${s.slice(0, 120)}…` : s;
}

/**
 * Carga el historial persistido de una pestaña desde el backend.
 * Idempotente: si ya se cargó, no vuelve a pedirlo.
 */
export async function loadThreadHistory(tabId: string, force = false): Promise<number> {
  if (!force && tabs.wasHistoryLoaded(tabId)) {
    return tabs.store.tabs.find((t) => t.id === tabId)?.messages.length ?? 0;
  }
  try {
    const r = await api.threadMessages(tabId);
    const msgs = (r?.messages ?? []).map(toChatMsg);
    // No pisar una conversación en curso que ya tenga mensajes en la UI.
    const current = tabs.store.tabs.find((t) => t.id === tabId)?.messages ?? [];
    if (current.length === 0) tabs.setHistory(tabId, msgs);
    else tabs.markHistoryLoaded(tabId);
    return msgs.length;
  } catch (e) {
    // Sin historial (pestaña nueva) no es un error a mostrar.
    tabs.markHistoryLoaded(tabId);
    return 0;
  }
}
