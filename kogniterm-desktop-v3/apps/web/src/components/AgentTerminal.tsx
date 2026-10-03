import { createEffect, onCleanup, onMount, Show } from "solid-js";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";

interface AgentTerminalProps {
  tabId: string;
  terminalId: string;
  tool?: string;
  command?: string;
  output?: string;
  active?: boolean;
  interactive?: boolean;
  onInput: (text: string) => void;
}

/**
 * Terminal inline vinculada a la ejecución worker del agente.
 * Diseño minimalista con tarjeta curvada, barra de título elegante y sin bordes toscos.
 */
export function AgentTerminal(props: AgentTerminalProps) {
  let hostRef: HTMLDivElement | undefined;
  let term: Terminal | undefined;
  let fit: FitAddon | undefined;
  let applied = "";
  let renderedId = props.terminalId;
  let wasInteractive = false;

  const displayCommand = () =>
    props.command && props.command !== "execute_command" ? props.command : (props.tool ?? "bash");

  function scrollChatIfFollowing() {
    const scroller = hostRef?.closest("[data-chat-scroll]") as HTMLElement | null;
    if (!scroller) return;
    const distanceFromBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
    if (distanceFromBottom < 140) {
      scroller.scrollTo({ top: scroller.scrollHeight, behavior: "smooth" });
    }
  }

  function writeSnapshot(snapshot: string, followChat = true) {
    if (!term) return;
    if (snapshot === applied) return;
    const finish = () => {
      applied = snapshot;
      if (followChat) scrollChatIfFollowing();
    };
    if (applied && snapshot.startsWith(applied)) {
      term.write(snapshot.slice(applied.length), finish);
    } else {
      term.clear();
      if (snapshot) {
        term.write(snapshot, finish);
      } else {
        finish();
      }
    }
  }

  function fitTerminal() {
    if (!term || !fit) return;
    try {
      fit.fit();
      const dims = fit.proposeDimensions();
      if (dims) term.resize(Math.max(80, dims.cols), 16);
    } catch {
      /* Fallback si el cálculo de dimensiones falla temporalmente */
    }
  }

  onMount(() => {
    term = new Terminal({
      cols: 80,
      rows: 16,
      scrollback: 2000,
      cursorBlink: true,
      convertEol: true,
      fontSize: 12,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
      theme: {
        background: "#05070d",
        foreground: "#f1f5f9",
        cursor: "#60a5fa",
        selectionBackground: "#2563eb44",
      },
    });
    fit = new FitAddon();
    term.loadAddon(fit);
    term.open(hostRef!);
    fitTerminal();
    term.onData((data) => {
      if (props.active) props.onInput(data);
    });

    const observer = new ResizeObserver(() => fitTerminal());
    if (hostRef) observer.observe(hostRef);
    onCleanup(() => {
      observer.disconnect();
      term?.dispose();
      term = undefined;
      applied = "";
    });
  });

  createEffect(() => {
    if (props.terminalId !== renderedId) {
      renderedId = props.terminalId;
      applied = "";
      term?.clear();
    }
    writeSnapshot(props.output ?? "");
  });

  createEffect(() => {
    const active = Boolean(props.active);
    if (term) term.options.disableStdin = !active;
    const interactive = Boolean(props.interactive && active);
    if (interactive && !wasInteractive) {
      wasInteractive = true;
      try {
        term?.focus();
      } catch {}
    } else if (!interactive) {
      wasInteractive = false;
    }
  });

  return (
    <div class="w-full overflow-hidden rounded-2xl bg-[#05070d] shadow-[0_8px_32px_rgba(0,0,0,0.55)] transition-all">
      {/* Cabecera estilizada con dots y comandos */}
      <div class="flex items-center gap-2.5 bg-[#0b0f19] px-4 py-2 text-[12px] select-none">
        <div class="flex items-center gap-1.5 mr-1">
          <span class="w-2.5 h-2.5 rounded-full bg-red-500/80" />
          <span class="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
          <span class="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
        </div>
        
        <span class="text-[11px] font-mono text-slate-400">terminal</span>
        <span class="truncate font-mono text-slate-200 text-[11.5px] max-w-sm" title={displayCommand()}>
          $ {displayCommand()}
        </span>

        <div class="flex-1" />

        <Show when={props.active && props.interactive}>
          <span class="rounded-full bg-amber-500/20 px-2.5 py-0.5 text-[10.5px] font-medium text-amber-200 animate-pulse">
            interactiva: escribe aquí
          </span>
        </Show>
        <Show when={props.active && !props.interactive}>
          <span class="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-[10.5px] font-medium text-emerald-300">
            ejecutando
          </span>
        </Show>
        <Show when={!props.active}>
          <span class="rounded-full bg-white/[0.05] px-2.5 py-0.5 text-[10.5px] text-slate-400">
            finalizada
          </span>
        </Show>
      </div>

      <div ref={hostRef} class="h-56 w-full px-2 py-1" />

      {/* Pie de terminal */}
      <div class="flex items-center gap-2 bg-[#0b0f19] px-4 py-1.5 text-[11px] text-slate-400 select-none">
        <Show
          when={props.active}
          fallback={<span>Salida de ejecución vinculada al proceso del agente.</span>}
        >
          <span>Envío interactivo activo: flechas, contraseñas y Ctrl+C.</span>
          <div class="flex-1" />
          <button
            class="rounded-full bg-white/[0.08] hover:bg-white/[0.14] px-2.5 py-0.5 text-[11px] font-mono text-slate-200 hover:text-white transition-all active:scale-95"
            title="Enviar señal Ctrl+C (interrumpir)"
            onClick={() => props.onInput("\x03")}
          >
            Ctrl+C
          </button>
        </Show>
      </div>
    </div>
  );
}
