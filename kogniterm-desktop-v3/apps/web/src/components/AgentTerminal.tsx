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
 * Muestra los snapshots acumulados de `terminal_output` con render ANSI real
 * y envía teclas al worker mediante `terminal_input`, sin tocar el PTY lateral.
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
      scroller.scrollTo({ top: scroller.scrollHeight });
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
      // La PTY del worker usa 80 columnas por defecto; no reducir por debajo.
      if (dims) term.resize(Math.max(80, dims.cols), 16);
    } catch {
      /* El tamaño falló una vez; no debe romper la ejecución. */
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
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
      theme: {
        background: "#000000",
        foreground: "#e6edf3",
        cursor: "#58a6ff",
        selectionBackground: "#264f78",
      },
    });
    fit = new FitAddon();
    term.loadAddon(fit);
    term.open(hostRef!);
    fitTerminal();
    term.onData((data) => {
      if (props.active) props.onInput(data);
    });
    // El efecto siguiente aplica el snapshot inicial y los cambios posteriores.

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
      } catch {
        /* El foco es una mejora; no debe fallar la terminal. */
      }
    } else if (!interactive) {
      wasInteractive = false;
    }
  });

  return (
    <div class="w-full overflow-hidden rounded-lg border border-[#30363d] bg-black">
      <div class="flex items-center gap-2 border-b border-[#21262d] bg-[#0d1117] px-3 py-1.5 text-[12px]">
        <span
          class={`h-1.5 w-1.5 rounded-full ${
            props.active ? "bg-emerald-400" : "bg-[#6e7681]"
          }`}
        />
        <span class="font-mono text-[#8b949e]">terminal del agente</span>
        <span class="truncate font-mono text-[#e6edf3]" title={displayCommand()}>
          $ {displayCommand()}
        </span>
        <div class="flex-1" />
        <Show when={props.active && props.interactive}>
          <span class="rounded bg-amber-500/20 px-1.5 py-0.5 text-[11px] text-amber-200">
            interactiva: escribe aquí
          </span>
        </Show>
        <Show when={props.active && !props.interactive}>
          <span class="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[11px] text-emerald-200">
            ejecutando
          </span>
        </Show>
        <Show when={!props.active}>
          <span class="text-[11px] text-[#6e7681]">finalizada</span>
        </Show>
      </div>
      <div ref={hostRef} class="h-56 w-full" />
      <div class="flex items-center gap-2 border-t border-[#21262d] bg-[#0d1117] px-3 py-1 text-[11px] text-[#6e7681]">
        <Show
          when={props.active}
          fallback={<span>Salida completa de la ejecución del agente vinculada a este comando.</span>}
        >
          <span>Las teclas van a la ejecución actual: contraseñas, confirmaciones, flechas y Ctrl+C.</span>
          <div class="flex-1" />
          <button
            class="rounded border border-[#30363d] px-2 py-0.5 text-[#8b949e] hover:text-white"
            title="Enviar Ctrl+C a la ejecución actual"
            onClick={() => props.onInput("\x03")}
          >
            Ctrl+C
          </button>
        </Show>
      </div>
    </div>
  );
}
