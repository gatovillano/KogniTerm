import { For, Show, createEffect, createSignal, onCleanup, onMount } from "solid-js";
import { WorkspaceFileItem, api } from "../lib/api";

export interface AutocompleteState {
  type: "file" | "command";
  query: string;
  start: number;
  end: number;
}

export interface AutocompleteCommand {
  name: string;
  trigger: string;
  description: string;
  category: string;
  icon: string;
}

export const BUILTIN_COMMANDS: AutocompleteCommand[] = [
  { name: "/help", trigger: "help", description: "Mostrar menú de comandos y ayuda interactiva", category: "Ayuda", icon: "❓" },
  { name: "/reset", trigger: "reset", description: "Reiniciar conversación y memoria del agente", category: "Sesión", icon: "🔄" },
  { name: "/clear", trigger: "clear", description: "Limpiar la vista y reiniciar la conversación", category: "Sesión", icon: "🧹" },
  { name: "/undo", trigger: "undo", description: "Deshacer la última interacción / pregunta y respuesta", category: "Historial", icon: "↩️" },
  { name: "/compact", trigger: "compact", description: "Comprimir y resumir historial de conversación", category: "Contexto", icon: "📦" },
  { name: "/compress", trigger: "compress", description: "Comprimir historial de contexto (alias)", category: "Contexto", icon: "🗜️" },
  { name: "/skills", trigger: "skills", description: "Listar todas las habilidades (skills) disponibles", category: "Herramientas", icon: "🛠️" },
  { name: "/models", trigger: "models", description: "Ver o cambiar modelo LLM activo", category: "Modelo", icon: "🤖" },
  { name: "/provider", trigger: "provider", description: "Información del proveedor LLM configurado", category: "Modelo", icon: "🌐" },
  { name: "/plan", trigger: "plan", description: "Ver o alternar modo de planificación de tareas", category: "Agente", icon: "📋" },
  { name: "/init", trigger: "init", description: "Re-indexar archivos del espacio de trabajo", category: "Workspace", icon: "🔍" },
  { name: "/index", trigger: "index", description: "Re-indexar archivos del workspace (alias)", category: "Workspace", icon: "⚡" },
  { name: "/mcp", trigger: "mcp", description: "Gestionar servidores y herramientas MCP", category: "Herramientas", icon: "🔌" },
  { name: "/session", trigger: "session", description: "Listar y gestionar sesiones guardadas", category: "Sesión", icon: "🧵" },
  { name: "/resume", trigger: "resume", description: "Reanudar una sesión guardada (/resume <id>)", category: "Sesión", icon: "📂" },
  { name: "/theme", trigger: "theme", description: "Cambiar tema de colores visual de la terminal", category: "Ajustes", icon: "🎨" },
  { name: "/instructions", trigger: "instructions", description: "Ver o editar instrucciones del agente", category: "Agente", icon: "📝" },
  { name: "/keys", trigger: "keys", description: "Configurar API keys de proveedores", category: "Config", icon: "🔑" },
  { name: "/config", trigger: "config", description: "Ver configuración del sistema", category: "Config", icon: "⚙️" },
];

export function getFileIcon(isDir: boolean, path: string, meta?: string): string {
  if (isDir) return "📁";
  const ext = path.slice(path.lastIndexOf(".")).toLowerCase();
  if (ext === ".py") return "🐍";
  if ([".ts", ".tsx", ".js", ".jsx"].includes(ext)) return "🌐";
  if ([".json", ".yaml", ".yml", ".toml", ".ini", ".env"].includes(ext)) return "⚙️";
  if ([".md", ".rst", ".txt", ".doc"].includes(ext)) return "📝";
  if ([".sh", ".bash", ".zsh"].includes(ext)) return "🖥️";
  if ([".html", ".css", ".scss"].includes(ext)) return "🎨";
  if ([".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"].includes(ext)) return "🖼️";
  if (meta && meta.includes(" ")) return meta.split(" ")[0];
  return "📄";
}

export interface ChatAutocompleteProps {
  tabId: string;
  state: () => AutocompleteState | null;
  onSelectFile: (file: WorkspaceFileItem) => void;
  onSelectCommand: (cmd: AutocompleteCommand) => void;
  onClose: () => void;
  ref?: (instance: { handleKeyDown: (e: KeyboardEvent) => boolean }) => void;
}

