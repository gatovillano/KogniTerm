import { For, Show, createSignal, onMount } from "solid-js";
import { api, type MCPServerStatus, type MCPScope } from "../lib/api";

function dot(status?: string, disabled?: boolean) {
  if (disabled || status === "disabled") {
    return <span class="w-2 h-2 rounded-full bg-slate-500" title="Deshabilitado" />;
  }
  if (status === "connected") {
    return <span class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" title="Conectado" />;
  }
  return <span class="w-2 h-2 rounded-full bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.7)]" title="Desconectado" />;
}

/** Paridad con `/mcp` de la TUI: list / add stdio|sse / toggle / test / delete. */
export function MCPPanel() {
  const [servers, setServers] = createSignal<Record<string, MCPServerStatus>>({});
  const [loading, setLoading] = createSignal(true);
  const [err, setErr] = createSignal("");
  const [notice, setNotice] = createSignal("");
  const [busy, setBusy] = createSignal<string | null>(null);
  const [showAdd, setShowAdd] = createSignal(false);

  // formulario
  const [fName, setFName] = createSignal("");
  const [fTransport, setFTransport] = createSignal<"stdio" | "sse">("stdio");
  const [fCommand, setFCommand] = createSignal("");
  const [fArgs, setFArgs] = createSignal("");
  const [fUrl, setFUrl] = createSignal("");
  const [fEnv, setFEnv] = createSignal("");
  const [fScope, setFScope] = createSignal<MCPScope>("project");

  async function refresh() {
    setLoading(true);
    try {
      setServers(await api.listMCP());
      setErr("");
    } catch (e) {
      setErr(String(e));
      setServers({});
    } finally {
      setLoading(false);
    }
  }
  onMount(refresh);

  function parseEnv(): Record<string, string> | undefined {
    const out: Record<string, string> = {};
    for (const line of fEnv().split("\n")) {
      const t = line.trim();
      if (!t || t.startsWith("#")) continue;
      const i = t.indexOf("=");
      if (i > 0) out[t.slice(0, i).trim()] = t.slice(i + 1).trim();
    }
    return Object.keys(out).length ? out : undefined;
  }

  function buildConfig(): Record<string, any> {
    if (fTransport() === "sse") return { transport: "sse", url: fUrl().trim() };
    const cfg: Record<string, any> = {
      transport: "stdio",
      command: fCommand().trim(),
      args: fArgs().split(/\s+/).map((s) => s.trim()).filter(Boolean),
    };
    const env = parseEnv();
    if (env) cfg.env = env;
    return cfg;
  }

  function valid(): boolean {
    if (!fName().trim()) return false;
    if (fTransport() === "sse") return !!fUrl().trim();
    return !!fCommand().trim();
  }

  async function save() {
    if (!valid() || busy()) return;
    setBusy("save");
    setNotice("");
    try {
      await api.saveMCP(fName().trim(), buildConfig(), fScope());
      setNotice(`✅ Servidor '${fName().trim()}' guardado (${fScope()}).`);
      setShowAdd(false);
      await refresh();
    } catch (e) {
      setNotice(`❌ Error: ${e}`);
    } finally {
      setBusy(null);
    }
  }

  async function test() {
    if (!valid() || busy()) return;
    setBusy("test");
    setNotice("");
    try {
      const r = await api.testMCP(buildConfig());
      setNotice(`🧪 ${JSON.stringify(r).slice(0, 300)}`);
    } catch (e) {
      setNotice(`❌ Error: ${e}`);
    } finally {
      setBusy(null);
    }
  }

  async function toggle(name: string) {
    setBusy(`t:${name}`);
    try {
      await api.toggleMCP(name);
      await refresh();
    } catch (e) {
      setNotice(`❌ Error: ${e}`);
    } finally {
      setBusy(null);
    }
  }

  async function remove(name: string) {
    if (!confirm(`¿Eliminar servidor MCP '${name}'?`)) return;
    setBusy(`d:${name}`);
    try {
      await api.deleteMCP(name);
      await refresh();
    } catch (e) {
      setNotice(`❌ Error: ${e}`);
    } finally {
      setBusy(null);
    }
  }

  const names = () => Object.keys(servers());

  return (
    <div class="space-y-3 pt-1 select-none">
      <Show when={notice()}>
        <p class="px-2 py-1 text-[12px] text-amber-300 break-words animate-fade-in">{notice()}</p>
      </Show>
      <Show when={err()}>
        <p class="px-2 py-1 text-[12px] text-red-300">{err()}</p>
      </Show>

      <div class="flex items-center px-1">
        <span class="text-[12px] text-slate-400 font-mono">
          {loading() ? "Cargando…" : `${names().length} servidor(es)`}
        </span>
        <div class="flex-1" />
        <button
          onClick={refresh}
          class="w-7 h-7 rounded-full flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/[0.08] transition-all mr-1"
          title="Recargar lista"
        >
          ↻
        </button>
        <button
          onClick={() => setShowAdd(!showAdd())}
          class="text-[12px] px-3.5 py-1.5 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium shadow-[0_0_12px_rgba(99,102,241,0.25)] transition-all active:scale-95"
        >
          {showAdd() ? "− Cerrar" : "＋ Añadir"}
        </button>
      </div>

      {/* ── lista ── */}
      <div class="max-h-[240px] overflow-y-auto space-y-1.5">
        <Show when={names().length === 0 && !loading()}>
          <p class="py-8 text-[12.5px] text-slate-400 text-center">Sin servidores MCP. Añade uno con ＋ Añadir.</p>
        </Show>
        <For each={names()}>
          {(name) => {
            const s = () => servers()[name];
            const tools = () => s().tools ?? [];
            return (
              <div class="px-4 py-3 rounded-2xl bg-white/[0.03] hover:bg-white/[0.05] transition-all">
                <div class="flex items-center gap-2.5">
                  {dot(s().status, s().disabled)}
                  <span class="text-[13.5px] text-white font-semibold font-mono">{name}</span>
                  <span class="text-[11px] text-slate-400 font-mono px-2 py-0.5 rounded-full bg-white/[0.04]">
                    {s().transport ?? "stdio"}
                  </span>
                  <Show when={s().disabled}>
                    <span class="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-medium">
                      deshabilitado
                    </span>
                  </Show>
                  <div class="flex-1" />
                  <button
                    onClick={() => toggle(name)}
                    disabled={busy() !== null}
                    class="w-7 h-7 rounded-full flex items-center justify-center bg-white/[0.06] hover:bg-white/[0.12] text-slate-300 hover:text-white transition-all active:scale-90 text-[11px] disabled:opacity-50"
                    title="Activar / desactivar"
                  >
                    {busy() === `t:${name}` ? "…" : s().disabled ? "▶" : "⏸"}
                  </button>
                  <button
                    onClick={() => remove(name)}
                    disabled={busy() !== null}
                    class="w-7 h-7 rounded-full flex items-center justify-center bg-white/[0.06] hover:bg-red-500/20 text-slate-400 hover:text-red-300 transition-all active:scale-90 text-[11px] disabled:opacity-50"
                    title="Eliminar"
                  >
                    ✕
                  </button>
                </div>
                <Show when={tools().length > 0}>
                  <p class="text-[11.5px] text-slate-400 font-mono mt-1.5 truncate" title={tools().join(", ")}>
                    🔧 {tools().slice(0, 6).join(", ")}
                    {tools().length > 6 ? ` +${tools().length - 6}` : ""}
                  </p>
                </Show>
                <Show when={s().error}>
                  <p class="text-[11.5px] text-red-300 mt-1 break-words">{s().error}</p>
                </Show>
              </div>
            );
          }}
        </For>
      </div>

      {/* ── alta ── */}
      <Show when={showAdd()}>
        <div class="mt-3 p-4 rounded-2xl bg-white/[0.03] space-y-3 animate-slide-up">
          <div class="flex gap-2">
            <input
              value={fName()}
              onInput={(e) => setFName(e.currentTarget.value)}
              placeholder="nombre (p.ej. git, memory)"
              class="flex-1 bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-blue-500/30 rounded-xl px-3.5 py-2 text-[13px] text-white placeholder-slate-500 outline-none transition-all"
            />
            <select
              value={fTransport()}
              onChange={(e) => setFTransport(e.currentTarget.value as "stdio" | "sse")}
              class="bg-white/[0.06] rounded-xl px-3 py-2 text-[12.5px] text-white outline-none"
            >
              <option value="stdio">stdio (local)</option>
              <option value="sse">sse (remoto)</option>
            </select>
            <select
              value={fScope()}
              onChange={(e) => setFScope(e.currentTarget.value as MCPScope)}
              title="Ámbito: project (.kogniterm/config.json) o global (~/.kogniterm)"
              class="bg-white/[0.06] rounded-xl px-3 py-2 text-[12.5px] text-white outline-none"
            >
              <option value="project">project</option>
              <option value="global">global</option>
            </select>
          </div>
          <Show
            when={fTransport() === "stdio"}
            fallback={
              <input
                value={fUrl()}
                onInput={(e) => setFUrl(e.currentTarget.value)}
                placeholder="https://servidor:8000/sse"
                class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-blue-500/30 rounded-xl px-3.5 py-2 text-[13px] font-mono text-white placeholder-slate-500 outline-none transition-all"
              />
            }
          >
            <input
              value={fCommand()}
              onInput={(e) => setFCommand(e.currentTarget.value)}
              placeholder="comando (p.ej. uvx, npx, python3)"
              class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-blue-500/30 rounded-xl px-3.5 py-2 text-[13px] font-mono text-white placeholder-slate-500 outline-none transition-all"
            />
            <input
              value={fArgs()}
              onInput={(e) => setFArgs(e.currentTarget.value)}
              placeholder="args separados por espacios"
              class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-blue-500/30 rounded-xl px-3.5 py-2 text-[13px] font-mono text-white placeholder-slate-500 outline-none transition-all"
            />
            <textarea
              value={fEnv()}
              onInput={(e) => setFEnv(e.currentTarget.value)}
              placeholder="variables de entorno opcionales (KEY=VALOR por línea)"
              rows={2}
              class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-blue-500/30 rounded-xl px-3.5 py-2 text-[12px] font-mono text-white placeholder-slate-500 outline-none transition-all"
            />
          </Show>
          <div class="flex gap-2 justify-end pt-1">
            <button
              onClick={test}
              disabled={!valid() || busy() !== null}
              class="px-4 py-2 rounded-full bg-white/[0.08] hover:bg-white/[0.14] text-[12.5px] text-slate-300 hover:text-white transition-all active:scale-95 disabled:opacity-50"
            >
              {busy() === "test" ? "Probando…" : "🧪 Probar"}
            </button>
            <button
              onClick={save}
              disabled={!valid() || busy() !== null}
              class="px-5 py-2 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-[12.5px] font-medium shadow-[0_0_15px_rgba(99,102,241,0.3)] transition-all active:scale-95 disabled:opacity-50"
            >
              {busy() === "save" ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </div>
      </Show>
    </div>
  );
}
