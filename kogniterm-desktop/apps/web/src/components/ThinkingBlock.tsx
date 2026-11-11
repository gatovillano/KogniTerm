import { Show, createSignal } from "solid-js";

interface ThinkingBlockProps {
  /** Razonamiento crudo del modelo. */
  text?: string;
  /** El mensaje sigue en streaming: solo cambia el rótulo, nunca la expansión. */
  pending?: boolean;
}

/**
 * Bloque de pensamiento ("thinking") del asistente.
 * Se mantiene comprimido con vista previa truncada y desplegable bajo demanda.
 */
export function ThinkingBlock(props: ThinkingBlockProps) {
  const [open, setOpen] = createSignal(false);

  return (
    <details
      class="thinking select-text mb-2.5"
      open={open()}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>
        <Show when={props.pending}>
          <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse shrink-0" />
        </Show>
        <span class="shrink-0 font-mono text-[11.5px] text-[var(--kt-text-secondary)]">
          <Show when={props.pending} fallback="Razonamiento">
            Razonando…
          </Show>
        </span>
        <span class="min-w-0 truncate font-mono text-[11.5px] opacity-75">{props.text}</span>
      </summary>
      <div class="mt-2 pt-2 border-t border-[var(--kt-border-subtle)] whitespace-pre-wrap font-mono text-[11.5px] text-[var(--kt-text-muted)] leading-relaxed">
        {props.text}
      </div>
    </details>
  );
}
