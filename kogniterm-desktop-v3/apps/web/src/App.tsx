import { Show, createSignal, onMount } from "solid-js";
import { TabBar } from "./components/TabBar";
import { ChatView } from "./components/ChatView";
import { ProviderModal, ModelModal, KeysModal, UnifiedSettingsModal, type SettingsTab } from "./components/SettingsModals";
import { ApprovalDialog, QuestionDialog, PendingBadge } from "./components/ApprovalDialog";
import { TerminalPanel } from "./components/TerminalPanel";
import { ConversationsView } from "./components/ConversationsView";
import { approvals } from "./lib/approvals";
import { api, type LLMConfig } from "./lib/api";
import { tabs } from "./lib/tabs";

type ModalKind = null | { view: "settings"; tab: SettingsTab } | "provider" | "models" | "keys";

export function App() {
  const [modal, setModal] = createSignal<ModalKind>(null);
  const [llm, setLlm] = createSignal<LLMConfig | null>(null);
  const [llmErr, setLlmErr] = createSignal("");
  const [termOpen, setTermOpen] = createSignal(localStorage.getItem("kogniterm-v3-term") !== "0");
  const [termW, setTermW] = createSignal<number | null>(Number(localStorage.getItem("kogniterm-v3-term-w") ?? 46));
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
    if (e.key === "Escape") setModal(null);
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
    <div class="h-screen w-screen flex flex-col bg-[#0d1117] text-[#e6edf3]">
      {/* Topbar: estética v2 + estado LLM nativo */}
      <div class="flex items-center gap-2 px-3 py-2 bg-[#010409] border-b border-[#21262d]">
        <span class="text-[15px]">◈</span>
        <span class="text-[13px] font-semibold">KogniTerm</span>
        <span class="text-[11px] px-1.5 py-0.5 rounded bg-[#238636] text-white font-mono">v3 nativa</span>
        <div class="flex-1" />
        <Show when={llm()} fallback={<span class="text-[12px] text-red-300">{llmErr() || "…"}</span>}>
          <span class="text-[12px] text-[#8b949e] font-mono hidden md:inline">
            {llm()!.provider} · {llm()!.model} {llm()!.has_key ? "· key ✓" : "· sin key"}
          </span>
        </Show>
        <PendingBadge tabId={tabs.store.activeId} />
        <button
          class={`text-[12px] px-2.5 py-1 rounded-md border font-medium ${
            approvals.state.autoApprove[tabs.store.activeId]
              ? "bg-amber-500/20 border-amber-500/60 text-amber-200"
              : "bg-[#161b22] border-[#30363d] text-[#8b949e] hover:text-white"
          }`}
          title={
            approvals.state.autoApprove[tabs.store.activeId]
              ? "Auto-aprobación ACTIVA en esta pestaña: comandos y ediciones se ejecutan sin preguntar. Click para desactivar."
              : "Activar auto-aprobación en esta pestaña (como Shift+Tab de la TUI): no pedirá confirmación."
          }
          onClick={() => approvals.setAuto(tabs.store.activeId, !approvals.state.autoApprove[tabs.store.activeId])}
        >
          {approvals.state.autoApprove[tabs.store.activeId] ? "⚡ auto ON" : "⚡ auto"}
        </button>
        <button
          class={`text-[12px] px-2.5 py-1 rounded-md border font-medium ${
            termOpen()
              ? "bg-[#1f6feb]/20 border-[#1f6feb]/60 text-[#79c0ff]"
              : "bg-[#161b22] border-[#30363d] text-[#8b949e] hover:text-white"
          }`}
          title="Mostrar/ocultar la terminal integrada (Ctrl+`)"
          onClick={toggleTerm}
        >
          ▸ terminal
        </button>
        <button
          class="text-[12px] px-2.5 py-1 rounded-md bg-[#238636] hover:bg-[#2ea043] text-white font-medium"
          onClick={() => setModal({ view: "settings", tab: "provider" })}
          title="Ajustes de proveedor, modelo, keys, conexión y MCP (Ctrl+,)"
        >
          ⚙ Ajustes
        </button>
        <button class="text-[12px] px-2 py-1 text-[#8b949e] hover:text-white" onClick={refreshLLM} title="Recargar config LLM">
          ↻
        </button>
      </div>

      <TabBar view={view()} onToggleView={() => setViewPersist(view() === "chat" ? "conversations" : "chat")} onShowChat={() => setViewPersist("chat")} />

      <Show
        when={view() === "chat"}
        fallback={<ConversationsView onOpenChat={() => setViewPersist("chat")} />}
      >
        <div class="flex-1 min-h-0 flex">
          <div class="flex-1 min-w-0">
            {/* keyed: al cambiar de pestaña se remonta ChatView para que cada
                una tenga su propio WebSocket y su historial. */}
            <Show when={tabs.store.activeId} keyed>
              {(activeId) => <ChatView tabId={activeId} />}
            </Show>
          </div>
          <Show when={termOpen()}>
            <div
              class="w-1 cursor-col-resize flex-none bg-transparent hover:bg-[#1f6feb]/60 transition-colors"
              onPointerDown={startResize}
              title="Arrastra para redimensionar la terminal"
            />
            <div class="flex-none" style={{ width: `${termW() ?? 46}%` }}>
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
