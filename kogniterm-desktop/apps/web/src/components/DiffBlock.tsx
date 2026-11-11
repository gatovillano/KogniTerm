import { For, Show, createMemo, createSignal } from "solid-js";
import { IconCheck, IconCopy, IconFile } from "./Icons";

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
 * Widget de diff aplicado — tarjeta de código oscura de alto contraste.
 */
export function DiffBlock(props: {
  diff: string;
  filePath?: string;
  operation?: string;
  collapsible?: boolean;
}) {
  const [open, setOpen] = createSignal(true);
  const [copied, setCopied] = createSignal(false);
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

  function copyDiff() {
    if (!props.diff) return;
    void navigator.clipboard.writeText(props.diff).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    });
  }

  const lineClass = (kind: DiffLine["kind"]) => {
    switch (kind) {
      case "add":
        return "bg-emerald-500/12 text-emerald-300 border-l-2 border-emerald-400/70";
      case "del":
        return "bg-red-500/12 text-red-300 border-l-2 border-red-400/70";
      case "hunk":
        return "bg-sky-500/10 text-sky-300 font-semibold border-l-2 border-sky-400/50";
      case "meta":
        return "text-zinc-400 font-semibold border-l-2 border-transparent";
      default:
        return "text-zinc-300 border-l-2 border-transparent";
    }
  };

  return (
    <div class="animate-slide-up my-2 select-text rounded-2xl overflow-hidden bg-[var(--kt-bg-code)] border border-white/[0.08] shadow-[var(--kt-shadow-md)]">
      <div class="flex items-center gap-2 px-3.5 py-2 bg-white/[0.035] border-b border-white/[0.06] select-none">
        <IconFile size={13} class="text-zinc-400 shrink-0" />
        <span class="text-[12px] font-mono font-medium text-zinc-200 truncate" title={path()}>
          {path()}
        </span>
        <Show when={props.operation}>
          <span class="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] text-zinc-400 font-mono shrink-0">
            {props.operation}
          </span>
        </Show>
        <div class="flex-1" />
        <Show when={stats().added > 0}>
          <span class="text-[11px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300">
            +{stats().added}
          </span>
        </Show>
        <Show when={stats().removed > 0}>
          <span class="text-[11px] font-mono px-1.5 py-0.5 rounded bg-red-500/15 text-red-300">
            −{stats().removed}
          </span>
        </Show>
        <button
          type="button"
          onClick={copyDiff}
          class={`h-6 px-2.5 rounded-full flex items-center gap-1 transition-all text-[11px] font-medium ml-1 ${
            copied()
              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
              : "text-zinc-400 hover:text-white bg-white/[0.05] hover:bg-white/[0.1]"
          }`}
          title="Copiar diff"
        >
          <Show when={copied()} fallback={<IconCopy size={11} />}>
            <IconCheck size={11} class="text-emerald-400" />
          </Show>
          <span>{copied() ? "Copiado" : "Copiar"}</span>
        </button>
      </div>

      <div class="overflow-x-auto">
        <pre class="py-2 font-mono text-[11.5px] leading-relaxed">
          <For each={visible()}>
            {(l) => <div class={`px-3 whitespace-pre ${lineClass(l.kind)}`}>{l.text || " "}</div>}
          </For>
        </pre>

        <Show when={collapsible()}>
          <button
            onClick={() => setOpen(!open())}
            class="w-full py-1.5 text-[11px] font-medium text-zinc-400 hover:text-white bg-white/[0.03] hover:bg-white/[0.06] border-t border-white/[0.06] transition-colors"
          >
            {open() ? "Ver menos" : `Ver ${lines().length - COLLAPSE_THRESHOLD} líneas más`}
          </button>
        </Show>
      </div>
    </div>
  );
}
