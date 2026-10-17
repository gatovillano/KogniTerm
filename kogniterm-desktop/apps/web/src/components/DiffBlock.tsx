import { For, Show, createMemo, createSignal } from "solid-js";

interface DiffLine {
  kind: "add" | "del" | "ctx" | "hunk" | "meta";
  text: string;
}

function classify(line: string): DiffLine["kind"] {
  if (line.startsWith("+++") || line.startsWith("---")) return "meta";
  if (line.startsWith("@@")) return "hunk";
  if (line.startsWith("+")) return "add";
  if (line.startsWith("-")) return "del";
  return "ctx";
}

/**
 * Widget de diff aplicado — equivalente visual al `DiffRenderer` de la TUI.
 * Recibe el diff unificado que el servidor emite en el evento `diff_applied`
 * (ver `ServerUI.print_diff_applied` en kogniterm/server/session_pool.py).
 */
export function DiffBlock(props: {
  diff: string;
  filePath?: string;
  operation?: string;
  /** Inicio plegado cuando el diff es largo (el usuario lo despliega). */
  collapsible?: boolean;
}) {
  const [open, setOpen] = createSignal(true);
  const COLLAPSE_THRESHOLD = 24;

  const lines = createMemo<DiffLine[]>(() =>
    String(props.diff ?? "")
      .replace(/\r\n/g, "\n")
      .split("\n")
      .map((text) => ({ kind: classify(text), text })),
  );

  const stats = createMemo(() => {
    let added = 0;
    let removed = 0;
    for (const l of lines()) {
      if (l.kind === "add") added++;
      else if (l.kind === "del") removed++;
    }
    return { added, removed };
  });

  const path = () => props.filePath || "archivo";
  const isLong = () => lines().length > COLLAPSE_THRESHOLD;
  const collapsible = () => props.collapsible !== false && isLong();
  const visible = () => (collapsible() && !open() ? lines().slice(0, COLLAPSE_THRESHOLD) : lines());

  const lineClass = (kind: DiffLine["kind"]) => {
    switch (kind) {
      case "add":
        return "bg-emerald-500/10 text-emerald-300";
      case "del":
        return "bg-red-500/10 text-red-300";
      case "hunk":
        return "bg-sky-500/10 text-sky-300 font-semibold";
      case "meta":
        return "text-zinc-400 font-semibold";
      default:
        return "text-zinc-300";
    }
  };

  return (
    <div class="animate-slide-up my-2 select-text">
      <div class="flex items-center gap-2 px-3 py-1.5 rounded-t-2xl bg-white/[0.04] border border-white/[0.06] border-b-0">
        <span class="text-[11.5px] font-semibold text-zinc-200 truncate" title={path()}>
          {path()}
        </span>
        <Show when={props.operation}>
          <span class="text-[10px] px-1.5 py-0.5 rounded-full bg-white/[0.06] text-zinc-400 font-mono shrink-0">
            {props.operation}
          </span>
        </Show>
        <div class="flex-1" />
        <Show when={stats().added > 0}>
          <span class="text-[11px] font-mono text-emerald-400">+{stats().added}</span>
        </Show>
        <Show when={stats().removed > 0}>
          <span class="text-[11px] font-mono text-red-400">−{stats().removed}</span>
        </Show>
      </div>

      <div class="rounded-b-2xl border border-white/[0.06] bg-black/40 overflow-x-auto">
        <pre class="px-3 py-2.5 font-mono text-[11.5px] leading-relaxed">
          <For each={visible()}>
            {(l) => <div class={`px-1 -mx-1 whitespace-pre ${lineClass(l.kind)}`}>{l.text || " "}</div>}
          </For>
        </pre>

        <Show when={collapsible()}>
          <button
            onClick={() => setOpen(!open())}
            class="w-full py-1.5 text-[11px] text-zinc-400 hover:text-white bg-white/[0.03] hover:bg-white/[0.06] transition-colors"
          >
            {open() ? "Ver menos" : `Ver ${lines().length - COLLAPSE_THRESHOLD} líneas más`}
          </button>
        </Show>
      </div>
    </div>
  );
}