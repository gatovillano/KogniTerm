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

/** Vista de conversaciones: lista centrada minimalista, agrupada por workspace/proyecto. */
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
    tabs.openThread(t.id, t.title || "Conversación");
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
      if (tabs.isOpen(t.id)) tabs.close(t.id);
      await refresh();
    } catch (e) {
      setErr(String(e));
    }
  }

  return (
    <div class="h-full overflow-y-auto bg-[#080b11] select-none">
      <div class="mx-auto w-full max-w-3xl px-6 py-10 text-left">
        <div class="flex items-center gap-3 mb-1.5">
          <h1 class="text-[20px] font-semibold text-white tracking-tight">Conversaciones</h1>
          <span class="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-white/[0.06] text-slate-400">
            {totalShown()} en {groups().length} workspace(s)
          </span>
          <div class="flex-1" />
          <button
            onClick={refresh}
            class="w-7 h-7 rounded-full flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/[0.08] transition-all"
            title="Recargar"
          >
            ↻
          </button>
        </div>
        <p class="text-[13px] text-slate-400 mb-6">
          Historial de sesiones persistidas en el backend de KogniTerm, organizadas por proyecto.
        </p>

        {/* Barra de búsqueda curvada */}
        <div class="relative mb-8">
          <input
            value={q()}
            onInput={(e) => setQ(e.currentTarget.value)}
            placeholder="Filtrar por título o directorio…"
            class="w-full bg-zinc-900/90 hover:bg-zinc-900 focus:bg-zinc-900 focus:ring-2 focus:ring-white/20 border border-white/[0.08] rounded-full px-5 py-2.5 text-[13.5px] text-white placeholder-zinc-500 outline-none transition-all shadow-[0_4px_20px_rgba(0,0,0,0.4)]"
          />
        </div>

        <Show when={err()}>
          <p class="mb-4 text-[12px] text-red-300 px-2">{err()}</p>
        </Show>
        <Show when={loading()}>
          <p class="text-[13px] text-zinc-400 py-12 text-center animate-pulse">Cargando conversaciones…</p>
        </Show>

        <Show when={!loading() && groups().length === 0}>
          <div class="text-center py-16 text-zinc-500">
            <span class="text-3xl block mb-2 opacity-50">📂</span>
            <p class="text-[14px]">No hay conversaciones guardadas todavía.</p>
          </div>
        </Show>

        <div class="space-y-3">
          <For each={groups()}>
            {(g) => {
              const isCollapsed = () => !!collapsed()[g.dir];
              return (
                <section class="rounded-2xl bg-zinc-900/60 hover:bg-zinc-900/80 border border-white/[0.06] transition-all duration-200 overflow-hidden shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
                  {/* Cabecera del grupo */}
                  <header
                    class="flex items-center gap-2.5 px-4 py-3 cursor-pointer select-none hover:bg-white/[0.03] transition-colors"
                    onClick={() => toggleCollapse(g.dir)}
                    title={isCollapsed() ? "Desplegar" : "Replegar"}
                  >
                    <span class="text-[11px] text-zinc-400 w-3 shrink-0 transition-transform duration-200">
                      {isCollapsed() ? "▸" : "▾"}
                    </span>
                    <h2 class="text-[13.5px] font-semibold text-white shrink-0">{g.name}</h2>
                    <span class="text-[11.5px] text-zinc-400 font-mono truncate" title={g.dir}>
                      {shortPath(g.dir)}
                    </span>
                    <span class="text-[11px] font-mono text-zinc-500 shrink-0">· {g.items.length}</span>
                    <div class="flex-1" />
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        void newThread(g.dir);
                      }}
                      disabled={busy() !== null}
                      class="text-[11.5px] px-3 py-1 rounded-full bg-white/[0.08] hover:bg-white/[0.14] text-zinc-200 hover:text-white transition-all active:scale-95 disabled:opacity-50 shrink-0 font-medium"
                      title="Nueva conversación en este workspace"
                    >
                      ＋ nueva
                    </button>
                  </header>

                  <Show when={!isCollapsed()}>
                    <div class="space-y-1 px-3 pb-3 pt-1">
                      <For each={visibleItems(g)}>
                        {(t) => (
                          <div
                            class={`group flex items-center gap-3 rounded-xl px-3.5 py-2.5 cursor-pointer transition-all duration-150 ${
                              tabs.isOpen(t.id)
                                ? "bg-white/[0.1] text-white shadow-sm"
                                : "hover:bg-white/[0.04] text-zinc-300"
                            }`}
                            onClick={() => open(t)}
                          >
                            <span class="text-zinc-400 text-[11.5px] w-16 shrink-0 tabular-nums font-mono">
                              {relTime(t.updated_at ?? t.created_at)}
                            </span>
                            <span class="text-[13px] text-zinc-200 group-hover:text-white font-medium truncate flex-1">
                              {t.title || t.id}
                            </span>
                            <Show when={tabs.isOpen(t.id)}>
                              <span class="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.12] text-zinc-200 font-medium shrink-0">
                                abierta
                              </span>
                            </Show>
                            <span class="text-[11px] text-zinc-400 font-mono tabular-nums shrink-0">
                              {t.message_count ?? 0}
                            </span>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                void remove(t);
                              }}
                              class="w-6 h-6 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-300 hover:bg-red-500/15 transition-all shrink-0 text-[12px]"
                              title="Eliminar conversación"
                            >
                              ✕
                            </button>
                          </div>
                        )}
                      </For>
                      <Show when={g.items.length > PAGE}>
                        <button
                          onClick={() => setExpanded((e) => ({ ...e, [g.dir]: !e[g.dir] }))}
                          class="w-full text-center py-2 rounded-xl text-[12px] text-slate-400 hover:text-white hover:bg-white/[0.04] transition-all mt-1"
                        >
                          {expanded()[g.dir] ? "− Ver menos" : `Ver ${g.items.length - PAGE} más…`}
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
          <section class="mt-10 pt-6">
            <h2 class="text-[12px] font-semibold text-slate-400 uppercase tracking-wider mb-3">
              Workspaces registrados
            </h2>
            <div class="flex flex-wrap gap-2">
              <For each={workspaces()}>
                {(w) => (
                  <span class="text-[11.5px] font-mono px-3 py-1 rounded-full bg-white/[0.04] text-slate-400">
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
