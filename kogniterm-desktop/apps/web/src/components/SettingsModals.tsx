import { For, Show, createSignal } from "solid-js";
import { api, apiRoot, token, setToken, setApiUrl, PROVIDERS, KEY_PROVIDERS, type LLMConfig } from "../lib/api";
import { MCPPanel } from "./MCPPanel";

function Shell(props: { title: string; onClose: () => void; children: any }) {
  return (
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xl animate-fade-in p-4" onClick={props.onClose}>
      <div
        class="w-[520px] max-w-[92vw] max-h-[85vh] overflow-hidden rounded-3xl glass-modal p-6 animate-scale-in flex flex-col select-none"
        onClick={(e) => e.stopPropagation()}
      >
        <div class="pb-3 flex items-center">
          <span class="text-white text-[16px] font-semibold tracking-tight">{props.title}</span>
          <div class="flex-1" />
          <button
            class="w-7 h-7 rounded-full flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/[0.08] transition-all text-[13px]"
            onClick={props.onClose}
          >
            ✕
          </button>
        </div>
        <div class="flex-1 min-h-0 overflow-y-auto pt-1">{props.children}</div>
      </div>
    </div>
  );
}

function FilterInput(props: { value: string; onInput: (v: string) => void; placeholder: string }) {
  return (
    <div class="my-2">
      <input
        value={props.value}
        onInput={(e) => props.onInput(e.currentTarget.value)}
        placeholder={props.placeholder}
        class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 border border-white/[0.08] rounded-full px-4 py-2 text-[13px] text-white placeholder-zinc-500 outline-none transition-all"
      />
    </div>
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
      <div class="max-h-[340px] overflow-y-auto space-y-1">
        <For each={list()}>
          {(p) => (
            <button
              onClick={() => pick(p.id)}
              class="w-full text-left px-4 py-2.5 rounded-2xl hover:bg-white/[0.06] flex items-center gap-3 transition-all active:scale-[0.98]"
            >
              <Show when={props.current?.provider === p.id} fallback={<span class="w-2 h-2 rounded-full bg-slate-600" />}>
                <span class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" />
              </Show>
              <span class="text-[13.5px] text-white font-medium">{p.label}</span>
              <span class="text-[11px] text-slate-400 font-mono ml-auto">{p.id}</span>
              <Show when={busy() === p.id}>
                <span class="text-[11px] text-amber-300">…</span>
              </Show>
            </button>
          )}
        </For>
      </div>
      <p class="pt-3 text-[11.5px] text-slate-400">Igual que /provider en TUI. Cambia default_model y recarga sesiones.</p>
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
    <Shell title={`Modelos de ${props.current?.provider ?? "proveedor"}`} onClose={props.onClose}>
      <FilterInput value={q()} onInput={setQ} placeholder="Filtrar modelos…" />
      <Show when={err()}>
        <p class="text-[12px] text-red-300 mb-2">{err()}</p>
      </Show>
      <div class="max-h-[340px] overflow-y-auto space-y-1">
        <For each={list()}>
          {(m) => (
            <button
              onClick={() => pick(m)}
              class="w-full text-left px-4 py-2 rounded-2xl hover:bg-white/[0.06] transition-all active:scale-[0.98]"
            >
              <span class={`text-[13px] font-mono ${m === props.current?.model ? "text-emerald-300 font-semibold" : "text-white"}`}>
                {m}
              </span>
            </button>
          )}
        </For>
        <Show when={list().length === 0 && !err()}>
          <p class="py-6 text-[12.5px] text-slate-400 text-center">Sin resultados para el filtro.</p>
        </Show>
      </div>
    </Shell>
  );
}

export type SettingsTab = "provider" | "models" | "keys" | "connection" | "mcp";

