import { createEffect, createResource, createSignal, onCleanup } from "solid-js";
import { Marked } from "marked";
import { createHighlighter, type Highlighter } from "shiki";
import DOMPurify from "dompurify";

let highlighterPromise: Promise<Highlighter> | null = null;

function getHighlighter(): Promise<Highlighter> {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: ["github-dark"],
      langs: [
        "typescript",
        "javascript",
        "tsx",
        "jsx",
        "python",
        "bash",
        "shell",
        "json",
        "yaml",
        "markdown",
        "diff",
        "html",
        "css",
        "rust",
        "go",
        "java",
        "sql",
        "toml",
        "ini",
        "dockerfile",
        "plaintext",
      ],
    });
  }
  return highlighterPromise;
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

async function renderMarkdown(text: string): Promise<string> {
  const hl = await getHighlighter();
  const m = new Marked({ gfm: true, breaks: true });
  m.use({
    renderer: {
      // Enlaces: siempre con target="_blank" para que Electron los derive al
      // navegador vía setWindowOpenHandler en vez de navegar la ventana.
      link({ href, title, text }: { href: string; title?: string | null; text: string }) {
        const t = title ? ` title="${escapeHtml(title)}"` : "";
        return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer"${t}>${text}</a>`;
      },
      code({ text: code, lang }: { text: string; lang?: string }) {
        const language = (lang || "plaintext").toLowerCase();
        try {
          if (!(hl.getLoadedLanguages() as string[]).includes(language)) throw new Error("unknown lang");
          return hl.codeToHtml(code, { lang: language, theme: "github-dark" });
        } catch {
          return `<pre class="shiki"><code>${escapeHtml(code)}</code></pre>`;
        }
      },
    },
  });
  const raw = await m.parse(text);
  // DOMPurify quitaría target/_blank sin ADD_ATTR: hay que conservarlo para
  // que Electron derive el enlace al navegador vía setWindowOpenHandler.
  return DOMPurify.sanitize(raw, { ADD_ATTR: ["target", "rel"] });
}

// Renderizado síncrono ligero para streaming en tiempo real (sin shiki async)
function renderMarkdownSync(text: string): string {
  const m = new Marked({ gfm: true, breaks: true });
  m.use({
    renderer: {
      link({ href, title, text }: { href: string; title?: string | null; text: string }) {
        const t = title ? ` title="${escapeHtml(title)}"` : "";
        return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer"${t}>${text}</a>`;
      },
      code({ text: code, lang }: { text: string; lang?: string }) {
        return `<pre class="shiki"><code>${escapeHtml(code)}</code></pre>`;
      },
    },
  });
  const raw = m.parse(text) as string;
  return DOMPurify.sanitize(raw, { ADD_ATTR: ["target", "rel"] });
}

/** Markdown con highlight (shiki/github-dark) y streaming real en tiempo real con renderizado de Markdown.
 */
export function Markdown(props: { text: string; center?: boolean; streaming?: boolean }) {
  const [stable, setStable] = createSignal(props.text);
  let timer: number | undefined;
  let lastFlush = 0;
  const THROTTLE_MS = 100;

  createEffect(() => {
    const cur = props.text;
    const streaming = props.streaming;
    clearTimeout(timer);
    if (streaming) {
      const now = Date.now();
      const elapsed = now - lastFlush;
      if (elapsed >= THROTTLE_MS) {
        lastFlush = now;
        setStable(cur);
      } else {
        timer = window.setTimeout(() => {
          lastFlush = Date.now();
          setStable(cur);
        }, THROTTLE_MS - elapsed);
      }
      return;
    }
    // Mensaje finalizado: render inmediato (una sola vez).
    lastFlush = Date.now();
    setStable(cur);
  });
  onCleanup(() => clearTimeout(timer));

  // Solo se re-ejecuta cuando `stable` cambia (throttled), no por cada token.
  const [html] = createResource(stable, renderMarkdown);

  // Vista streaming: renderizado markdown síncrono en tiempo real por token.
  const streamingHtml = () => renderMarkdownSync(props.text);

  // Clics en enlaces: en Electron se delega a shell.openExternal vía preload
  // (evita que un <a> sin target navegue la ventana); en navegador basta con
  // el target="_blank" del renderer, aquí solo se refuerza con noopener.
  const onLinkClick = (e: MouseEvent) => {
    const anchor = (e.target as HTMLElement | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
    if (!anchor) return;
    const href = anchor.getAttribute("href") ?? "";
    if (!/^(https?:|mailto:)/i.test(href)) return;
    const openExternal = (globalThis as any).kogniterm?.openExternal as ((u: string) => void) | undefined;
    if (typeof openExternal === "function") {
      e.preventDefault();
      openExternal(href);
    } else {
      e.preventDefault();
      window.open(href, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div
      class={`md ${props.center ? "md-center" : ""}`}
      onClick={onLinkClick}
      innerHTML={
        props.streaming
          ? streamingHtml()
          : (html() ?? renderMarkdownSync(stable()))
      }
    />
  );
}
