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

  const [addMode, setAddMode] = createSignal<"form" | "json">("form");
  const [rawJson, setRawJson] = createSignal("");

  // formulario
  const [fName, setFName] = createSignal("");
  const [fTransport, setFTransport] = createSignal<"stdio" | "sse">("stdio");
  const [fCommand, setFCommand] = createSignal("");
  const [fArgs, setFArgs] = createSignal("");
  const [fUrl, setFUrl] = createSignal("");
  const [fHeaders, setFHeaders] = createSignal("");
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

  function parseHeaders(): Record<string, string> | undefined {
    const out: Record<string, string> = {};
    for (const line of fHeaders().split("\n")) {
      const t = line.trim();
      if (!t || t.startsWith("#")) continue;
      const i = t.indexOf(":") > 0 ? t.indexOf(":") : t.indexOf("=");
      if (i > 0) out[t.slice(0, i).trim()] = t.slice(i + 1).trim();
    }
    return Object.keys(out).length ? out : undefined;
  }

  function buildConfig(): Record<string, any> {
    if (fTransport() === "sse") {
      const cfg: Record<string, any> = { transport: "sse", url: fUrl().trim() };
      const hdrs = parseHeaders();
      if (hdrs) cfg.headers = hdrs;
      return cfg;
    }

    let cmd = fCommand().trim();
    let args = fArgs().split(/\s+/).map((s) => s.trim()).filter(Boolean);

    // Si el usuario pegó el comando completo con argumentos en el campo de comando
    if (cmd.includes(" ") || cmd.includes("\t")) {
      const parts = cmd.split(/\s+/).filter(Boolean);
      cmd = parts[0];
      args = [...parts.slice(1), ...args];
    }

    // Asegurar flag -y para npx para evitar que bloquee esperando confirmación
    if (cmd.endsWith("npx") && !args.includes("-y") && !args.includes("--yes")) {
      args.unshift("-y");
    }

    const cfg: Record<string, any> = {
      transport: "stdio",
      command: cmd,
      args,
    };
    const env = parseEnv();
    if (env) cfg.env = env;
    return cfg;
  }

  function handleCommandInput(val: string) {
    const trimmed = val.trim();
    if (trimmed.startsWith("{")) {
      populateFromJson(trimmed);
      return;
    }
    if ((trimmed.startsWith("npx ") || trimmed.startsWith("node ") || trimmed.startsWith("uvx ")) && !fArgs().trim()) {
      const parts = trimmed.split(/\s+/);
      setFCommand(parts[0]);
      setFArgs(parts.slice(1).join(" "));
      if (!fName().trim()) {
        const pkg = parts.find((p) => !p.startsWith("-") && p !== parts[0]);
        if (pkg) {
          const clean = pkg.replace(/^@.*\//, "").replace(/[^a-zA-Z0-9_-]/g, "");
          if (clean) setFName(clean);
        }
      }
      return;
    }
    setFCommand(val);
  }

  function populateFromJson(text: string): boolean {
    try {
      const parsed = JSON.parse(text);
      let srvName = "";
      let srvConf: any = null;

      if (parsed.mcpServers && typeof parsed.mcpServers === "object") {
        const keys = Object.keys(parsed.mcpServers);
        if (keys.length > 0) {
          srvName = keys[0];
          srvConf = parsed.mcpServers[srvName];
        }
      } else if (parsed.command || parsed.url) {
        srvConf = parsed;
      } else {
        const keys = Object.keys(parsed);
        if (keys.length > 0 && typeof parsed[keys[0]] === "object") {
          srvName = keys[0];
          srvConf = parsed[srvName];
        }
      }

      if (srvConf) {
        if (srvName && !fName().trim()) setFName(srvName);
        if (srvConf.url || srvConf.transport === "sse") {
          setFTransport("sse");
          setFUrl(srvConf.url || "");
          if (srvConf.headers) {
            setFHeaders(
              Object.entries(srvConf.headers)
                .map(([k, v]) => `${k}: ${v}`)
                .join("\n")
            );
          }
        } else {
          setFTransport("stdio");
          setFCommand(srvConf.command || "");
          setFArgs(Array.isArray(srvConf.args) ? srvConf.args.join(" ") : "");
          if (srvConf.env) {
            setFEnv(
              Object.entries(srvConf.env)
                .map(([k, v]) => `${k}=${v}`)
                .join("\n")
            );
          }
        }
        setAddMode("form");
        setNotice("✅ Configuración importada al formulario.");
        return true;
      }
    } catch {
      // Ignorar si no es JSON válido aún
    }
    return false;
  }

  function valid(): boolean {
    if (addMode() === "json") return !!rawJson().trim();
    if (!fName().trim()) return false;
    if (fTransport() === "sse") return !!fUrl().trim();
    return !!fCommand().trim();
  }

  async function save() {
    if (!valid() || busy()) return;
    setBusy("save");
    setNotice("");
    try {
      if (addMode() === "json") {
        await api.saveMCPRaw(rawJson().trim(), fScope());
        setNotice(`✅ Servidor(es) guardado(s) desde JSON (${fScope()}).`);
      } else {
        await api.saveMCP(fName().trim(), buildConfig(), fScope());
        setNotice(`✅ Servidor '${fName().trim()}' guardado (${fScope()}).`);
      }
      setShowAdd(false);
      setRawJson("");
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
      const cfg = addMode() === "json" ? { raw_json: rawJson().trim() } : buildConfig();
      const r = await api.testMCP(cfg);
      setNotice(`🧪 ${JSON.stringify(r).slice(0, 300)}`);
    } catch (e) {
      setNotice(`❌ Error: ${e}`);
    } finally {
      setBusy(null);
    }
  }

  async function toggle(name: string) {
    setBusy(`t:${name}`);
    setNotice("");
    try {
      const r = await api.toggleMCP(name);
      setNotice(r.disabled ? `⏸ Servidor '${name}' deshabilitado.` : `▶ Servidor '${name}' habilitado.`);
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
    setNotice("");
    try {
      await api.deleteMCP(name);
      setNotice(`✅ Servidor '${name}' eliminado.`);
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
          class="text-[12px] px-3.5 py-1.5 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-100 font-medium border border-white/[0.08] shadow-sm transition-all active:scale-95"
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
                  <Show when={s().source}>
                    <span
                      class="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-300 font-mono border border-violet-500/30"
                      title={`Detectado automáticamente desde ${s().source}`}
                    >
                      {s().source === "claude_code"
                        ? "claude code"
                        : s().source === "claude_code_project"
                        ? "claude (proyecto)"
                        : s().source === "claude_desktop"
                        ? "claude desktop"
                        : s().source === "project_mcp_json"
                        ? ".mcp.json"
                        : s().source}
                    </span>
                  </Show>
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
          <div class="flex items-center justify-between pb-1 border-b border-white/[0.06]">
            <div class="flex gap-1.5">
              <button
                onClick={() => setAddMode("form")}
                class={`px-3 py-1 rounded-lg text-[12px] font-medium transition-all ${
                  addMode() === "form"
                    ? "bg-white/[0.12] text-white"
                    : "text-slate-400 hover:text-white hover:bg-white/[0.05]"
                }`}
              >
                Formulario
              </button>
              <button
                onClick={() => setAddMode("json")}
                class={`px-3 py-1 rounded-lg text-[12px] font-medium transition-all ${
                  addMode() === "json"
                    ? "bg-white/[0.12] text-white"
                    : "text-slate-400 hover:text-white hover:bg-white/[0.05]"
                }`}
              >
                Pegar JSON (Claude / mcpservers)
              </button>
            </div>
            <select
              value={fScope()}
              onChange={(e) => setFScope(e.currentTarget.value as MCPScope)}
              title="Ámbito: project (.kogniterm/config.json) o global (~/.kogniterm)"
              class="bg-white/[0.06] rounded-lg px-2.5 py-1 text-[11.5px] text-white outline-none"
            >
              <option value="project">project</option>
              <option value="global">global</option>
            </select>
          </div>

          <Show
            when={addMode() === "form"}
            fallback={
              <div class="space-y-2">
                <textarea
                  value={rawJson()}
                  onInput={(e) => setRawJson(e.currentTarget.value)}
                  placeholder={`Pega aquí el JSON de mcpservers.org o Claude Desktop:\n{\n  "mcpServers": {\n    "ai-docs": {\n      "command": "npx",\n      "args": ["-y", "hyperresearch-ai-docs-mcp"]\n    }\n  }\n}`}
                  rows={6}
                  class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 rounded-xl px-3.5 py-2.5 text-[12px] font-mono text-white placeholder-zinc-500 outline-none transition-all resize-y"
                />
                <div class="flex justify-between items-center text-[11px] text-slate-400">
                  <span>💡 Detecta automáticamente formato Claude Desktop, mcpservers.org o lista de servidores.</span>
                  <button
                    onClick={() => populateFromJson(rawJson())}
                    class="text-indigo-400 hover:text-indigo-300 font-medium px-2 py-1"
                  >
                    Rellenar en formulario ↗
                  </button>
                </div>
              </div>
            }
          >
            <div class="flex gap-2">
              <input
                value={fName()}
                onInput={(e) => setFName(e.currentTarget.value)}
                placeholder="nombre (p.ej. git, memory, ai-docs)"
                class="flex-1 bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 rounded-xl px-3.5 py-2 text-[13px] text-white placeholder-zinc-500 outline-none transition-all"
              />
              <select
                value={fTransport()}
                onChange={(e) => setFTransport(e.currentTarget.value as "stdio" | "sse")}
                class="bg-white/[0.06] rounded-xl px-3 py-2 text-[12.5px] text-white outline-none"
              >
                <option value="stdio">stdio (npx, uvx, local)</option>
                <option value="sse">sse (remoto / url)</option>
              </select>
            </div>
            <Show
              when={fTransport() === "stdio"}
              fallback={
                <div class="space-y-2">
                  <input
                    value={fUrl()}
                    onInput={(e) => setFUrl(e.currentTarget.value)}
                    placeholder="https://mcp.hyperresearch.ai/mcp o http://localhost:8000/sse"
                    class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 rounded-xl px-3.5 py-2 text-[13px] font-mono text-white placeholder-zinc-500 outline-none transition-all"
                  />
                  <textarea
                    value={fHeaders()}
                    onInput={(e) => setFHeaders(e.currentTarget.value)}
                    placeholder="Headers HTTP opcionales (Authorization: Bearer ..., uno por línea)"
                    rows={2}
                    class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 rounded-xl px-3.5 py-2 text-[12px] font-mono text-white placeholder-zinc-500 outline-none transition-all"
                  />
                </div>
              }
            >
              <input
                value={fCommand()}
                onInput={(e) => handleCommandInput(e.currentTarget.value)}
                placeholder="comando (ej. npx -y @modelcontextprotocol/server-memory, uvx, node)"
                class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 rounded-xl px-3.5 py-2 text-[13px] font-mono text-white placeholder-zinc-500 outline-none transition-all"
              />
              <input
                value={fArgs()}
                onInput={(e) => setFArgs(e.currentTarget.value)}
                placeholder="args adicionales (opcional si ya los pusiste en comando)"
                class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 rounded-xl px-3.5 py-2 text-[13px] font-mono text-white placeholder-zinc-500 outline-none transition-all"
              />
              <textarea
                value={fEnv()}
                onInput={(e) => setFEnv(e.currentTarget.value)}
                placeholder="variables de entorno opcionales (KEY=VALOR por línea)"
                rows={2}
                class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 rounded-xl px-3.5 py-2 text-[12px] font-mono text-white placeholder-zinc-500 outline-none transition-all"
              />
            </Show>
          </Show>

          <div class="flex gap-2 justify-end pt-1">
            <button
              onClick={test}
              disabled={!valid() || busy() !== null}
              class="px-4 py-2 rounded-full bg-white/[0.08] hover:bg-white/[0.14] text-[12.5px] text-zinc-300 hover:text-white transition-all active:scale-95 disabled:opacity-50"
            >
              {busy() === "test" ? "Probando…" : "🧪 Probar"}
            </button>
            <button
              onClick={save}
              disabled={!valid() || busy() !== null}
              class="px-5 py-2 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-100 text-[12.5px] font-medium border border-white/[0.08] shadow-sm transition-all active:scale-95 disabled:opacity-50"
            >
              {busy() === "save" ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </div>
      </Show>
    </div>
  );
}
