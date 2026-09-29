import { For, Show, createMemo } from "solid-js";
import { tabs } from "../lib/tabs";

export function TabBar(props: {
  view: "chat" | "conversations";
  onToggleView: () => void;
  onShowChat: () => void;
}) {
  return (
    <div class="flex items-center gap-1 px-2 py-1.5 bg-[#0d1117] border-b border-[#21262d] overflow-x-auto">
      {/* Botón a la izquierda de las pestañas: lista de conversaciones */}
      <button
        onClick={props.onToggleView}
        title="Conversaciones (agrupadas por proyecto)"
        class={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[13px] border shrink-0 ${
          props.view === "conversations"
            ? "bg-[#21262d] text-white border-[#30363d]"
            : "text-[#8b949e] border-transparent hover:bg-[#161b22] hover:text-white"
        }`}
      >
        <span class="text-[14px] leading-none">☰</span>
        <span class="hidden sm:inline">Conversaciones</span>
      </button>

      <span class="w-px h-5 bg-[#21262d] mx-1 shrink-0" />

      <For each={tabs.store.tabs}>
        {(t) => {
          const active = createMemo(() => t.id === tabs.store.activeId);
          return (
            <div
              class={`group flex items-center gap-2 px-3 py-1.5 rounded-md text-[13px] cursor-pointer border shrink-0 ${
                active() ? "bg-[#161b22] text-white border-[#30363d]" : "text-[#8b949e] border-transparent hover:bg-[#161b22]"
              }`}
              onClick={() => {
                tabs.select(t.id);
                props.onShowChat();
              }}
            >
              <span class={`w-1.5 h-1.5 rounded-full ${active() ? "bg-emerald-400" : "bg-[#30363d]"}`} />
              <span class="max-w-[140px] truncate">{t.title}</span>
              <Show when={tabs.store.tabs.length > 1}>
                <button
                  class="opacity-0 group-hover:opacity-100 hover:text-white px-1"
                  onClick={(e) => {
                    e.stopPropagation();
                    tabs.close(t.id);
                  }}
                  title="Cerrar pestaña"
                >
                  ×
                </button>
              </Show>
            </div>
          );
        }}
      </For>
      <button
        class="ml-1 px-2.5 py-1 rounded-md text-[#8b949e] hover:text-white hover:bg-[#161b22] text-[13px] shrink-0"
        onClick={() => {
          tabs.newTab();
          props.onShowChat();
        }}
        title="Nueva pestaña (sesión)"
      >
        +
      </button>
    </div>
  );
}
