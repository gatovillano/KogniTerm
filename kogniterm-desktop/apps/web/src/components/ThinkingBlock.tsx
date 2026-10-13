import { createEffect, createSignal } from "solid-js";

interface ThinkingBlockProps {
  /** Razonamiento crudo del modelo. */
  text?: string;
  /** El mensaje sigue en streaming: se muestra expandido mientras el modelo piensa. */
  pending?: boolean;
}

/**
 * Bloque de pensamiento ("thinking") del asistente.
 *
 * Se apoya en el CSS `.thinking` de index.css, que espera un `<details>/<summary>`
 * (`.thinking > summary` con cursor pointer, `content:"›"` y `.thinking[open]`).
 * Antes se renderizaba como un `<div>` plano, por lo que el click no hacía nada.
 */
export function ThinkingBlock(props: ThinkingBlockProps) {
  const [open, setOpen] = createSignal(props.pending);
  const [userTouched, setUserTouched] = createSignal(false);

  // Al terminar el streaming se colapsa automáticamente, salvo que el usuario
  // haya abierto/cerrado manualmente (entonces se respeta su elección).
  createEffect(() => {
    if (!props.pending && !userTouched()) setOpen(false);
  });

  return (
    <details
      class="thinking select-text mb-2"
      open={open()}
      onToggle={(e) => {
        setUserTouched(true);
        setOpen(e.currentTarget.open);
      }}
    >
      <summary>
        <span class="min-w-0 truncate font-mono">{props.text}</span>
      </summary>
      <div class="mt-1.5 whitespace-pre-wrap font-mono text-zinc-400">{props.text}</div>
    </details>
  );
}
