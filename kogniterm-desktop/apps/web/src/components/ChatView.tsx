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
import { ThinkingBlock } from "./ThinkingBlock";
import { DiffBlock } from "./DiffBlock";
import type { SettingsTab } from "./SettingsModals";
import {
  IconArrowDown,
  IconArrowUp,
  IconCheck,
  IconClock,
  IconClose,
  IconCopy,
  IconFile,
  IconFolder,
  IconMic,
  IconPaperclip,
  IconPlay,
  IconRefresh,
  IconSpark,
  IconStop,
} from "./Icons";

const QUICK_PROMPTS = [
  {
    title: "Explorar el proyecto",
    subtitle: "Analiza estructura, stack y archivos clave",
    prompt: "Analiza la estructura de este proyecto y explícame sus componentes principales.",
  },
  {
    title: "Revisar cambios recientes",
    subtitle: "Resume el estado actual de git y diff",
    prompt: "Revisa el estado de git (git status y últimos commits) y resume los cambios recientes.",
  },
  {
    title: "Ejecutar y diagnosticar",
    subtitle: "Corre tests o verifica que todo compile",
    prompt: "Verifica si los tests o el build del proyecto pasan correctamente.",
  },
  {
    title: "Buscar mejoras",
    subtitle: "Detecta bugs potenciales o deuda técnica",
    prompt: "Revisa el código actual en busca de posibles bugs, edge cases o mejoras claras.",
  },
];

