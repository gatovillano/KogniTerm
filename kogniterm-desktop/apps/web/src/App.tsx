import { Show, createSignal, onCleanup, onMount } from "solid-js";
import { TabBar } from "./components/TabBar";
import { ChatView } from "./components/ChatView";
import {
  ProviderModal,
  ModelModal,
  KeysModal,
  UnifiedSettingsModal,
  type SettingsTab,
} from "./components/SettingsModals";
import { ApprovalDialog, QuestionDialog, PendingBadge } from "./components/ApprovalDialog";
import { PasswordDialog } from "./components/PasswordDialog";
import { TerminalPanel } from "./components/TerminalPanel";
import { ConversationsView } from "./components/ConversationsView";
import {
  IconBolt,
  IconCpu,
  IconMoon,
  IconMoreHorizontal,
  IconRefresh,
  IconSettings,
  IconSun,
  IconTerminal,
  IconWarning,
} from "./components/Icons";
import { approvals } from "./lib/approvals";
import { setAutoApprove } from "./lib/session";
import { theme, toggleTheme } from "./lib/theme";
import { api, type LLMConfig } from "./lib/api";
import { tabs } from "./lib/tabs";

type ModalKind = null | { view: "settings"; tab: SettingsTab } | "provider" | "models" | "keys";

