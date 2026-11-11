import { For, Show, createMemo, createSignal, onMount } from "solid-js";
import { api, type ThreadInfo, type Workspace } from "../lib/api";
import { tabs } from "../lib/tabs";
import { loadThreadHistory } from "../lib/history";
import {
  IconChevronDown,
  IconChevronRight,
  IconClose,
  IconFolder,
  IconPlus,
  IconRefresh,
  IconSearch,
  IconTrash,
} from "./Icons";

function relTime(iso?: string): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "ahora";
  if (min < 60) return `hace ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `hace ${h} h`;
  const d = Math.floor(h / 24);
  if (d < 30) return `hace ${d} d`;
  return new Date(iso).toLocaleDateString("es", { day: "numeric", month: "short" });
}

const shortPath = (p: string) => {
  const parts = p.split("/").filter(Boolean);
  return parts.length <= 2 ? p : `…/${parts.slice(-2).join("/")}`;
};

function readCollapsed(): Record<string, boolean> {
  try {
    return (JSON.parse(localStorage.getItem("kogniterm-v3-collapsed") ?? "{}") ?? {}) as Record<string, boolean>;
  } catch {
    return {};
  }
}

/** Vista de conversaciones: lista centrada minimalista, agrupada por workspace/proyecto. */
export function ConversationsView(props: { onOpenChat: () => void }) {
  const [workspaces, setWorkspaces] = createSignal<Workspace[]>([]);
  const [threads, setThreads] = createSignal<ThreadInfo[]>([]);
  const [loading, setLoading] = createSignal(true);
  const [err, setErr] = createSignal("");
  const [busy, setBusy] = createSignal<string | null>(null);
  const [q, setQ] = createSignal("");

  // Estado para añadir workspace
  const [showAddWs, setShowAddWs] = createSignal(false);
  const [wsPath, setWsPath] = createSignal("");
  const [wsErr, setWsErr] = createSignal("");
  const [addingWs, setAddingWs] = createSignal(false);
  const [browseCurrent, setBrowseCurrent] = createSignal("");
  const [browseParent, setBrowseParent] = createSignal<string | null>(null);
  const [browseDirs, setBrowseDirs] = createSignal<Array<{ name: string; path: string }>>([]);
  const [browseLoading, setBrowseLoading] = createSignal(false);

  const hasNativePicker = () => typeof (globalThis as any).kogniterm?.pickDirectory === "function";

  async function refresh() {
    setLoading(true);
    try {
      const [ws, th] = await Promise.all([api.listWorkspaces(), api.listThreads()]);
      setWorkspaces(ws.workspaces ?? []);
      setThreads(th.threads ?? []);
      setErr("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }
  onMount(refresh);

  async function loadBrowse(targetPath?: string) {
    setBrowseLoading(true);
    try {
      const res = await api.browseDirectories(targetPath);
      setBrowseCurrent(res.current);
      setBrowseParent(res.parent);
      setBrowseDirs(res.directories ?? []);
      if (!wsPath().trim()) {
        setWsPath(res.current);
      }
    } catch {
      /* ignore */
    } finally {
      setBrowseLoading(false);
    }
  }

  function openAddWorkspaceModal() {
    setWsErr("");
    setShowAddWs(true);
    void loadBrowse(wsPath().trim() || undefined);
  }

  async function pickNativeFolder() {
    try {
      const picker = (globalThis as any).kogniterm?.pickDirectory;
      if (typeof picker !== "function") return;
      const chosen: string | null = await picker();
      if (chosen) {
        setWsPath(chosen);
        setWsErr("");
        void loadBrowse(chosen);
      }
    } catch (e) {
      setWsErr(String(e));
    }
  }

  async function submitAddWorkspace(startChat = false) {
    const clean = wsPath().trim();
    if (!clean) {
      setWsErr("Introduce o selecciona la ruta de una carpeta.");
      return;
    }
    setAddingWs(true);
    setWsErr("");
    try {
      const res = await api.addWorkspace(clean);
      const addedPath = res.workspace?.path || clean;
      // Asegurar que quede desplegado al añadirlo
      setCollapsed((c) => {
        const next = { ...c, [addedPath]: false };
        try {
          localStorage.setItem("kogniterm-v3-collapsed", JSON.stringify(next));
        } catch {}
        return next;
      });
      setShowAddWs(false);
      setWsPath("");
      await refresh();
      if (startChat) {
        await newThread(addedPath);
      }
    } catch (e: any) {
      setWsErr(e?.message || String(e));
    } finally {
      setAddingWs(false);
    }
  }

  async function registerExistingDir(dir: string) {
    setBusy(dir);
    try {
      await api.addWorkspace(dir);
      await refresh();
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  async function unregisterWorkspace(dir: string, name: string) {
    if (!confirm(`¿Quitar el workspace "${name}" de la lista?\n(No se borrarán los archivos ni las conversaciones en disco)`)) {
      return;
    }
    setBusy(dir);
    try {
      await api.removeWorkspace(dir);
      await refresh();
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  const groups = createMemo(() => {
    const filter = q().trim().toLowerCase();
    const byDir = new Map<string, ThreadInfo[]>();
    const known = new Map(workspaces().map((w) => [w.path, w.name]));

    // Incluir todos los workspaces registrados aunque aún no tengan conversaciones
    for (const w of workspaces()) {
      if (!byDir.has(w.path)) {
        byDir.set(w.path, []);
      }
    }

    for (const t of threads()) {
      const dir = t.workspace_dir || "(sin workspace)";
      if (filter && !`${t.title} ${dir} ${known.get(dir) ?? ""}`.toLowerCase().includes(filter)) continue;
      const arr = byDir.get(dir);
      if (arr) arr.push(t);
      else byDir.set(dir, [t]);
    }

    return [...byDir.entries()]
      .filter(([dir, items]) => {
        if (!filter) return true;
        if (items.length > 0) return true;
        const name = known.get(dir) || dir.split("/").filter(Boolean).pop() || dir;
        return `${name} ${dir}`.toLowerCase().includes(filter);
      })
      .map(([dir, items]) => ({
        dir,
        name: known.get(dir) || dir.split("/").filter(Boolean).pop() || dir,
        registered: known.has(dir),
        items: items.sort(
          (a, b) => new Date(b.updated_at ?? b.created_at ?? 0).getTime() - new Date(a.updated_at ?? a.created_at ?? 0).getTime(),
        ),
      }))
      .sort((a, b) => Number(b.registered) - Number(a.registered) || a.name.localeCompare(b.name));
  });

  const totalShown = createMemo(() => groups().reduce((n, g) => n + g.items.length, 0));

  const [expanded, setExpanded] = createSignal<Record<string, boolean>>({});
  const [collapsed, setCollapsed] = createSignal<Record<string, boolean>>(readCollapsed());
  const PAGE = 15;
  const visibleItems = (g: { dir: string; items: ThreadInfo[] }) =>
    expanded()[g.dir] ? g.items : g.items.slice(0, PAGE);

  function toggleCollapse(dir: string) {
    setCollapsed((c) => {
      const next = { ...c, [dir]: !c[dir] };
      try {
        localStorage.setItem("kogniterm-v3-collapsed", JSON.stringify(next));
      } catch {}
      return next;
    });
  }

  function open(t: ThreadInfo) {
    const wsDir = t.workspace_dir && t.workspace_dir !== "(sin workspace)" ? t.workspace_dir : undefined;
    tabs.openThread(t.id, t.title || "Conversación", wsDir);
    void loadThreadHistory(t.id);
    props.onOpenChat();
  }

  async function newThread(dir: string) {
    setBusy(dir);
    try {
      const wsDir = dir !== "(sin workspace)" ? dir : undefined;
      const r = await api.createThread(wsDir);
      if (r?.thread_id) {
        tabs.openThread(r.thread_id, "Nueva conversación", wsDir);
        void loadThreadHistory(r.thread_id);
        props.onOpenChat();
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function remove(t: ThreadInfo) {
    if (!confirm(`¿Eliminar la conversación "${t.title || t.id}"?`)) return;
    try {
      await api.deleteThread(t.id);
      if (tabs.isOpen(t.id)) tabs.close(t.id);
      await refresh();
    } catch (e) {
      setErr(String(e));
    }
  }

  return (
    <div class="h-full overflow-y-auto kt-canvas-bg select-none">
      <div class="mx-auto w-full max-w-3xl px-6 py-8 sm:py-10 text-left">
        <div class="flex flex-wrap items-center gap-3 mb-1.5">
          <h1 class="text-[22px] font-semibold text-[var(--kt-text-primary)] tracking-tight">Conversaciones</h1>
          <span class="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-[var(--kt-bg-hover)] border border-[var(--kt-border-subtle)] text-[var(--kt-text-muted)] tabular-nums">
            {totalShown()} en {groups().length} workspace(s)
          </span>
          <div class="flex-1" />
          <button
            onClick={() => (showAddWs() ? setShowAddWs(false) : openAddWorkspaceModal())}
            class={`text-[12px] px-3.5 py-1.5 rounded-xl font-medium transition-all active:scale-95 flex items-center gap-1.5 border ${
              showAddWs()
                ? "bg-[var(--kt-btn-primary-bg)] text-[var(--kt-btn-primary-text)] border-transparent shadow-sm"
                : "bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] text-[var(--kt-text-primary)] border-[var(--kt-border-default)]"
            }`}
            title="Añadir una carpeta de proyecto como workspace"
          >
            <IconPlus size={13} />
            <span>Añadir workspace</span>
          </button>
          <button
            onClick={refresh}
            class="w-8 h-8 rounded-xl flex items-center justify-center text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] border border-transparent hover:border-[var(--kt-border-subtle)] transition-all"
            title="Recargar"
          >
            <IconRefresh size={14} />
          </button>
        </div>
        <p class="text-[13px] text-[var(--kt-text-muted)] mb-6">
          Historial de sesiones persistidas en el backend de KogniTerm, organizadas por proyecto.
        </p>

        {/* Panel desplegable para añadir un nuevo workspace */}
        <Show when={showAddWs()}>
          <div class="mb-6 rounded-2xl kt-card p-4 animate-scale-in space-y-3">
            <div class="flex items-center justify-between">
              <div>
                <h2 class="text-[14px] font-semibold text-[var(--kt-text-primary)]">Añadir Workspace</h2>
                <p class="text-[12px] text-[var(--kt-text-muted)]">
                  Ingresa la ruta del directorio o explora las carpetas para registrarlo en tus conversaciones.
                </p>
              </div>
              <button
                onClick={() => setShowAddWs(false)}
                class="w-7 h-7 rounded-xl flex items-center justify-center text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)]"
                title="Cerrar"
              >
                <IconClose size={13} />
              </button>
            </div>

            <div class="flex items-center gap-2">
              <input
                value={wsPath()}
                onInput={(e) => {
                  setWsPath(e.currentTarget.value);
                  setWsErr("");
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    void submitAddWorkspace(false);
                  } else if (e.key === "Escape") {
                    setShowAddWs(false);
                  }
                }}
                placeholder="/ruta/a/tu/proyecto o ~/mi-proyecto"
                class="flex-1 bg-[var(--kt-bg-hover)] focus:bg-[var(--kt-bg-input)] border border-[var(--kt-border-default)] focus:border-[var(--kt-border-strong)] rounded-xl px-3.5 py-2 text-[13px] font-mono text-[var(--kt-text-primary)] placeholder-[var(--kt-text-faint)] outline-none transition-all"
              />
              <button
                type="button"
                onClick={() => void loadBrowse(wsPath().trim() || undefined)}
                class="px-3 py-2 rounded-xl bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] text-[12px] text-[var(--kt-text-secondary)] hover:text-[var(--kt-text-primary)] border border-[var(--kt-border-subtle)] transition-all shrink-0"
                title="Explorar la ruta escrita"
              >
                Explorar
              </button>
              <Show when={hasNativePicker()}>
                <button
                  type="button"
                  onClick={pickNativeFolder}
                  class="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] text-[12px] text-[var(--kt-text-primary)] border border-[var(--kt-border-default)] transition-all shrink-0 font-medium"
                  title="Seleccionar carpeta con el explorador del sistema"
                >
                  <IconFolder size={13} />
                  <span>Examinar…</span>
                </button>
              </Show>
            </div>

            {/* Explorador rápido de directorios del sistema */}
            <div class="rounded-xl bg-[var(--kt-bg-app)] border border-[var(--kt-border-subtle)] overflow-hidden">
              <div class="flex items-center gap-2 px-3 py-2 bg-[var(--kt-bg-hover)] border-b border-[var(--kt-border-subtle)] text-[11.5px]">
                <span class="text-[var(--kt-text-muted)]">Carpeta:</span>
                <span class="font-mono text-[var(--kt-text-primary)] truncate flex-1" title={browseCurrent()}>
                  {browseCurrent() || "…"}
                </span>
                <Show when={browseParent()}>
                  <button
                    type="button"
                    onClick={() => {
                      const p = browseParent();
                      if (p) {
                        setWsPath(p);
                        void loadBrowse(p);
                      }
                    }}
                    class="px-2.5 py-0.5 rounded-lg bg-[var(--kt-bg-active)] text-[var(--kt-text-secondary)] hover:text-[var(--kt-text-primary)] transition-all font-medium shrink-0"
                    title="Ir a la carpeta superior"
                  >
                    ↑ Subir
                  </button>
                </Show>
              </div>
              <div class="max-h-40 overflow-y-auto p-1.5 grid grid-cols-1 sm:grid-cols-2 gap-1">
                <Show
                  when={!browseLoading()}
                  fallback={
                    <div class="col-span-2 py-4 text-center text-[12px] text-[var(--kt-text-faint)]">
                      Cargando carpetas…
                    </div>
                  }
                >
                  <Show
                    when={browseDirs().length > 0}
                    fallback={
                      <div class="col-span-2 py-3 text-center text-[12px] text-[var(--kt-text-faint)]">
                        No hay subcarpetas visibles en este directorio.
                      </div>
                    }
                  >
                    <For each={browseDirs()}>
                      {(d) => (
                        <button
                          type="button"
                          onClick={() => {
                            setWsPath(d.path);
                            setWsErr("");
                            void loadBrowse(d.path);
                          }}
                          class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-left text-[12px] text-[var(--kt-text-secondary)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all truncate"
                          title={d.path}
                        >
                          <IconFolder size={13} class="text-[var(--kt-text-faint)] shrink-0" />
                          <span class="truncate font-mono">{d.name}</span>
                        </button>
                      )}
                    </For>
                  </Show>
                </Show>
              </div>
            </div>

            <Show when={wsErr()}>
              <p class="text-[12px] text-red-300 px-1">{wsErr()}</p>
            </Show>

            <div class="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setShowAddWs(false)}
                class="px-3.5 py-1.5 rounded-full text-[12px] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={addingWs() || !wsPath().trim()}
                onClick={() => void submitAddWorkspace(false)}
                class="px-4 py-1.5 rounded-full text-[12px] font-medium bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] text-[var(--kt-text-primary)] border border-[var(--kt-border-default)] transition-all active:scale-95 disabled:opacity-50"
              >
                {addingWs() ? "Añadiendo…" : "Añadir workspace"}
              </button>
              <button
                type="button"
                disabled={addingWs() || !wsPath().trim()}
                onClick={() => void submitAddWorkspace(true)}
                class="px-4 py-1.5 rounded-full text-[12px] font-semibold bg-[var(--kt-btn-primary-bg)] text-[var(--kt-btn-primary-text)] hover:bg-[var(--kt-btn-primary-hover)] transition-all active:scale-95 disabled:opacity-50 shadow-sm"
              >
                Añadir y abrir chat
              </button>
            </div>
          </div>
        </Show>

        {/* Barra de búsqueda */}
        <div class="relative mb-6">
          <IconSearch
            size={15}
            class="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--kt-text-faint)] pointer-events-none"
          />
          <input
            value={q()}
            onInput={(e) => setQ(e.currentTarget.value)}
            placeholder="Filtrar por título o directorio…"
            class="w-full kt-composer rounded-2xl pl-10 pr-9 py-2.5 text-[13.5px] text-[var(--kt-text-primary)] placeholder-[var(--kt-text-faint)] outline-none transition-all"
          />
          <Show when={q()}>
            <button
              type="button"
              onClick={() => setQ("")}
              class="absolute right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center text-[var(--kt-text-faint)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all"
              title="Limpiar búsqueda"
            >
              <IconClose size={12} />
            </button>
          </Show>
        </div>

        <Show when={err()}>
          <p class="mb-4 text-[12px] text-red-300 px-2">{err()}</p>
        </Show>
        <Show when={loading()}>
          <p class="text-[13px] text-[var(--kt-text-muted)] py-12 text-center animate-pulse">
            Cargando conversaciones…
          </p>
        </Show>

        <Show when={!loading() && groups().length === 0}>
          <div class="text-center py-16 text-[var(--kt-text-muted)] kt-card rounded-2xl">
            <div class="w-12 h-12 rounded-2xl bg-[var(--kt-bg-hover)] flex items-center justify-center mx-auto mb-3 text-[var(--kt-text-muted)]">
              <IconFolder size={22} />
            </div>
            <p class="text-[14px] mb-4">No hay workspaces ni conversaciones guardadas todavía.</p>
            <button
              onClick={openAddWorkspaceModal}
              class="inline-flex items-center gap-1.5 text-[12.5px] px-4 py-2 rounded-full bg-[var(--kt-btn-primary-bg)] text-[var(--kt-btn-primary-text)] hover:bg-[var(--kt-btn-primary-hover)] transition-all active:scale-95 font-medium"
            >
              <IconPlus size={13} />
              <span>Añadir primer workspace</span>
            </button>
          </div>
        </Show>

        <div class="space-y-3">
          <For each={groups()}>
            {(g) => {
              const isCollapsed = () => !!collapsed()[g.dir];
              return (
                <section class="rounded-2xl kt-card transition-all duration-200 overflow-hidden">
                  {/* Cabecera del grupo */}
                  <header
                    class="flex items-center gap-2.5 px-4 py-3 cursor-pointer select-none hover:bg-[var(--kt-bg-hover)] transition-colors"
                    onClick={() => toggleCollapse(g.dir)}
                    title={isCollapsed() ? "Desplegar" : "Replegar"}
                  >
                    <span class="text-[var(--kt-text-muted)] shrink-0">
                      {isCollapsed() ? <IconChevronRight size={14} /> : <IconChevronDown size={14} />}
                    </span>
                    <IconFolder size={14} class="text-[var(--kt-text-muted)] shrink-0" />
                    <h2 class="text-[13.5px] font-semibold text-[var(--kt-text-primary)] shrink-0">{g.name}</h2>
                    <span class="text-[11.5px] text-[var(--kt-text-faint)] font-mono truncate" title={g.dir}>
                      {shortPath(g.dir)}
                    </span>
                    <span class="text-[11px] font-mono text-[var(--kt-text-faint)] shrink-0 tabular-nums">
                      · {g.items.length}
                    </span>
                    <div class="flex-1" />
                    <Show when={!g.registered && g.dir !== "(sin workspace)"}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          void registerExistingDir(g.dir);
                        }}
                        disabled={busy() !== null}
                        class="text-[11px] px-2.5 py-1 rounded-full bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] transition-all active:scale-95 disabled:opacity-50 shrink-0"
                        title="Guardar este directorio como workspace registrado"
                      >
                        Guardar workspace
                      </button>
                    </Show>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        void newThread(g.dir);
                      }}
                      disabled={busy() !== null}
                      class="flex items-center gap-1 text-[11.5px] px-3 py-1 rounded-full bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] border border-[var(--kt-border-subtle)] text-[var(--kt-text-primary)] transition-all active:scale-95 disabled:opacity-50 shrink-0 font-medium"
                      title="Nueva conversación en este workspace"
                    >
                      <IconPlus size={11} />
                      <span>Nueva</span>
                    </button>
                    <Show when={g.registered}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          void unregisterWorkspace(g.dir, g.name);
                        }}
                        disabled={busy() !== null}
                        class="w-6 h-6 rounded-full flex items-center justify-center text-[var(--kt-text-faint)] hover:text-red-300 hover:bg-red-500/15 transition-all shrink-0"
                        title="Quitar workspace de la lista"
                      >
                        <IconClose size={11} />
                      </button>
                    </Show>
                  </header>

                  <Show when={!isCollapsed()}>
                    <div class="space-y-1 px-2.5 pb-2.5 pt-1 border-t border-[var(--kt-border-subtle)]">
                      <Show
                        when={g.items.length > 0}
                        fallback={
                          <div class="flex items-center justify-between px-3 py-2.5 rounded-xl bg-[var(--kt-bg-hover)] text-[12.5px] text-[var(--kt-text-muted)]">
                            <span>Sin conversaciones en este workspace todavía.</span>
                            <button
                              onClick={() => void newThread(g.dir)}
                              disabled={busy() !== null}
                              class="text-[12px] text-[var(--kt-text-primary)] hover:underline underline-offset-2 font-medium"
                            >
                              Iniciar primera conversación →
                            </button>
                          </div>
                        }
                      >
                        <For each={visibleItems(g)}>
                          {(t) => (
                            <div
                              class={`group flex items-center gap-3 rounded-xl px-3 py-2 cursor-pointer transition-all duration-150 ${
                                tabs.isOpen(t.id)
                                  ? "bg-[var(--kt-bg-active)] text-[var(--kt-text-primary)]"
                                  : "hover:bg-[var(--kt-bg-hover)] text-[var(--kt-text-secondary)]"
                              }`}
                              onClick={() => open(t)}
                            >
                              <span class="text-[var(--kt-text-faint)] text-[11.5px] w-16 shrink-0 tabular-nums font-mono">
                                {relTime(t.updated_at ?? t.created_at)}
                              </span>
                              <span class="text-[13px] text-[var(--kt-text-primary)] font-medium truncate flex-1">
                                {t.title || t.id}
                              </span>
                              <Show when={tabs.isOpen(t.id)}>
                                <span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 font-medium shrink-0">
                                  abierta
                                </span>
                              </Show>
                              <span class="text-[11px] text-[var(--kt-text-faint)] font-mono tabular-nums shrink-0 px-1.5 py-0.5 rounded bg-[var(--kt-bg-hover)]">
                                {t.message_count ?? 0}
                              </span>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  void remove(t);
                                }}
                                class="w-6 h-6 rounded-lg flex items-center justify-center opacity-0 group-hover:opacity-100 text-[var(--kt-text-faint)] hover:text-red-300 hover:bg-red-500/15 transition-all shrink-0"
                                title="Eliminar conversación"
                              >
                                <IconTrash size={12} />
                              </button>
                            </div>
                          )}
                        </For>
                        <Show when={g.items.length > PAGE}>
                          <button
                            onClick={() => setExpanded((e) => ({ ...e, [g.dir]: !e[g.dir] }))}
                            class="w-full text-center py-2 rounded-xl text-[12px] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all mt-1"
                          >
                            {expanded()[g.dir] ? "− Ver menos" : `Ver ${g.items.length - PAGE} más…`}
                          </button>
                        </Show>
                      </Show>
                    </div>
                  </Show>
                </section>
              );
            }}
          </For>
        </div>

        <Show when={!loading() && workspaces().length > 0}>
          <section class="mt-8 pt-6 border-t border-[var(--kt-border-subtle)]">
            <h2 class="text-[11px] font-semibold text-[var(--kt-text-faint)] uppercase tracking-wider mb-3">
              Workspaces registrados
            </h2>
            <div class="flex flex-wrap gap-2">
              <For each={workspaces()}>
                {(w) => (
                  <span
                    class="inline-flex items-center gap-1.5 text-[11.5px] font-mono pl-3 pr-1.5 py-1 rounded-full bg-[var(--kt-bg-hover)] border border-[var(--kt-border-subtle)] text-[var(--kt-text-secondary)] transition-colors"
                    title={w.path}
                  >
                    <button
                      type="button"
                      onClick={() => setQ(w.name)}
                      class="hover:text-[var(--kt-text-primary)] transition-colors"
                    >
                      {w.name}
                    </button>
                    <button
                      type="button"
                      onClick={() => void unregisterWorkspace(w.path, w.name)}
                      class="w-4 h-4 rounded-full flex items-center justify-center text-[var(--kt-text-faint)] hover:text-red-300 hover:bg-red-500/15 transition-colors"
                      title={`Quitar workspace ${w.name}`}
                    >
                      <IconClose size={10} />
                    </button>
                  </span>
                )}
              </For>
              <button
                type="button"
                onClick={openAddWorkspaceModal}
                class="inline-flex items-center gap-1 text-[11.5px] font-mono px-3 py-1 rounded-full bg-transparent hover:bg-[var(--kt-bg-hover)] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] border border-dashed border-[var(--kt-border-default)] transition-all"
              >
                <IconPlus size={11} />
                <span>añadir</span>
              </button>
            </div>
          </section>
        </Show>
      </div>
    </div>
  );
}
