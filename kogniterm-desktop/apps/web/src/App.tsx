import { Show, createSignal, onMount } from "solid-js";
import { TabBar } from "./components/TabBar";
import { ChatView } from "./components/ChatView";
import { ProviderModal, ModelModal, KeysModal, UnifiedSettingsModal, type SettingsTab } from "./components/SettingsModals";
import { ApprovalDialog, QuestionDialog, PendingBadge } from "./components/ApprovalDialog";
import { TerminalPanel } from "./components/TerminalPanel";
import { ConversationsView } from "./components/ConversationsView";
import { approvals } from "./lib/approvals";
import { setAutoApprove } from "./lib/session";
import { api, type LLMConfig } from "./lib/api";
import { tabs } from "./lib/tabs";

type ModalKind = null | { view: "settings"; tab: SettingsTab } | "provider" | "models" | "keys";

export function App() {
  const [modal, setModal] = createSignal<ModalKind>(null);
  const [llm, setLlm] = createSignal<LLMConfig | null>(null);
  const [llmErr, setLlmErr] = createSignal("");
  const [termOpen, setTermOpen] = createSignal(localStorage.getItem("kogniterm-v3-term") !== "0");
  const [termW, setTermW] = createSignal<number | null>(Number(localStorage.getItem("kogniterm-v3-term-w") ?? 46));
  const [menuOpen, setMenuOpen] = createSignal(false);
  const [view, setView] = createSignal<"chat" | "conversations">(
    (localStorage.getItem("kogniterm-v3-view") as "chat" | "conversations") ?? "chat",
  );

  function setViewPersist(v: "chat" | "conversations") {
    setView(v);
    localStorage.setItem("kogniterm-v3-view", v);
  }

  function toggleTerm() {
    const v = !termOpen();
    setTermOpen(v);
    localStorage.setItem("kogniterm-v3-term", v ? "1" : "0");
  }

  async function refreshLLM() {
    try {
      setLlm(await api.getLLM());
      setLlmErr("");
    } catch (e) {
      setLlmErr(`backend no disponible (${e}). Arranca: bash scripts/dev-backend.sh`);
    }
  }

  onMount(() => {
    void refreshLLM();
  });

  // atajos: Ctrl+, abre Ajustes; Ctrl+P/M/K abren Ajustes en esa pestaña (como /provider /models /keys)
  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === ",") {
      e.preventDefault();
      setModal({ view: "settings", tab: "provider" });
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") {
      e.preventDefault();
      setModal({ view: "settings", tab: "provider" });
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "m") {
      e.preventDefault();
      setModal({ view: "settings", tab: "models" });
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      setModal({ view: "settings", tab: "keys" });
    }
    if ((e.ctrlKey || e.metaKey) && e.key === "`") {
      e.preventDefault();
      toggleTerm();
    }
    if (e.key === "Escape") {
      setModal(null);
      setMenuOpen(false);
    }
  });

  // sidebar redimensionable (arrastrar el divisor)
  function startResize(e: PointerEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startW = termW() ?? 46;
    const move = (ev: PointerEvent) => {
      const delta = startX - ev.clientX;
      const next = Math.min(85, Math.max(22, startW + (delta / window.innerWidth) * 100));
      setTermW(next);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      setTermW((w) => {
        if (w != null) localStorage.setItem("kogniterm-v3-term-w", String(w));
        return w;
      });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  return (
    <div class="h-screen w-screen flex flex-col bg-[#090a0f] text-[#f4f4f5]">
      {/* Topbar: pestañas arriba, sin título KogniTerm v3 */}
      <header class="glass-header z-30 flex items-center gap-2 pl-2 pr-4 py-2 transition-all select-none">
        <div class="flex-1 min-w-0">
          <TabBar view={view()} onToggleView={() => setViewPersist(view() === "chat" ? "conversations" : "chat")} onShowChat={() => setViewPersist("chat")} />
        </div>

        <div class="flex items-center gap-2 shrink-0">
          <PendingBadge tabId={tabs.store.activeId} />
          
          <button
            class={`text-[12px] px-3 py-1 rounded-full font-medium transition-all duration-200 active:scale-95 ${
              approvals.isAuto(tabs.store.activeId)
                ? "bg-amber-500/20 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.25)]"
                : "bg-white/[0.05] text-zinc-400 hover:text-white hover:bg-white/[0.09]"
            }`}
            title={
              approvals.isAuto(tabs.store.activeId)
                ? "Auto-aprobación ACTIVA en esta pestaña: comandos y ediciones se ejecutan sin preguntar. Click para desactivar."
                : "Activar auto-aprobación en esta pestaña (como Shift+Tab de la TUI): no pedirá confirmación."
            }
            onClick={() => setAutoApprove(tabs.store.activeId, !approvals.isAuto(tabs.store.activeId))}
          >
            {approvals.isAuto(tabs.store.activeId) ? "⚡ auto ON" : "⚡ auto"}
          </button>

          <div class="relative">
            <button
              class="w-7 h-7 flex items-center justify-center rounded-full text-zinc-300 hover:text-white hover:bg-white/[0.08] transition-all active:scale-95 text-[15px]"
              onClick={() => setMenuOpen((v) => !v)}
              title="Menú"
              aria-haspopup="menu"
              aria-expanded={menuOpen()}
            >
              ☰
            </button>
            <Show when={menuOpen()}>
              <div class="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
              <div
                role="menu"
                class="absolute right-0 top-9 z-50 min-w-44 rounded-xl glass-dropdown border border-white/[0.08] p-1.5 animate-scale-in"
              >
                <button
                  role="menuitem"
                  class="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[12.5px] text-zinc-300 hover:text-white hover:bg-white/[0.07] transition-all text-left"
                  title="Mostrar/ocultar la terminal integrada (Ctrl+`)"
                  onClick={() => {
                    toggleTerm();
                    setMenuOpen(false);
                  }}
                >
                  <span class="text-[11px] w-4 text-center">▸</span>
                  <span>Terminal</span>
                  <span class="ml-auto text-[11px] text-zinc-500">{termOpen() ? "✓" : ""}</span>
                </button>
                <button
                  role="menuitem"
                  class="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[12.5px] text-zinc-300 hover:text-white hover:bg-white/[0.07] transition-all text-left"
                  title="Ajustes de proveedor, modelo, keys, conexión y MCP (Ctrl+,)"
                  onClick={() => {
                    setModal({ view: "settings", tab: "provider" });
                    setMenuOpen(false);
                  }}
                >
                  <span class="text-[11px] w-4 text-center">⚙</span>
                  <span>Ajustes</span>
                </button>
              </div>
            </Show>
          </div>

          <button
            class="w-7 h-7 flex items-center justify-center rounded-full text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-all duration-300 active:rotate-180 text-[13px]"
            onClick={refreshLLM}
            title="Recargar config LLM"
          >
            ↻
          </button>
        </div>
      </header>

      <Show
        when={view() === "chat"}
        fallback={<ConversationsView onOpenChat={() => setViewPersist("chat")} />}
      >
        <div class="flex-1 min-h-0 flex relative overflow-hidden">
          <div class="flex-1 min-w-0 h-full">
            {/* keyed: al cambiar de pestaña se remonta ChatView para que cada
                una tenga su propio WebSocket y su historial. */}
            <Show when={tabs.store.activeId} keyed>
              {(activeId) => <ChatView tabId={activeId} />}
            </Show>
          </div>
          <Show when={termOpen()}>
            <div
              class="w-1.5 cursor-col-resize flex-none bg-transparent hover:bg-white/10 transition-all duration-200 z-10 relative flex items-center justify-center group"
              onPointerDown={startResize}
              title="Arrastra para redimensionar la terminal"
            >
              <div class="w-0.5 h-8 rounded-full bg-white/10 group-hover:bg-zinc-300 group-hover:h-12 transition-all duration-200" />
            </div>
            <div class="flex-none h-full" style={{ width: `${termW() ?? 46}%` }}>
              <TerminalPanel tabId={tabs.store.activeId} />
            </div>
          </Show>
        </div>
      </Show>

      <Show when={modal() !== null && typeof modal() === "object" && (modal() as any).view === "settings"}>
        <UnifiedSettingsModal
          current={llm()}
          initialTab={(modal() as any).tab}
          onClose={() => setModal(null)}
          onDone={refreshLLM}
        />
      </Show>
      <Show when={modal() === "provider"}>
        <ProviderModal current={llm()} onClose={() => setModal(null)} onDone={refreshLLM} />
      </Show>
      <Show when={modal() === "models"}>
        <ModelModal current={llm()} onClose={() => setModal(null)} onDone={refreshLLM} />
      </Show>
      <Show when={modal() === "keys"}>
        <KeysModal onClose={() => setModal(null)} onDone={refreshLLM} />
      </Show>

      {/* Aprobaciones y preguntas del agente (bloquean al worker hasta responder) */}
      <ApprovalDialog tabId={tabs.store.activeId} />
      <QuestionDialog tabId={tabs.store.activeId} />
    </div>
  );
}
