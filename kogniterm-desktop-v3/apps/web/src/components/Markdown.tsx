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
  return DOMPurify.sanitize(raw);
}

/** Markdown con highlight (shiki/github-dark) y debounce para streaming. */
export function Markdown(props: { text: string; center?: boolean }) {
  const [stable, setStable] = createSignal(props.text);
  let timer: number | undefined;
  createEffect(() => {
    const cur = props.text;
    clearTimeout(timer);
    // si acaba de cerrarse un fence, render inmediato; si no, espera a que pare el stream
    timer = window.setTimeout(() => setStable(cur), 150);
  });
  onCleanup(() => clearTimeout(timer));

  const [html] = createResource(stable, renderMarkdown);

  return (
    <div
      class={`md ${props.center ? "md-center" : ""}`}
      innerHTML={html() ?? escapeHtml(stable()).replace(/\n/g, "<br>")}
    />
  );
}
