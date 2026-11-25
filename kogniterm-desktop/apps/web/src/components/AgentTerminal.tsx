import { createEffect, createSignal, onCleanup, onMount, Show } from "solid-js";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { copyTerminalToClipboard, setupTerminalCopyHandlers } from "../lib/terminal-clipboard";
import { getXtermTheme, theme } from "../lib/theme";
import { IconCheck, IconCopy } from "./Icons";

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
 */
export function AgentTerminal(props: AgentTerminalProps) {
  let hostRef: HTMLDivElement | undefined;
  let term: Terminal | undefined;
  let fit: FitAddon | undefined;
  let applied = "";
  let renderedId = props.terminalId;
  let wasInteractive = false;
  const [copied, setCopied] = createSignal(false);

  async function handleCopy() {
    const ok = await copyTerminalToClipboard(term, props.output);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

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
      fontFamily: '"JetBrains Mono", "Fira Code", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
      theme: getXtermTheme(theme()),
    });
    fit = new FitAddon();
    term.loadAddon(fit);
    term.open(hostRef!);
    fitTerminal();
    term.onData((data) => {
      if (props.active) props.onInput(data);
    });

    const cleanupCopy = setupTerminalCopyHandlers(term, hostRef);

    const observer = new ResizeObserver(() => fitTerminal());
    if (hostRef) observer.observe(hostRef);
    onCleanup(() => {
      cleanupCopy();
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

  createEffect(() => {
    const t = theme();
    if (term) term.options.theme = getXtermTheme(t);
  });

  return (
    <div class="w-full overflow-hidden rounded-2xl bg-[var(--kt-bg-terminal)] border border-[var(--kt-border-default)] shadow-[var(--kt-shadow-md)] transition-all">
      {/* Cabecera */}
      <div class="flex items-center gap-2.5 bg-[var(--kt-bg-terminal-header)] border-b border-[var(--kt-border-subtle)] px-3.5 py-2 text-[12px] select-none">
        <div class="flex items-center gap-1.5 mr-1">
          <span class="w-2.5 h-2.5 rounded-full bg-red-500/75" />
          <span class="w-2.5 h-2.5 rounded-full bg-amber-500/75" />
          <span class="w-2.5 h-2.5 rounded-full bg-emerald-500/75" />
        </div>

        <span class="truncate font-mono text-[var(--kt-text-primary)] text-[11.5px] max-w-md" title={displayCommand()}>
          <span class="text-[var(--kt-text-faint)] mr-1.5">$</span>
          {displayCommand()}
        </span>

        <div class="flex-1" />

        <Show when={props.active && props.interactive}>
          <span class="rounded-full bg-amber-500/20 border border-amber-500/30 px-2.5 py-0.5 text-[10.5px] font-medium text-amber-200 animate-pulse">
            interactiva
          </span>
        </Show>
        <Show when={props.active && !props.interactive}>
          <span class="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/25 px-2.5 py-0.5 text-[10.5px] font-medium text-emerald-300">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            ejecutando
          </span>
        </Show>
        <Show when={!props.active}>
          <span class="rounded-full bg-[var(--kt-bg-hover)] px-2.5 py-0.5 text-[10.5px] text-[var(--kt-text-muted)]">
            finalizada
          </span>
        </Show>

        <button
          class={`h-6 px-2.5 rounded-full flex items-center gap-1.5 transition-all text-[11px] font-medium ml-1 ${
            copied()
              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
              : "text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)]"
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
      </div>

      <div ref={hostRef} class="px-2.5 py-2 select-text" />
    </div>
  );
}
