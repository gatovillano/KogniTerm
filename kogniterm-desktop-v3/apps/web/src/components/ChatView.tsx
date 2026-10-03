import { For, Show, createEffect, createSignal, onMount } from "solid-js";
import { tabs } from "../lib/tabs";
import { useSession } from "../lib/session";
import { agents, useAgents } from "../lib/agents";
import { loadThreadHistory } from "../lib/history";
import { AgentTerminal } from "./AgentTerminal";
import { AgentSelector } from "./AgentSelector";
import { Markdown } from "./Markdown";

export function ChatView(props: { tabId: string }) {
  const session = useSession(props.tabId);
  const agentState = useAgents(props.tabId);
  const [draft, setDraft] = createSignal("");
  const [agentStatus, setAgentStatus] = createSignal("");
  let scrollRef: HTMLDivElement | undefined;
  let inputRef: HTMLInputElement | undefined;

  const tab = () => tabs.store.tabs.find((t) => t.id === props.tabId)!;

  // Historial persistido del hilo (al abrir una conversación o cambiar de pestaña).
  onMount(() => {
    if (tab()?.messages.length === 0) void loadThreadHistory(props.tabId);
  });

  createEffect(() => {
    tab().messages.length;
    scrollRef?.scrollTo({ top: scrollRef.scrollHeight, behavior: "smooth" });
  });

  function submit(e?: Event) {
    e?.preventDefault();
    const v = draft();
    if (!v.trim()) return;
    const selected = agentState.selected();
    if (!selected) {
      setAgentStatus(
        agentState.error()
          ? `Agentes no disponibles: ${agentState.error()}`
          : "Cargando el catálogo nativo de agentes…",
      );
      if (!agentState.catalog()) {
        void agents.ensureAgents(true);
      }
      return;
    }
    setAgentStatus("");
    setDraft("");
    session.send(v, selected.id);
    if (tab().messages.length <= 2) {
      tabs.rename(props.tabId, v.slice(0, 32) || tab().title);
    }
  }

  return (
    <div class="flex flex-col h-full bg-[#080b11] text-[#f1f5f9]">
      {/* Barra de estado minimalista y sin bordes */}
      <div class="flex items-center gap-2.5 px-5 py-2 text-[12px] text-slate-400 bg-white/[0.015] select-none">
        <div class="flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-white/[0.04]">
          <span
            class={`w-2 h-2 rounded-full transition-all duration-300 ${
              session.conn() === "open"
                ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]"
                : session.conn() === "connecting"
                  ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.7)]"
                  : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.7)]"
            }`}
          />
          <span class="font-mono text-slate-300 text-[11px]">{props.tabId}</span>
          <span class="text-slate-600">·</span>
          <span class="capitalize text-slate-400 text-[11px]">{session.conn()}</span>
        </div>

        <div class="flex-1" />

        <button
          class="w-6 h-6 rounded-full flex items-center justify-center hover:bg-white/[0.08] hover:text-white transition-all text-slate-400"
          onClick={() => session.reconnect()}
          title="Reconectar WebSocket"
        >
          ↻
        </button>

        <button
          class="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-red-500/15 text-red-300 hover:bg-red-500/25 transition-all active:scale-95"
          onClick={() => session.interrupt()}
          title="Interrumpir agente"
        >
          <span>■</span> stop
        </button>
      </div>

      {/* Área de mensajes del chat */}
      <div ref={scrollRef} data-chat-scroll class="flex-1 overflow-y-auto px-4 py-6">
        <div class="w-full max-w-3xl mx-auto space-y-4">
          <Show when={tab().messages.length === 0}>
            <div class="text-center text-slate-400 py-16 animate-fade-in flex flex-col items-center select-none">
              <div class="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600/30 to-indigo-500/20 flex items-center justify-center text-blue-400 text-3xl mb-4 shadow-[0_0_30px_rgba(99,102,241,0.2)]">
                ◈
              </div>
              <h2 class="text-white text-[18px] font-semibold tracking-tight">KogniTerm v3</h2>
              <p class="mt-1.5 text-[13px] text-slate-400 max-w-md">
                Entorno de ejecución y asistencia inteligente. Escribe tus instrucciones abajo o usa los comandos rápidos.
              </p>
              <div class="mt-6 flex flex-wrap gap-2 justify-center">
                <span class="px-3 py-1 rounded-full bg-white/[0.04] text-[11px] text-slate-400 font-mono">
                  Ctrl+P · Proveedor
                </span>
                <span class="px-3 py-1 rounded-full bg-white/[0.04] text-[11px] text-slate-400 font-mono">
                  Ctrl+M · Modelos
                </span>
                <span class="px-3 py-1 rounded-full bg-white/[0.04] text-[11px] text-slate-400 font-mono">
                  Ctrl+` · Terminal
                </span>
              </div>
            </div>
          </Show>

          <For each={tab().messages}>
            {(m) => (
              <Show
                when={m.role !== "assistant" && m.role !== "terminal"}
                fallback={
                  <Show
                    when={m.role === "terminal"}
                    fallback={
                      /* Agente: diseño minimalista y elegante sin bordes toscos */
                      <div class="w-full text-[13.5px] leading-relaxed text-[#f1f5f9] animate-slide-up">
                        <Show when={m.thinking?.trim()}>
                          <details class="thinking mb-2">
                            <summary>razonamiento</summary>
                            <div class="mt-2 text-slate-400 text-[12px]">{m.thinking}</div>
                          </details>
                        </Show>
                        <Markdown text={m.text} center />
                        {m.pending && (
                          <span class="inline-block w-2 h-4 ml-1 rounded-full bg-blue-400 animate-pulse align-middle" />
                        )}
                      </div>
                    }
                  >
                    <div class="animate-slide-up my-2">
                      <AgentTerminal
                        tabId={props.tabId}
                        terminalId={m.terminalId ?? m.id}
                        tool={m.terminalTool}
                        command={m.terminalCommand}
                        output={m.terminalOutput ?? ""}
                        active={m.terminalActive}
                        interactive={m.terminalInteractive}
                        onInput={(text) => session.sendTerminalInput(text)}
                      />
                    </div>
                  </Show>
                }
              >
                <div class={`flex animate-slide-up ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    class={`max-w-[85%] text-[13.5px] leading-relaxed transition-all ${
                      m.role === "user"
                        ? "bg-gradient-to-tr from-blue-600 to-indigo-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 shadow-[0_4px_16px_rgba(37,99,235,0.25)] whitespace-pre-wrap"
                        : m.role === "tool"
                          ? "bg-white/[0.04] text-amber-300 font-mono text-[12px] rounded-2xl p-3 whitespace-pre-wrap"
                          : "bg-red-500/10 text-red-200 rounded-2xl p-3 whitespace-pre-wrap"
                    }`}
                  >
                    <Show when={m.role === "user" && m.agent}>
                      <div class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/70">
                        {agents.byId(m.agent)?.name ?? m.agent}
                      </div>
                    </Show>
                    {m.text}
                  </div>
                </div>
              </Show>
            )}
          </For>
        </div>
      </div>

      {/* Dock de entrada flotante y curvo al pie de página */}
      <div class="p-4 bg-gradient-to-t from-[#080b11] via-[#080b11]/95 to-transparent">
        <div class="max-w-3xl mx-auto">
          <Show when={agentStatus()}>
            <p class="mb-2 text-[12px] text-amber-300/90 px-3 animate-fade-in">{agentStatus()}</p>
          </Show>
          <form
            onSubmit={submit}
            class="flex items-center gap-2 p-1.5 rounded-2xl bg-[#111624] hover:bg-[#131929] focus-within:bg-[#131929] focus-within:ring-2 focus-within:ring-blue-500/30 transition-all duration-200 shadow-[0_8px_32px_rgba(0,0,0,0.5)]"
          >
            <AgentSelector tabId={props.tabId} onSelect={() => inputRef?.focus()} />
            
            <input
              ref={inputRef}
              value={draft()}
              onInput={(e) => {
                setDraft(e.currentTarget.value);
                if (agentStatus()) setAgentStatus("");
              }}
              placeholder="Escribe un mensaje o tarea… (Enter para enviar)"
              class="flex-1 bg-transparent px-3 py-2 text-[13.5px] text-white placeholder-slate-500 outline-none"
            />

            <button
              type="submit"
              disabled={!draft().trim() || !agentState.selected()}
              title={
                agentState.selected()
                  ? `Enviar con ${agentState.selected()?.name}`
                  : "Selecciona un agente disponible antes de enviar"
              }
              class="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white flex items-center justify-center font-medium shadow-[0_0_15px_rgba(99,102,241,0.35)] transition-all duration-200 active:scale-90 disabled:opacity-30 disabled:pointer-events-none"
            >
              <svg class="w-4 h-4 fill-current rotate-45 transform -translate-x-0.5 translate-y-0.5" viewBox="0 0 20 20">
                <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
              </svg>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
