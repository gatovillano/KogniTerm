import { For, Show, createSignal } from "solid-js";
import { api, apiRoot, token, setToken, setApiUrl, PROVIDERS, KEY_PROVIDERS, type LLMConfig } from "../lib/api";
import { MCPPanel } from "./MCPPanel";

function Shell(props: { title: string; onClose: () => void; children: any }) {
  return (
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={props.onClose}>
      <div
        class="w-[480px] max-w-[90vw] max-h-[70vh] overflow-hidden rounded-lg bg-[#161b22] border border-[#30363d]"
        onClick={(e) => e.stopPropagation()}
      >
        <div class="px-4 py-3 border-b border-[#21262d] flex items-center">
          <span class="text-white text-[14px] font-medium">{props.title}</span>
          <div class="flex-1" />
          <button class="text-[#8b949e] hover:text-white" onClick={props.onClose}>
            ✕
          </button>
        </div>
        <div class="p-2">{props.children}</div>
      </div>
    </div>
  );
}

function FilterInput(props: { value: string; onInput: (v: string) => void; placeholder: string }) {
  return (
    <input
      value={props.value}
      onInput={(e) => props.onInput(e.currentTarget.value)}
      placeholder={props.placeholder}
      class="w-full m-2 bg-[#0d1117] border border-[#30363d] rounded-md px-3 py-2 text-[13px] text-white placeholder-[#6e7681] outline-none"
      style={{ width: "calc(100% - 16px)" }}
    />
  );
}

/** Modal Proveedor — espejo de TUI _handle_provider. */
export function ProviderModal(props: { current: LLMConfig | null; onClose: () => void; onDone: () => void }) {
  const [q, setQ] = createSignal("");
  const [busy, setBusy] = createSignal<string | null>(null);
  const list = () => PROVIDERS.filter((p) => (p.id + p.label).toLowerCase().includes(q().toLowerCase()));

  async function pick(id: string) {
    setBusy(id);
    try {
      await api.setLLM({ provider: id });
    } catch (e) {
      alert(`Error: ${e}`);
    } finally {
      setBusy(null);
      props.onDone();
      props.onClose();
    }
  }

  return (
    <Shell title="Seleccionar Proveedor" onClose={props.onClose}>
      <FilterInput value={q()} onInput={setQ} placeholder="Filtrar proveedores…" />
      <div class="max-h-[320px] overflow-y-auto">
        <For each={list()}>
          {(p) => (
            <button
              onClick={() => pick(p.id)}
              class="w-full text-left px-4 py-2 rounded-md hover:bg-[#21262d] flex items-center gap-2"
            >
              <Show when={props.current?.provider === p.id}>
                <span class="text-emerald-400">●</span>
              </Show>
              <span class="text-[13px] text-white">{p.label}</span>
              <span class="text-[11px] text-[#8b949e] font-mono ml-auto">{p.id}</span>
              <Show when={busy() === p.id}>
                <span class="text-[11px] text-amber-300">…</span>
              </Show>
            </button>
          )}
        </For>
      </div>
      <p class="px-4 py-2 text-[11px] text-[#6e7681]">Igual que /provider en TUI. Cambia default_model y recarga sesiones.</p>
    </Shell>
  );
}

