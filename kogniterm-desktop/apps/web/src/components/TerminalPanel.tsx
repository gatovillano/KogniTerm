import { createSignal, onCleanup, onMount, Show } from "solid-js";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { ptyApi, ptyIdForTab, ptyWsUrl } from "../lib/pty";
import { api } from "../lib/api";
import { tabs } from "../lib/tabs";
import { copyTerminalToClipboard, setupTerminalCopyHandlers } from "../lib/terminal-clipboard";
import { IconCheck, IconClose, IconCopy, IconRefresh, IconTerminal } from "./Icons";

interface TermHandle {
  term: Terminal;
  fit: FitAddon;
  ws: WebSocket | null;
  ptyId: string;
  cwd: string | undefined;
  status: (s: string) => void;
}

const handles = new Map<string, TermHandle>();

/** Sidebar derecho: shell interactivo real por pestaña. */
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
        handle.term.write("\r\n\x1b[33m[terminal desconectada — pulsa reconectar]\x1b[0m\r\n");
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
        fontFamily: '"JetBrains Mono", "Fira Code", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        cursorBlink: true,
        scrollback: 5000,
        theme: {
          background: "#08080a",
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
    const knownDir = tabs.store.tabs.find((t) => t.id === props.tabId)?.workspaceDir;
    if (knownDir && !h.cwd) {
      h.cwd = knownDir;
      setCwd(knownDir);
    }

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
    <div class="flex flex-col h-full bg-[#08080a]">
      {/* Cabecera oscura consistente con la consola */}
      <div class="flex items-center gap-2 px-3.5 py-2 bg-[#101014] border-b border-white/[0.06] text-[12px] select-none shrink-0">
        <div class="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.05] border border-white/[0.06]">
          <span
            class={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
              status() === "conectado"
                ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]"
                : status() === "conectando…"
                  ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.7)]"
                  : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.7)]"
            }`}
          />
          <IconTerminal size={11} class="text-zinc-400" />
          <span class="text-zinc-300 font-mono text-[11px]">pty</span>
        </div>

        <span class="text-zinc-400 font-mono text-[11px] truncate max-w-[200px]" title={cwd() ?? ptyId()}>
          {cwd() ?? ptyId()}
        </span>

        <div class="flex-1" />

        <button
          class={`h-6 px-2.5 rounded-full flex items-center gap-1.5 transition-all text-[11px] font-medium ${
            copied()
              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
              : "text-zinc-400 hover:text-white bg-white/[0.04] hover:bg-white/[0.1]"
          }`}
          onClick={handleCopy}
          onMouseDown={(e) => e.preventDefault()}
          title={copied() ? "¡Copiado!" : "Copiar contenido de la terminal (o selección actual)"}
        >
          <Show when={copied()} fallback={<IconCopy size={11} />}>
            <IconCheck size={11} class="text-emerald-400" />
          </Show>
          <span>{copied() ? "Copiado" : "Copiar"}</span>
        </button>

        <button
          class="w-6 h-6 rounded-full flex items-center justify-center text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-all"
          onClick={reconnect}
          title="Reconectar al mismo shell"
        >
          <IconRefresh size={12} />
        </button>
        <button
          class="w-6 h-6 rounded-full flex items-center justify-center text-zinc-400 hover:text-red-300 hover:bg-red-500/15 transition-all"
          onClick={restart}
          title="Matar shell y empezar uno nuevo"
        >
          <IconClose size={12} />
        </button>
      </div>

      <div ref={hostRef} class="flex-1 min-h-0 px-2.5 py-2 select-text" />

      <Show when={status() !== "conectado"}>
        <div class="p-3 flex justify-center border-t border-white/[0.06] bg-[#0e0e12]">
          <button
            onClick={reconnect}
            class="flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-white/[0.08] hover:bg-white/[0.14] border border-white/[0.1] text-[12px] text-white font-medium transition-all active:scale-95 shadow-sm"
          >
            <IconRefresh size={12} />
            <span>Reconectar terminal ({status()})</span>
          </button>
        </div>
      </Show>
    </div>
  );
}
