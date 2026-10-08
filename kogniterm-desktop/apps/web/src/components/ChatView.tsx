import { For, Show, createEffect, createSignal, onCleanup, onMount } from "solid-js";
import { ChatAttachment, ChatMsg, tabs, uid } from "../lib/tabs";
import { useSession } from "../lib/session";
import { agents, useAgents } from "../lib/agents";
import { loadThreadHistory } from "../lib/history";
import { AgentTerminal } from "./AgentTerminal";
import { AgentSelector } from "./AgentSelector";
import { Markdown } from "./Markdown";
import { ChatAutocomplete, AutocompleteState, AutocompleteCommand } from "./ChatAutocomplete";
import { TaskTrackerPanel } from "./TaskTrackerPanel";
import { Wordmark } from "./Wordmark";
import { tasksStore } from "../lib/tasks";
import { WorkspaceFileItem, api } from "../lib/api";
import { ToolIndicator } from "./ToolIndicator";

export function ChatView(props: { tabId: string }) {
  const session = useSession(props.tabId);
  const agentState = useAgents(props.tabId);
  const [draft, setDraft] = createSignal("");
  const [agentStatus, setAgentStatus] = createSignal("");
  const [copiedId, setCopiedId] = createSignal<string | null>(null);
  const [pausedQueue, setPausedQueue] = createSignal(false);
  const [autocompleteState, setAutocompleteState] = createSignal<AutocompleteState | null>(null);
  // Navegación por historial de solicitudes del usuario (estilo shell: ↑/↓).
  const [historyIndex, setHistoryIndex] = createSignal<number | null>(null);
  const [historyBackup, setHistoryBackup] = createSignal("");
  // Adjuntos pendientes (texto o imagen) antes de enviar.
  const [attachments, setAttachments] = createSignal<ChatAttachment[]>([]);
  const [attachError, setAttachError] = createSignal("");
  let scrollRef: HTMLDivElement | undefined;
  let inputRef: HTMLInputElement | undefined;
  let fileInputRef: HTMLInputElement | undefined;
  let autocompleteRef: { handleKeyDown: (e: KeyboardEvent) => boolean } | undefined;
  let queueTimeout: any = null;

  function checkAutocomplete() {
    if (!inputRef) {
      setAutocompleteState(null);
      return;
    }
    const val = draft();
    const pos = inputRef.selectionStart ?? val.length;
    const textBefore = val.slice(0, pos);

    // Archivos (@)
    const atMatch = /(?:^|\s)@([^\s@]*)$/.exec(textBefore);
    if (atMatch) {
      const query = atMatch[1];
      const triggerIndex = atMatch.index + (atMatch[0].startsWith(" ") ? 1 : 0);
      setAutocompleteState({
        type: "file",
        query,
        start: triggerIndex,
        end: pos,
      });
      return;
    }

    // Comandos (/)
    const slashMatch = /(?:^|\s)\/([a-zA-Z0-9_\-]*)$/.exec(textBefore);
    if (slashMatch) {
      const query = slashMatch[1];
      const triggerIndex = slashMatch.index + (slashMatch[0].startsWith(" ") ? 1 : 0);
      setAutocompleteState({
        type: "command",
        query,
        start: triggerIndex,
        end: pos,
      });
      return;
    }

    setAutocompleteState(null);
  }

  function handleSelectFile(file: WorkspaceFileItem) {
    const state = autocompleteState();
    if (!state || !inputRef) return;
    const before = draft().slice(0, state.start);
    const after = draft().slice(state.end);
    const isDir = file.is_dir;
    const insert = `@${file.path}${isDir ? "" : " "}`;
    const newText = before + insert + after;
    setDraft(newText);
    setAutocompleteState(null);
    const newPos = before.length + insert.length;
    requestAnimationFrame(() => {
      inputRef?.focus();
      inputRef?.setSelectionRange(newPos, newPos);
      if (isDir) {
        checkAutocomplete();
      }
    });
  }

  function handleSelectCommand(cmd: AutocompleteCommand) {
    const state = autocompleteState();
    if (!state || !inputRef) return;
    const before = draft().slice(0, state.start);
    const after = draft().slice(state.end);
    const insert = `${cmd.name} `;
    const newText = before + insert + after;
    setDraft(newText);
    setAutocompleteState(null);
    const newPos = before.length + insert.length;
    requestAnimationFrame(() => {
      inputRef?.focus();
      inputRef?.setSelectionRange(newPos, newPos);
    });
  }

  const tab = () => tabs.store.tabs.find((t) => t.id === props.tabId)!;

  // ── Adjuntos: texto se inlinea, imagen va como multimodal ──
  const MAX_ATTACHMENTS = 10;
  const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
  const MAX_TEXT_BYTES = 512 * 1024;
  const MAX_TEXT_CHARS = 50000;
  const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"]);
  const TEXT_EXTS = new Set([
    "txt", "md", "markdown", "json", "csv", "tsv", "log", "yaml", "yml", "toml",
    "xml", "html", "css", "js", "ts", "tsx", "jsx", "py", "rs", "go", "java",
    "c", "h", "cpp", "hpp", "sh", "sql", "r", "rb", "php", "swift", "kt",
    "dockerfile", "env", "ini", "cfg", "conf", "properties", "gradle",
  ]);

  function formatSize(n: number): string {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
  }

  function classifyFile(file: File): "image" | "text" | null {
    const ext = (file.name.split(".").pop() ?? "").toLowerCase();
    if (file.type.startsWith("image/") || IMAGE_EXTS.has(ext)) return "image";
    if (
      file.type.startsWith("text/") ||
      file.type === "application/json" ||
      file.type === "application/xml" ||
      TEXT_EXTS.has(ext) ||
      ext === ""
    )
      return "text";
    return null;
  }

  function readAsDataURL(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(String(r.result ?? ""));
      r.onerror = () => reject(new Error("read"));
      r.readAsDataURL(file);
    });
  }

  function readAsText(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(String(r.result ?? ""));
      r.onerror = () => reject(new Error("read"));
      r.readAsText(file);
    });
  }

  /** Redimensiona rasters grandes (fotos/capturas) para un envío liviano.
   *  El modelo ve igual de bien una imagen de 1536px que la original de 4K,
   *  pero el payload pasa de MBs a cientos de KB. GIF/SVG se dejan intactos. */
  const MAX_IMAGE_DIM = 1536;
  function downscaleImage(file: File): Promise<{ dataUrl: string; size: number }> {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        try {
          const scale = Math.min(1, MAX_IMAGE_DIM / Math.max(img.width, img.height));
          if (scale >= 1 && file.size <= MAX_IMAGE_BYTES) {
            URL.revokeObjectURL(url);
            void readAsDataURL(file).then((dataUrl) => resolve({ dataUrl, size: file.size }));
            return;
          }
          const w = Math.max(1, Math.round(img.width * scale));
          const h = Math.max(1, Math.round(img.height * scale));
          const canvas = document.createElement("canvas");
          canvas.width = w;
          canvas.height = h;
          const ctx = canvas.getContext("2d");
          if (!ctx) throw new Error("no-2d");
          ctx.drawImage(img, 0, 0, w, h);
          URL.revokeObjectURL(url);
          canvas.toBlob(
            (blob) => {
              if (!blob) {
                void readAsDataURL(file).then((dataUrl) => resolve({ dataUrl, size: file.size }));
                return;
              }
              const r = new FileReader();
              r.onload = () => resolve({ dataUrl: String(r.result ?? ""), size: blob.size });
              r.onerror = () => reject(new Error("read"));
              r.readAsDataURL(blob);
            },
            "image/jpeg",
            0.85,
          );
        } catch (e) {
          URL.revokeObjectURL(url);
          reject(e instanceof Error ? e : new Error("downscale"));
        }
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("decode"));
      };
      img.src = url;
    });
  }

  async function addFiles(files: FileList | File[] | null) {
    if (!files) return;
    const list = Array.from(files);
    if (!list.length) return;
    setAttachError("");
    for (const file of list) {
      if (attachments().length >= MAX_ATTACHMENTS) {
        setAttachError(`Máximo ${MAX_ATTACHMENTS} adjuntos por mensaje.`);
        break;
      }
      const kind = classifyFile(file);
      if (!kind) {
        setAttachError(`Tipo no soportado: ${file.name} (solo texto o imagen).`);
        continue;
      }
      try {
        if (kind === "image") {
          if (file.size > MAX_IMAGE_BYTES * 3) {
            setAttachError(`${file.name}: supera ${formatSize(MAX_IMAGE_BYTES * 3)}.`);
            continue;
          }
          const ext = (file.name.split(".").pop() ?? "").toLowerCase();
          const keepOriginal = ext === "gif" || ext === "svg" || file.type === "image/gif" || file.type === "image/svg+xml";
          const { dataUrl, size } = keepOriginal
            ? { dataUrl: await readAsDataURL(file), size: file.size }
            : await downscaleImage(file);
          if (size > MAX_IMAGE_BYTES * 3) {
            setAttachError(`${file.name}: aún muy pesada tras compresión.`);
            continue;
          }
          setAttachments((a) => [
            ...a,
            { id: uid("att"), name: file.name, mime: file.type || "image/*", size, kind, dataUrl },
          ]);
        } else {
          if (file.size > MAX_TEXT_BYTES) {
            setAttachError(`${file.name}: supera ${formatSize(MAX_TEXT_BYTES)} como texto.`);
            continue;
          }
          let content = await readAsText(file);
          if (content.length > MAX_TEXT_CHARS) {
            content = content.slice(0, MAX_TEXT_CHARS) + "\n\n[…contenido truncado…]";
          }
          setAttachments((a) => [
            ...a,
            { id: uid("att"), name: file.name, mime: file.type || "text/plain", size: file.size, kind, textContent: content },
          ]);
        }
      } catch {
        setAttachError(`No se pudo leer ${file.name}.`);
      }
    }
    inputRef?.focus();
  }

  function removeAttachment(id: string) {
    setAttachments((a) => a.filter((x) => x.id !== id));
  }

  function clearAttachments() {
    setAttachments([]);
    if (fileInputRef) fileInputRef.value = "";
  }

  /** Texto final: borrador + ficheros de texto inlineados. Imágenes aparte (multimodal). */
  function buildPayload(): { text: string; images: string[]; bubble: ChatAttachment[] } {
    const atts = attachments();
    const images = atts.filter((a) => a.kind === "image" && a.dataUrl).map((a) => a.dataUrl!);
    let text = draft();
    for (const a of atts) {
      if (a.kind !== "text") continue;
      const ext = (a.name.split(".").pop() ?? "").toLowerCase();
      text += `\n\nAdjunto: ${a.name}\n\`\`\`${ext}\n${a.textContent ?? ""}\n\`\`\``;
    }
    if (!text.trim() && images.length) text = "Describe o analiza la(s) imagen(es) adjunta(s).";
    return { text, images, bubble: atts };
  }

  // Meta del input: modelo activo (solo nombre) y carpeta de trabajo actual.
  const [modelName, setModelName] = createSignal("");
  const [workDir, setWorkDir] = createSignal("");
  const [workPath, setWorkPath] = createSignal("");

  async function refreshInputMeta() {
    try {
      const cfg = await api.getLLM();
      const m = cfg.model ?? "";
      setModelName(m.includes("/") ? m.split("/").pop()! : m);
    } catch {
      setModelName("");
    }
    try {
      const s = await api.workspaceStatus(props.tabId);
      const p = s.path ?? "";
      setWorkPath(p);
      const parts = p.split("/").filter(Boolean);
      setWorkDir(parts.length ? parts[parts.length - 1] : p);
    } catch {
      setWorkDir("");
      setWorkPath("");
    }
  }

  // Historial de solicitudes del usuario en esta pestaña (orden cronológico).
  const userHistory = () => {
    const msgs = tab()?.messages.filter((m) => m.role === "user" && m.text.trim()) ?? [];
    // Evita duplicados consecutivos (p.ej. reenvíos idénticos seguidos).
    const out: string[] = [];
    for (const m of msgs) {
      if (out.length === 0 || out[out.length - 1] !== m.text) out.push(m.text);
    }
    return out;
  };

  function resetHistoryNav() {
    setHistoryIndex(null);
    setHistoryBackup("");
  }

  // Al cambiar de pestaña se sale del modo historial.
  createEffect(() => {
    props.tabId;
    resetHistoryNav();
  });

  function applyHistoryValue(value: string) {
    setDraft(value);
    setAutocompleteState(null);
    requestAnimationFrame(() => {
      inputRef?.focus();
      try {
        inputRef?.setSelectionRange(value.length, value.length);
      } catch {
        /* input no enfocado: ignorar */
      }
    });
  }

  /** Navega el historial. dir=-1 (↑ anterior) | dir=+1 (↓ siguiente). Devuelve true si consumió la tecla. */
  function navigateHistory(dir: -1 | 1): boolean {
    const h = userHistory();
    if (h.length === 0) return false;
    const idx = historyIndex();
    if (idx === null) {
      if (dir > 0) return false; // ↓ con borrador fresco no hace nada (como en shell)
      setHistoryBackup(draft());
      const last = h.length - 1;
      setHistoryIndex(last);
      applyHistoryValue(h[last]);
      return true;
    }
    const next = idx + dir;
    if (next < 0) return true; // ya en la más antigua: retener
    if (next >= h.length) {
      // Volver al borrador que el usuario estaba escribiendo.
      const backup = historyBackup();
      resetHistoryNav();
      applyHistoryValue(backup);
      return true;
    }
    setHistoryIndex(next);
    applyHistoryValue(h[next]);
    return true;
  }

  // Historial persistido del hilo (al abrir una conversación o cambiar de pestaña).
  onMount(() => {
    if (tab()?.messages.length === 0) void loadThreadHistory(props.tabId);
    void tasksStore.fetchSessionTodos(props.tabId);
    void refreshInputMeta();
  });

  // Al cambiar de pestaña se refresca la carpeta de trabajo mostrada.
  createEffect(() => {
    props.tabId;
    void refreshInputMeta();
  });

  createEffect(() => {
    tab().messages.length;
    scrollRef?.scrollTo({ top: scrollRef.scrollHeight, behavior: "smooth" });
  });

  /** Auto-scroll en tiempo real durante el streaming (texto/tools/terminal).
   *  Solo si el usuario ya está cerca del fondo, para no robarle el scroll
   *  cuando revisa mensajes anteriores. */
  createEffect(() => {
    const msgs = tab()?.messages ?? [];
    // Firma reactiva: cambia con cada token en streaming.
    const sig = msgs
      .map(
        (m) =>
          `${m.id}:${m.text?.length ?? 0}:${m.thinking?.length ?? 0}:${m.terminalOutput?.length ?? 0}:${m.toolStatus ?? ""}`,
      )
      .join("|");
    sig; // dependencia explícita
    const el = scrollRef;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 160;
    if (nearBottom) el.scrollTo({ top: el.scrollHeight });
  });

  function copyMessage(id: string, text: string) {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => {
      if (copiedId() === id) setCopiedId(null);
    }, 1500);
  }

  const isOperating = () => {
    if (session.running()) return true;
    const t = tab();
    if (!t) return false;
    return t.messages.some(
      (m) =>
        (m.role === "assistant" && m.pending) ||
        (m.role === "terminal" && m.terminalActive) ||
        (m.role === "tool" && m.toolStatus === "running"),
    );
  };

  const queuedMessages = () => tab()?.messages.filter((m) => m.queued) ?? [];

  function enqueueDraft() {
    const v = draft().trim();
    const hasAtt = attachments().length > 0;
    if (!v && !hasAtt) return;
    const selected = agentState.selected();
    const { text, images, bubble } = buildPayload();
    tabs.enqueue(props.tabId, {
      id: uid("q"),
      role: "user",
      text,
      agent: selected?.id,
      queued: true,
      queuedAt: Date.now(),
      ...(bubble.length ? { attachments: bubble } : {}),
      ...(images.length ? { images } : {}),
    });
    setDraft("");
    clearAttachments();
    setAutocompleteState(null);
    resetHistoryNav();
    scrollRef?.scrollTo({ top: scrollRef.scrollHeight, behavior: "smooth" });
  }

  function handleInterrupt() {
    session.interrupt();
    if (queuedMessages().length > 0) {
      setPausedQueue(true);
    }
  }

  function resumeQueue() {
    setPausedQueue(false);
    const q = queuedMessages();
    if (q.length > 0 && !isOperating()) {
      const next = q[0];
      session.sendQueued(next.id, next.text, next.agent);
    }
  }

  function runQueuedNow(m: ChatMsg) {
    setPausedQueue(false);
    if (isOperating()) {
      session.interrupt();
    }
    setTimeout(() => {
      session.sendQueued(m.id, m.text, m.agent);
    }, 150);
  }

  createEffect(() => {
    const operating = isOperating();
    const paused = pausedQueue();
    const q = queuedMessages();
    if (!operating && !paused && q.length > 0) {
      if (queueTimeout) clearTimeout(queueTimeout);
      queueTimeout = setTimeout(() => {
        if (!isOperating() && !pausedQueue()) {
          const next = queuedMessages()[0];
          if (next) {
            session.sendQueued(next.id, next.text, next.agent);
          }
        }
      }, 400);
    }
  });

  onCleanup(() => {
    if (queueTimeout) clearTimeout(queueTimeout);
  });

  function submit(e?: Event) {
    e?.preventDefault();
    const hasAtt = attachments().length > 0;
    if (isOperating()) {
      enqueueDraft();
      return;
    }
    const v = draft();
    if (!v.trim() && !hasAtt) return;
    const selected = agentState.selected();
    if (!selected) {
      setAgentStatus(
        agentState.error()
          ? `Agentes no disponibles: ${agentState.error()}`
          : "Cargando el catálogo nativo de agentes…",
      );
      if (!agentState.catalog()) {
        void agents.ensureAgents(true);
      }
      return;
    }
    setAgentStatus("");
    const { text, images, bubble } = buildPayload();
    setDraft("");
    clearAttachments();
    setAutocompleteState(null);
    resetHistoryNav();
    setPausedQueue(false);
    session.send(text, selected.id, images, bubble);
    if (tab().messages.length <= 2) {
      tabs.rename(props.tabId, (v.trim() || bubble[0]?.name || tab().title).slice(0, 32));
    }
  }

  return (
    <div class="flex flex-col h-full bg-[#090a0f] text-[#f4f4f5]">
      {/* Barra de estado minimalista y sin bordes */}
      <div class="flex items-center gap-2.5 px-5 py-2 text-[12px] text-zinc-400 bg-white/[0.015] select-none">
        <div class="flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-white/[0.04]">
          <span
            class={`w-2 h-2 rounded-full transition-all duration-300 ${
              session.conn() === "open"
                ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]"
                : session.conn() === "connecting"
                  ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.7)]"
                  : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.7)]"
            }`}
          />
          <span class="font-mono text-zinc-300 text-[11px]">{props.tabId}</span>
          <span class="text-zinc-600">·</span>
          <span class="capitalize text-zinc-400 text-[11px]">{session.conn()}</span>
        </div>

        <div class="flex-1" />

        <button
          class="w-6 h-6 rounded-full flex items-center justify-center hover:bg-white/[0.08] hover:text-white transition-all text-zinc-400"
          onClick={() => session.reconnect()}
          title="Reconectar WebSocket"
        >
          ↻
        </button>

        <Show when={isOperating()}>
          <button
            class="flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium bg-red-500/15 text-red-300 hover:bg-red-500/25 border border-red-500/20 shadow-sm transition-all active:scale-95 animate-pulse"
            onClick={() => session.interrupt()}
            title="Detener ejecución del agente"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-red-400" />
            <span>Detener</span>
          </button>
        </Show>
      </div>

      {/* Área de mensajes del chat con texto seleccionable y copiable */}
      <div ref={scrollRef} data-chat-scroll class="flex-1 overflow-y-auto px-4 py-6 select-text">
        <div class="w-full max-w-3xl mx-auto space-y-4">
          <Show when={tab().messages.length === 0}>
            <div class="text-center text-zinc-400 py-16 animate-fade-in flex flex-col items-center select-none">
              {/* Wordmark vectorial de la v2 (packages/ui/src/v2/components/wordmark-v2.tsx) */}
              <Wordmark class="tui-banner" />
              <p class="mt-4 text-[13px] text-zinc-400 max-w-md">
                Entorno de ejecución y asistencia inteligente. Escribe tus instrucciones abajo o usa los comandos rápidos.
              </p>
              <div class="mt-6 flex flex-wrap gap-2 justify-center">
                <span class="px-3 py-1 rounded-full bg-white/[0.04] text-[11px] text-zinc-400 font-mono">
                  Ctrl+P · Proveedor
                </span>
                <span class="px-3 py-1 rounded-full bg-white/[0.04] text-[11px] text-zinc-400 font-mono">
                  Ctrl+M · Modelos
                </span>
                <span class="px-3 py-1 rounded-full bg-white/[0.04] text-[11px] text-zinc-400 font-mono">
                  Ctrl+` · Terminal
                </span>
              </div>
            </div>
          </Show>

          <For each={tab().messages}>
            {(m) => (
              <Show
                when={m.role === "tool"}
                fallback={
                  <Show
                    when={m.role !== "assistant" && m.role !== "terminal"}
                    fallback={
                      <Show
                        when={m.role === "terminal"}
                        fallback={
                          /* Agente: diseño minimalista en escala de grises con texto seleccionable */
                          <div class="group relative w-full text-[13.5px] leading-relaxed text-[#f4f4f5] animate-slide-up select-text">
                            <Show when={m.thinking?.trim()}>
                              <div class="thinking flex items-center gap-2 text-[12px] text-zinc-400 select-text mb-2">
                                <span class="shrink-0 text-zinc-500">
                                  <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                                    <path d="M9 5l7 7-7 7" />
                                  </svg>
                                </span>
                                <span class="min-w-0 truncate font-mono">{m.thinking}</span>
                              </div>
                            </Show>
                            <Markdown text={m.text} center streaming={m.pending} />
                            {m.pending && (
                              <span class="inline-block w-2 h-4 ml-1 rounded-full bg-zinc-400 animate-pulse align-middle" />
                            )}

                            <Show when={m.text && !m.pending}>
                              <div class="opacity-0 group-hover:opacity-100 transition-opacity duration-200 mt-1 flex justify-start">
                                <button
                                  onClick={() => copyMessage(m.id, m.text)}
                                  class="text-[11px] text-zinc-400 hover:text-white px-2 py-0.5 rounded-full bg-white/[0.04] hover:bg-white/[0.08] transition-all flex items-center gap-1"
                                  title="Copiar respuesta"
                                >
                                  <span>{copiedId() === m.id ? "✓ Copiado" : "Copiar"}</span>
                                </button>
                              </div>
                            </Show>
                          </div>
                        }
                      >
                        <div class="animate-slide-up my-2">
                          <AgentTerminal
                            tabId={props.tabId}
                            terminalId={m.terminalId ?? m.id}
                            tool={m.terminalTool}
                            command={m.terminalCommand}
                            output={m.terminalOutput ?? ""}
                            active={m.terminalActive}
                            interactive={m.terminalInteractive}
                            onInput={(text) => session.sendTerminalInput(text)}
                          />
                        </div>
                      </Show>
                    }
                  >
                    <div class={`group flex animate-slide-up ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                      <div class="relative max-w-[85%]">
                        <Show
                          when={m.role === "user" && m.queued}
                          fallback={
                            <div
                              class={`text-[13.5px] leading-relaxed transition-all select-text ${
                                m.role === "user"
                                  ? "bg-zinc-800/95 hover:bg-zinc-800 text-zinc-100 rounded-2xl rounded-br-sm px-4 py-2.5 shadow-[0_4px_16px_rgba(0,0,0,0.35)] border border-white/[0.06] whitespace-pre-wrap"
                                  : "bg-red-500/10 text-red-200 rounded-2xl p-3 whitespace-pre-wrap border border-red-500/20"
                              }`}
                            >
                              <Show when={m.role === "user" && m.agent}>
                                <div class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                                  {agents.byId(m.agent)?.name ?? m.agent}
                                </div>
                              </Show>
                              <Show when={(m.images?.length ?? 0) > 0 || (m.attachments?.filter((a) => a.kind === "image" && a.dataUrl).length ?? 0) > 0}>
                                <div class="flex flex-wrap gap-2 mb-2">
                                  <For each={m.images ?? m.attachments?.filter((a) => a.kind === "image" && a.dataUrl).map((a) => a.dataUrl!) ?? []}>
                                    {(src) => (
                                      <img
                                        src={src}
                                        alt="adjunto"
                                        class="max-w-[220px] max-h-[160px] rounded-xl border border-white/10 object-cover cursor-zoom-in"
                                        onClick={() => window.open(src, "_blank")}
                                      />
                                    )}
                                  </For>
                                </div>
                              </Show>
                              <Show when={(m.attachments?.filter((a) => a.kind === "text").length ?? 0) > 0}>
                                <div class="flex flex-wrap gap-1.5 mb-2">
                                  <For each={m.attachments?.filter((a) => a.kind === "text") ?? []}>
                                    {(a) => (
                                      <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/[0.06] text-[11px] font-mono text-zinc-300">
                                        📄 {a.name}
                                      </span>
                                    )}
                                  </For>
                                </div>
                              </Show>
                              {m.text}
                            </div>
                          }
                        >
                          {/* Burbuja elegante para mensaje en cola */}
                          <div class="bg-zinc-900/95 text-zinc-200 rounded-2xl rounded-br-sm p-3.5 shadow-[0_6px_24px_rgba(0,0,0,0.45)] border border-dashed border-amber-500/40 transition-all backdrop-blur-sm">
                            <div class="flex items-center justify-between gap-3 mb-2 pb-1.5 border-b border-white/[0.06]">
                              <div class="flex items-center gap-2">
                                <span class="inline-flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">
                                  <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                                  En cola
                                </span>
                                <Show when={m.agent}>
                                  <span class="text-[10px] font-mono text-zinc-400">
                                    {agents.byId(m.agent)?.name ?? m.agent}
                                  </span>
                                </Show>
                              </div>
                              <div class="flex items-center gap-1.5">
                                <button
                                  onClick={() => runQueuedNow(m)}
                                  class="text-[11px] text-zinc-200 hover:text-white px-2 py-0.5 rounded-full bg-white/[0.06] hover:bg-white/[0.12] transition-all font-medium"
                                  title="Ejecutar inmediatamente este mensaje encolado"
                                >
                                  Enviar ya
                                </button>
                                <button
                                  onClick={() => tabs.dequeue(props.tabId, m.id)}
                                  class="text-[11px] text-zinc-400 hover:text-red-400 px-1.5 py-0.5 rounded-full hover:bg-white/[0.06] transition-all"
                                  title="Cancelar este mensaje de la cola"
                                >
                                  ✕
                                </button>
                              </div>
                            </div>
                            <div class="text-[13.5px] leading-relaxed whitespace-pre-wrap select-text text-zinc-100">
                              <Show when={(m.images?.length ?? 0) > 0}>
                                <div class="flex flex-wrap gap-2 mb-2">
                                  <For each={m.images ?? []}>
                                    {(src) => (
                                      <img
                                        src={src}
                                        alt="adjunto"
                                        class="max-w-[220px] max-h-[160px] rounded-xl border border-white/10 object-cover"
                                      />
                                    )}
                                  </For>
                                </div>
                              </Show>
                              {m.text}
                            </div>
                          </div>
                        </Show>

                        <button
                          onClick={() => copyMessage(m.id, m.text)}
                          class="opacity-0 group-hover:opacity-100 transition-opacity duration-200 absolute -top-2.5 right-2 text-[10px] text-zinc-400 hover:text-white px-2 py-0.5 rounded-full bg-zinc-900 border border-white/[0.08] shadow-sm"
                          title="Copiar mensaje"
                        >
                          {copiedId() === m.id ? "✓" : "Copiar"}
                        </button>
                      </div>
                    </div>
                  </Show>
                }
              >
                {/* Indicador de ejecución de herramienta: solo título (ícono + acción) */}
                <div class="animate-slide-up my-1.5 w-full">
                  <ToolIndicator message={m} operating={isOperating()} />
                </div>
              </Show>
            )}
          </For>
        </div>
      </div>

      {/* Dock de entrada flotante y curvo al pie de página (tonos grises) */}
      <div class="p-4 bg-gradient-to-t from-[#090a0f] via-[#090a0f]/95 to-transparent">
        <div class="max-w-3xl mx-auto relative">
          <ChatAutocomplete
            tabId={props.tabId}
            state={autocompleteState}
            onSelectFile={handleSelectFile}
            onSelectCommand={handleSelectCommand}
            onClose={() => setAutocompleteState(null)}
            ref={(inst) => {
              autocompleteRef = inst;
            }}
          />

          <Show when={agentStatus()}>
            <p class="mb-2 text-[12px] text-amber-300/90 px-3 animate-fade-in">{agentStatus()}</p>
          </Show>

          {/* Barra flotante de estado de la cola */}
          <Show when={queuedMessages().length > 0}>
            <div class="mb-2.5 flex items-center justify-between gap-3 px-3.5 py-2 rounded-2xl bg-zinc-900/90 border border-amber-500/25 shadow-[0_4px_20px_rgba(0,0,0,0.5)] text-[12px] text-zinc-300 animate-slide-up backdrop-blur-md">
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                <span class="font-medium text-amber-200">
                  {queuedMessages().length === 1
                    ? "1 mensaje en cola"
                    : `${queuedMessages().length} mensajes en cola`}
                </span>
                <span class="text-zinc-500 text-[11px]">
                  {pausedQueue()
                    ? "· en pausa tras detención manual"
                    : "· se ejecutará en secuencia automáticamente"}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <Show when={pausedQueue()}>
                  <button
                    type="button"
                    onClick={resumeQueue}
                    class="text-[11px] font-medium text-amber-300 hover:text-white bg-amber-500/20 hover:bg-amber-500/30 px-2.5 py-0.5 rounded-full transition-all"
                  >
                    ▶ Reanudar
                  </button>
                </Show>
                <button
                  type="button"
                  onClick={() => tabs.clearQueue(props.tabId)}
                  class="text-[11px] text-zinc-400 hover:text-red-300 hover:bg-white/[0.06] px-2 py-0.5 rounded-lg transition-all"
                >
                  Vaciar cola
                </button>
              </div>
            </div>
          </Show>

          {/* Panel de seguimiento de tareas desplegable desde el input bar */}
          <TaskTrackerPanel tabId={props.tabId} />

          {/* Chips de adjuntos pendientes */}
          <Show when={attachments().length > 0}>
            <div class="flex flex-wrap gap-2 px-2 pt-1.5">
              <For each={attachments()}>
                {(a) => (
                  <div class="flex items-center gap-2 pl-1.5 pr-2 py-1 rounded-xl bg-white/[0.05] border border-white/[0.08] text-[12px] text-zinc-200 max-w-full">
                    <Show
                      when={a.kind === "image" && a.dataUrl}
                      fallback={<span class="text-[14px]">📄</span>}
                    >
                      <img src={a.dataUrl} alt={a.name} class="w-9 h-9 rounded-lg object-cover border border-white/10" />
                    </Show>
                    <div class="min-w-0 leading-tight">
                      <div class="truncate max-w-[220px] font-medium">{a.name}</div>
                      <div class="text-[10px] text-zinc-500 font-mono">
                        {a.kind === "image" ? "imagen" : "texto"} · {formatSize(a.size)}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeAttachment(a.id)}
                      class="w-5 h-5 rounded-full flex items-center justify-center text-zinc-400 hover:text-red-300 hover:bg-white/[0.08] transition-all"
                      title={`Quitar ${a.name}`}
                    >
                      ✕
                    </button>
                  </div>
                )}
              </For>
            </div>
          </Show>

          <Show when={attachError()}>
            <p class="px-3 pt-1 text-[12px] text-red-300/90">{attachError()}</p>
          </Show>

          <form
            onSubmit={submit}
            class="flex flex-col gap-0.5 px-1.5 pt-1.5 pb-1 rounded-2xl bg-zinc-900/90 hover:bg-zinc-900 focus-within:bg-zinc-900 focus-within:ring-2 focus-within:ring-white/20 border border-white/[0.08] transition-all duration-200 shadow-none"
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              class="hidden"
              onChange={(e) => {
                void addFiles(e.currentTarget.files);
                e.currentTarget.value = "";
              }}
            />
            <div class="flex items-center gap-2">
            <AgentSelector tabId={props.tabId} onSelect={() => inputRef?.focus()} />

            <button
              type="button"
              onClick={() => fileInputRef?.click()}
              title="Adjuntar texto o imagen (también puedes pegar con Ctrl+V)"
              class="w-9 h-9 shrink-0 rounded-xl bg-transparent hover:bg-white/[0.06] text-zinc-400 hover:text-white border border-transparent hover:border-white/[0.08] flex items-center justify-center transition-all active:scale-90"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
              </svg>
            </button>

            <input
              ref={inputRef}
              value={draft()}
              onInput={(e) => {
                setDraft(e.currentTarget.value);
                if (agentStatus()) setAgentStatus("");
                // El usuario editó a mano: abandona la navegación del historial.
                if (historyIndex() !== null) resetHistoryNav();
                checkAutocomplete();
              }}
              onPaste={(e) => {
                const files = e.clipboardData?.files;
                if (files && files.length > 0) {
                  e.preventDefault();
                  void addFiles(files);
                }
              }}
              onKeyDown={(e) => {
                if (autocompleteRef?.handleKeyDown(e)) {
                  return;
                }
                // Historial de solicitudes solo cuando no hay autocompletado abierto
                // (el autocompletado ya consume ↑/↓ mientras está visible).
                if (e.key === "ArrowUp" || e.key === "ArrowDown") {
                  if (autocompleteState()) return;
                  if (navigateHistory(e.key === "ArrowUp" ? -1 : 1)) {
                    e.preventDefault();
                    e.stopPropagation();
                  }
                  return;
                }
                if (e.key === "Escape" && historyIndex() !== null) {
                  const backup = historyBackup();
                  resetHistoryNav();
                  applyHistoryValue(backup);
                  e.preventDefault();
                  e.stopPropagation();
                }
              }}
              onClick={() => checkAutocomplete()}
              onKeyUp={(e) => {
                if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
                  checkAutocomplete();
                }
              }}
              placeholder={
                isOperating()
                  ? "Escribe para encolar la siguiente tarea… (Enter para encolar)"
                  : "Escribe un mensaje o tarea… (/ comandos, @ archivos, 📎 adjuntos)"
              }
              class="flex-1 bg-transparent px-3 py-2 text-[13.5px] text-white placeholder-zinc-500 outline-none select-text"
            />

            <Show
              when={isOperating()}
              fallback={
                <button
                  type="submit"
                  disabled={(!draft().trim() && attachments().length === 0) || !agentState.selected()}
                  title={
                    agentState.selected()
                      ? `Enviar con ${agentState.selected()?.name}`
                      : "Selecciona un agente disponible antes de enviar"
                  }
                  class="w-9 h-9 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-white/[0.08] flex items-center justify-center font-medium shadow-sm transition-all duration-200 active:scale-90 disabled:opacity-30 disabled:pointer-events-none"
                >
                  <svg class="w-4 h-4 fill-current rotate-45 transform -translate-x-0.5 translate-y-0.5" viewBox="0 0 20 20">
                    <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                  </svg>
                </button>
              }
            >
              <div class="flex items-center gap-1.5">
                <Show when={draft().trim() || attachments().length > 0}>
                  <button
                    type="button"
                    onClick={enqueueDraft}
                    title="Añadir a la cola (Enter)"
                    class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-white/[0.08] text-[12px] font-medium shadow-sm transition-all duration-200 active:scale-95 animate-fade-in"
                  >
                    <span class="text-amber-300 text-[11px]">⏳</span>
                    <span>Encolar</span>
                    <span class="text-[10px] text-zinc-400 font-mono">↵</span>
                  </button>
                </Show>

                <button
                  type="button"
                  onClick={handleInterrupt}
                  title="Detener ejecución del agente (Stop)"
                  class="w-9 h-9 rounded-xl bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/35 flex items-center justify-center font-medium shadow-[0_0_14px_rgba(239,68,68,0.25)] transition-all duration-200 active:scale-90"
                >
                  <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                    <rect x="5" y="5" width="14" height="14" rx="2.5" />
                  </svg>
                </button>
              </div>
            </Show>
            </div>
            {/* Barra inferior del input: carpeta actual a la izquierda, modelo a la derecha */}
            <div class="flex items-center justify-between gap-3 px-3 py-1 text-[11px] leading-none select-none">
              <Show when={workDir()} fallback={<span class="text-zinc-600">…</span>}>
                <span class="min-w-0 truncate text-zinc-500" title={workPath()}>
                  <span class="mr-1.5 text-zinc-600">📁</span>{workDir()}
                </span>
              </Show>
              <Show when={modelName()}>
                <span class="shrink-0 font-mono text-zinc-500" title={modelName()}>{modelName()}</span>
              </Show>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
