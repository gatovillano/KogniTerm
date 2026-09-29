import { For, Show, createMemo, createSignal, onMount } from "solid-js";
import { api, type ThreadInfo, type Workspace } from "../lib/api";
import { tabs } from "../lib/tabs";
import { loadThreadHistory } from "../lib/history";

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

/** Vista de conversaciones: lista centrada, agrupada por workspace/proyecto. */
export function ConversationsView(props: { onOpenChat: () => void }) {
  const [workspaces, setWorkspaces] = createSignal<Workspace[]>([]);
  const [threads, setThreads] = createSignal<ThreadInfo[]>([]);
  const [loading, setLoading] = createSignal(true);
  const [err, setErr] = createSignal("");
  const [busy, setBusy] = createSignal<string | null>(null);
  const [q, setQ] = createSignal("");

  async function refresh() {
    setLoading(true);
    try {
      // Los hilos se piden sin filtro: el backend ya incluye los workspaces de
      // las sesiones activas.
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

  /** Agrupa por workspace_dir, incluyendo los que aún no están registrados. */
  const groups = createMemo(() => {
    const filter = q().trim().toLowerCase();
    const byDir = new Map<string, ThreadInfo[]>();
    for (const t of threads()) {
      const dir = t.workspace_dir || "(sin workspace)";
      if (filter && !`${t.title} ${dir}`.toLowerCase().includes(filter)) continue;
      const arr = byDir.get(dir);
      if (arr) arr.push(t);
      else byDir.set(dir, [t]);
    }
    // Orden: workspaces registrados primero y por nombre; luego el resto.
    const known = new Map(workspaces().map((w) => [w.path, w.name]));
    return [...byDir.entries()]
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

  /** Render por grupos acotado: hay workspaces con cientos de conversaciones. */
  const [expanded, setExpanded] = createSignal<Record<string, boolean>>({});
  /** Workspaces plegados (persistido para no perder el estado al recargar). */
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
    tabs.openThread(t.id, t.title || "Conversación");
    // Cargar el historial antes de saltar al chat evita ver la pestaña vacía.
    void loadThreadHistory(t.id);
    props.onOpenChat();
  }

  async function newThread(dir: string) {
    setBusy(dir);
    try {
      const r = await api.createThread(dir);
      if (r?.thread_id) {
        tabs.openThread(r.thread_id, "Nueva conversación");
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
      await refresh();
    } catch (e) {
      setErr(String(e));
    }
  }

  return (
    <div class="h-full overflow-y-auto bg-[#0d1117]">
      {/* mx-auto centra la columna; el contenedor padre es un block a ancho completo */}
      <div class="mx-auto w-full max-w-3xl px-5 py-8 text-left">
        <div class="flex items-center gap-3 mb-1">
          <h1 class="text-[17px] font-semibold text-white">Conversaciones</h1>
          <span class="text-[12px] text-[#6e7681]">{totalShown()} en {groups().length} workspace(s)</span>
          <div class="flex-1" />
          <button onClick={refresh} class="text-[12px] text-[#8b949e] hover:text-white px-2" title="Recargar">
            ↻
          </button>
        </div>
        <p class="text-[12px] text-[#6e7681] mb-5">
          Las conversaciones persistidas por el backend KogniTerm, agrupadas por proyecto.
        </p>

        <input
          value={q()}
          onInput={(e) => setQ(e.currentTarget.value)}
          placeholder="Filtrar por título o ruta…"
          class="w-full bg-[#161b22] border border-[#30363d] rounded-md px-3 py-2 text-[13px] text-white placeholder-[#6e7681] outline-none focus:border-[#1f6feb] mb-6"
        />

        <Show when={err()}>
          <p class="mb-4 text-[12px] text-red-300">{err()}</p>
        </Show>
        <Show when={loading()}>
          <p class="text-[13px] text-[#8b949e] py-6 text-center">Cargando conversaciones…</p>
        </Show>

        <Show when={!loading() && groups().length === 0}>
          <p class="text-[13px] text-[#8b949e] py-6 text-center">
            No hay conversaciones guardadas todavía.
          </p>
        </Show>

        <div class="space-y-2">
          <For each={groups()}>
            {(g) => {
              const isCollapsed = () => !!collapsed()[g.dir];
              return (
                <section class="rounded-lg border border-[#21262d] overflow-hidden">
                  {/* Cabecera plegable */}
                  <header
                    class="flex items-center gap-2 px-3 py-2 cursor-pointer select-none hover:bg-[#161b22] transition-colors"
                    onClick={() => toggleCollapse(g.dir)}
                    title={isCollapsed() ? "Desplegar" : "Replegar"}
                  >
                    <span class="text-[11px] text-[#6e7681] w-3 shrink-0">{isCollapsed() ? "▸" : "▾"}</span>
                    <h2 class="text-[13px] font-semibold text-[#e6edf3] shrink-0">{g.name}</h2>
                    <span class="text-[11px] text-[#6e7681] font-mono truncate" title={g.dir}>
                      {shortPath(g.dir)}
                    </span>
                    <span class="text-[11px] text-[#6e7681] shrink-0 tabular-nums">· {g.items.length}</span>
                    <div class="flex-1" />
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        void newThread(g.dir);
                      }}
                      disabled={busy() !== null}
                      class="text-[11px] px-2 py-0.5 rounded border border-[#30363d] text-[#8b949e] hover:text-white hover:border-[#8b949e] disabled:opacity-50 shrink-0"
                      title="Nueva conversación en este workspace"
                    >
                      ＋ nueva
                    </button>
                  </header>

                  <Show when={!isCollapsed()}>
                    <div class="space-y-1.5 px-3 pb-3">
                      <For each={visibleItems(g)}>
                        {(t) => (
                          <div
                            class={`group flex items-center gap-3 rounded-md border px-3 py-2 cursor-pointer transition-colors ${
                              tabs.isOpen(t.id)
                                ? "border-[#1f6feb]/60 bg-[#161b22]"
                                : "border-[#21262d] hover:border-[#30363d] hover:bg-[#161b22]"
                            }`}
                            onClick={() => open(t)}
                          >
                            <span class="text-[#6e7681] text-[12px] w-16 shrink-0 tabular-nums">
                              {relTime(t.updated_at ?? t.created_at)}
                            </span>
                            <span class="text-[13px] text-[#e6edf3] truncate flex-1">{t.title || t.id}</span>
                            <Show when={tabs.isOpen(t.id)}>
                              <span class="text-[10px] px-1.5 py-0.5 rounded bg-[#1f6feb]/20 text-[#79c0ff] shrink-0">
                                abierta
                              </span>
                            </Show>
                            <span class="text-[11px] text-[#6e7681] tabular-nums shrink-0">{t.message_count ?? 0}</span>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                void remove(t);
                              }}
                              class="opacity-0 group-hover:opacity-100 text-[#8b949e] hover:text-red-300 px-1 shrink-0"
                              title="Eliminar conversación"
                            >
                              🗑
                            </button>
                          </div>
                        )}
                      </For>
                      <Show when={g.items.length > PAGE}>
                        <button
                          onClick={() => setExpanded((e) => ({ ...e, [g.dir]: !e[g.dir] }))}
                          class="w-full text-left px-3 py-1.5 rounded-md text-[12px] text-[#8b949e] hover:text-white hover:bg-[#161b22]"
                        >
                          {expanded()[g.dir] ? "− ver menos" : `ver ${g.items.length - PAGE} más…`}
                        </button>
                      </Show>
                    </div>
                  </Show>
                </section>
              );
            }}
          </For>
        </div>

        <Show when={!loading() && workspaces().length > 0}>
          <section class="mt-8 pt-5 border-t border-[#21262d]">
            <h2 class="text-[12px] font-semibold text-[#8b949e] mb-2">Workspaces registrados</h2>
            <div class="flex flex-wrap gap-2">
              <For each={workspaces()}>
                {(w) => (
                  <span class="text-[11px] font-mono px-2 py-1 rounded bg-[#161b22] border border-[#21262d] text-[#8b949e]">
                    {w.name}
                  </span>
                )}
              </For>
            </div>
          </section>
        </Show>
      </div>
    </div>
  );
}
