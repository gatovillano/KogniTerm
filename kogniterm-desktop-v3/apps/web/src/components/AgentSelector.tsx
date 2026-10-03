import { For, Show, createMemo, createSignal } from "solid-js";
import { useAgents, type NativeAgent } from "../lib/agents";

interface AgentSelectorProps {
  tabId: string;
  onSelect?: () => void;
}

/**
 * Selector de agentes nativos en el input del chat.
 * Solo muestra motores conversacionales publicados por `GET /api/agents`, por
 * lo que el botón visible y el motor enviado al backend usan el mismo ID.
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
        class={`flex h-[38px] max-w-[190px] items-center gap-2 rounded-md border px-2.5 text-[13px] transition-colors ${
          agentState.selected()
            ? "border-[#30363d] bg-[#161b22] text-white hover:border-[#1f6feb]"
            : "cursor-not-allowed border-[#21262d] bg-[#0d1117] text-[#6e7681]"
        }`}
      >
        <span aria-hidden="true" class="text-[15px] leading-none text-[#58a6ff]">
          ◍
        </span>
        <span class="truncate font-medium">{buttonLabel()}</span>
        <span aria-hidden="true" class="text-[11px] text-[#6e7681]">
          ▾
        </span>
      </button>

      <Show when={open() && agentState.selected()}>
        <button
          type="button"
          aria-hidden="true"
          tabIndex={-1}
          onClick={close}
          class="fixed inset-0 z-10 cursor-default bg-transparent"
        />
        <div class="absolute bottom-full left-0 z-20 mb-2 w-80 max-w-[86vw] overflow-hidden rounded-lg border border-[#30363d] bg-[#0d1117] shadow-xl">
          <div class="border-b border-[#21262d] p-2">
            <input
              value={query()}
              onInput={(event) => setQuery(event.currentTarget.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") close();
              }}
              placeholder="Buscar agente…"
              class="w-full rounded-md border border-[#30363d] bg-[#161b22] px-2.5 py-1.5 text-[13px] text-white outline-none placeholder:text-[#6e7681] focus:border-[#1f6feb]"
            />
          </div>
          <div class="max-h-64 overflow-y-auto p-1.5">
            <For each={filtered()} fallback={<p class="px-2.5 py-3 text-[12px] text-[#8b949e]">Sin resultados.</p>}>
              {(agent) => {
                const active = () => agentState.selected()?.id === agent.id;
                return (
                  <button
                    type="button"
                    onClick={() => choose(agent.id)}
                    class={`flex w-full items-start gap-2.5 rounded-md px-2.5 py-2 text-left transition-colors ${
                      active() ? "bg-[#1f6feb]/20" : "hover:bg-[#161b22]"
                    }`}
                  >
                    <span aria-hidden="true" class={`mt-0.5 text-[13px] ${active() ? "text-[#79c0ff]" : "text-[#6e7681]"}`}>
                      {active() ? "●" : "○"}
                    </span>
                    <span class="min-w-0 flex-1">
                      <span class="block truncate text-[13px] font-medium text-white">{agent.name}</span>
                      <span class="block text-[12px] leading-snug text-[#8b949e]">{agent.description}</span>
                      <span class="mt-0.5 block font-mono text-[11px] text-[#6e7681]">{agent.engine}</span>
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
