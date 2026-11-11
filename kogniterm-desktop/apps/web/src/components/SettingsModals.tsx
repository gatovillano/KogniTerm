import { For, Show, createSignal } from "solid-js";
import { api, apiRoot, token, setToken, setApiUrl, PROVIDERS, KEY_PROVIDERS, type LLMConfig } from "../lib/api";
import { MCPPanel } from "./MCPPanel";
import { PricingPanel } from "./PricingPanel";
import {
  IconCheck,
  IconClose,
  IconCpu,
  IconCreditCard,
  IconGlobe,
  IconKey,
  IconPlug,
  IconRefresh,
  IconSearch,
  IconSettings,
  IconSpark,
} from "./Icons";

function Shell(props: { title: string; onClose: () => void; wide?: boolean; children: any }) {
  return (
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xl animate-fade-in p-4"
      onClick={props.onClose}
    >
      <div
        class={`${
          props.wide ? "w-[800px] h-[580px]" : "w-[520px] max-h-[85vh]"
        } max-w-[94vw] max-h-[88vh] overflow-hidden rounded-3xl glass-modal animate-scale-in flex flex-col select-none`}
        onClick={(e) => e.stopPropagation()}
      >
        <div class="px-6 py-4 flex items-center border-b border-[var(--kt-border-subtle)] shrink-0">
          <div class="flex items-center gap-2.5">
            <span class="w-7 h-7 rounded-xl bg-[var(--kt-bg-hover)] border border-[var(--kt-border-subtle)] flex items-center justify-center text-[var(--kt-text-muted)]">
              <IconSettings size={14} />
            </span>
            <span class="text-[var(--kt-text-primary)] text-[15px] font-semibold tracking-tight">{props.title}</span>
          </div>
          <div class="flex-1" />
          <button
            class="w-7 h-7 rounded-xl flex items-center justify-center text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all"
            onClick={props.onClose}
            title="Cerrar (Esc)"
          >
            <IconClose size={14} />
          </button>
        </div>
        <div class="flex-1 min-h-0 flex flex-col overflow-hidden">{props.children}</div>
      </div>
    </div>
  );
}

function FilterInput(props: { value: string; onInput: (v: string) => void; placeholder: string }) {
  return (
    <div class="relative mb-3">
      <IconSearch
        size={14}
        class="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--kt-text-faint)] pointer-events-none"
      />
      <input
        value={props.value}
        onInput={(e) => props.onInput(e.currentTarget.value)}
        placeholder={props.placeholder}
        class="w-full bg-[var(--kt-bg-hover)] focus:bg-[var(--kt-bg-input)] border border-[var(--kt-border-subtle)] focus:border-[var(--kt-border-strong)] rounded-xl pl-9 pr-4 py-2 text-[13px] text-[var(--kt-text-primary)] placeholder-[var(--kt-text-faint)] outline-none transition-all"
      />
    </div>
  );
}

/** Modal Proveedor */
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
      <div class="p-5 overflow-y-auto flex-1">
        <FilterInput value={q()} onInput={setQ} placeholder="Filtrar proveedores…" />
        <div class="max-h-[340px] overflow-y-auto space-y-1">
          <For each={list()}>
            {(p) => {
              const active = () => props.current?.provider === p.id;
              return (
                <button
                  onClick={() => pick(p.id)}
                  class={`w-full text-left px-3.5 py-2.5 rounded-xl flex items-center gap-3 transition-all active:scale-[0.99] border ${
                    active()
                      ? "bg-[var(--kt-bg-active)] border-[var(--kt-border-default)]"
                      : "border-transparent hover:bg-[var(--kt-bg-hover)]"
                  }`}
                >
                  <Show
                    when={active()}
                    fallback={<span class="w-2 h-2 rounded-full bg-[var(--kt-text-faint)] opacity-40" />}
                  >
                    <span class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" />
                  </Show>
                  <span class="text-[13.5px] text-[var(--kt-text-primary)] font-medium">{p.label}</span>
                  <span class="text-[11px] text-[var(--kt-text-faint)] font-mono ml-auto">{p.id}</span>
                  <Show when={busy() === p.id}>
                    <span class="text-[11px] text-amber-300">…</span>
                  </Show>
                </button>
              );
            }}
          </For>
        </div>
        <p class="pt-3 text-[11.5px] text-[var(--kt-text-muted)]">
          Igual que /provider en TUI. Cambia default_model y recarga sesiones.
        </p>
      </div>
    </Shell>
  );
}

