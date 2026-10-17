import { Show, createSignal } from "solid-js";

interface ThinkingBlockProps {
  /** Razonamiento crudo del modelo. */
  text?: string;
  /** El mensaje sigue en streaming: solo cambia el rótulo, nunca la expansión. */
  pending?: boolean;
}

/**
 * Bloque de pensamiento ("thinking") del asistente.
 *
 * Se apoya en el CSS `.thinking` de index.css, que espera un `<details>/<summary>`
 * (`.thinking > summary` con cursor pointer, `content:"›"` y `.thinking[open]`).
 * Antes se renderizaba como un `<div>` plano, por lo que el click no hacía nada.
 *
 * Se mantiene SIEMPRE comprimido (una sola línea con vista previa truncada),
 * incluso mientras el modelo transmite: abrirlo a mano obliga a que el bloque
 * ocupe la pantalla y empuje la respuesta hacia abajo. El texto completo sigue
 * disponible al desplegarlo.
 */
export function ThinkingBlock(props: ThinkingBlockProps) {
  const [open, setOpen] = createSignal(false);

  return (
    <details
      class="thinking select-text mb-2"
      open={open()}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>
        <span class="shrink-0 font-mono">
          <Show when={props.pending} fallback="Pensamiento">
            Pensando…
          </Show>
        </span>
        <span class="min-w-0 truncate font-mono">{props.text}</span>
      </summary>
      <div class="mt-1.5 whitespace-pre-wrap font-mono text-zinc-400">{props.text}</div>
    </details>
  );
}