import { Show, createSignal, onCleanup } from "solid-js";
import { ChatMsg, isTerminalTool } from "../lib/tabs";
import { IconCheck, IconClose } from "./Icons";

interface ToolIndicatorProps {
  message: ChatMsg;
  /** La pestaña sigue operando (streaming/terminal/herramientas activas). */
  operating?: boolean;
}

const SQUARE_FRAMES = ["▖", "▘", "▝", "▗"];

function SquareSpinner() {
  const [frame, setFrame] = createSignal(0);
  const timer = setInterval(() => setFrame((f) => (f + 1) % SQUARE_FRAMES.length), 120);
  onCleanup(() => clearInterval(timer));
  return <span class="shrink-0 font-mono text-[12px] leading-none text-amber-400">{SQUARE_FRAMES[frame()]}</span>;
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

  const status = () => props.message.toolStatus || "completed";
  const isRunning = () => status() === "running";
  const isError = () => status() === "error";
  const showSpinner = () => isRunning() && props.operating !== false;

  return (
    <div
      class="inline-flex max-w-full items-center gap-2 px-3 py-1.5 rounded-xl bg-[var(--kt-bg-surface)] border border-[var(--kt-border-subtle)] text-[12px] select-text shadow-sm"
      title={title()}
    >
      <span class="shrink-0 flex items-center justify-center">
        <Show
          when={showSpinner()}
          fallback={
            <Show
              when={isError()}
              fallback={<IconCheck size={12} class="text-emerald-400" />}
            >
              <IconClose size={12} class="text-red-400" />
            </Show>
          }
        >
          <SquareSpinner />
        </Show>
      </span>
      <span class="shrink-0 font-mono text-[11px] font-medium text-[var(--kt-text-primary)] px-1.5 py-0.5 rounded-md bg-[var(--kt-bg-hover)]">
        {toolName()}
      </span>
      <Show when={action()}>
        <span class="min-w-0 truncate font-mono text-[11.5px] text-[var(--kt-text-muted)]">
          {action()}
        </span>
      </Show>
    </div>
  );
}