/** Modal Modelo */
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
      <div class="p-5 overflow-y-auto flex-1">
        <FilterInput value={q()} onInput={setQ} placeholder="Filtrar modelos…" />
        <Show when={err()}>
          <p class="text-[12px] text-red-300 mb-2">{err()}</p>
        </Show>
        <div class="max-h-[340px] overflow-y-auto space-y-1">
          <For each={list()}>
            {(m) => {
              const active = () => m === props.current?.model;
              return (
                <button
                  onClick={() => pick(m)}
                  class={`w-full text-left px-3.5 py-2 rounded-xl flex items-center justify-between transition-all active:scale-[0.99] border ${
                    active()
                      ? "bg-[var(--kt-bg-active)] border-[var(--kt-border-default)]"
                      : "border-transparent hover:bg-[var(--kt-bg-hover)]"
                  }`}
                >
                  <span
                    class={`text-[13px] font-mono ${
                      active() ? "text-emerald-300 font-semibold" : "text-[var(--kt-text-primary)]"
                    }`}
                  >
                    {m}
                  </span>
                  <Show when={active()}>
                    <IconCheck size={13} class="text-emerald-400 shrink-0" />
                  </Show>
                </button>
              );
            }}
          </For>
          <Show when={list().length === 0 && !err()}>
            <p class="py-6 text-[12.5px] text-[var(--kt-text-muted)] text-center">Sin resultados para el filtro.</p>
          </Show>
        </div>
      </div>
    </Shell>
  );
}

export type SettingsTab = "provider" | "models" | "keys" | "connection" | "mcp" | "pricing";

const NAV_ITEMS: Array<{ id: SettingsTab; label: string; desc: string }> = [
  { id: "provider", label: "Proveedor", desc: "Motor LLM principal" },
  { id: "models", label: "Modelos", desc: "Selección del modelo activo" },
  { id: "keys", label: "API Keys", desc: "Credenciales por proveedor" },
  { id: "connection", label: "Conexión", desc: "Backend nativo y token" },
  { id: "mcp", label: "Servidores MCP", desc: "Herramientas y contexto externo" },
  { id: "pricing", label: "Pagos y Planes", desc: "Suscripción y facturación" },
];

