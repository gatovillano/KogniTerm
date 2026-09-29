import { For, Show, createSignal, onMount } from "solid-js";
import { api, type MCPServerStatus, type MCPScope } from "../lib/api";

function dot(status?: string, disabled?: boolean): string {
  if (disabled || status === "disabled") return "⏸️";
  if (status === "connected") return "🟢";
  return "🔴";
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
    <div class="p-2">
      <Show when={notice()}>
        <p class="px-2 py-1 text-[12px] text-amber-200 break-words">{notice()}</p>
      </Show>
      <Show when={err()}>
        <p class="px-2 py-1 text-[12px] text-red-300">{err()}</p>
      </Show>

      <div class="flex items-center px-2 py-1">
        <span class="text-[12px] text-[#8b949e]">{loading() ? "Cargando…" : `${names().length} servidor(es)`}</span>
        <div class="flex-1" />
        <button onClick={refresh} class="text-[12px] text-[#8b949e] hover:text-white px-2" title="Recargar lista">
          ↻
        </button>
        <button
          onClick={() => setShowAdd(!showAdd())}
          class="text-[12px] px-2.5 py-1 rounded-md bg-[#238636] hover:bg-[#2ea043] text-white"
        >
          {showAdd() ? "− Cerrar" : "＋ Añadir"}
        </button>
      </div>

      {/* ── lista ── */}
      <div class="max-h-[220px] overflow-y-auto">
        <Show when={names().length === 0 && !loading()}>
          <p class="px-4 py-3 text-[12px] text-[#8b949e]">Sin servidores MCP. Añade uno con ＋ Añadir.</p>
        </Show>
        <For each={names()}>
          {(name) => {
            const s = () => servers()[name];
            const tools = () => s().tools ?? [];
            return (
              <div class="px-3 py-2 rounded-md hover:bg-[#21262d] border-b border-[#21262d]">
                <div class="flex items-center gap-2">
                  <span>{dot(s().status, s().disabled)}</span>
                  <span class="text-[13px] text-white font-mono">{name}</span>
                  <span class="text-[11px] text-[#8b949e]">{s().transport ?? "stdio"}</span>
                  <Show when={s().disabled}>
                    <span class="text-[10px] px-1 rounded bg-amber-500/20 text-amber-200">deshabilitado</span>
                  </Show>
                  <div class="flex-1" />
                  <button
                    onClick={() => toggle(name)}
                    disabled={busy() !== null}
                    class="text-[12px] px-2 py-0.5 rounded bg-[#161b22] border border-[#30363d] text-[#8b949e] hover:text-white disabled:opacity-50"
                    title="Activar / desactivar"
                  >
                    {busy() === `t:${name}` ? "…" : s().disabled ? "▶" : "⏸"}
                  </button>
                  <button
                    onClick={() => remove(name)}
                    disabled={busy() !== null}
                    class="text-[12px] px-2 py-0.5 rounded bg-[#161b22] border border-[#30363d] text-[#8b949e] hover:text-red-300 disabled:opacity-50"
                    title="Eliminar"
                  >
                    🗑
                  </button>
                </div>
                <Show when={tools().length > 0}>
                  <p class="text-[11px] text-[#6e7681] font-mono mt-0.5 truncate" title={tools().join(", ")}>
                    🔧 {tools().slice(0, 6).join(", ")}
                    {tools().length > 6 ? ` +${tools().length - 6}` : ""}
                  </p>
                </Show>
                <Show when={s().error}>
                  <p class="text-[11px] text-red-300 mt-0.5 break-words">{s().error}</p>
                </Show>
              </div>
            );
          }}
        </For>
      </div>

      {/* ── alta ── */}
      <Show when={showAdd()}>
        <div class="mt-2 p-2 rounded-md bg-[#0d1117] border border-[#30363d] space-y-2">
          <div class="flex gap-2">
            <input
              value={fName()}
              onInput={(e) => setFName(e.currentTarget.value)}
              placeholder="nombre (p.ej. caldav)"
              class="flex-1 bg-[#161b22] border border-[#30363d] rounded-md px-2.5 py-1.5 text-[13px] text-white placeholder-[#6e7681] outline-none"
            />
            <select
              value={fTransport()}
              onChange={(e) => setFTransport(e.currentTarget.value as "stdio" | "sse")}
              class="bg-[#161b22] border border-[#30363d] rounded-md px-2 py-1.5 text-[13px] text-white outline-none"
            >
              <option value="stdio">stdio (local)</option>
              <option value="sse">sse (remoto)</option>
            </select>
            <select
              value={fScope()}
              onChange={(e) => setFScope(e.currentTarget.value as MCPScope)}
              title="Ámbito: project (.kogniterm/config.json) o global (~/.kogniterm)"
              class="bg-[#161b22] border border-[#30363d] rounded-md px-2 py-1.5 text-[13px] text-white outline-none"
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
                class="w-full bg-[#161b22] border border-[#30363d] rounded-md px-2.5 py-1.5 text-[13px] font-mono text-white placeholder-[#6e7681] outline-none"
              />
            }
          >
            <input
              value={fCommand()}
              onInput={(e) => setFCommand(e.currentTarget.value)}
              placeholder="comando (p.ej. uvx, npx, python3)"
              class="w-full bg-[#161b22] border border-[#30363d] rounded-md px-2.5 py-1.5 text-[13px] font-mono text-white placeholder-[#6e7681] outline-none"
            />
            <input
              value={fArgs()}
              onInput={(e) => setFArgs(e.currentTarget.value)}
              placeholder="args separados por espacios (p.ej. mcp-server-caldav --user x)"
              class="w-full bg-[#161b22] border border-[#30363d] rounded-md px-2.5 py-1.5 text-[13px] font-mono text-white placeholder-[#6e7681] outline-none"
            />
            <textarea
              value={fEnv()}
              onInput={(e) => setFEnv(e.currentTarget.value)}
              placeholder="env opcional, una KEY=VALOR por línea"
              rows={2}
              class="w-full bg-[#161b22] border border-[#30363d] rounded-md px-2.5 py-1.5 text-[12px] font-mono text-white placeholder-[#6e7681] outline-none"
            />
          </Show>
          <div class="flex gap-2 justify-end">
            <button
              onClick={test}
              disabled={!valid() || busy() !== null}
              class="px-3 py-1.5 rounded-md bg-[#161b22] border border-[#30363d] text-[13px] text-[#8b949e] hover:text-white disabled:opacity-50"
            >
              {busy() === "test" ? "Probando…" : "🧪 Probar sin guardar"}
            </button>
            <button
              onClick={save}
              disabled={!valid() || busy() !== null}
              class="px-4 py-1.5 rounded-md bg-[#238636] text-white text-[13px] disabled:opacity-50"
            >
              {busy() === "save" ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </div>
      </Show>
    </div>
  );
}
