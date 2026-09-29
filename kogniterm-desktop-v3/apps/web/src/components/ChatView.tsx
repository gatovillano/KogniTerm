import { For, Show, createEffect, createSignal, onMount } from "solid-js";
import { tabs } from "../lib/tabs";
import { useSession } from "../lib/session";
import { loadThreadHistory } from "../lib/history";
import { Markdown } from "./Markdown";

export function ChatView(props: { tabId: string }) {
  const session = useSession(props.tabId);
  const [draft, setDraft] = createSignal("");
  let scrollRef: HTMLDivElement | undefined;

  const tab = () => tabs.store.tabs.find((t) => t.id === props.tabId)!;

  // Historial persistido del hilo (al abrir una conversación o cambiar de pestaña).
  onMount(() => {
    if (tab()?.messages.length === 0) void loadThreadHistory(props.tabId);
  });

  createEffect(() => {
    tab().messages.length;
    scrollRef?.scrollTo({ top: scrollRef.scrollHeight });
  });

  function submit(e?: Event) {
    e?.preventDefault();
    const v = draft();
    if (!v.trim()) return;
    setDraft("");
    session.send(v);
    if (tab().messages.length <= 2) {
      tabs.rename(props.tabId, v.slice(0, 32) || tab().title);
    }
  }

  return (
    <div class="flex flex-col h-full bg-[#0d1117]">
      <div class="flex items-center gap-2 px-4 py-2 border-b border-[#21262d] text-[12px] text-[#8b949e]">
        <span
          class={`w-2 h-2 rounded-full ${
            session.conn() === "open" ? "bg-emerald-400" : session.conn() === "connecting" ? "bg-amber-400" : "bg-red-400"
          }`}
        />
        <span class="font-mono">{props.tabId}</span>
        <span>·</span>
        <span>{session.conn()}</span>
        <div class="flex-1" />
        <button class="hover:text-white" onClick={() => session.reconnect()} title="Reconectar WS">
          ↻
        </button>
        <button class="hover:text-white" onClick={() => session.interrupt()} title="Interrumpir agente">
          ■ stop
        </button>
      </div>

      {/* Una sola columna centrada: usuario y agente comparten bordes.
          El agente ancla a la izquierda de la columna, el usuario a la derecha. */}
      <div ref={scrollRef} class="flex-1 overflow-y-auto px-4 py-4">
        <div class="w-full max-w-3xl mx-auto space-y-3">
          <Show when={tab().messages.length === 0}>
            <div class="text-center text-[#8b949e] text-[13px] mt-10">
              <div class="text-[28px] mb-2">◈</div>
              <p class="text-white text-[15px] font-medium">KogniTerm v3 nativa</p>
              <p class="mt-1">Escribe abajo. Usa /provider · /models · /keys en el menú superior.</p>
            </div>
          </Show>
          <For each={tab().messages}>
            {(m) => (
              <Show
                when={m.role !== "assistant"}
                fallback={
                  /* Agente: sin fondo ni borde, anclado a la izquierda de la columna. */
                  <div class="w-full text-[13px] leading-relaxed text-[#e6edf3]">
                    <Show when={m.thinking?.trim()}>
                      <details class="thinking mb-1.5">
                        <summary>razonamiento</summary>
                        <div class="mt-1">{m.thinking}</div>
                      </details>
                    </Show>
                    <Markdown text={m.text} center />
                    {m.pending && <span class="animate-pulse text-[#58a6ff]">▍</span>}
                  </div>
                }
              >
                <div class={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    class={`max-w-[80%] px-3 py-2 rounded-lg text-[13px] leading-relaxed ${
                      m.role === "user"
                        ? "bg-[#1f6feb] text-white whitespace-pre-wrap"
                        : m.role === "tool"
                          ? "bg-[#161b22] text-[#d29922] border border-[#30363d] font-mono text-[12px] whitespace-pre-wrap"
                          : "bg-[#161b22] text-red-300 border border-[#30363d] whitespace-pre-wrap"
                    }`}
                  >
                    {m.text}
                  </div>
                </div>
              </Show>
            )}
          </For>
        </div>
      </div>

      <form onSubmit={submit} class="p-3 border-t border-[#21262d]">
        <div class="flex gap-2">
          <input
            value={draft()}
            onInput={(e) => setDraft(e.currentTarget.value)}
            placeholder="Escribe un mensaje… (Enter para enviar)"
            class="flex-1 bg-[#161b22] border border-[#30363d] rounded-md px-3 py-2 text-[13px] text-white placeholder-[#6e7681] outline-none focus:border-[#1f6feb]"
          />
          <button
            type="submit"
            class="px-4 py-2 rounded-md bg-[#238636] hover:bg-[#2ea043] text-white text-[13px] font-medium"
          >
            Enviar
          </button>
        </div>
      </form>
    </div>
  );
}