/** Ajustes unificados: Proveedor, Modelo, Keys, Conexión y MCP en una sola ventana. */
export function UnifiedSettingsModal(props: {
  current: LLMConfig | null;
  initialTab?: SettingsTab;
  onClose: () => void;
  onDone: () => void;
}) {
  const [tab, setTab] = createSignal<SettingsTab>(props.initialTab ?? "provider");
  const [q, setQ] = createSignal("");
  const [notice, setNotice] = createSignal("");

  const [selProv, setSelProv] = createSignal<string>(props.current?.provider ?? "google");
  const [models, setModels] = createSignal<string[]>([]);
  const [loadingModels, setLoadingModels] = createSignal(false);
  const [modelsErr, setModelsErr] = createSignal("");
  const [busyProv, setBusyProv] = createSignal<string | null>(null);

  const [keyProv, setKeyProv] = createSignal<string | null>(null);
  const [keyVal, setKeyVal] = createSignal("");
  const [busyKey, setBusyKey] = createSignal(false);

  const [connUrl, setConnUrl] = createSignal(apiRoot());
  const [connToken, setConnToken] = createSignal(token() ?? "");
  const [busyConn, setBusyConn] = createSignal(false);

  async function loadModels(provId: string) {
    setLoadingModels(true);
    setModelsErr("");
    try {
      const data = await api.getModels();
      const entry = data.providers.find((p) => p.id === provId);
      setModels(entry?.models ?? data.providers.flatMap((p) => p.models));
    } catch (e) {
      setModelsErr(`No se pudieron cargar modelos de ${provId}: ${e}`);
      setModels([]);
    } finally {
      setLoadingModels(false);
    }
  }

  void loadModels(selProv());

  async function pickProvider(id: string) {
    setBusyProv(id);
    setNotice("");
    try {
      await api.setLLM({ provider: id });
      setSelProv(id);
      props.onDone();
      setTab("models");
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
      setNotice(`Key guardada para ${p}. Modelos recargados.`);
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
    <Shell title="⚙ Ajustes del Sistema" onClose={props.onClose}>
      {/* Selector de pestañas en cápsula tipo dock */}
      <div class="flex gap-1 p-1 rounded-full bg-white/[0.04] mb-3 overflow-x-auto select-none">
        {(["provider", "models", "keys", "connection", "mcp"] as SettingsTab[]).map((t) => (
          <button
            onClick={() => switchTab(t)}
            class={`px-3 py-1.5 rounded-full text-[12px] font-medium transition-all duration-150 active:scale-95 shrink-0 ${
              tab() === t ? "bg-white/[0.12] text-white shadow-sm" : "text-slate-400 hover:text-white"
            }`}
          >
            {t === "provider"
              ? "Proveedor"
              : t === "models"
                ? "Modelo"
                : t === "keys"
                  ? "Keys"
                  : t === "connection"
                    ? "Conexión"
                    : "MCP"}
          </button>
        ))}
        <div class="flex-1" />
        <Show when={tab() === "provider" || tab() === "models"}>
          <button
            onClick={() => void loadModels(selProv())}
            class="px-2.5 py-1 text-[11px] text-slate-400 hover:text-white rounded-full transition-all"
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
        <p class="px-2 py-1 text-[12px] text-amber-300 animate-fade-in">{notice()}</p>
      </Show>

      {/* ── PROVIDER ── */}
      <Show when={tab() === "provider"}>
        <div class="max-h-[300px] overflow-y-auto space-y-1">
          <For each={provList()}>
            {(p) => (
              <button
                onClick={() => pickProvider(p.id)}
                class="w-full text-left px-4 py-2.5 rounded-2xl hover:bg-white/[0.06] flex items-center gap-3 transition-all active:scale-[0.98]"
              >
                <Show when={selProv() === p.id} fallback={<span class="w-2 h-2 rounded-full bg-slate-600" />}>
                  <span class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" />
                </Show>
                <span class="text-[13px] text-white font-medium">{p.label}</span>
                <span class="text-[11px] text-slate-400 font-mono ml-auto">{p.id}</span>
                <Show when={busyProv() === p.id}>
                  <span class="text-[11px] text-amber-300">…</span>
                </Show>
              </button>
            )}
          </For>
        </div>
        <p class="pt-3 text-[11.5px] text-slate-400">Elegir proveedor lo activa y salta a Modelos con la lista en vivo de su API.</p>
      </Show>

      {/* ── MODELS ── */}
      <Show when={tab() === "models"}>
        <div class="px-2 py-1 flex items-center gap-2 mb-2">
          <span class="text-[12px] text-slate-400">Proveedor:</span>
          <select
            value={selProv()}
            onChange={(e) => {
              setSelProv(e.currentTarget.value);
              void loadModels(e.currentTarget.value);
            }}
            class="bg-white/[0.06] rounded-xl px-3 py-1 text-[12px] text-white outline-none"
          >
            <For each={PROVIDERS}>{(p) => <option value={p.id}>{p.label}</option>}</For>
          </select>
          <Show when={loadingModels()}>
            <span class="text-[11px] text-amber-300 animate-pulse">cargando desde API…</span>
          </Show>
        </div>
        <Show when={modelsErr()}>
          <p class="px-2 py-1 text-[12px] text-red-300">{modelsErr()}</p>
        </Show>
        <div class="max-h-[280px] overflow-y-auto space-y-1">
          <For each={modelList()}>
            {(m) => (
              <button
                onClick={() => pickModel(m)}
                class="w-full text-left px-4 py-2 rounded-2xl hover:bg-white/[0.06] transition-all active:scale-[0.98]"
              >
                <span class={`text-[13px] font-mono ${m === props.current?.model ? "text-emerald-300 font-semibold" : "text-white"}`}>{m}</span>
              </button>
            )}
          </For>
          <Show when={modelList().length === 0 && !modelsErr() && !loadingModels()}>
            <p class="py-6 text-[12px] text-slate-400 text-center">Sin resultados para el filtro.</p>
          </Show>
        </div>
      </Show>

      {/* ── KEYS ── */}
      <Show when={tab() === "keys"}>
        <Show
          when={!keyProv()}
          fallback={
            <div class="p-2 space-y-3">
              <p class="text-[13px] text-white">
                API Key para <b class="font-mono text-zinc-200">{keyProv()}</b>
                <span class="text-zinc-400"> ({KEY_PROVIDERS.find((k) => k.id === keyProv())?.env})</span>
              </p>
              <input
                type="password"
                value={keyVal()}
                onInput={(e) => setKeyVal(e.currentTarget.value)}
                placeholder="Introduce la llave…"
                class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 border border-white/[0.08] rounded-2xl px-4 py-2.5 text-[13px] text-white outline-none transition-all"
                onKeyDown={(e) => {
                  if (e.key === "Enter") void saveKey();
                  if (e.key === "Escape") setKeyProv(null);
                }}
              />
              <div class="flex gap-2 pt-2">
                <button
                  onClick={() => setKeyProv(null)}
                  class="px-4 py-1.5 rounded-full text-[13px] text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-all"
                >
                  ← Volver
                </button>
                <div class="flex-1" />
                <button
                  onClick={saveKey}
                  disabled={!keyVal() || busyKey()}
                  class="px-5 py-2 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-100 text-[13px] font-medium shadow-sm border border-white/[0.08] transition-all active:scale-95 disabled:opacity-50"
                >
                  {busyKey() ? "Guardando…" : "Guardar y recargar"}
                </button>
              </div>
            </div>
          }
        >
          <div class="space-y-1">
            <For each={KEY_PROVIDERS}>
              {(k) => (
                <button
                  onClick={() => {
                    setKeyVal("");
                    setKeyProv(k.id);
                  }}
                  class="w-full text-left px-4 py-2.5 rounded-2xl hover:bg-white/[0.06] flex items-center gap-3 transition-all active:scale-[0.98]"
                >
                  <span class="text-[13.5px] text-white capitalize font-medium">{k.id}</span>
                  <span class="text-[11px] text-zinc-400 font-mono ml-auto">{k.env}</span>
                </button>
              )}
            </For>
          </div>
          <p class="pt-3 text-[11.5px] text-zinc-400">Al guardar, se recargan los modelos en vivo de ese proveedor.</p>
        </Show>
      </Show>

      {/* ── CONEXIÓN ── */}
      <Show when={tab() === "connection"}>
        <div class="space-y-3 pt-1 select-text">
          <div>
            <label class="block text-[12px] text-zinc-400 mb-1">URL del backend nativo</label>
            <input
              value={connUrl()}
              onInput={(e) => setConnUrl(e.currentTarget.value)}
              placeholder="http://127.0.0.1:8755"
              class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 border border-white/[0.08] rounded-2xl px-4 py-2.5 text-[13px] font-mono text-white outline-none transition-all"
            />
          </div>
          <div>
            <label class="block text-[12px] text-zinc-400 mb-1">Token de autenticación</label>
            <input
              type="password"
              value={connToken()}
              onInput={(e) => setConnToken(e.currentTarget.value)}
              placeholder="Bearer token… (vacío si no tiene auth)"
              class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 border border-white/[0.08] rounded-2xl px-4 py-2.5 text-[13px] font-mono text-white outline-none transition-all"
              onKeyDown={(e) => {
                if (e.key === "Enter") void testConnection();
              }}
            />
          </div>
          <div class="flex justify-end pt-2">
            <button
              onClick={testConnection}
              disabled={busyConn()}
              class="px-5 py-2 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-100 text-[13px] font-medium shadow-sm border border-white/[0.08] transition-all active:scale-95 disabled:opacity-50"
            >
              {busyConn() ? "Probando…" : "Guardar y probar"}
            </button>
          </div>
          <p class="text-[11.5px] text-zinc-400">
            Se guarda en el cliente y aplica al instante a las conexiones REST y WebSocket.
          </p>
        </div>
      </Show>

      {/* ── MCP ── */}
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
          <div class="space-y-3">
            <p class="text-[13px] text-white">
              API Key para <b class="font-mono text-zinc-200">{stepProv()}</b>
              <span class="text-zinc-400"> ({KEY_PROVIDERS.find((k) => k.id === stepProv())?.env})</span>
            </p>
            <input
              type="password"
              value={key()}
              onInput={(e) => setKey(e.currentTarget.value)}
              placeholder="Introduce la llave…"
              class="w-full bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 rounded-2xl px-4 py-2.5 text-[13px] text-white outline-none transition-all"
              onKeyDown={(e) => {
                if (e.key === "Enter") void save();
                if (e.key === "Escape") setStepProv(null);
              }}
            />
            <div class="flex gap-2 pt-2">
              <button
                onClick={() => setStepProv(null)}
                class="px-4 py-1.5 rounded-full text-[13px] text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-all"
              >
                ← Volver
              </button>
              <div class="flex-1" />
              <button
                onClick={save}
                disabled={!key() || busy()}
                class="px-5 py-2 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-white/[0.08] text-[13px] font-medium shadow-sm transition-all active:scale-95 disabled:opacity-50"
              >
                {busy() ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </div>
        }
      >
        <div class="space-y-1">
          <For each={KEY_PROVIDERS}>
            {(k) => (
              <button
                onClick={() => {
                  setKey("");
                  setStepProv(k.id);
                }}
                class="w-full text-left px-4 py-2.5 rounded-2xl hover:bg-white/[0.06] flex items-center gap-3 transition-all active:scale-[0.98]"
              >
                <span class="text-[13.5px] text-white capitalize font-medium">{k.id}</span>
                <span class="text-[11px] text-slate-400 font-mono ml-auto">{k.env}</span>
              </button>
            )}
          </For>
        </div>
        <p class="pt-3 text-[11.5px] text-slate-400">Igual que /keys en TUI. POST /config/llm con provider + api_key.</p>
      </Show>
    </Shell>
  );
}