/** Modal Modelo — espejo de TUI _handle_models (filtra por proveedor activo). */
export function ModelModal(props: { current: LLMConfig | null; onClose: () => void; onDone: () => void }) {
  const [q, setQ] = createSignal("");
  const [models, setModels] = createSignal<string[]>([]);
  const [err, setErr] = createSignal("");

  (async () => {
    try {
      const data = await api.getModels();
      const prov = props.current?.provider ?? "google";
      const entry = data.providers.find((p) => p.id === prov);
      setModels(entry?.models ?? data.providers.flatMap((p) => p.models));
    } catch (e) {
      setErr(String(e));
    }
  })();

  const list = () => models().filter((m) => m.toLowerCase().includes(q().toLowerCase()));

  async function pick(model: string) {
    try {
      await api.setLLM({ model });
    } catch (e) {
      alert(`Error: ${e}`);
      return;
    }
    props.onDone();
    props.onClose();
  }

  return (
    <Shell title={`Seleccionar Modelo (${props.current?.provider ?? "…"})`} onClose={props.onClose}>
      <FilterInput value={q()} onInput={setQ} placeholder="Filtrar modelos…" />
      <Show when={err()}>
        <p class="px-4 py-2 text-[12px] text-red-300">{err()}</p>
      </Show>
      <div class="max-h-[320px] overflow-y-auto">
        <For each={list()}>
          {(m) => (
            <button onClick={() => pick(m)} class="w-full text-left px-4 py-1.5 rounded-md hover:bg-[#21262d]">
              <span class={`text-[13px] font-mono ${m === props.current?.model ? "text-emerald-300" : "text-white"}`}>{m}</span>
            </button>
          )}
        </For>
        <Show when={list().length === 0 && !err()}>
          <p class="px-4 py-3 text-[12px] text-[#8b949e]">Cargando modelos…</p>
        </Show>
      </div>
    </Shell>
  );
}

export type SettingsTab = "provider" | "models" | "keys" | "connection" | "mcp";

/** Menú de configuración unificado: Proveedor → Modelos live → Keys.
 *  Al cambiar de proveedor recarga la lista desde GET /models/available
 *  (el backend consulta la API correspondiente si hay key, si no fallback).
 *  Al guardar una key recarga modelos para ese proveedor. */
