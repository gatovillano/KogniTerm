import { For, Show } from "solid-js";
import { tabs } from "../lib/tabs";
import { IconClose, IconConversations, IconPlus } from "./Icons";

export function TabBar(props: {
  view: "chat" | "conversations";
  onToggleView: () => void;
  onShowChat: () => void;
}) {
  return (
    <nav class="flex flex-1 min-w-0 items-center gap-1.5 px-1 py-0.5 bg-transparent select-none">
      {/* Botón de conversaciones / proyectos */}
      <button
        onClick={props.onToggleView}
        title="Conversaciones y Workspaces"
        class={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-[12.5px] font-medium transition-all duration-150 active:scale-[0.97] shrink-0 border ${
          props.view === "conversations"
            ? "bg-[var(--kt-bg-active)] text-[var(--kt-text-primary)] border-[var(--kt-border-default)] shadow-sm"
            : "border-transparent text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)]"
        }`}
      >
        <IconConversations size={14} class="opacity-85" />
        <span class="hidden sm:inline">Sesiones</span>
      </button>

      <span class="w-px h-4 bg-[var(--kt-border-subtle)] mx-0.5 shrink-0" />

      {/* Lista de pestañas */}
      <div class="flex flex-1 min-w-0 items-center gap-1 overflow-x-auto py-0.5 no-scrollbar">
        <For each={tabs.store.tabs}>
          {(t) => {
            const active = () => props.view === "chat" && t.id === tabs.store.activeId;
            return (
              <div
                class={`group flex items-center gap-2 pl-2.5 pr-1.5 py-1 rounded-xl text-[12.5px] font-medium cursor-pointer shrink-0 transition-all duration-150 border ${
                  active()
                    ? "bg-[var(--kt-bg-elevated)] text-[var(--kt-text-primary)] border-[var(--kt-border-default)] shadow-[var(--kt-shadow-sm)]"
                    : "border-transparent text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)]"
                }`}
                title={t.workspaceDir ? `${t.title}\n${t.workspaceDir}` : t.title}
                onClick={() => {
                  tabs.select(t.id);
                  props.onShowChat();
                }}
                onAuxClick={(e) => {
                  if (e.button === 1 && tabs.store.tabs.length > 1) {
                    e.preventDefault();
                    tabs.close(t.id);
                  }
                }}
              >
                <span
                  class={`w-1.5 h-1.5 rounded-full shrink-0 transition-all duration-300 ${
                    active()
                      ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]"
                      : "bg-[var(--kt-text-faint)] opacity-50"
                  }`}
                />
                <span class="max-w-[148px] truncate">{t.title}</span>
                <Show when={tabs.store.tabs.length > 1}>
                  <button
                    class={`w-4 h-4 rounded-md flex items-center justify-center transition-all ml-0.5 text-[var(--kt-text-faint)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-active)] ${
                      active() ? "opacity-65 hover:opacity-100" : "opacity-0 group-hover:opacity-80"
                    }`}
                    onClick={(e) => {
                      e.stopPropagation();
                      tabs.close(t.id);
                    }}
                    title="Cerrar pestaña"
                  >
                    <IconClose size={11} />
                  </button>
                </Show>
              </div>
            );
          }}
        </For>

        <button
          class="w-7 h-7 ml-0.5 flex items-center justify-center rounded-xl text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all duration-150 active:scale-90 shrink-0"
          onClick={() => {
            tabs.newTab();
            props.onShowChat();
          }}
          title="Nueva pestaña (sesión)"
        >
          <IconPlus size={14} />
        </button>
      </div>
    </nav>
  );
}
