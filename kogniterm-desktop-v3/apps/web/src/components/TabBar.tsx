import { For, Show, createMemo } from "solid-js";
import { tabs } from "../lib/tabs";

export function TabBar(props: {
  view: "chat" | "conversations";
  onToggleView: () => void;
  onShowChat: () => void;
}) {
  return (
    <nav class="flex items-center gap-1.5 px-3 py-1.5 bg-[#090d15]/90 backdrop-blur-md overflow-x-auto select-none transition-colors">
      {/* Botón de conversaciones: estilo cápsula moderno */}
      <button
        onClick={props.onToggleView}
        title="Conversaciones (agrupadas por proyecto)"
        class={`flex items-center gap-2 px-3 py-1 rounded-full text-[12.5px] font-medium transition-all duration-200 active:scale-95 shrink-0 ${
          props.view === "conversations"
            ? "bg-white/[0.12] text-white shadow-sm"
            : "text-slate-400 hover:text-white hover:bg-white/[0.05]"
        }`}
      >
        <span class="text-[13px] leading-none opacity-80">☰</span>
        <span class="hidden sm:inline">Conversaciones</span>
      </button>

      <span class="w-px h-3.5 bg-white/[0.08] mx-1 shrink-0" />

      {/* Lista de pestañas tipo cápsulas / floating pills */}
      <div class="flex items-center gap-1 overflow-x-auto py-0.5">
        <For each={tabs.store.tabs}>
          {(t) => {
            const active = createMemo(() => t.id === tabs.store.activeId);
            return (
              <div
                class={`group flex items-center gap-2 px-3 py-1 rounded-full text-[12.5px] font-medium cursor-pointer shrink-0 transition-all duration-200 active:scale-[0.98] ${
                  active()
                    ? "bg-white/[0.12] text-white shadow-[0_2px_10px_rgba(0,0,0,0.3)]"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.05]"
                }`}
                onClick={() => {
                  tabs.select(t.id);
                  props.onShowChat();
                }}
              >
                <span
                  class={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
                    active() ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" : "bg-slate-600"
                  }`}
                />
                <span class="max-w-[150px] truncate">{t.title}</span>
                <Show when={tabs.store.tabs.length > 1}>
                  <button
                    class="w-4 h-4 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-white/15 text-slate-400 hover:text-white text-[11px] leading-none transition-all ml-0.5"
                    onClick={(e) => {
                      e.stopPropagation();
                      tabs.close(t.id);
                    }}
                    title="Cerrar pestaña"
                  >
                    ✕
                  </button>
                </Show>
              </div>
            );
          }}
        </For>
      </div>

      <button
        class="w-6 h-6 ml-1 flex items-center justify-center rounded-full text-slate-400 hover:text-white hover:bg-white/[0.08] text-[15px] leading-none transition-all duration-150 active:scale-90 shrink-0"
        onClick={() => {
          tabs.newTab();
          props.onShowChat();
        }}
        title="Nueva pestaña (sesión)"
      >
        +
      </button>
    </nav>
  );
}
