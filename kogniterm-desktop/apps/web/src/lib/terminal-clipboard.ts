import type { Terminal } from "@xterm/xterm";

/**
 * Elimina secuencias de escape ANSI de un texto.
 */
export function stripAnsi(text: string): string {
  // eslint-disable-next-line no-control-regex
  return text.replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, "").replace(/\x1b\].*?(\x07|\x1b\\)/g, "");
}

/**
 * Extrae el texto visible de un terminal xterm (o la selección actual si existe).
 * Respeta el wrapping de líneas para evitar saltos de línea artificiales.
 */
export function getTerminalText(term?: Terminal, fallbackText?: string): string {
  if (term && term.hasSelection()) {
    const sel = term.getSelection();
    if (sel && sel.length > 0) return sel;
  }

  if (term) {
    const buffer = term.buffer.active;
    const lines: string[] = [];
    for (let i = 0; i < buffer.length; i++) {
      const line = buffer.getLine(i);
      if (!line) continue;
      const str = line.translateToString(true);
      if (line.isWrapped && lines.length > 0) {
        lines[lines.length - 1] += str;
      } else {
        lines.push(str);
      }
    }
    // Eliminar líneas en blanco al final
    while (lines.length > 0 && lines[lines.length - 1].trim() === "") {
      lines.pop();
    }
    const result = lines.join("\n").trimEnd();
    if (result.length > 0) return result;
  }

  if (fallbackText) {
    return stripAnsi(fallbackText).trimEnd();
  }

  return "";
}

/**
 * Copia el contenido del terminal (o la selección activa) al portapapeles.
 */
export async function copyTerminalToClipboard(term?: Terminal, fallbackText?: string): Promise<boolean> {
  const text = getTerminalText(term, fallbackText);
  if (!text) return false;

  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      textarea.style.pointerEvents = "none";
      document.body.appendChild(textarea);
      textarea.select();
      const success = document.execCommand("copy");
      document.body.removeChild(textarea);
      return success;
    }
  } catch (err) {
    console.error("No se pudo copiar el contenido de la terminal:", err);
    return false;
  }
}

/**
 * Configura los atajos de teclado (Ctrl+C, Cmd+C, Ctrl+Shift+C) y el clic derecho
 * para copiar la selección de la terminal sin interrumpir procesos corriendo en PTY
 * cuando haya texto seleccionado.
 */
export function setupTerminalCopyHandlers(term: Terminal, hostElement?: HTMLElement): () => void {
  term.attachCustomKeyEventHandler((ev: KeyboardEvent) => {
    const isCopyKey = ev.key === "c" || ev.key === "C";
    const isCtrlOrMeta = ev.ctrlKey || ev.metaKey;

    if (ev.type === "keydown" && isCtrlOrMeta && isCopyKey) {
      // Ctrl+Shift+C (estándar de terminal Linux) o Ctrl+C / Cmd+C cuando hay texto seleccionado
      if (ev.shiftKey || term.hasSelection()) {
        const sel = term.getSelection();
        if (sel) {
          void copyTerminalToClipboard(term);
          term.clearSelection();
          return false; // Evita enviar \x03 (SIGINT) al PTY
        }
      }
    }
    return true;
  });

  const onContextMenu = (ev: MouseEvent) => {
    if (term.hasSelection()) {
      ev.preventDefault();
      void copyTerminalToClipboard(term);
      term.clearSelection();
    }
  };

  const target = hostElement ?? term.element;
  target?.addEventListener("contextmenu", onContextMenu);

  return () => {
    target?.removeEventListener("contextmenu", onContextMenu);
  };
}
