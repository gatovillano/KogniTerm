import { For, Show, createMemo, createSignal } from "solid-js";
import { useAgents, type NativeAgent } from "../lib/agents";
import { IconCheck, IconChevronDown, IconSearch, IconSpark } from "./Icons";

interface AgentSelectorProps {
  tabId: string;
  onSelect?: () => void;
}

/**
 * Selector de agentes nativos en el compositor del chat.
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
        class={`flex h-8 max-w-[190px] items-center gap-1.5 rounded-xl px-2.5 text-[12px] font-medium transition-all duration-150 active:scale-95 border ${
          agentState.selected()
            ? "bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] text-[var(--kt-text-primary)] border-[var(--kt-border-subtle)]"
            : "cursor-not-allowed bg-transparent border-transparent text-[var(--kt-text-faint)]"
        }`}
      >
        <IconSpark size={12} class="shrink-0 text-[var(--kt-text-muted)]" />
        <span class="truncate">{buttonLabel()}</span>
        <IconChevronDown size={12} class="shrink-0 text-[var(--kt-text-muted)]" />
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
          <div class="relative p-1 mb-1">
            <IconSearch size={13} class="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--kt-text-faint)] pointer-events-none" />
            <input
              value={query()}
              onInput={(event) => setQuery(event.currentTarget.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") close();
              }}
              placeholder="Buscar agente…"
              class="w-full rounded-xl bg-[var(--kt-bg-hover)] pl-8 pr-3 py-1.5 text-[12.5px] text-[var(--kt-text-primary)] outline-none placeholder:text-[var(--kt-text-faint)] border border-[var(--kt-border-subtle)] focus:border-[var(--kt-border-strong)] transition-all"
            />
          </div>
          <div class="max-h-64 overflow-y-auto space-y-1 p-0.5">
            <For
              each={filtered()}
              fallback={
                <p class="px-3 py-4 text-[12px] text-[var(--kt-text-muted)] text-center">Sin resultados.</p>
              }
            >
              {(agent) => {
                const active = () => agentState.selected()?.id === agent.id;
                return (
                  <button
                    type="button"
                    onClick={() => choose(agent.id)}
                    class={`flex w-full items-start gap-2.5 rounded-xl px-3 py-2 text-left transition-all duration-150 active:scale-[0.98] border ${
                      active()
                        ? "bg-[var(--kt-bg-active)] text-[var(--kt-text-primary)] border-[var(--kt-border-default)]"
                        : "border-transparent hover:bg-[var(--kt-bg-hover)] text-[var(--kt-text-secondary)]"
                    }`}
                  >
                    <span class="mt-0.5 shrink-0 w-4 h-4 rounded-md flex items-center justify-center">
                      <Show
                        when={active()}
                        fallback={<span class="w-1.5 h-1.5 rounded-full bg-[var(--kt-text-faint)] opacity-60" />}
                      >
                        <IconCheck size={13} class="text-emerald-400" />
                      </Show>
                    </span>
                    <span class="min-w-0 flex-1">
                      <span class="flex items-center justify-between gap-2">
                        <span class="truncate text-[13px] font-semibold text-[var(--kt-text-primary)]">
                          {agent.name}
                        </span>
                        <span class="shrink-0 font-mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--kt-bg-hover)] text-[var(--kt-text-muted)]">
                          {agent.engine}
                        </span>
                      </span>
                      <span class="block text-[11.5px] leading-snug text-[var(--kt-text-muted)] line-clamp-2 mt-0.5">
                        {agent.description}
                      </span>
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
