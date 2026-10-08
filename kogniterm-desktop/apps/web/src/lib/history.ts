import { api, type ThreadMessage } from "./api";
import { tabs, uid, isTerminalTool, type ChatMsg } from "./tabs";

/** Convierte el historial del backend al formato de burbuja de la UI. */
function toChatMsg(m: ThreadMessage, toolMap?: Map<string, { name: string; args: any }>): ChatMsg | null {
  // El backend ya normaliza a user/assistant/tool/system, pero por si llega
  // un nombre de tipo de LangChain sin mapear.
  const raw = String(m.role ?? "");
  const role: ChatMsg["role"] =
    raw === "human" ? "user" : raw === "ai" ? "assistant" : raw === "tool" ? "tool" : (raw as ChatMsg["role"]) || "system";
  let text = typeof m.content === "string" ? m.content : "";

  if (role === "tool") {
    const meta = m.tool_call_id ? toolMap?.get(m.tool_call_id) : undefined;
    const name = meta?.name || "herramienta";
    // execute_command y comandos de terminal usan la terminal interactiva, no el ToolIndicator
    if (isTerminalTool(name)) {
      return null;
    }
    return {
      id: m.id || uid("h"),
      role: "tool",
      text,
      toolName: name,
      toolArgs: meta?.args,
      toolOutput: text,
      toolStatus: "completed",
      toolCallId: m.tool_call_id || undefined,
    };
  }

  // Si el mensaje de IA solo trae tool_calls, formateamos como llamada de herramienta
  if (role === "assistant" && !text && m.tool_calls?.length) {
    const first = m.tool_calls[0];
    if (isTerminalTool(first.name)) {
      return null;
    }
    return {
      id: m.id || uid("h"),
      role: "tool",
      text: `⚙ ${first.name}`,
      toolName: first.name,
      toolArgs: first.args,
      toolStatus: "completed",
      toolCallId: first.id,
      thinking: m.reasoning || undefined,
    };
  }

  return {
    id: m.id || uid("h"),
    role,
    text,
    thinking: m.reasoning || undefined,
    ...(m.images?.length ? { images: m.images } : {}),
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
    const list = r?.messages ?? [];

    const toolMap = new Map<string, { name: string; args: any }>();
    for (const m of list) {
      if (m.tool_calls && Array.isArray(m.tool_calls)) {
        for (const tc of m.tool_calls) {
          if (tc.id) {
            toolMap.set(tc.id, { name: tc.name, args: tc.args });
          }
        }
      }
    }

    const msgs = list.map((m) => toChatMsg(m, toolMap)).filter((m): m is ChatMsg => m !== null);
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
