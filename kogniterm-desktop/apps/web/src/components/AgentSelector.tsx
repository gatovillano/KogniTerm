import { For, Show, createMemo, createSignal } from "solid-js";
import { useAgents, type NativeAgent } from "../lib/agents";

interface AgentSelectorProps {
  tabId: string;
  onSelect?: () => void;
}

/**
 * Selector de agentes nativos en el input del chat.
 * Diseño minimalista con botón curvo, popover de cristal y animaciones fluidas.
 */
export function AgentSelector(props: AgentSelectorProps) {
  const agentState = useAgents(props.tabId);
  const [open, setOpen] = createSignal(false);
  const [query, setQuery] = createSignal("");

  const filtered = createMemo(() => {
    const text = query().trim().toLowerCase();
    const items = agentState.catalog()?.agents ?? [];
    if (!text) return items;
    return items.filter((agent: NativeAgent) =>
      `${agent.id} ${agent.name} ${agent.description} ${agent.engine}`.toLowerCase().includes(text),
    );
  });

  const buttonLabel = () => {
    if (agentState.loading()) return "Agentes…";
    const selected = agentState.selected();
    if (selected) return selected.name;
    if (agentState.error()) return "Sin agentes";
    return "Agente";
  };

  const buttonTitle = () => {
    if (agentState.loading()) return "Cargando el catálogo nativo de agentes…";
    const selected = agentState.selected();
    if (selected) return `${selected.description}\nMotor: ${selected.engine}`;
    if (agentState.error()) return `No se pudo cargar el catálogo: ${agentState.error()}`;
    return "Selecciona un agente disponible";
  };

  function close() {
    setOpen(false);
    setQuery("");
  }

  function choose(id: string) {
    agentState.select(id);
    close();
    props.onSelect?.();
  }

  return (
    <div class="relative shrink-0">
      <button
        type="button"
        data-action="agent-selector"
        disabled={!agentState.selected()}
        onClick={() => (open() ? close() : setOpen(true))}
        title={buttonTitle()}
        class={`flex h-[36px] max-w-[200px] items-center gap-2 rounded-xl px-3 text-[12.5px] font-medium transition-all duration-200 active:scale-95 ${
          agentState.selected()
            ? "bg-white/[0.06] hover:bg-white/[0.1] text-white"
            : "cursor-not-allowed bg-white/[0.02] text-slate-500"
        }`}
      >
        <span aria-hidden="true" class="w-2 h-2 rounded-full bg-zinc-300 shadow-[0_0_6px_rgba(255,255,255,0.4)]" />
        <span class="truncate">{buttonLabel()}</span>
        <span aria-hidden="true" class="text-[10px] text-zinc-400">
          ▾
        </span>
      </button>

      <Show when={open() && agentState.selected()}>
        <button
          type="button"
          aria-hidden="true"
          tabIndex={-1}
          onClick={close}
          class="fixed inset-0 z-40 cursor-default bg-transparent"
        />
        <div class="absolute bottom-full left-0 z-50 mb-3 w-80 max-w-[86vw] overflow-hidden rounded-2xl glass-dropdown p-2 animate-scale-in">
          <div class="p-1 mb-1">
            <input
              value={query()}
              onInput={(event) => setQuery(event.currentTarget.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") close();
              }}
              placeholder="Buscar agente…"
              class="w-full rounded-full bg-white/[0.06] px-3.5 py-1.5 text-[12.5px] text-white outline-none placeholder:text-zinc-500 focus:bg-white/[0.1] transition-all"
            />
          </div>
          <div class="max-h-64 overflow-y-auto space-y-1 p-0.5">
            <For each={filtered()} fallback={<p class="px-3 py-4 text-[12px] text-zinc-400 text-center">Sin resultados.</p>}>
              {(agent) => {
                const active = () => agentState.selected()?.id === agent.id;
                return (
                  <button
                    type="button"
                    onClick={() => choose(agent.id)}
                    class={`flex w-full items-start gap-2.5 rounded-xl px-3 py-2 text-left transition-all duration-150 active:scale-[0.98] ${
                      active() ? "bg-white/[0.12] text-white" : "hover:bg-white/[0.06] text-zinc-300"
                    }`}
                  >
                    <span
                      aria-hidden="true"
                      class={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${
                        active() ? "bg-zinc-200 shadow-[0_0_6px_rgba(255,255,255,0.5)]" : "bg-zinc-600"
                      }`}
                    />
                    <span class="min-w-0 flex-1">
                      <span class="block truncate text-[13px] font-semibold text-white">{agent.name}</span>
                      <span class="block text-[12px] leading-snug text-slate-400 line-clamp-2 mt-0.5">{agent.description}</span>
                      <span class="mt-1 block font-mono text-[10.5px] text-slate-400">{agent.engine}</span>
                    </span>
                  </button>
                );
              }}
            </For>
          </div>
        </div>
      </Show>
    </div>
  );
}