export function UnifiedSettingsModal(props: {
  current: LLMConfig | null;
  initialTab?: SettingsTab;
  onClose: () => void;
  onDone: () => void;
}) {
  const [tab, setTab] = createSignal<SettingsTab>(props.initialTab ?? "provider");
  const [q, setQ] = createSignal("");
  const [selProv, setSelProv] = createSignal<string>(props.current?.provider ?? "google");
  const [models, setModels] = createSignal<string[]>([]);
  const [loadingModels, setLoadingModels] = createSignal(false);
  const [modelsErr, setModelsErr] = createSignal("");
  const [busyProv, setBusyProv] = createSignal<string | null>(null);
  const [keyProv, setKeyProv] = createSignal<string | null>(null);
  const [keyVal, setKeyVal] = createSignal("");
  const [busyKey, setBusyKey] = createSignal(false);
  const [notice, setNotice] = createSignal("");
  const [connUrl, setConnUrl] = createSignal(apiRoot());
  const [connToken, setConnToken] = createSignal(token());
  const [busyConn, setBusyConn] = createSignal(false);

  async function loadModels(provider: string) {
    setLoadingModels(true);
    setModelsErr("");
    try {
      const data = await api.getModels();
      const entry = data.providers.find((p) => p.id === provider);
      setModels(entry?.models ?? []);
      if (!entry || entry.models.length === 0) setModelsErr(`Sin modelos para '${provider}'. Configura su key primero.`);
    } catch (e) {
      setModelsErr(String(e));
      setModels([]);
    } finally {
      setLoadingModels(false);
    }
  }

  // carga inicial + al cambiar de proveedor o al entrar a la pestaña modelos
  if (tab() === "models") void loadModels(selProv());

  async function pickProvider(id: string) {
    setBusyProv(id);
    setNotice("");
    try {
      await api.setLLM({ provider: id });
      setSelProv(id);
      props.onDone(); // refresca topbar (GET /config/llm)
      setTab("models");
      setQ("");
      await loadModels(id);
      setNotice(`Proveedor → ${id}. Lista recargada desde su API.`);
    } catch (e) {
      setNotice(`Error: ${e}`);
    } finally {
      setBusyProv(null);
    }
  }

  async function pickModel(model: string) {
    try {
      await api.setLLM({ model });
    } catch (e) {
      setNotice(`Error: ${e}`);
      return;
    }
    props.onDone();
    props.onClose();
  }

  async function saveKey() {
    const p = keyProv() ?? selProv();
    if (!p || !keyVal()) return;
    setBusyKey(true);
    try {
      await api.setLLM({ provider: p, api_key: keyVal() });
      props.onDone();
      setSelProv(p);
      setKeyVal("");
      setKeyProv(null);
      setTab("models");
      await loadModels(p);
      setNotice(`Key guardada para ${p}. Modelos recargados en vivo.`);
    } catch (e) {
      setNotice(`Error: ${e}`);
    } finally {
      setBusyKey(false);
    }
  }

  async function testConnection() {
    setBusyConn(true);
    setNotice("");
    try {
      setApiUrl(connUrl());
      setToken(connToken());
      const h = await api.health();
      setNotice(`Conectado: ${JSON.stringify(h).slice(0, 120)}`);
      props.onDone();
    } catch (e) {
      setNotice(`Sin conexión: ${e}`);
    } finally {
      setBusyConn(false);
    }
  }

  const provList = () => PROVIDERS.filter((p) => (p.id + p.label).toLowerCase().includes(q().toLowerCase()));
  const modelList = () => models().filter((m) => m.toLowerCase().includes(q().toLowerCase()));

  function switchTab(t: SettingsTab) {
    setTab(t);
    setQ("");
    setNotice("");
    if (t === "models") void loadModels(selProv());
  }

  return (
    <Shell title="⚙ Ajustes — Proveedor · Modelos · Keys · Conexión · MCP" onClose={props.onClose}>
      {/* tabs */}
      <div class="flex gap-1 px-2 pt-1 flex-wrap">
        {(["provider", "models", "keys", "connection", "mcp"] as SettingsTab[]).map((t) => (
          <button
            onClick={() => switchTab(t)}
            class={`px-2.5 py-1.5 rounded-md text-[13px] ${tab() === t ? "bg-[#21262d] text-white" : "text-[#8b949e] hover:text-white"}`}
          >
            {t === "provider" ? "1 · Proveedor" : t === "models" ? "2 · Modelo" : t === "keys" ? "3 · Keys" : t === "connection" ? "4 · Conexión" : "5 · MCP"}
          </button>
        ))}
        <div class="flex-1" />
        <Show when={tab() === "provider" || tab() === "models"}>
          <button
            onClick={() => void loadModels(selProv())}
            class="px-2 py-1.5 text-[12px] text-[#8b949e] hover:text-white"
            title="Recargar modelos desde la API del proveedor"
          >
            ↻ recargar
          </button>
        </Show>
      </div>

      <Show when={tab() !== "connection" && tab() !== "mcp"}>
        <FilterInput
          value={q()}
          onInput={setQ}
          placeholder={tab() === "provider" ? "Filtrar proveedores…" : tab() === "models" ? `Filtrar modelos de ${selProv()}…` : "Filtrar…"}
        />
      </Show>

      <Show when={notice()}>
        <p class="px-4 py-1 text-[12px] text-amber-200">{notice()}</p>
      </Show>

      {/* ── PROVIDER ── */}
      <Show when={tab() === "provider"}>
        <div class="max-h-[300px] overflow-y-auto">
          <For each={provList()}>
            {(p) => (
              <button onClick={() => pickProvider(p.id)} class="w-full text-left px-4 py-2 rounded-md hover:bg-[#21262d] flex items-center gap-2">
                <Show when={selProv() === p.id}>
                  <span class="text-emerald-400">●</span>
                </Show>
                <span class="text-[13px] text-white">{p.label}</span>
                <span class="text-[11px] text-[#8b949e] font-mono ml-auto">{p.id}</span>
                <Show when={busyProv() === p.id}>
                  <span class="text-[11px] text-amber-300">…</span>
                </Show>
              </button>
            )}
          </For>
        </div>
        <p class="px-4 py-2 text-[11px] text-[#6e7681]">Elegir proveedor lo activa y salta a Modelos con la lista live de su API.</p>
      </Show>

      {/* ── MODELS (live por proveedor seleccionado) ── */}
      <Show when={tab() === "models"}>
        <div class="px-4 py-1 flex items-center gap-2">
          <span class="text-[11px] text-[#8b949e]">Proveedor:</span>
          <select
            value={selProv()}
            onChange={(e) => {
              setSelProv(e.currentTarget.value);
              void loadModels(e.currentTarget.value);
            }}
            class="bg-[#0d1117] border border-[#30363d] rounded-md px-2 py-1 text-[12px] text-white outline-none"
          >
            <For each={PROVIDERS}>{(p) => <option value={p.id}>{p.label}</option>}</For>
          </select>
          <Show when={loadingModels()}>
            <span class="text-[11px] text-amber-300">cargando desde API…</span>
          </Show>
        </div>
        <Show when={modelsErr()}>
          <p class="px-4 py-1 text-[12px] text-red-300">{modelsErr()}</p>
        </Show>
        <div class="max-h-[280px] overflow-y-auto">
          <For each={modelList()}>
            {(m) => (
              <button onClick={() => pickModel(m)} class="w-full text-left px-4 py-1.5 rounded-md hover:bg-[#21262d]">
                <span class={`text-[13px] font-mono ${m === props.current?.model ? "text-emerald-300" : "text-white"}`}>{m}</span>
              </button>
            )}
          </For>
          <Show when={modelList().length === 0 && !modelsErr() && !loadingModels()}>
            <p class="px-4 py-3 text-[12px] text-[#8b949e]">Sin resultados para el filtro.</p>
          </Show>
        </div>
      </Show>

      {/* ── KEYS ── */}
      <Show when={tab() === "keys"}>
        <Show
          when={!keyProv()}
          fallback={
            <div class="p-2">
              <p class="px-2 py-1 text-[13px] text-white">
                API Key para <b class="font-mono">{keyProv()}</b>
                <span class="text-[#8b949e]"> ({KEY_PROVIDERS.find((k) => k.id === keyProv())?.env})</span>
              </p>
              <input
                type="password"
                value={keyVal()}
                onInput={(e) => setKeyVal(e.currentTarget.value)}
                placeholder="Introduce la llave…"
                class="w-full m-2 bg-[#0d1117] border border-[#30363d] rounded-md px-3 py-2 text-[13px] text-white outline-none"
                style={{ width: "calc(100% - 16px)" }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void saveKey();
                  if (e.key === "Escape") setKeyProv(null);
                }}
              />
              <div class="flex gap-2 p-2">
                <button onClick={() => setKeyProv(null)} class="px-3 py-1.5 rounded-md text-[13px] text-[#8b949e] hover:text-white">
                  ← Volver
                </button>
                <div class="flex-1" />
                <button
                  onClick={saveKey}
                  disabled={!keyVal() || busyKey()}
                  class="px-4 py-1.5 rounded-md bg-[#238636] text-white text-[13px] disabled:opacity-50"
                >
                  {busyKey() ? "Guardando…" : "Guardar y recargar modelos"}
                </button>
              </div>
            </div>
          }
        >
          <For each={KEY_PROVIDERS}>
            {(k) => (
              <button
                onClick={() => {
                  setKeyVal("");
                  setKeyProv(k.id);
                }}
                class="w-full text-left px-4 py-2 rounded-md hover:bg-[#21262d] flex items-center gap-2"
              >
                <span class="text-[13px] text-white capitalize">{k.id}</span>
                <span class="text-[11px] text-[#8b949e] font-mono ml-auto">{k.env}</span>
              </button>
            )}
          </For>
          <p class="px-4 py-2 text-[11px] text-[#6e7681]">Al guardar, se recargan los modelos live de ese proveedor.</p>
        </Show>
      </Show>

      {/* ── CONEXIÓN (URL + token en runtime, sin rebuild) ── */}
      <Show when={tab() === "connection"}>
        <div class="p-2 space-y-2">
          <label class="block px-2 pt-1 text-[12px] text-[#8b949e]">URL del backend nativo</label>
          <input
            value={connUrl()}
            onInput={(e) => setConnUrl(e.currentTarget.value)}
            placeholder="http://127.0.0.1:8755  (vacío = proxy /kapi en dev)"
            class="w-full m-2 bg-[#0d1117] border border-[#30363d] rounded-md px-3 py-2 text-[13px] font-mono text-white outline-none"
            style={{ width: "calc(100% - 16px)" }}
          />
          <label class="block px-2 text-[12px] text-[#8b949e]">Token (KOGNITERM_API_TOKEN del servidor)</label>
          <input
            type="password"
            value={connToken()}
            onInput={(e) => setConnToken(e.currentTarget.value)}
            placeholder="Bearer token… (vacío = sin auth local)"
            class="w-full m-2 bg-[#0d1117] border border-[#30363d] rounded-md px-3 py-2 text-[13px] font-mono text-white outline-none"
            style={{ width: "calc(100% - 16px)" }}
            onKeyDown={(e) => {
              if (e.key === "Enter") void testConnection();
            }}
          />
          <div class="flex gap-2 p-2">
            <div class="flex-1" />
            <button
              onClick={testConnection}
              disabled={busyConn()}
              class="px-4 py-1.5 rounded-md bg-[#238636] text-white text-[13px] disabled:opacity-50"
            >
              {busyConn() ? "Probando…" : "Guardar y probar"}
            </button>
          </div>
          <p class="px-4 py-1 text-[11px] text-[#6e7681]">
            Se guarda en localStorage y aplica al instante (REST y WS). Recarga la página para reabrir sockets con la nueva URL.
          </p>
        </div>
      </Show>

      {/* ── MCP (servidores Model Context Protocol) ── */}
      <Show when={tab() === "mcp"}>
        <MCPPanel />
      </Show>
    </Shell>
  );
}
export function KeysModal(props: { onClose: () => void; onDone: () => void }) {
  const [stepProv, setStepProv] = createSignal<string | null>(null);
  const [key, setKey] = createSignal("");
  const [busy, setBusy] = createSignal(false);

  async function save() {
    if (!stepProv() || !key()) return;
    setBusy(true);
    try {
      await api.setLLM({ provider: stepProv()!, api_key: key() });
    } catch (e) {
      alert(`Error: ${e}`);
      setBusy(false);
      return;
    }
    setBusy(false);
    props.onDone();
    props.onClose();
  }

  return (
    <Shell title="Configurar API Keys" onClose={props.onClose}>
      <Show
        when={!stepProv()}
        fallback={
          <div class="p-2">
            <p class="px-2 py-1 text-[13px] text-white">
              API Key para <b class="font-mono">{stepProv()}</b>
              <span class="text-[#8b949e]"> ({KEY_PROVIDERS.find((k) => k.id === stepProv())?.env})</span>
            </p>
            <input
              type="password"
              value={key()}
              onInput={(e) => setKey(e.currentTarget.value)}
              placeholder="Introduce la llave…"
              class="w-full m-2 bg-[#0d1117] border border-[#30363d] rounded-md px-3 py-2 text-[13px] text-white outline-none"
              style={{ width: "calc(100% - 16px)" }}
              onKeyDown={(e) => {
                if (e.key === "Enter") void save();
                if (e.key === "Escape") setStepProv(null);
              }}
            />
            <div class="flex gap-2 p-2">
              <button onClick={() => setStepProv(null)} class="px-3 py-1.5 rounded-md text-[13px] text-[#8b949e] hover:text-white">
                ← Volver
              </button>
              <div class="flex-1" />
              <button
                onClick={save}
                disabled={!key() || busy()}
                class="px-4 py-1.5 rounded-md bg-[#238636] text-white text-[13px] disabled:opacity-50"
              >
                {busy() ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </div>
        }
      >
        <For each={KEY_PROVIDERS}>
          {(k) => (
            <button
              onClick={() => {
                setKey("");
                setStepProv(k.id);
              }}
              class="w-full text-left px-4 py-2 rounded-md hover:bg-[#21262d] flex items-center gap-2"
            >
              <span class="text-[13px] text-white capitalize">{k.id}</span>
              <span class="text-[11px] text-[#8b949e] font-mono ml-auto">{k.env}</span>
            </button>
          )}
        </For>
        <p class="px-4 py-2 text-[11px] text-[#6e7681]">Igual que /keys en TUI. POST /config/llm con provider + api_key.</p>
      </Show>
    </Shell>
  );
}
