import { Match, Switch, createSignal, onCleanup } from "solid-js";
import { ChatMsg, isTerminalTool } from "../lib/tabs";

interface ToolIndicatorProps {
  message: ChatMsg;
  /** La pestaña sigue operando (streaming/terminal/herramientas activas). */
  operating?: boolean;
}

/** Frames del spinner cuadrado (cuadrantes rotando), mismo ritmo que la TUI (120ms). */
const SQUARE_FRAMES = ["▖", "▘", "▝", "▗"];

function SquareSpinner() {
  const [frame, setFrame] = createSignal(0);
  const timer = setInterval(() => setFrame((f) => (f + 1) % SQUARE_FRAMES.length), 120);
  onCleanup(() => clearInterval(timer));
  return <span class="shrink-0 font-mono text-[13px] leading-none text-amber-300">{SQUARE_FRAMES[frame()]}</span>;
}

export function ToolIndicator(props: ToolIndicatorProps) {
  const toolName = () => {
    if (props.message.toolName) return props.message.toolName;
    const txt = props.message.text || "";
    if (txt.startsWith("▶ ")) return txt.slice(2).trim().split(/\s+/)[0] || "herramienta";
    if (txt.startsWith("⚙ ")) return txt.slice(2).trim().split(/[(\s]/)[0] || "herramienta";
    if (txt.startsWith("· ")) return "actividad";
    return "herramienta";
  };

  // EXCEPCIÓN: execute_command y comandos de terminal usan AgentTerminal exclusivamente
  if (isTerminalTool(props.message.toolName || toolName())) {
    return null;
  }

  const toolCategory = () => {
    const name = toolName().toLowerCase();
    if (
      name.includes("read") ||
      name.includes("view") ||
      name.includes("cat") ||
      name.includes("head") ||
      name.includes("list_dir") ||
      name.includes("search_file")
    ) {
      return "read";
    }
    if (
      name.includes("write") ||
      name.includes("edit") ||
      name.includes("replace") ||
      name.includes("patch") ||
      name.includes("update_file")
    ) {
      return "edit";
    }
    if (
      name.includes("search") ||
      name.includes("web") ||
      name.includes("fetch") ||
      name.includes("url") ||
      name.includes("browse")
    ) {
      return "web";
    }
    if (name === "ejecutando" || name === "actividad" || name === "spinner") {
      return "activity";
    }
    return "default";
  };

  const action = () => {
    if (props.message.toolDescription) return String(props.message.toolDescription);
    if (props.message.toolCommand) return String(props.message.toolCommand);
    if (typeof props.message.toolArgs === "object" && props.message.toolArgs !== null) {
      const a = props.message.toolArgs as Record<string, any>;
      if (a.command) return String(a.command);
      if (a.file_path || a.path || a.target_path) return String(a.file_path || a.path || a.target_path);
      if (a.query) return String(a.query);
      if (a.url) return String(a.url);
    }
    const txt = props.message.text || "";
    if (txt.startsWith("▶ ")) return txt.slice(2).trim();
    if (txt.startsWith("· ")) return txt.slice(2).trim();
    return "";
  };

  const title = () => {
    const a = action();
    return a ? `${toolName()} · ${a}` : toolName();
  };

  const isRunning = () => (props.message.toolStatus || "completed") === "running";
  /** Solo gira si la herramienta sigue marcada en ejecución Y la pestaña sigue operando.
   *  Si el backend no cerró la herramienta pero la ejecución ya terminó, se muestra el ícono. */
  const showSpinner = () => isRunning() && props.operating !== false;

  return (
    <div class="my-1 flex items-center gap-2 text-[12px] select-text" title={title()}>
      <Switch fallback={
        <svg class="w-3.5 h-3.5 shrink-0 text-zinc-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      }>
        <Match when={showSpinner()}>
          <SquareSpinner />
        </Match>
        <Match when={toolCategory() === "read"}>
          <svg class="w-3.5 h-3.5 shrink-0 text-sky-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
        </Match>
        <Match when={toolCategory() === "edit"}>
          <svg class="w-3.5 h-3.5 shrink-0 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
        </Match>
        <Match when={toolCategory() === "web"}>
          <svg class="w-3.5 h-3.5 shrink-0 text-violet-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="2" y1="12" x2="22" y2="12" />
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
          </svg>
        </Match>
        <Match when={toolCategory() === "activity"}>
          <span class="shrink-0 text-[12px] text-amber-300 animate-spin">◈</span>
        </Match>
      </Switch>
      <span class="min-w-0 truncate font-mono text-zinc-400">{title()}</span>
    </div>
  );
}