/** Ajustes unificados en diseño de dos columnas */
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

  function navIcon(id: SettingsTab) {
    switch (id) {
      case "provider":
        return <IconSpark size={14} />;
      case "models":
        return <IconCpu size={14} />;
      case "keys":
        return <IconKey size={14} />;
      case "connection":
        return <IconGlobe size={14} />;
      case "mcp":
        return <IconPlug size={14} />;
      case "pricing":
        return <IconCreditCard size={14} />;
    }
  }

  const currentNav = () => NAV_ITEMS.find((n) => n.id === tab())!;

  return (
    <Shell title="Ajustes de KogniTerm" onClose={props.onClose} wide>
      <div class="flex flex-col sm:flex-row flex-1 min-h-0 overflow-hidden">
        {/* Barra lateral de navegación */}
        <aside class="sm:w-52 shrink-0 border-b sm:border-b-0 sm:border-r border-[var(--kt-border-subtle)] bg-[var(--kt-bg-app)]/40 p-2.5 flex sm:flex-col gap-1 overflow-x-auto sm:overflow-y-auto">
          <For each={NAV_ITEMS}>
            {(item) => {
              const active = () => tab() === item.id;
              return (
                <button
                  onClick={() => switchTab(item.id)}
                  class={`flex items-center gap-2.5 px-3 py-2 rounded-xl text-[12.5px] font-medium transition-all duration-150 shrink-0 text-left border ${
                    active()
                      ? "bg-[var(--kt-bg-active)] text-[var(--kt-text-primary)] border-[var(--kt-border-default)] shadow-sm"
                      : "border-transparent text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)]"
                  }`}
                >
                  <span class={active() ? "text-[var(--kt-text-primary)]" : "text-[var(--kt-text-faint)]"}>
                    {navIcon(item.id)}
                  </span>
                  <span class="truncate">{item.label}</span>
                </button>
              );
            }}
          </For>
        </aside>

        {/* Panel derecho de contenido */}
        <div class="flex-1 min-w-0 min-h-0 overflow-y-auto p-5 sm:p-6">
          <div class="flex items-center justify-between gap-3 mb-4">
            <div>
              <h3 class="text-[15px] font-semibold text-[var(--kt-text-primary)]">{currentNav().label}</h3>
              <p class="text-[12px] text-[var(--kt-text-muted)]">{currentNav().desc}</p>
            </div>
            <Show when={tab() === "provider" || tab() === "models"}>
              <button
                onClick={() => void loadModels(selProv())}
                class="flex items-center gap-1.5 px-3 py-1.5 text-[11.5px] font-medium text-[var(--kt-text-secondary)] hover:text-[var(--kt-text-primary)] bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] border border-[var(--kt-border-subtle)] rounded-xl transition-all"
                title="Recargar modelos desde la API del proveedor"
              >
                <IconRefresh size={12} />
                <span>Recargar</span>
              </button>
            </Show>
          </div>

          <Show when={tab() === "provider" || tab() === "models"}>
            <FilterInput
              value={q()}
              onInput={setQ}
              placeholder={tab() === "provider" ? "Filtrar proveedores…" : `Filtrar modelos de ${selProv()}…`}
            />
          </Show>

          <Show when={notice()}>
            <p class="mb-3 px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/25 text-[12px] text-amber-300 animate-fade-in">
              {notice()}
            </p>
          </Show>

          {/* ── PROVIDER ── */}
          <Show when={tab() === "provider"}>
            <div class="space-y-1">
              <For each={provList()}>
                {(p) => {
                  const active = () => selProv() === p.id;
                  return (
                    <button
                      onClick={() => pickProvider(p.id)}
                      class={`w-full text-left px-3.5 py-2.5 rounded-xl flex items-center gap-3 transition-all active:scale-[0.99] border ${
                        active()
                          ? "bg-[var(--kt-bg-active)] border-[var(--kt-border-default)]"
                          : "border-transparent hover:bg-[var(--kt-bg-hover)]"
                      }`}
                    >
                      <Show
                        when={active()}
                        fallback={<span class="w-2 h-2 rounded-full bg-[var(--kt-text-faint)] opacity-40" />}
                      >
                        <span class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" />
                      </Show>
                      <span class="text-[13px] text-[var(--kt-text-primary)] font-medium">{p.label}</span>
                      <span class="text-[11px] text-[var(--kt-text-faint)] font-mono ml-auto">{p.id}</span>
                      <Show when={busyProv() === p.id}>
                        <span class="text-[11px] text-amber-300">…</span>
                      </Show>
                    </button>
                  );
                }}
              </For>
            </div>
            <p class="pt-3 text-[11.5px] text-[var(--kt-text-muted)]">
              Elegir un proveedor lo activa y carga la lista en vivo de modelos desde su API.
            </p>
          </Show>

          {/* ── MODELS ── */}
          <Show when={tab() === "models"}>
            <div class="flex items-center gap-2 mb-3">
              <span class="text-[12px] text-[var(--kt-text-muted)]">Proveedor:</span>
              <select
                value={selProv()}
                onChange={(e) => {
                  setSelProv(e.currentTarget.value);
                  void loadModels(e.currentTarget.value);
                }}
                class="bg-[var(--kt-bg-hover)] border border-[var(--kt-border-subtle)] rounded-xl px-3 py-1.5 text-[12px] text-[var(--kt-text-primary)] outline-none"
              >
                <For each={PROVIDERS}>{(p) => <option value={p.id}>{p.label}</option>}</For>
              </select>
              <Show when={loadingModels()}>
                <span class="text-[11px] text-amber-300 animate-pulse">cargando desde API…</span>
              </Show>
            </div>
            <Show when={modelsErr()}>
              <p class="mb-2 px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/25 text-[12px] text-red-300">
                {modelsErr()}
              </p>
            </Show>
            <div class="space-y-1">
              <For each={modelList()}>
                {(m) => {
                  const active = () => m === props.current?.model;
                  return (
                    <button
                      onClick={() => pickModel(m)}
                      class={`w-full text-left px-3.5 py-2 rounded-xl flex items-center justify-between transition-all active:scale-[0.99] border ${
                        active()
                          ? "bg-[var(--kt-bg-active)] border-[var(--kt-border-default)]"
                          : "border-transparent hover:bg-[var(--kt-bg-hover)]"
                      }`}
                    >
                      <span
                        class={`text-[13px] font-mono ${
                          active() ? "text-emerald-300 font-semibold" : "text-[var(--kt-text-primary)]"
                        }`}
                      >
                        {m}
                      </span>
                      <Show when={active()}>
                        <IconCheck size={13} class="text-emerald-400 shrink-0" />
                      </Show>
                    </button>
                  );
                }}
              </For>
              <Show when={modelList().length === 0 && !modelsErr() && !loadingModels()}>
                <p class="py-6 text-[12px] text-[var(--kt-text-muted)] text-center">Sin resultados para el filtro.</p>
              </Show>
            </div>
          </Show>

          {/* ── KEYS ── */}
          <Show when={tab() === "keys"}>
            <Show
              when={!keyProv()}
              fallback={
                <div class="space-y-3">
                  <p class="text-[13px] text-[var(--kt-text-primary)]">
                    API Key para <b class="font-mono">{keyProv()}</b>
                    <span class="text-[var(--kt-text-muted)]">
                      {" "}
                      ({KEY_PROVIDERS.find((k) => k.id === keyProv())?.env})
                    </span>
                  </p>
                  <input
                    type="password"
                    value={keyVal()}
                    onInput={(e) => setKeyVal(e.currentTarget.value)}
                    placeholder="Introduce la llave…"
                    class="w-full bg-[var(--kt-bg-hover)] focus:bg-[var(--kt-bg-input)] border border-[var(--kt-border-default)] focus:border-[var(--kt-border-strong)] rounded-xl px-4 py-2.5 text-[13px] text-[var(--kt-text-primary)] outline-none transition-all font-mono"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void saveKey();
                      if (e.key === "Escape") setKeyProv(null);
                    }}
                  />
                  <div class="flex gap-2 pt-2">
                    <button
                      onClick={() => setKeyProv(null)}
                      class="px-4 py-1.5 rounded-full text-[13px] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all"
                    >
                      ← Volver
                    </button>
                    <div class="flex-1" />
                    <button
                      onClick={saveKey}
                      disabled={!keyVal() || busyKey()}
                      class="px-5 py-2 rounded-full bg-[var(--kt-btn-primary-bg)] hover:bg-[var(--kt-btn-primary-hover)] text-[var(--kt-btn-primary-text)] text-[13px] font-semibold shadow-sm transition-all active:scale-95 disabled:opacity-40"
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
                      class="w-full text-left px-3.5 py-2.5 rounded-xl hover:bg-[var(--kt-bg-hover)] flex items-center gap-3 transition-all active:scale-[0.99]"
                    >
                      <IconKey size={13} class="text-[var(--kt-text-faint)]" />
                      <span class="text-[13.5px] text-[var(--kt-text-primary)] capitalize font-medium">{k.id}</span>
                      <span class="text-[11px] text-[var(--kt-text-faint)] font-mono ml-auto">{k.env}</span>
                    </button>
                  )}
                </For>
              </div>
              <p class="pt-3 text-[11.5px] text-[var(--kt-text-muted)]">
                Al guardar, se recargan los modelos en vivo de ese proveedor.
              </p>
            </Show>
          </Show>

          {/* ── CONEXIÓN ── */}
          <Show when={tab() === "connection"}>
            <div class="space-y-4 select-text">
              <div>
                <label class="block text-[12px] font-medium text-[var(--kt-text-muted)] mb-1.5">
                  URL del backend nativo
                </label>
                <input
                  value={connUrl()}
                  onInput={(e) => setConnUrl(e.currentTarget.value)}
                  placeholder="http://127.0.0.1:8755"
                  class="w-full bg-[var(--kt-bg-hover)] focus:bg-[var(--kt-bg-input)] border border-[var(--kt-border-default)] focus:border-[var(--kt-border-strong)] rounded-xl px-4 py-2.5 text-[13px] font-mono text-[var(--kt-text-primary)] outline-none transition-all"
                />
              </div>
              <div>
                <label class="block text-[12px] font-medium text-[var(--kt-text-muted)] mb-1.5">
                  Token de autenticación
                </label>
                <input
                  type="password"
                  value={connToken()}
                  onInput={(e) => setConnToken(e.currentTarget.value)}
                  placeholder="Bearer token… (vacío si no tiene auth)"
                  class="w-full bg-[var(--kt-bg-hover)] focus:bg-[var(--kt-bg-input)] border border-[var(--kt-border-default)] focus:border-[var(--kt-border-strong)] rounded-xl px-4 py-2.5 text-[13px] font-mono text-[var(--kt-text-primary)] outline-none transition-all"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void testConnection();
                  }}
                />
              </div>
              <div class="flex justify-end pt-1">
                <button
                  onClick={testConnection}
                  disabled={busyConn()}
                  class="px-5 py-2 rounded-full bg-[var(--kt-btn-primary-bg)] hover:bg-[var(--kt-btn-primary-hover)] text-[var(--kt-btn-primary-text)] text-[13px] font-semibold shadow-sm transition-all active:scale-95 disabled:opacity-40"
                >
                  {busyConn() ? "Probando…" : "Guardar y probar"}
                </button>
              </div>
              <p class="text-[11.5px] text-[var(--kt-text-muted)]">
                Se guarda en el cliente y aplica al instante a las conexiones REST y WebSocket.
              </p>
            </div>
          </Show>

          {/* ── MCP ── */}
          <Show when={tab() === "mcp"}>
            <MCPPanel />
          </Show>

          {/* ── Pagos y Suscripciones ── */}
          <Show when={tab() === "pricing"}>
            <PricingPanel />
          </Show>
        </div>
      </div>
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
      <div class="p-5 overflow-y-auto flex-1">
        <Show
          when={!stepProv()}
          fallback={
            <div class="space-y-3">
              <p class="text-[13px] text-[var(--kt-text-primary)]">
                API Key para <b class="font-mono">{stepProv()}</b>
                <span class="text-[var(--kt-text-muted)]">
                  {" "}
                  ({KEY_PROVIDERS.find((k) => k.id === stepProv())?.env})
                </span>
              </p>
              <input
                type="password"
                value={key()}
                onInput={(e) => setKey(e.currentTarget.value)}
                placeholder="Introduce la llave…"
                class="w-full bg-[var(--kt-bg-hover)] focus:bg-[var(--kt-bg-input)] border border-[var(--kt-border-default)] focus:border-[var(--kt-border-strong)] rounded-xl px-4 py-2.5 text-[13px] text-[var(--kt-text-primary)] outline-none transition-all font-mono"
                onKeyDown={(e) => {
                  if (e.key === "Enter") void save();
                  if (e.key === "Escape") setStepProv(null);
                }}
              />
              <div class="flex gap-2 pt-2">
                <button
                  onClick={() => setStepProv(null)}
                  class="px-4 py-1.5 rounded-full text-[13px] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] hover:bg-[var(--kt-bg-hover)] transition-all"
                >
                  ← Volver
                </button>
                <div class="flex-1" />
                <button
                  onClick={save}
                  disabled={!key() || busy()}
                  class="px-5 py-2 rounded-full bg-[var(--kt-btn-primary-bg)] hover:bg-[var(--kt-btn-primary-hover)] text-[var(--kt-btn-primary-text)] text-[13px] font-semibold shadow-sm transition-all active:scale-95 disabled:opacity-40"
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
                  class="w-full text-left px-3.5 py-2.5 rounded-xl hover:bg-[var(--kt-bg-hover)] flex items-center gap-3 transition-all active:scale-[0.99]"
                >
                  <IconKey size={13} class="text-[var(--kt-text-faint)]" />
                  <span class="text-[13.5px] text-[var(--kt-text-primary)] capitalize font-medium">{k.id}</span>
                  <span class="text-[11px] text-[var(--kt-text-faint)] font-mono ml-auto">{k.env}</span>
                </button>
              )}
            </For>
          </div>
          <p class="pt-3 text-[11.5px] text-[var(--kt-text-muted)]">
            Igual que /keys en TUI. POST /config/llm con provider + api_key.
          </p>
        </Show>
      </div>
    </Shell>
  );
}
