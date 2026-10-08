import { createSignal, onCleanup } from "solid-js";
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
    <div class="my-1 flex items-center gap-2 text-[12px] select-text text-zinc-400" title={title()}>
      <span class="shrink-0 text-zinc-500">
        {showSpinner() ? (
          <SquareSpinner />
        ) : (
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M9 5l7 7-7 7" />
          </svg>
        )}
      </span>
      <span class="min-w-0 truncate font-mono">{title()}</span>
    </div>
  );
}