export function ChatView(props: {
  tabId: string;
  onOpenSettings?: (tab: SettingsTab) => void;
  onToggleTerm?: () => void;
}) {
  const session = useSession(props.tabId);
  const agentState = useAgents(props.tabId);
  const [draft, setDraft] = createSignal("");
  const [agentStatus, setAgentStatus] = createSignal("");
  const [copiedId, setCopiedId] = createSignal<string | null>(null);
  const [pausedQueue, setPausedQueue] = createSignal(false);
  const [autocompleteState, setAutocompleteState] = createSignal<AutocompleteState | null>(null);
  const [showScrollBottom, setShowScrollBottom] = createSignal(false);
  const [isDragging, setIsDragging] = createSignal(false);
  const [lightboxSrc, setLightboxSrc] = createSignal<string | null>(null);
  let dragDepth = 0;
  // Navegación por historial de solicitudes del usuario (estilo shell: ↑/↓).
  const [historyIndex, setHistoryIndex] = createSignal<number | null>(null);
  const [historyBackup, setHistoryBackup] = createSignal("");
  // Adjuntos pendientes (texto o imagen) antes de enviar.
  const [attachments, setAttachments] = createSignal<ChatAttachment[]>([]);
  const [attachError, setAttachError] = createSignal("");

  // Grabación de audio / dictado por voz (faster-whisper base)
  const [isRecording, setIsRecording] = createSignal(false);
  const [isTranscribing, setIsTranscribing] = createSignal(false);
  const [recordingSeconds, setRecordingSeconds] = createSignal(0);
  const [audioError, setAudioError] = createSignal("");
  let mediaRecorder: MediaRecorder | null = null;
  let audioStream: MediaStream | null = null;
  let audioChunks: Blob[] = [];
  let recordTimer: any = null;
  let cancelRecordingRef = false;

  function formatSeconds(secs: number): string {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  }

  async function startRecording() {
    setAudioError("");
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setAudioError("El entorno no soporta captura de micrófono.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStream = stream;
      audioChunks = [];
      cancelRecordingRef = false;

      let mimeType = "";
      if (typeof MediaRecorder !== "undefined") {
        if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
          mimeType = "audio/webm;codecs=opus";
        } else if (MediaRecorder.isTypeSupported("audio/webm")) {
          mimeType = "audio/webm";
        } else if (MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")) {
          mimeType = "audio/ogg;codecs=opus";
        }
      }

      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorder = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunks.push(e.data);
        }
      };

      recorder.onstop = async () => {
        if (audioStream) {
          audioStream.getTracks().forEach((track) => track.stop());
          audioStream = null;
        }

        if (cancelRecordingRef) {
          audioChunks = [];
          setIsRecording(false);
          setRecordingSeconds(0);
          return;
        }

        const blobType = recorder.mimeType || "audio/webm";
        const audioBlob = new Blob(audioChunks, { type: blobType });
        audioChunks = [];
        setIsRecording(false);
        setRecordingSeconds(0);

        if (audioBlob.size === 0) {
          return;
        }

        setIsTranscribing(true);
        try {
          const res = await api.transcribeAudio(audioBlob);
          const text = res.text?.trim() ?? "";
          if (text) {
            setDraft((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text));
            requestAnimationFrame(() => {
              inputRef?.focus();
              const len = draft().length;
              inputRef?.setSelectionRange(len, len);
            });
          }
        } catch (err: any) {
          const msg = err?.message || "Error al transcribir audio";
          setAudioError(msg);
          setTimeout(() => setAudioError(""), 5000);
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);

      clearInterval(recordTimer);
      recordTimer = setInterval(() => {
        setRecordingSeconds((s) => s + 1);
      }, 1000);
    } catch (err: any) {
      console.error("Error al acceder al micrófono:", err);
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        setAudioError("Permiso de micrófono denegado.");
      } else {
        setAudioError("No se pudo iniciar la captura de audio.");
      }
      setTimeout(() => setAudioError(""), 5000);
    }
  }

  function stopRecording(cancelled: boolean = false) {
    cancelRecordingRef = cancelled;
    clearInterval(recordTimer);
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      try {
        mediaRecorder.stop();
      } catch {
        /* ignore */
      }
    }
    if (cancelled && audioStream) {
      audioStream.getTracks().forEach((track) => track.stop());
      audioStream = null;
      setIsRecording(false);
      setRecordingSeconds(0);
    }
  }

  function toggleRecording() {
    if (isRecording()) {
      stopRecording(false);
    } else {
      void startRecording();
    }
  }
  let scrollRef: HTMLDivElement | undefined;
  let inputRef: HTMLTextAreaElement | undefined;
  let fileInputRef: HTMLInputElement | undefined;
  let autocompleteRef: { handleKeyDown: (e: KeyboardEvent) => boolean } | undefined;
  let queueTimeout: any = null;

  function adjustTextareaHeight() {
    if (!inputRef) return;
    inputRef.style.height = "auto";
    const maxHeight = 200; // ~8-9 líneas
    const nextHeight = Math.min(inputRef.scrollHeight, maxHeight);
    inputRef.style.height = `${Math.max(nextHeight, 38)}px`;
    inputRef.style.overflowY = inputRef.scrollHeight > maxHeight ? "auto" : "hidden";
  }

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

  createEffect(() => {
    draft();
    requestAnimationFrame(() => {
      adjustTextareaHeight();
    });
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
    clearInterval(recordTimer);
    if (audioStream) {
      audioStream.getTracks().forEach((track) => track.stop());
    }
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      try {
        mediaRecorder.stop();
      } catch {
        /* ignore */
      }
    }
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

  function handleChatScroll() {
    if (!scrollRef) return;
    const dist = scrollRef.scrollHeight - scrollRef.scrollTop - scrollRef.clientHeight;
    setShowScrollBottom(dist > 200);
  }

  function scrollToBottom() {
    scrollRef?.scrollTo({ top: scrollRef.scrollHeight, behavior: "smooth" });
  }

  function applyQuickPrompt(text: string) {
    setDraft(text);
    requestAnimationFrame(() => {
      adjustTextareaHeight();
      inputRef?.focus();
      const len = text.length;
      inputRef?.setSelectionRange(len, len);
    });
  }

  function onDragEnter(e: DragEvent) {
    if (!e.dataTransfer?.types?.includes("Files")) return;
    e.preventDefault();
    dragDepth += 1;
    setIsDragging(true);
  }

  function onDragOver(e: DragEvent) {
    if (!e.dataTransfer?.types?.includes("Files")) return;
    e.preventDefault();
  }

  function onDragLeave(e: DragEvent) {
    if (!e.dataTransfer?.types?.includes("Files")) return;
    e.preventDefault();
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) setIsDragging(false);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    dragDepth = 0;
    setIsDragging(false);
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      void addFiles(files);
    }
  }

  return (
    <div
      class="flex flex-col h-full kt-canvas-bg text-[var(--kt-text-primary)] relative"
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      {/* Overlay de Drag & Drop */}
      <Show when={isDragging()}>
        <div class="absolute inset-0 z-40 flex items-center justify-center bg-black/60 backdrop-blur-md p-6 animate-fade-in pointer-events-none">
          <div class="w-full max-w-md rounded-3xl border-2 border-dashed border-[var(--kt-border-strong)] bg-[var(--kt-bg-elevated)]/90 px-8 py-12 text-center shadow-[var(--kt-shadow-lg)]">
            <div class="w-12 h-12 rounded-2xl bg-[var(--kt-bg-active)] flex items-center justify-center mx-auto mb-3 text-[var(--kt-text-primary)]">
              <IconPaperclip size={22} />
            </div>
            <p class="text-[15px] font-semibold text-[var(--kt-text-primary)]">Suelta tus archivos aquí</p>
            <p class="text-[12.5px] text-[var(--kt-text-muted)] mt-1">
              Imágenes, código o texto se adjuntarán al mensaje actual.
            </p>
          </div>
        </div>
      </Show>

      {/* Lightbox para vista previa de imágenes */}
      <Show when={lightboxSrc()}>
        {(src) => (
          <div
            class="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-xl p-6 animate-fade-in"
            onClick={() => setLightboxSrc(null)}
          >
            <button
              type="button"
              onClick={() => setLightboxSrc(null)}
              class="absolute top-5 right-5 w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition-all"
              title="Cerrar vista previa"
            >
              <IconClose size={16} />
            </button>
            <img
              src={src()}
              alt="Vista previa"
              class="max-w-[90vw] max-h-[86vh] rounded-2xl shadow-2xl border border-white/10 object-contain animate-scale-in"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        )}
      </Show>

      {/* Sub-barra de estado de sesión */}
      <div class="flex items-center gap-2 px-4 py-1.5 text-[11.5px] text-[var(--kt-text-muted)] border-b border-[var(--kt-border-subtle)] bg-[var(--kt-bg-app)]/50 select-none shrink-0">
        <div class="flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-[var(--kt-bg-hover)] border border-[var(--kt-border-subtle)]">
          <span
            class={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
              session.conn() === "open"
                ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]"
                : session.conn() === "connecting"
                  ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.7)] animate-pulse"
                  : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.7)]"
            }`}
          />
          <span class="font-mono text-[var(--kt-text-secondary)] text-[11px] max-w-[160px] truncate">{props.tabId}</span>
          <span class="opacity-40">·</span>
          <span class="text-[var(--kt-text-muted)] text-[11px]">
            {session.conn() === "open"
              ? "conectado"
              : session.conn() === "connecting"
                ? "conectando"
                : "desconectado"}
          </span>
        </div>

        <Show when={workDir()}>
          <div
            class="hidden sm:flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[var(--kt-bg-hover)] border border-[var(--kt-border-subtle)] max-w-[260px]"
            title={workPath()}
          >
            <IconFolder size={11} class="text-[var(--kt-text-faint)] shrink-0" />
            <span class="font-mono text-[11px] text-[var(--kt-text-muted)] truncate">{workDir()}</span>
          </div>
        </Show>

        <div class="flex-1" />

        <button
          class="w-6 h-6 rounded-lg flex items-center justify-center hover:bg-[var(--kt-bg-hover)] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] transition-all"
          onClick={() => session.reconnect()}
          title="Reconectar WebSocket"
        >
          <IconRefresh size={12} />
        </button>

        <Show when={isOperating()}>
          <button
            class="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-red-500/15 text-red-300 hover:bg-red-500/25 border border-red-500/25 shadow-sm transition-all active:scale-95"
            onClick={() => session.interrupt()}
            title="Detener ejecución del agente"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
            <span>Detener</span>
          </button>
        </Show>
      </div>

      {/* Área de mensajes del chat */}
      <div
        ref={scrollRef}
        data-chat-scroll
        onScroll={handleChatScroll}
        class="flex-1 overflow-y-auto px-4 sm:px-6 py-6 select-text relative"
      >
        <div class="w-full max-w-3xl mx-auto space-y-5">
          <Show when={tab().messages.length === 0}>
            <div class="text-center py-10 sm:py-14 animate-fade-in flex flex-col items-center select-none">
              <Wordmark class="tui-banner" />
              <p class="mt-3 text-[13.5px] text-[var(--kt-text-muted)] max-w-md leading-relaxed">
                Estación de trabajo inteligente para código, shell y agentes autónomos.
              </p>

              {/* Tarjetas de inicio rápido */}
              <div class="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-xl text-left">
                <For each={QUICK_PROMPTS}>
                  {(item) => (
                    <button
                      type="button"
                      onClick={() => applyQuickPrompt(item.prompt)}
                      class="group p-3.5 rounded-2xl kt-card hover:border-[var(--kt-border-strong)] hover:bg-[var(--kt-bg-elevated)] transition-all duration-150 active:scale-[0.985] text-left"
                    >
                      <div class="flex items-center justify-between gap-2">
                        <span class="text-[13px] font-semibold text-[var(--kt-text-primary)]">
                          {item.title}
                        </span>
                        <IconArrowUp
                          size={13}
                          class="rotate-45 text-[var(--kt-text-faint)] group-hover:text-[var(--kt-text-primary)] group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all"
                        />
                      </div>
                      <p class="text-[11.5px] text-[var(--kt-text-muted)] mt-1 leading-snug">
                        {item.subtitle}
                      </p>
                    </button>
                  )}
                </For>
              </div>

              {/* Atajos interactivos */}
              <div class="mt-6 flex flex-wrap gap-2 justify-center">
                <button
                  type="button"
                  onClick={() => props.onOpenSettings?.("provider")}
                  class="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] border border-[var(--kt-border-subtle)] text-[11px] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] transition-all"
                >
                  <kbd class="kt-kbd">Ctrl+P</kbd>
                  <span>Proveedor</span>
                </button>
                <button
                  type="button"
                  onClick={() => props.onOpenSettings?.("models")}
                  class="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] border border-[var(--kt-border-subtle)] text-[11px] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] transition-all"
                >
                  <kbd class="kt-kbd">Ctrl+M</kbd>
                  <span>Modelos</span>
                </button>
                <button
                  type="button"
                  onClick={() => props.onToggleTerm?.()}
                  class="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] border border-[var(--kt-border-subtle)] text-[11px] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] transition-all"
                >
                  <kbd class="kt-kbd">Ctrl+`</kbd>
                  <span>Terminal</span>
                </button>
              </div>
            </div>
          </Show>

          <For each={tab().messages}>
            {(m) => (
              <Show
                when={m.role === "diff"}
                fallback={
                  <Show
                    when={m.role === "tool"}
                    fallback={
                      <Show
                        when={m.role !== "assistant" && m.role !== "terminal"}
                        fallback={
                          <Show
                            when={m.role === "terminal"}
                            fallback={
                              /* Respuesta del asistente: diseño editorial limpio */
                              <div class="group relative w-full text-[14px] leading-relaxed text-[var(--kt-text-primary)] animate-slide-up select-text">
                                <div class="flex items-center gap-2 mb-1.5 select-none">
                                  <span class="w-5 h-5 rounded-lg bg-[var(--kt-bg-hover)] border border-[var(--kt-border-subtle)] flex items-center justify-center text-[var(--kt-text-muted)]">
                                    <IconSpark size={11} />
                                  </span>
                                  <span class="text-[11.5px] font-semibold tracking-tight text-[var(--kt-text-muted)]">
                                    {m.agent ? (agents.byId(m.agent)?.name ?? m.agent) : "KogniTerm"}
                                  </span>
                                  <Show when={m.pending}>
                                    <span class="text-[10.5px] font-mono text-amber-400/90 animate-pulse">
                                      escribiendo…
                                    </span>
                                  </Show>
                                </div>

                                <div class="pl-7">
                                  <Show when={m.thinking?.trim()}>
                                    <ThinkingBlock text={m.thinking} pending={m.pending} />
                                  </Show>
                                  <Markdown text={m.text} streaming={m.pending} />
                                  {m.pending && (
                                    <span class="inline-block w-1.5 h-4 ml-1 rounded-full bg-[var(--kt-text-muted)] animate-pulse align-middle" />
                                  )}

                                  <Show when={m.text && !m.pending}>
                                    <div class="opacity-0 group-hover:opacity-100 transition-opacity duration-150 mt-2 flex justify-start">
                                      <button
                                        onClick={() => copyMessage(m.id, m.text)}
                                        class="text-[11px] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] px-2.5 py-1 rounded-full bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] border border-[var(--kt-border-subtle)] transition-all flex items-center gap-1.5"
                                        title="Copiar respuesta"
                                      >
                                        <Show when={copiedId() === m.id} fallback={<IconCopy size={11} />}>
                                          <IconCheck size={11} class="text-emerald-400" />
                                        </Show>
                                        <span>{copiedId() === m.id ? "Copiado" : "Copiar"}</span>
                                      </button>
                                    </div>
                                  </Show>
                                </div>
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
                          <div class="relative max-w-[84%]">
                            <Show
                              when={m.role === "user" && m.queued}
                              fallback={
                                <div
                                  class={`text-[13.5px] leading-relaxed transition-all select-text ${
                                    m.role === "user"
                                      ? "bg-[var(--kt-user-bubble)] text-[var(--kt-text-primary)] rounded-2xl rounded-br-md px-4 py-2.5 shadow-[var(--kt-shadow-sm)] border border-[var(--kt-user-bubble-border)] whitespace-pre-wrap"
                                      : "bg-red-500/10 text-red-200 rounded-2xl p-3.5 whitespace-pre-wrap border border-red-500/25"
                                  }`}
                                >
                                  <Show when={m.role === "user" && m.agent}>
                                    <div class="mb-1 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--kt-bg-hover)] text-[10px] font-semibold uppercase tracking-wider text-[var(--kt-text-muted)]">
                                      {agents.byId(m.agent)?.name ?? m.agent}
                                    </div>
                                  </Show>
                                  <Show
                                    when={
                                      (m.images?.length ?? 0) > 0 ||
                                      (m.attachments?.filter((a) => a.kind === "image" && a.dataUrl).length ?? 0) > 0
                                    }
                                  >
                                    <div class="flex flex-wrap gap-2 mb-2">
                                      <For
                                        each={
                                          m.images ??
                                          m.attachments?.filter((a) => a.kind === "image" && a.dataUrl).map((a) => a.dataUrl!) ??
                                          []
                                        }
                                      >
                                        {(src) => (
                                          <img
                                            src={src}
                                            alt="adjunto"
                                            class="max-w-[220px] max-h-[160px] rounded-xl border border-[var(--kt-border-default)] object-cover cursor-zoom-in hover:opacity-90 transition-opacity"
                                            onClick={() => setLightboxSrc(src)}
                                          />
                                        )}
                                      </For>
                                    </div>
                                  </Show>
                                  <Show when={(m.attachments?.filter((a) => a.kind === "text").length ?? 0) > 0}>
                                    <div class="flex flex-wrap gap-1.5 mb-2">
                                      <For each={m.attachments?.filter((a) => a.kind === "text") ?? []}>
                                        {(a) => (
                                          <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[var(--kt-bg-hover)] border border-[var(--kt-border-subtle)] text-[11px] font-mono text-[var(--kt-text-secondary)]">
                                            <IconFile size={11} />
                                            <span>{a.name}</span>
                                          </span>
                                        )}
                                      </For>
                                    </div>
                                  </Show>
                                  {m.text}
                                </div>
                              }
                            >
                              {/* Burbuja para mensaje en cola */}
                              <div class="bg-[var(--kt-bg-elevated)] text-[var(--kt-text-primary)] rounded-2xl rounded-br-md p-3.5 shadow-[var(--kt-shadow-md)] border border-dashed border-amber-500/45 transition-all">
                                <div class="flex items-center justify-between gap-3 mb-2 pb-1.5 border-b border-[var(--kt-border-subtle)]">
                                  <div class="flex items-center gap-2">
                                    <span class="inline-flex items-center gap-1.5 text-[10.5px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">
                                      <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                                      En cola
                                    </span>
                                    <Show when={m.agent}>
                                      <span class="text-[10.5px] font-mono text-[var(--kt-text-muted)]">
                                        {agents.byId(m.agent)?.name ?? m.agent}
                                      </span>
                                    </Show>
                                  </div>
                                  <div class="flex items-center gap-1.5">
                                    <button
                                      onClick={() => runQueuedNow(m)}
                                      class="text-[11px] text-[var(--kt-text-primary)] px-2.5 py-0.5 rounded-full bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] border border-[var(--kt-border-subtle)] transition-all font-medium"
                                      title="Ejecutar inmediatamente este mensaje encolado"
                                    >
                                      Enviar ya
                                    </button>
                                    <button
                                      onClick={() => tabs.dequeue(props.tabId, m.id)}
                                      class="w-6 h-6 rounded-full flex items-center justify-center text-[var(--kt-text-muted)] hover:text-red-300 hover:bg-red-500/15 transition-all"
                                      title="Cancelar este mensaje de la cola"
                                    >
                                      <IconClose size={11} />
                                    </button>
                                  </div>
                                </div>
                                <div class="text-[13.5px] leading-relaxed whitespace-pre-wrap select-text">
                                  <Show when={(m.images?.length ?? 0) > 0}>
                                    <div class="flex flex-wrap gap-2 mb-2">
                                      <For each={m.images ?? []}>
                                        {(src) => (
                                          <img
                                            src={src}
                                            alt="adjunto"
                                            class="max-w-[220px] max-h-[160px] rounded-xl border border-[var(--kt-border-default)] object-cover cursor-zoom-in"
                                            onClick={() => setLightboxSrc(src)}
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
                              class="opacity-0 group-hover:opacity-100 transition-opacity duration-150 absolute -top-2.5 right-2 text-[10.5px] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] px-2 py-0.5 rounded-full bg-[var(--kt-bg-elevated)] border border-[var(--kt-border-default)] shadow-sm flex items-center gap-1"
                              title="Copiar mensaje"
                            >
                              <Show when={copiedId() === m.id} fallback={<IconCopy size={10} />}>
                                <IconCheck size={10} class="text-emerald-400" />
                              </Show>
                              <span>{copiedId() === m.id ? "Copiado" : "Copiar"}</span>
                            </button>
                          </div>
                        </div>
                      </Show>
                    }
                  >
                    <div class="animate-slide-up my-1 w-full pl-7">
                      <ToolIndicator message={m} operating={isOperating()} />
                    </div>
                  </Show>
                }
              >
                <div class="pl-0 sm:pl-7">
                  <DiffBlock diff={m.diffContent ?? ""} filePath={m.diffFilePath} operation={m.diffOperation} />
                </div>
              </Show>
            )}
          </For>
        </div>
      </div>

      {/* Botón flotante para volver al final */}
      <Show when={showScrollBottom()}>
        <div class="pointer-events-none absolute bottom-36 left-0 right-0 flex justify-center z-20 animate-fade-in">
          <button
            type="button"
            onClick={scrollToBottom}
            class="pointer-events-auto flex items-center gap-1.5 px-3.5 py-1.5 rounded-full glass-dropdown text-[12px] font-medium text-[var(--kt-text-primary)] hover:scale-105 active:scale-95 transition-all"
            title="Ir al último mensaje"
          >
            <IconArrowDown size={13} />
            <span>Ir al final</span>
          </button>
        </div>
      </Show>

      {/* Dock de entrada flotante */}
      <div class="px-4 pb-4 pt-2 kt-dock-fade shrink-0">
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
            <p class="mb-2 text-[12px] text-amber-300 px-3 animate-fade-in">{agentStatus()}</p>
          </Show>

          {/* Barra flotante de estado de la cola */}
          <Show when={queuedMessages().length > 0}>
            <div class="mb-2.5 flex items-center justify-between gap-3 px-3.5 py-2 rounded-2xl kt-card border-amber-500/30 text-[12px] text-[var(--kt-text-secondary)] animate-slide-up">
              <div class="flex items-center gap-2 min-w-0">
                <span class="w-2 h-2 rounded-full bg-amber-400 animate-pulse shrink-0" />
                <span class="font-medium text-amber-300 shrink-0">
                  {queuedMessages().length === 1
                    ? "1 mensaje en cola"
                    : `${queuedMessages().length} mensajes en cola`}
                </span>
                <span class="text-[var(--kt-text-faint)] text-[11px] truncate hidden sm:inline">
                  {pausedQueue()
                    ? "· en pausa tras detención manual"
                    : "· se ejecutará en secuencia automáticamente"}
                </span>
              </div>
              <div class="flex items-center gap-2 shrink-0">
                <Show when={pausedQueue()}>
                  <button
                    type="button"
                    onClick={resumeQueue}
                    class="flex items-center gap-1 text-[11px] font-medium text-amber-300 bg-amber-500/20 hover:bg-amber-500/30 px-2.5 py-1 rounded-full transition-all"
                  >
                    <IconPlay size={10} />
                    <span>Reanudar</span>
                  </button>
                </Show>
                <button
                  type="button"
                  onClick={() => tabs.clearQueue(props.tabId)}
                  class="text-[11px] text-[var(--kt-text-muted)] hover:text-red-300 hover:bg-[var(--kt-bg-hover)] px-2 py-1 rounded-lg transition-all"
                >
                  Vaciar
                </button>
              </div>
            </div>
          </Show>

          {/* Panel de seguimiento de tareas */}
          <TaskTrackerPanel tabId={props.tabId} />

          {/* Chips de adjuntos pendientes */}
          <Show when={attachments().length > 0}>
            <div class="flex flex-wrap gap-2 px-1 pb-2">
              <For each={attachments()}>
                {(a) => (
                  <div class="flex items-center gap-2 pl-1.5 pr-2 py-1 rounded-xl kt-card text-[12px] text-[var(--kt-text-primary)] max-w-full animate-scale-in">
                    <Show
                      when={a.kind === "image" && a.dataUrl}
                      fallback={
                        <span class="w-8 h-8 rounded-lg bg-[var(--kt-bg-hover)] flex items-center justify-center text-[var(--kt-text-muted)]">
                          <IconFile size={14} />
                        </span>
                      }
                    >
                      <img
                        src={a.dataUrl}
                        alt={a.name}
                        class="w-8 h-8 rounded-lg object-cover border border-[var(--kt-border-subtle)] cursor-zoom-in"
                        onClick={() => setLightboxSrc(a.dataUrl!)}
                      />
                    </Show>
                    <div class="min-w-0 leading-tight">
                      <div class="truncate max-w-[200px] font-medium text-[12px]">{a.name}</div>
                      <div class="text-[10px] text-[var(--kt-text-faint)] font-mono">
                        {a.kind === "image" ? "imagen" : "texto"} · {formatSize(a.size)}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeAttachment(a.id)}
                      class="w-5 h-5 rounded-full flex items-center justify-center text-[var(--kt-text-faint)] hover:text-red-300 hover:bg-red-500/15 transition-all"
                      title={`Quitar ${a.name}`}
                    >
                      <IconClose size={11} />
                    </button>
                  </div>
                )}
              </For>
            </div>
          </Show>

          <Show when={attachError()}>
            <p class="px-3 pb-1.5 text-[12px] text-red-300">{attachError()}</p>
          </Show>

          {/* Indicador de grabación de audio */}
          <Show when={isRecording()}>
            <div class="mb-2 flex items-center justify-between px-3.5 py-2 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-300 animate-fade-in">
              <div class="flex items-center gap-2.5">
                <div class="flex items-center gap-0.5 h-3.5" aria-hidden="true">
                  <span class="w-0.5 h-full bg-red-400 rounded-full voice-bar" style={{ "animation-delay": "0ms" }} />
                  <span class="w-0.5 h-full bg-red-400 rounded-full voice-bar" style={{ "animation-delay": "150ms" }} />
                  <span class="w-0.5 h-full bg-red-400 rounded-full voice-bar" style={{ "animation-delay": "300ms" }} />
                  <span class="w-0.5 h-full bg-red-400 rounded-full voice-bar" style={{ "animation-delay": "450ms" }} />
                </div>
                <span class="font-medium tabular-nums">Grabando ({formatSeconds(recordingSeconds())})</span>
                <span class="text-[var(--kt-text-muted)] hidden sm:inline">· Faster-Whisper base</span>
              </div>
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => stopRecording(false)}
                  class="px-2.5 py-1 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-200 border border-red-500/40 font-medium text-[11px] transition-all"
                >
                  Transcribir (↵)
                </button>
                <button
                  type="button"
                  onClick={() => stopRecording(true)}
                  class="px-2.5 py-1 rounded-lg bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] text-[var(--kt-text-secondary)] border border-[var(--kt-border-subtle)] text-[11px] transition-all"
                >
                  Cancelar (Esc)
                </button>
              </div>
            </div>
          </Show>

          {/* Indicador de transcripción */}
          <Show when={isTranscribing()}>
            <div class="mb-2 flex items-center gap-2 px-3.5 py-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300">
              <svg class="w-3.5 h-3.5 animate-spin text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <span>Transcribiendo audio con Faster-Whisper base…</span>
            </div>
          </Show>

          <Show when={audioError()}>
            <div class="mb-2 flex items-center justify-between px-3.5 py-2 rounded-xl bg-red-500/15 border border-red-500/30 text-xs text-red-300">
              <span class="truncate">{audioError()}</span>
              <button type="button" onClick={() => setAudioError("")} class="ml-2 hover:opacity-75">
                <IconClose size={12} />
              </button>
            </div>
          </Show>

          {/* Compositor principal */}
          <form onSubmit={submit} class="kt-composer rounded-2xl p-2 transition-all duration-200">
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

            <textarea
              ref={inputRef}
              rows={1}
              value={draft()}
              onInput={(e) => {
                setDraft(e.currentTarget.value);
                adjustTextareaHeight();
                if (agentStatus()) setAgentStatus("");
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
                if (isRecording()) {
                  if (e.key === "Escape") {
                    e.preventDefault();
                    stopRecording(true);
                    return;
                  }
                  if (e.key === "Enter") {
                    e.preventDefault();
                    stopRecording(false);
                    return;
                  }
                }
                if (autocompleteRef?.handleKeyDown(e)) {
                  return;
                }
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                  return;
                }
                if (e.key === "ArrowUp" || e.key === "ArrowDown") {
                  if (autocompleteState()) return;
                  const el = inputRef;
                  if (el) {
                    const hasNewlines = draft().includes("\n");
                    if (e.key === "ArrowUp" && hasNewlines && (el.selectionStart ?? 0) > 0) {
                      return;
                    }
                    if (e.key === "ArrowDown" && hasNewlines && (el.selectionEnd ?? 0) < draft().length) {
                      return;
                    }
                  }
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
                isRecording()
                  ? "Habla ahora… presiona Enter o clic en el micrófono para transcribir"
                  : isTranscribing()
                    ? "Transcribiendo tu voz con faster-whisper base…"
                    : isOperating()
                      ? "Escribe para encolar la siguiente tarea… (Enter para encolar)"
                      : "Escribe una instrucción… (/ comandos, @ archivos, arrastra o pega imágenes)"
              }
              class="w-full bg-transparent px-2.5 pt-1 pb-2 text-[13.5px] text-[var(--kt-text-primary)] placeholder-[var(--kt-text-faint)] outline-none select-text resize-none min-h-[38px] max-h-[200px] leading-relaxed"
            />

            {/* Barra inferior de herramientas dentro del compositor */}
            <div class="flex items-center justify-between gap-2 pt-1.5 border-t border-[var(--kt-border-subtle)] select-none">
              <div class="flex items-center gap-1 min-w-0">
                <AgentSelector tabId={props.tabId} onSelect={() => inputRef?.focus()} />

                <button
                  type="button"
                  onClick={() => fileInputRef?.click()}
                  title="Adjuntar texto o imagen (también puedes arrastrar o pegar con Ctrl+V)"
                  class="w-8 h-8 shrink-0 rounded-xl bg-transparent hover:bg-[var(--kt-bg-hover)] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] flex items-center justify-center transition-all active:scale-90"
                >
                  <IconPaperclip size={15} />
                </button>

                <button
                  type="button"
                  onClick={toggleRecording}
                  disabled={isTranscribing()}
                  title={
                    isRecording()
                      ? `Detener grabación y transcribir (${formatSeconds(recordingSeconds())})`
                      : isTranscribing()
                        ? "Transcribiendo con Faster-Whisper base…"
                        : "Dictar por voz (Faster-Whisper base)"
                  }
                  class={`w-8 h-8 shrink-0 rounded-xl flex items-center justify-center transition-all active:scale-90 ${
                    isRecording()
                      ? "bg-red-500/20 text-red-400 border border-red-500/40 shadow-[0_0_12px_rgba(239,68,68,0.35)] animate-pulse"
                      : isTranscribing()
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30 cursor-wait"
                        : "bg-transparent hover:bg-[var(--kt-bg-hover)] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)]"
                  }`}
                >
                  <Show
                    when={!isTranscribing()}
                    fallback={
                      <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                      </svg>
                    }
                  >
                    <Show
                      when={!isRecording()}
                      fallback={<span class="w-2.5 h-2.5 rounded-full bg-red-400" />}
                    >
                      <IconMic size={15} />
                    </Show>
                  </Show>
                </button>
              </div>

              <div class="flex items-center gap-2 shrink-0">
                <Show when={workDir()}>
                  <span
                    class="hidden sm:inline-flex items-center gap-1 text-[11px] text-[var(--kt-text-faint)] max-w-[140px] truncate"
                    title={workPath()}
                  >
                    <IconFolder size={11} class="shrink-0" />
                    <span class="truncate">{workDir()}</span>
                  </span>
                </Show>
                <Show when={modelName()}>
                  <button
                    type="button"
                    onClick={() => props.onOpenSettings?.("models")}
                    class="hidden md:inline-block font-mono text-[11px] text-[var(--kt-text-faint)] hover:text-[var(--kt-text-secondary)] max-w-[150px] truncate transition-colors"
                    title={`${modelName()} — clic para cambiar modelo`}
                  >
                    {modelName()}
                  </button>
                </Show>

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
                      class="w-8 h-8 rounded-xl bg-[var(--kt-btn-primary-bg)] hover:bg-[var(--kt-btn-primary-hover)] text-[var(--kt-btn-primary-text)] flex items-center justify-center shadow-sm transition-all duration-150 active:scale-90 disabled:opacity-25 disabled:pointer-events-none"
                    >
                      <IconArrowUp size={16} />
                    </button>
                  }
                >
                  <div class="flex items-center gap-1.5">
                    <Show when={draft().trim() || attachments().length > 0}>
                      <button
                        type="button"
                        onClick={enqueueDraft}
                        title="Añadir a la cola (Enter)"
                        class="flex items-center gap-1.5 h-8 px-3 rounded-xl bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] text-[var(--kt-text-primary)] border border-[var(--kt-border-default)] text-[11.5px] font-medium transition-all active:scale-95 animate-fade-in"
                      >
                        <IconClock size={12} class="text-amber-300" />
                        <span>Encolar</span>
                      </button>
                    </Show>

                    <button
                      type="button"
                      onClick={handleInterrupt}
                      title="Detener ejecución del agente"
                      class="w-8 h-8 rounded-xl bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/35 flex items-center justify-center shadow-[0_0_14px_rgba(239,68,68,0.2)] transition-all active:scale-90"
                    >
                      <IconStop size={13} />
                    </button>
                  </div>
                </Show>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