export function ChatAutocomplete(props: ChatAutocompleteProps) {
  const [selectedIndex, setSelectedIndex] = createSignal(0);
  const [fileResults, setFileResults] = createSignal<WorkspaceFileItem[]>([]);
  const [commandsList, setCommandsList] = createSignal<AutocompleteCommand[]>(BUILTIN_COMMANDS);
  const [loading, setLoading] = createSignal(false);
  let listRef: HTMLDivElement | undefined;
  let debounceTimer: any = null;

  // Cargar comandos dinámicos desde backend al montar
  onMount(() => {
    void (async () => {
      try {
        const remoteCmds = await api.listCommands();
        if (remoteCmds && remoteCmds.length > 0) {
          const map = new Map<string, AutocompleteCommand>();
          for (const c of BUILTIN_COMMANDS) {
            map.set(c.trigger.toLowerCase(), c);
          }
          for (const rc of remoteCmds) {
            const trigger = (rc.name || rc.id).replace(/^\//, "").toLowerCase();
            if (!map.has(trigger)) {
              map.set(trigger, {
                name: `/${trigger}`,
                trigger,
                description: rc.description || `Comando /${trigger}`,
                category: rc.category || "Sistema",
                icon: "⚡",
              });
            }
          }
          setCommandsList(Array.from(map.values()));
        }
      } catch {
        // Fallback a BUILTIN_COMMANDS
      }
    })();
  });

  // Filtrado de comandos según la query
  const filteredCommands = () => {
    const s = props.state();
    if (!s || s.type !== "command") return [];
    const q = s.query.toLowerCase().trim();
    if (!q) return commandsList();
    return commandsList().filter(
      (c) =>
        c.trigger.toLowerCase().includes(q) ||
        c.name.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q),
    );
  };

  // Búsqueda de archivos debounced según la query
  createEffect(() => {
    const s = props.state();
    if (!s || s.type !== "file") {
      setFileResults([]);
      setLoading(false);
      return;
    }

    const q = s.query;
    setLoading(true);
    if (debounceTimer) clearTimeout(debounceTimer);

    debounceTimer = setTimeout(async () => {
      try {
        const resp = await api.searchFiles(q, props.tabId, 25);
        if (props.state()?.type === "file") {
          setFileResults(resp.results || []);
          setSelectedIndex(0);
        }
      } catch {
        if (props.state()?.type === "file") {
          setFileResults([]);
        }
      } finally {
        setLoading(false);
      }
    }, 120);
  });

  onCleanup(() => {
    if (debounceTimer) clearTimeout(debounceTimer);
  });

  // Reset selected index cuando cambia el tipo o los comandos
  createEffect(() => {
    props.state()?.query;
    setSelectedIndex(0);
  });

  // Auto-scroll al elemento seleccionado
  createEffect(() => {
    const idx = selectedIndex();
    if (!listRef) return;
    const el = listRef.children[idx] as HTMLElement | undefined;
    if (el) {
      el.scrollIntoView({ block: "nearest" });
    }
  });

  const currentItems = () => {
    const s = props.state();
    if (!s) return [];
    if (s.type === "file") return fileResults();
    return filteredCommands();
  };

  function selectCurrent() {
    const s = props.state();
    if (!s) return;
    const items = currentItems();
    const idx = selectedIndex();
    if (items.length === 0 || idx < 0 || idx >= items.length) return;

    if (s.type === "file") {
      props.onSelectFile(items[idx] as WorkspaceFileItem);
    } else {
      props.onSelectCommand(items[idx] as AutocompleteCommand);
    }
  }

  function handleKeyDown(e: KeyboardEvent): boolean {
    const s = props.state();
    if (!s) return false;

    const items = currentItems();

    if (e.key === "ArrowDown") {
      e.preventDefault();
      e.stopPropagation();
      if (items.length > 0) {
        setSelectedIndex((prev) => (prev + 1) % items.length);
      }
      return true;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      e.stopPropagation();
      if (items.length > 0) {
        setSelectedIndex((prev) => (prev - 1 + items.length) % items.length);
      }
      return true;
    }

    if (e.key === "Enter" || e.key === "Tab") {
      if (items.length > 0) {
        e.preventDefault();
        e.stopPropagation();
        selectCurrent();
        return true;
      }
    }

    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      props.onClose();
      return true;
    }

    return false;
  }

  // Exponer handleKeyDown mediante ref
  if (props.ref) {
    props.ref({ handleKeyDown });
  }

  return (
    <Show when={props.state()}>
      <div
        class="absolute bottom-full mb-3 left-0 right-0 z-50 overflow-hidden rounded-2xl bg-zinc-900/95 border border-white/10 shadow-[0_-12px_40px_rgba(0,0,0,0.7)] backdrop-blur-xl animate-slide-up select-none max-w-3xl mx-auto"
        onMouseDown={(e) => e.preventDefault()}
      >
        {/* Cabecera del Autocompletado */}
        <div class="flex items-center justify-between px-3.5 py-2 border-b border-white/[0.06] bg-white/[0.02] text-[11.5px] text-zinc-400">
          <div class="flex items-center gap-2">
            <Show
              when={props.state()?.type === "file"}
              fallback={
                <span class="flex items-center gap-1.5 font-medium text-emerald-400">
                  <span>⚡</span>
                  <span>Comandos KogniTerm</span>
                </span>
              }
            >
              <span class="flex items-center gap-1.5 font-medium text-indigo-400">
                <span>📁</span>
                <span>Archivos del Workspace</span>
              </span>
            </Show>
            <Show when={props.state()?.query}>
              <span class="px-1.5 py-0.2 rounded bg-white/[0.05] text-[11px] font-mono text-zinc-300">
                {props.state()?.query}
              </span>
            </Show>
          </div>

          <div class="flex items-center gap-3 text-[11px] text-zinc-500">
            <Show when={loading()}>
              <span class="flex items-center gap-1 text-zinc-400">
                <span class="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                Buscando…
              </span>
            </Show>
            <span>
              <kbd class="px-1 py-0.5 rounded bg-white/[0.05] text-[10px] font-mono text-zinc-400">↑↓</kbd> navegar
            </span>
            <span>
              <kbd class="px-1 py-0.5 rounded bg-white/[0.05] text-[10px] font-mono text-zinc-400">↵/Tab</kbd> seleccionar
            </span>
            <span>
              <kbd class="px-1 py-0.5 rounded bg-white/[0.05] text-[10px] font-mono text-zinc-400">Esc</kbd> cerrar
            </span>
          </div>
        </div>

        {/* Lista de resultados */}
        <div ref={listRef} class="max-h-64 overflow-y-auto p-1.5 space-y-0.5">
          <Show
            when={currentItems().length > 0}
            fallback={
              <div class="px-4 py-6 text-center text-[12.5px] text-zinc-500">
                {loading() ? "Buscando coincidencias…" : "No se encontraron coincidencias."}
              </div>
            }
          >
            <Show
              when={props.state()?.type === "file"}
              fallback={
                <For each={filteredCommands()}>
                  {(cmd, idx) => {
                    const isSelected = () => selectedIndex() === idx();
                    return (
                      <div
                        class={`flex items-center justify-between gap-3 px-3 py-2 rounded-xl cursor-pointer transition-all duration-150 ${
                          isSelected()
                            ? "bg-white/[0.1] text-white shadow-sm ring-1 ring-white/10"
                            : "text-zinc-300 hover:bg-white/[0.04] hover:text-zinc-200"
                        }`}
                        onMouseEnter={() => setSelectedIndex(idx())}
                        onClick={() => props.onSelectCommand(cmd)}
                      >
                        <div class="flex items-center gap-2.5 min-w-0">
                          <span class="text-[14px] shrink-0">{cmd.icon}</span>
                          <span class="font-mono font-medium text-[13px] text-emerald-300 shrink-0">
                            {cmd.name}
                          </span>
                          <span class="text-[12px] text-zinc-400 truncate">
                            {cmd.description}
                          </span>
                        </div>
                        <span class="text-[10px] font-medium tracking-wide uppercase px-2 py-0.5 rounded-full bg-white/[0.05] text-zinc-400 shrink-0">
                          {cmd.category}
                        </span>
                      </div>
                    );
                  }}
                </For>
              }
            >
              <For each={fileResults()}>
                {(file, idx) => {
                  const isSelected = () => selectedIndex() === idx();
                  const icon = () => getFileIcon(file.is_dir, file.path, file.meta);
                  const isDir = file.is_dir;

                  // Separar nombre de archivo y directorio padre para mejor legibilidad
                  const parts = file.path.split("/");
                  const filename = isDir ? parts.filter(Boolean).pop() + "/" : parts.pop();
                  const dirpath = parts.filter(Boolean).length > 0 ? parts.join("/") + "/" : "";

                  return (
                    <div
                      class={`flex items-center justify-between gap-3 px-3 py-2 rounded-xl cursor-pointer transition-all duration-150 ${
                        isSelected()
                          ? "bg-white/[0.1] text-white shadow-sm ring-1 ring-white/10"
                          : "text-zinc-300 hover:bg-white/[0.04] hover:text-zinc-200"
                      }`}
                      onMouseEnter={() => setSelectedIndex(idx())}
                      onClick={() => props.onSelectFile(file)}
                    >
                      <div class="flex items-center gap-2.5 min-w-0">
                        <span class="text-[14px] shrink-0">{icon()}</span>
                        <div class="flex items-baseline gap-1 min-w-0 text-[13px]">
                          <Show when={dirpath}>
                            <span class="text-zinc-500 font-mono text-[12px] truncate">{dirpath}</span>
                          </Show>
                          <span class={`font-mono truncate ${isDir ? "text-indigo-300 font-medium" : "text-zinc-100"}`}>
                            {filename}
                          </span>
                        </div>
                      </div>

                      <div class="flex items-center gap-2 shrink-0">
                        <Show when={file.meta}>
                          <span class="text-[10.5px] font-mono text-zinc-500 px-1.5 py-0.5 rounded bg-white/[0.03]">
                            {file.meta}
                          </span>
                        </Show>
                        <Show when={isDir}>
                          <span class="text-[10px] font-semibold uppercase tracking-wider text-indigo-400/90 px-1.5 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20">
                            Carpeta
                          </span>
                        </Show>
                      </div>
                    </div>
                  );
                }}
              </For>
            </Show>
          </Show>
        </div>
      </div>
    </Show>
  );
}
