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

function wrapCodeBlock(preHtml: string, lang?: string): string {
  const label = escapeHtml((lang || "text").toLowerCase());
  return `<div class="md-code-block"><div class="md-code-header"><span>${label}</span><button type="button" class="md-code-copy">Copiar</button></div>${preHtml}</div>`;
}

async function renderMarkdown(text: string): Promise<string> {
  const hl = await getHighlighter();
  const m = new Marked({ gfm: true, breaks: true });
  m.use({
    renderer: {
      link({ href, title, text }: { href: string; title?: string | null; text: string }) {
        const t = title ? ` title="${escapeHtml(title)}"` : "";
        return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer"${t}>${text}</a>`;
      },
      code({ text: code, lang }: { text: string; lang?: string }) {
        const language = (lang || "plaintext").toLowerCase();
        try {
          if (!(hl.getLoadedLanguages() as string[]).includes(language)) throw new Error("unknown lang");
          return wrapCodeBlock(hl.codeToHtml(code, { lang: language, theme: "github-dark" }), lang || language);
        } catch {
          return wrapCodeBlock(`<pre class="shiki"><code>${escapeHtml(code)}</code></pre>`, lang || "text");
        }
      },
    },
  });
  const raw = await m.parse(text);
  return DOMPurify.sanitize(raw, { ADD_ATTR: ["target", "rel"] });
}

function renderMarkdownSync(text: string): string {
  const m = new Marked({ gfm: true, breaks: true });
  m.use({
    renderer: {
      link({ href, title, text }: { href: string; title?: string | null; text: string }) {
        const t = title ? ` title="${escapeHtml(title)}"` : "";
        return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer"${t}>${text}</a>`;
      },
      code({ text: code, lang }: { text: string; lang?: string }) {
        return wrapCodeBlock(`<pre class="shiki"><code>${escapeHtml(code)}</code></pre>`, lang || "text");
      },
    },
  });
  const raw = m.parse(text) as string;
  return DOMPurify.sanitize(raw, { ADD_ATTR: ["target", "rel"] });
}

/** Markdown con highlight (shiki/github-dark), copia en bloques de código y streaming en tiempo real. */
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
    lastFlush = Date.now();
    setStable(cur);
  });
  onCleanup(() => clearTimeout(timer));

  const [html] = createResource(stable, renderMarkdown);
  const streamingHtml = () => renderMarkdownSync(props.text);

  const onContentClick = (e: MouseEvent) => {
    const target = e.target as HTMLElement | null;
    if (!target) return;

    const copyBtn = target.closest?.(".md-code-copy") as HTMLButtonElement | null;
    if (copyBtn) {
      const wrap = copyBtn.closest(".md-code-block");
      const codeEl = wrap?.querySelector("pre code");
      const codeText = codeEl?.textContent ?? "";
      if (codeText) {
        void navigator.clipboard.writeText(codeText).then(() => {
          copyBtn.textContent = "✓ Copiado";
          copyBtn.classList.add("is-copied");
          setTimeout(() => {
            copyBtn.textContent = "Copiar";
            copyBtn.classList.remove("is-copied");
          }, 1600);
        });
      }
      return;
    }

    const anchor = target.closest?.("a[href]") as HTMLAnchorElement | null;
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
      onClick={onContentClick}
      innerHTML={props.streaming ? streamingHtml() : (html() ?? renderMarkdownSync(stable()))}
    />
  );
}