export function App() {
  const [modal, setModal] = createSignal<ModalKind>(null);
  const [llm, setLlm] = createSignal<LLMConfig | null>(null);
  const [llmErr, setLlmErr] = createSignal("");
  const [termOpen, setTermOpen] = createSignal(localStorage.getItem("kogniterm-v3-term") !== "0");
  const [termW, setTermW] = createSignal<number | null>(Number(localStorage.getItem("kogniterm-v3-term-w") ?? 44));
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
      setLlmErr(`Backend no disponible (${e})`);
    }
  }

  onMount(() => {
    void refreshLLM();

    const onKeyDown = (e: KeyboardEvent) => {
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
    };
    window.addEventListener("keydown", onKeyDown);
    onCleanup(() => window.removeEventListener("keydown", onKeyDown));
  });

  function startResize(e: PointerEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startW = termW() ?? 44;
    const move = (ev: PointerEvent) => {
      const delta = startX - ev.clientX;
      const next = Math.min(82, Math.max(22, startW + (delta / window.innerWidth) * 100));
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

  const shortModel = () => {
    const m = llm()?.model ?? "";
    if (!m) return "";
    return m.includes("/") ? m.split("/").pop()! : m;
  };

  return (
    <div class="h-screen w-screen flex flex-col bg-[var(--kt-bg-app)] text-[var(--kt-text-primary)]">
      {/* Topbar */}
      <header class="glass-header z-30 flex items-center gap-2 pl-2 pr-3 py-1.5 transition-colors select-none shrink-0">
        <div class="flex-1 min-w-0">
          <TabBar
            view={view()}
            onToggleView={() => setViewPersist(view() === "chat" ? "conversations" : "chat")}
            onShowChat={() => setViewPersist("chat")}
          />
        </div>

        <div class="flex items-center gap-1.5 shrink-0">
          <PendingBadge tabId={tabs.store.activeId} />

          {/* Estado del backend o modelo activo */}
          <Show
            when={!llmErr()}
            fallback={
              <button
                onClick={() => setModal({ view: "settings", tab: "connection" })}
                title={`${llmErr()} — Clic para configurar conexión`}
                class="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-[11.5px] font-medium bg-red-500/15 text-red-300 border border-red-500/25 hover:bg-red-500/25 transition-all"
              >
                <IconWarning size={13} />
                <span>Backend offline</span>
              </button>
            }
          >
            <Show when={shortModel()}>
              <button
                onClick={() => setModal({ view: "settings", tab: "models" })}
                title={`Proveedor: ${llm()?.provider} · Modelo: ${llm()?.model} (Ctrl+M)`}
                class="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-[11.5px] font-mono text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] border border-[var(--kt-border-subtle)] transition-all max-w-[190px]"
              >
                <IconCpu size={12} class="shrink-0 opacity-75" />
                <span class="truncate">{shortModel()}</span>
              </button>
            </Show>
          </Show>

          {/* Auto-aprobación */}
          <button
            class={`flex items-center gap-1.5 text-[12px] px-2.5 py-1 rounded-xl font-medium transition-all duration-150 active:scale-95 border ${
              approvals.isAuto(tabs.store.activeId)
                ? "bg-amber-500/15 text-amber-300 border-amber-500/35 shadow-[0_0_12px_rgba(245,158,11,0.2)]"
                : "bg-transparent border-transparent text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)]"
            }`}
            title={
              approvals.isAuto(tabs.store.activeId)
                ? "Auto-aprobación ACTIVA en esta pestaña: comandos y ediciones se ejecutan sin preguntar. Clic para desactivar."
                : "Activar auto-aprobación en esta pestaña: no pedirá confirmación."
            }
            onClick={() => setAutoApprove(tabs.store.activeId, !approvals.isAuto(tabs.store.activeId))}
          >
            <IconBolt size={13} />
            <span class="hidden sm:inline">{approvals.isAuto(tabs.store.activeId) ? "Auto ON" : "Auto"}</span>
          </button>

          {/* Toggle directo de Terminal lateral */}
          <button
            class={`w-8 h-7 flex items-center justify-center rounded-xl transition-all duration-150 active:scale-95 border ${
              termOpen()
                ? "bg-[var(--kt-bg-active)] text-[var(--kt-text-primary)] border-[var(--kt-border-default)]"
                : "border-transparent text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)]"
            }`}
            onClick={toggleTerm}
            title="Mostrar/ocultar terminal lateral (Ctrl+`)"
          >
            <IconTerminal size={14} />
          </button>

          {/* Tema claro/oscuro */}
          <button
            class="w-8 h-7 flex items-center justify-center rounded-xl text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all duration-150 active:scale-90"
            onClick={toggleTheme}
            title={theme() === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
          >
            {theme() === "dark" ? <IconSun size={14} /> : <IconMoon size={14} />}
          </button>

          {/* Ajustes directos */}
          <button
            class="w-8 h-7 flex items-center justify-center rounded-xl text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all duration-150 active:scale-90"
            onClick={() => setModal({ view: "settings", tab: "provider" })}
            title="Ajustes del sistema (Ctrl+,)"
          >
            <IconSettings size={14} />
          </button>

          {/* Menú adicional */}
          <div class="relative">
            <button
              class={`w-8 h-7 flex items-center justify-center rounded-xl transition-all active:scale-95 ${
                menuOpen()
                  ? "bg-[var(--kt-bg-active)] text-[var(--kt-text-primary)]"
                  : "text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)]"
              }`}
              onClick={() => setMenuOpen((v) => !v)}
              title="Más opciones"
              aria-haspopup="menu"
              aria-expanded={menuOpen()}
            >
              <IconMoreHorizontal size={15} />
            </button>
            <Show when={menuOpen()}>
              <div class="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
              <div
                role="menu"
                class="absolute right-0 top-9 z-50 w-56 rounded-2xl glass-dropdown p-1.5 animate-scale-in"
              >
                <button
                  role="menuitem"
                  class="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-[12.5px] text-[var(--kt-text-secondary)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all text-left"
                  onClick={() => {
                    toggleTerm();
                    setMenuOpen(false);
                  }}
                >
                  <IconTerminal size={14} class="text-[var(--kt-text-muted)]" />
                  <span class="flex-1">Terminal lateral</span>
                  <span class="kt-kbd">{termOpen() ? "ON" : "Ctrl+`"}</span>
                </button>
                <button
                  role="menuitem"
                  class="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-[12.5px] text-[var(--kt-text-secondary)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all text-left"
                  onClick={() => {
                    setModal({ view: "settings", tab: "provider" });
                    setMenuOpen(false);
                  }}
                >
                  <IconSettings size={14} class="text-[var(--kt-text-muted)]" />
                  <span class="flex-1">Ajustes</span>
                  <span class="kt-kbd">Ctrl+,</span>
                </button>
                <div class="my-1 h-px bg-[var(--kt-border-subtle)]" />
                <button
                  role="menuitem"
                  class="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-[12.5px] text-[var(--kt-text-secondary)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all text-left"
                  onClick={() => {
                    void refreshLLM();
                    setMenuOpen(false);
                  }}
                >
                  <IconRefresh size={14} class="text-[var(--kt-text-muted)]" />
                  <span class="flex-1">Recargar config LLM</span>
                </button>
              </div>
            </Show>
          </div>
        </div>
      </header>

      <Show
        when={view() === "chat"}
        fallback={<ConversationsView onOpenChat={() => setViewPersist("chat")} />}
      >
        <div class="flex-1 min-h-0 flex relative overflow-hidden">
          <div class="flex-1 min-w-0 h-full">
            <Show when={tabs.store.activeId} keyed>
              {(activeId) => (
                <ChatView
                  tabId={activeId}
                  onOpenSettings={(t) => setModal({ view: "settings", tab: t })}
                  onToggleTerm={toggleTerm}
                />
              )}
            </Show>
          </div>
          <Show when={termOpen()}>
            <div
              class="w-1.5 cursor-col-resize flex-none bg-transparent hover:bg-[var(--kt-bg-hover)] transition-colors duration-150 z-10 relative flex items-center justify-center group border-l border-[var(--kt-border-subtle)]"
              onPointerDown={startResize}
              title="Arrastra para redimensionar la terminal"
            >
              <div class="w-0.5 h-8 rounded-full bg-[var(--kt-border-default)] group-hover:bg-[var(--kt-text-muted)] group-hover:h-14 transition-all duration-200" />
            </div>
            <div class="flex-none h-full" style={{ width: `${termW() ?? 44}%` }}>
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

      {/* Aprobaciones, preguntas y contraseñas del agente */}
      <ApprovalDialog tabId={tabs.store.activeId} />
      <QuestionDialog tabId={tabs.store.activeId} />
      <PasswordDialog tabId={tabs.store.activeId} />
    </div>
  );
}
