import { createSignal, onCleanup, onMount, Show } from "solid-js";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { ptyApi, ptyIdForTab, ptyWsUrl } from "../lib/pty";
import { api } from "../lib/api";

interface TermHandle {
  term: Terminal;
  fit: FitAddon;
  ws: WebSocket | null;
  ptyId: string;
  cwd: string | undefined;
  status: (s: string) => void;
}

const handles = new Map<string, TermHandle>();

/** Sidebar derecho: shell interactivo real por pestaña (passwords, flechas, Ctrl+C todo nativo). */
export function TerminalPanel(props: { tabId: string }) {
  let hostRef: HTMLDivElement | undefined;
  const [status, setStatus] = createSignal("conectando…");
  const [cwd, setCwd] = createSignal<string | undefined>();
  const ptyId = () => ptyIdForTab(props.tabId);

  function connect(handle: TermHandle) {
    const id = handle.ptyId;
    try {
      // `directory` solo aplica al auto-crear el PTY (si ya existe, reengancha el mismo shell)
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
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        cursorBlink: true,
        scrollback: 5000,
        theme: {
          background: "#0d1117",
          foreground: "#e6edf3",
          cursor: "#58a6ff",
          selectionBackground: "#264f78",
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

    // resolver workspace de la sesión antes del primer connect
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

    const ro = new ResizeObserver(() => {
      try {
        h.fit.fit();
        const dims = h.fit.proposeDimensions();
        if (dims && h.ws?.readyState === WebSocket.OPEN) void ptyApi.resize(h.ptyId, dims.cols, dims.rows);
      } catch {}
    });
    ro.observe(hostRef!);
    onCleanup(() => ro.disconnect());
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
    <div class="flex flex-col h-full bg-[#0d1117] border-l border-[#21262d]">
      <div class="flex items-center gap-2 px-3 py-1.5 border-b border-[#21262d] text-[12px]">
        <span class="text-[#8b949e] font-mono">terminal</span>
        <span
          class={`w-1.5 h-1.5 rounded-full ${status() === "conectado" ? "bg-emerald-400" : status() === "conectando…" ? "bg-amber-400" : "bg-red-400"}`}
        />
        <span class="text-[#6e7681] font-mono truncate" title={cwd() ?? ptyId()}>
          {cwd() ?? ptyId()}
        </span>
        <div class="flex-1" />
        <button class="text-[#8b949e] hover:text-white px-1" onClick={reconnect} title="Reconectar al mismo shell">
          ↻
        </button>
        <button class="text-[#8b949e] hover:text-red-300 px-1" onClick={restart} title="Matar shell y empezar uno nuevo">
          ✕
        </button>
      </div>
      <div ref={hostRef} class="flex-1 min-h-0 px-1" />
      <Show when={status() !== "conectado"}>
        <button onClick={reconnect} class="m-2 px-3 py-1.5 rounded-md bg-[#21262d] hover:bg-[#30363d] text-[12px] text-white">
          Reconectar terminal ({status()})
        </button>
      </Show>
    </div>
  );
}
