import { createSignal, onCleanup, onMount, Show } from "solid-js";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { ptyApi, ptyIdForTab, ptyWsUrl } from "../lib/pty";
import { api } from "../lib/api";
import { copyTerminalToClipboard, setupTerminalCopyHandlers } from "../lib/terminal-clipboard";

interface TermHandle {
  term: Terminal;
  fit: FitAddon;
  ws: WebSocket | null;
  ptyId: string;
  cwd: string | undefined;
  status: (s: string) => void;
}

const handles = new Map<string, TermHandle>();

/** Sidebar derecho: shell interactivo real por pestaña con diseño moderno y sin bordes. */
export function TerminalPanel(props: { tabId: string }) {
  let hostRef: HTMLDivElement | undefined;
  const [status, setStatus] = createSignal("conectando…");
  const [cwd, setCwd] = createSignal<string | undefined>();
  const [copied, setCopied] = createSignal(false);
  const ptyId = () => ptyIdForTab(props.tabId);

  async function handleCopy() {
    const h = handles.get(props.tabId);
    const ok = await copyTerminalToClipboard(h?.term);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  function connect(handle: TermHandle) {
    const id = handle.ptyId;
    try {
      const ws = new WebSocket(ptyWsUrl(id, handle.cwd));
      handle.ws = ws;
      setStatus("conectando…");
      ws.onopen = () => {
        setStatus("conectado");
        const dims = handle.fit.proposeDimensions();
        if (dims) void ptyApi.resize(id, dims.cols, dims.rows);
      };
      ws.onmessage = (ev) => {
        if (typeof ev.data === "string") handle.term.write(ev.data);
      };
      ws.onclose = () => {
        setStatus("desconectado");
        handle.term.write("\r\n\x1b[33m[terminal desconectada — pulsa ↻ para reconectar]\x1b[0m\r\n");
      };
      ws.onerror = () => setStatus("error");
    } catch {
      setStatus("error");
    }
  }

  onMount(() => {
    let handle = handles.get(props.tabId);
    if (!handle) {
      const term = new Terminal({
        fontSize: 12.5,
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        cursorBlink: true,
        scrollback: 5000,
        theme: {
          background: "#090a0f",
          foreground: "#f4f4f5",
          cursor: "#e4e4e7",
          selectionBackground: "rgba(255, 255, 255, 0.28)",
        },
      });
      const fit = new FitAddon();
      term.loadAddon(fit);
      handle = { term, fit, ws: null, ptyId: ptyId(), cwd: undefined, status: setStatus };
      handles.set(props.tabId, handle);
      term.onData((data) => {
        const ws = handles.get(props.tabId)?.ws;
        if (ws && ws.readyState === WebSocket.OPEN) ws.send(data);
      });
    }
    const h = handle;

    void api
      .workspaceStatus(props.tabId)
      .then((s) => {
        if (s?.path) {
          h.cwd = s.path;
          setCwd(s.path);
        }
      })
      .catch(() => {})
      .finally(() => {
        h.term.open(hostRef!);
        queueMicrotask(() => {
          try {
            h.fit.fit();
          } catch {}
        });
        if (!h.ws || h.ws.readyState === WebSocket.CLOSED) connect(h);
      });

    const cleanupCopy = setupTerminalCopyHandlers(h.term, hostRef);

    const ro = new ResizeObserver(() => {
      try {
        h.fit.fit();
        const dims = h.fit.proposeDimensions();
        if (dims && h.ws?.readyState === WebSocket.OPEN) void ptyApi.resize(h.ptyId, dims.cols, dims.rows);
      } catch {}
    });
    ro.observe(hostRef!);
    onCleanup(() => {
      cleanupCopy();
      ro.disconnect();
    });
  });

  async function reconnect() {
    const h = handles.get(props.tabId);
    if (!h) return;
    try {
      h.ws?.close();
    } catch {}
    h.ws = null;
    h.term.write("\r\n\x1b[36m[reconectando…]\x1b[0m\r\n");
    connect(h);
  }

  async function restart() {
    const h = handles.get(props.tabId);
    if (!h) return;
    try {
      h.ws?.close();
    } catch {}
    h.ws = null;
    await ptyApi.kill(h.ptyId);
    h.term.clear();
    connect(h);
  }

  return (
    <div class="flex flex-col h-full bg-[#080b11]">
      {/* Cabecera minimalista sin bordes */}
      <div class="flex items-center gap-2.5 px-4 py-2 bg-white/[0.02] text-[12px] select-none">
        <div class="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.04]">
          <span
            class={`w-2 h-2 rounded-full transition-all duration-300 ${
              status() === "conectado"
                ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]"
                : status() === "conectando…"
                  ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.7)]"
                  : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.7)]"
            }`}
          />
          <span class="text-slate-300 font-mono text-[11px]">pty</span>
        </div>

        <span class="text-slate-400 font-mono text-[11px] truncate max-w-[180px]" title={cwd() ?? ptyId()}>
          {cwd() ?? ptyId()}
        </span>

        <div class="flex-1" />

        <button
          class={`h-6 px-2.5 rounded-full flex items-center gap-1.5 transition-all text-[11px] font-medium ${
            copied()
              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
              : "text-slate-400 hover:text-white hover:bg-white/[0.08]"
          }`}
          onClick={handleCopy}
          onMouseDown={(e) => e.preventDefault()}
          title={copied() ? "¡Copiado!" : "Copiar contenido de la terminal (o selección actual)"}
        >
          {copied() ? (
            <>
              <svg class="w-3 h-3 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span>Copiado</span>
            </>
          ) : (
            <>
              <svg class="w-3 h-3 opacity-70" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
              <span>Copiar</span>
            </>
          )}
        </button>

        <button
          class="w-6 h-6 rounded-full flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/[0.08] transition-all"
          onClick={reconnect}
          title="Reconectar al mismo shell"
        >
          ↻
        </button>
        <button
          class="w-6 h-6 rounded-full flex items-center justify-center text-slate-400 hover:text-red-300 hover:bg-red-500/10 transition-all text-[11px]"
          onClick={restart}
          title="Matar shell y empezar uno nuevo"
        >
          ✕
        </button>
      </div>

      <div ref={hostRef} class="flex-1 min-h-0 px-2 py-1 select-text" />

      <Show when={status() !== "conectado"}>
        <div class="p-3 flex justify-center">
          <button
            onClick={reconnect}
            class="px-4 py-1.5 rounded-full bg-white/[0.08] hover:bg-white/[0.14] text-[12px] text-white font-medium transition-all active:scale-95 shadow-sm"
          >
            Reconectar terminal ({status()})
          </button>
        </div>
      </Show>
    </div>
  );
}
