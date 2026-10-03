import { ButtonV2 } from "@kogniterm/ui/v2/button-v2"
import { Dialog, DialogBody, DialogFooter, DialogHeader, DialogTitle } from "@kogniterm/ui/v2/dialog-v2"
import { DividerV2 } from "@kogniterm/ui/v2/divider-v2"
import { TextInputV2 } from "@kogniterm/ui/v2/text-input-v2"
import { SegmentedControlV2, SegmentedControlItemV2 } from "@kogniterm/ui/v2/segmented-control-v2"
import { IconButtonV2 } from "@kogniterm/ui/v2/icon-button-v2"
import { Icon } from "@kogniterm/ui/icon"
import { useDialog } from "@kogniterm/ui/context/dialog"
import { type Component, For, Show, createSignal, onMount } from "solid-js"
import { createStore, produce } from "solid-js/store"
import { useLanguage } from "@/context/language"
import { useServerSDK } from "@/context/server-sdk"
import { showToast } from "@/utils/toast"
import type { MCPServerItem, MCPServerPayload, MCPTestResult } from "@/api/client"
import "./settings-v2.css"

interface KeyVal {
  id: string
  key: string
  value: string
}

interface FormState {
  name: string
  transport: "stdio" | "sse"
  command: string
  args: string
  env: KeyVal[]
  url: string
  headers: KeyVal[]
  scope: "global" | "project"
}

interface Preset {
  id: string
  label: string
  name: string
  transport: "stdio" | "sse"
  command: string
  args: string
  env?: Record<string, string>
  url?: string
}

const PRESETS: Preset[] = [
  {
    id: "filesystem",
    label: "Filesystem",
    name: "filesystem",
    transport: "stdio",
    command: "npx",
    args: "-y @modelcontextprotocol/server-filesystem .",
  },
  {
    id: "postgres",
    label: "PostgreSQL",
    name: "postgres",
    transport: "stdio",
    command: "npx",
    args: "-y @modelcontextprotocol/server-postgres postgresql://localhost:5432/dbname",
  },
  {
    id: "github",
    label: "GitHub",
    name: "github",
    transport: "stdio",
    command: "npx",
    args: "-y @modelcontextprotocol/server-github",
    env: { GITHUB_PERSONAL_ACCESS_TOKEN: "" },
  },
  {
    id: "sqlite",
    label: "SQLite",
    name: "sqlite",
    transport: "stdio",
    command: "uvx",
    args: "mcp-server-sqlite --db-path ./database.db",
  },
  {
    id: "puppeteer",
    label: "Puppeteer",
    name: "puppeteer",
    transport: "stdio",
    command: "npx",
    args: "-y @modelcontextprotocol/server-puppeteer",
  },
  {
    id: "memory",
    label: "Memory",
    name: "memory",
    transport: "stdio",
    command: "npx",
    args: "-y @modelcontextprotocol/server-memory",
  },
  {
    id: "fetch",
    label: "Fetch",
    name: "fetch",
    transport: "stdio",
    command: "uvx",
    args: "mcp-server-fetch",
  },
]

export const DialogMcpServerV2: Component<{
  mode: "add" | "edit"
  server?: MCPServerItem
  onSaved?: () => void
}> = (props) => {
  const dialog = useDialog()
  const language = useLanguage()
  const serverSdk = useServerSDK()

  const [form, setForm] = createStore<FormState>({
    name: "",
    transport: "stdio",
    command: "",
    args: "",
    env: [],
    url: "",
    headers: [],
    scope: "project",
  })

  const [error, setError] = createSignal<string | null>(null)
  const [busy, setBusy] = createSignal(false)
  const [testing, setTesting] = createSignal(false)
  const [testResult, setTestResult] = createSignal<MCPTestResult | null>(null)

  onMount(() => {
    if (props.mode === "edit" && props.server) {
      const s = props.server
      setForm({
        name: s.name,
        transport: s.transport ?? "stdio",
        command: s.command ?? "",
        args: Array.isArray(s.args) ? s.args.join(" ") : "",
        env: Object.entries(s.env ?? {}).map(([key, value]) => ({
          id: Math.random().toString(36).slice(2),
          key,
          value,
        })),
        url: s.url ?? "",
        headers: Object.entries(s.headers ?? {}).map(([key, value]) => ({
          id: Math.random().toString(36).slice(2),
          key,
          value,
        })),
        scope: s.scope ?? "project",
      })
    }
  })

  const applyPreset = (preset: Preset) => {
    setForm(
      produce((draft) => {
        if (!draft.name || draft.name.trim() === "") {
          draft.name = preset.name
        }
        draft.transport = preset.transport
        draft.command = preset.command
        draft.args = preset.args
        if (preset.env) {
          draft.env = Object.entries(preset.env).map(([key, value]) => ({
            id: Math.random().toString(36).slice(2),
            key,
            value,
          }))
        }
        if (preset.url) {
          draft.url = preset.url
        }
      }),
    )
    setTestResult(null)
    setError(null)
  }

  const addEnvVar = () => {
    setForm(
      "env",
      produce((items) => {
        items.push({ id: Math.random().toString(36).slice(2), key: "", value: "" })
      }),
    )
  }

  const removeEnvVar = (id: string) => {
    setForm(
      "env",
      produce((items) => {
        const idx = items.findIndex((i) => i.id === id)
        if (idx !== -1) items.splice(idx, 1)
      }),
    )
  }

  const addHeader = () => {
    setForm(
      "headers",
      produce((items) => {
        items.push({ id: Math.random().toString(36).slice(2), key: "", value: "" })
      }),
    )
  }

  const removeHeader = (id: string) => {
    setForm(
      "headers",
      produce((items) => {
        const idx = items.findIndex((i) => i.id === id)
        if (idx !== -1) items.splice(idx, 1)
      }),
    )
  }

  const buildPayloadConfig = (): MCPServerPayload["config"] => {
    if (form.transport === "stdio") {
      const argsList = form.args
        .trim()
        .split(/\s+/)
        .filter(Boolean)
      const envObj: Record<string, string> = {}
      for (const item of form.env) {
        if (item.key.trim()) envObj[item.key.trim()] = item.value
      }
      return {
        transport: "stdio",
        command: form.command.trim(),
        args: argsList,
        env: envObj,
        disabled: false,
        scope: form.scope,
      }
    } else {
      const headersObj: Record<string, string> = {}
      for (const item of form.headers) {
        if (item.key.trim()) headersObj[item.key.trim()] = item.value
      }
      return {
        transport: "sse",
        url: form.url.trim(),
        headers: headersObj,
        disabled: false,
        scope: form.scope,
      }
    }
  }

  const runTestConnection = async () => {
    setError(null)
    setTestResult(null)
    const config = buildPayloadConfig()

    if (config.transport === "stdio" && !config.command) {
      setError(language.t("settings.mcp.error.commandRequired") || "El comando es requerido para probar la conexión")
      return
    }
    if (config.transport === "sse" && !config.url) {
      setError(language.t("settings.mcp.error.urlRequired") || "La URL es requerida para probar la conexión")
      return
    }

    setTesting(true)
    try {
      const client = serverSdk().api.kogniTerm
      const res = await client.testMcpConnection(config)
      setTestResult(res)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      setTestResult({ status: "error", message })
    } finally {
      setTesting(false)
    }
  }

  const submit = async () => {
    setError(null)
    const name = form.name.trim()
    if (!name) {
      setError(language.t("settings.mcp.error.nameRequired") || "El nombre del servidor es requerido")
      return
    }
    if (!/^[a-zA-Z0-9_\-\.]+$/.test(name)) {
      setError(
        language.t("settings.mcp.error.invalidName") ||
          "El nombre solo puede contener letras, números, puntos, guiones y guiones bajos",
      )
      return
    }

    const config = buildPayloadConfig()
    if (config.transport === "stdio" && !config.command) {
      setError(language.t("settings.mcp.error.commandRequired") || "El comando ejecutable es requerido")
      return
    }
    if (config.transport === "sse" && !config.url) {
      setError(language.t("settings.mcp.error.urlRequired") || "La URL del servidor SSE es requerida")
      return
    }

    setBusy(true)
    try {
      const client = serverSdk().api.kogniTerm
      await client.setMcpServer({
        name,
        config,
        scope: form.scope,
      })

      showToast({
        variant: "success",
        icon: "circle-check",
        title:
          props.mode === "add"
            ? language.t("settings.mcp.toast.created") || `Servidor MCP "${name}" creado`
            : language.t("settings.mcp.toast.updated") || `Servidor MCP "${name}" actualizado`,
      })

      props.onSaved?.()
      dialog.close()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      setError(message)
    } finally {
      setBusy(false)
    }
  }

  const title = () =>
    props.mode === "add"
      ? language.t("settings.mcp.dialog.add.title") || "Agregar Servidor MCP"
      : language.t("settings.mcp.dialog.edit.title") || "Editar Servidor MCP"

  return (
    <Dialog fit class="settings-v2-server-dialog">
      <DialogHeader hideClose={true}>
        <DialogTitle>{title()}</DialogTitle>
      </DialogHeader>
      <DividerV2 />
      <DialogBody class="flex w-full min-w-0 flex-1 flex-col px-4 pt-4 pb-2 gap-4 max-h-[75vh] overflow-y-auto no-scrollbar">
        {/* Quick Presets (Only in Add mode) */}
        <Show when={props.mode === "add"}>
          <div class="flex flex-col gap-1.5">
            <span class="text-11-medium text-text-muted">
              {language.t("settings.mcp.presets.title") || "Plantillas rápidas:"}
            </span>
            <div class="flex flex-wrap gap-1.5">
              <For each={PRESETS}>
                {(preset) => (
                  <button
                    type="button"
                    class="px-2 py-1 text-11-medium rounded bg-surface-raised-base hover:bg-surface-raised-base-hover text-text-base transition-colors border border-border-muted"
                    onClick={() => applyPreset(preset)}
                  >
                    {preset.label}
                  </button>
                )}
              </For>
            </div>
          </div>
        </Show>

        {/* Server Name */}
        <div class="flex w-full min-w-0 flex-col gap-1.5">
          <label class="settings-v2-server-dialog-label">
            {language.t("common.name") || "Nombre del servidor"}
          </label>
          <TextInputV2
            type="text"
            appearance="large"
            class="!w-full self-stretch"
            value={form.name}
            disabled={props.mode === "edit" || busy()}
            placeholder="ej: postgres, filesystem, github..."
            onInput={(e) => setForm("name", e.currentTarget.value)}
          />
        </div>

        {/* Transport Type */}
        <div class="flex w-full min-w-0 flex-col gap-1.5">
          <label class="settings-v2-server-dialog-label">
            {language.t("settings.mcp.field.transport") || "Tipo de Transporte"}
          </label>
          <SegmentedControlV2
            value={form.transport}
            disabled={busy()}
            onChange={(val) => {
              if (val === "stdio" || val === "sse") {
                setForm("transport", val)
                setTestResult(null)
              }
            }}
          >
            <SegmentedControlItemV2 value="stdio">
              <span>{language.t("settings.mcp.transport.stdio") || "Comando Local (stdio)"}</span>
            </SegmentedControlItemV2>
            <SegmentedControlItemV2 value="sse">
              <span>{language.t("settings.mcp.transport.sse") || "Servidor Remoto (SSE)"}</span>
            </SegmentedControlItemV2>
          </SegmentedControlV2>
        </div>

        {/* stdio fields */}
        <Show when={form.transport === "stdio"}>
          <div class="flex w-full min-w-0 flex-col gap-1.5">
            <label class="settings-v2-server-dialog-label">
              {language.t("settings.mcp.field.command") || "Comando ejecutable"}
            </label>
            <TextInputV2
              type="text"
              appearance="large"
              class="!w-full self-stretch font-mono"
              value={form.command}
              disabled={busy()}
              placeholder="npx, uvx, python, docker..."
              onInput={(e) => setForm("command", e.currentTarget.value)}
            />
          </div>

          <div class="flex w-full min-w-0 flex-col gap-1.5">
            <label class="settings-v2-server-dialog-label">
              {language.t("settings.mcp.field.args") || "Argumentos (separados por espacio)"}
            </label>
            <TextInputV2
              type="text"
              appearance="large"
              class="!w-full self-stretch font-mono"
              value={form.args}
              disabled={busy()}
              placeholder="-y @modelcontextprotocol/server-postgres postgresql://..."
              onInput={(e) => setForm("args", e.currentTarget.value)}
            />
          </div>

          {/* Environment Variables */}
          <div class="flex w-full min-w-0 flex-col gap-2">
            <div class="flex items-center justify-between">
              <label class="settings-v2-server-dialog-label">
                {language.t("settings.mcp.field.env") || "Variables de Entorno"}
              </label>
              <ButtonV2
                type="button"
                size="small"
                variant="ghost-muted"
                icon="plus"
                onClick={addEnvVar}
                disabled={busy()}
              >
                {language.t("common.add") || "Agregar variable"}
              </ButtonV2>
            </div>
            <Show when={form.env.length > 0}>
              <div class="flex flex-col gap-1.5">
                <For each={form.env}>
                  {(item) => (
                    <div class="flex items-center gap-2">
                      <TextInputV2
                        type="text"
                        appearance="base"
                        class="flex-1 font-mono"
                        placeholder="CLAVE (ej. API_KEY)"
                        value={item.key}
                        disabled={busy()}
                        onInput={(e) => {
                          const val = e.currentTarget.value
                          setForm("env", (it) => it.id === item.id, "key", val)
                        }}
                      />
                      <TextInputV2
                        type="text"
                        appearance="base"
                        class="flex-1 font-mono"
                        placeholder="valor"
                        value={item.value}
                        disabled={busy()}
                        onInput={(e) => {
                          const val = e.currentTarget.value
                          setForm("env", (it) => it.id === item.id, "value", val)
                        }}
                      />
                      <IconButtonV2
                        type="button"
                        size="small"
                        variant="ghost-muted"
                        disabled={busy()}
                        icon={<Icon name="close" class="size-3.5 text-text-muted hover:text-text-base" />}
                        onClick={() => removeEnvVar(item.id)}
                      />
                    </div>
                  )}
                </For>
              </div>
            </Show>
          </div>
        </Show>

        {/* sse fields */}
        <Show when={form.transport === "sse"}>
          <div class="flex w-full min-w-0 flex-col gap-1.5">
            <label class="settings-v2-server-dialog-label">
              {language.t("settings.mcp.field.url") || "URL del Endpoint SSE"}
            </label>
            <TextInputV2
              type="text"
              appearance="large"
              class="!w-full self-stretch font-mono"
              value={form.url}
              disabled={busy()}
              placeholder="http://localhost:8000/sse"
              onInput={(e) => setForm("url", e.currentTarget.value)}
            />
          </div>

          {/* HTTP Headers */}
          <div class="flex w-full min-w-0 flex-col gap-2">
            <div class="flex items-center justify-between">
              <label class="settings-v2-server-dialog-label">
                {language.t("settings.mcp.field.headers") || "Headers HTTP"}
              </label>
              <ButtonV2
                type="button"
                size="small"
                variant="ghost-muted"
                icon="plus"
                onClick={addHeader}
                disabled={busy()}
              >
                {language.t("common.add") || "Agregar Header"}
              </ButtonV2>
            </div>
            <Show when={form.headers.length > 0}>
              <div class="flex flex-col gap-1.5">
                <For each={form.headers}>
                  {(item) => (
                    <div class="flex items-center gap-2">
                      <TextInputV2
                        type="text"
                        appearance="base"
                        class="flex-1 font-mono"
                        placeholder="Header (ej. Authorization)"
                        value={item.key}
                        disabled={busy()}
                        onInput={(e) => {
                          const val = e.currentTarget.value
                          setForm("headers", (it) => it.id === item.id, "key", val)
                        }}
                      />
                      <TextInputV2
                        type="text"
                        appearance="base"
                        class="flex-1 font-mono"
                        placeholder="Valor (ej. Bearer token)"
                        value={item.value}
                        disabled={busy()}
                        onInput={(e) => {
                          const val = e.currentTarget.value
                          setForm("headers", (it) => it.id === item.id, "value", val)
                        }}
                      />
                      <IconButtonV2
                        type="button"
                        size="small"
                        variant="ghost-muted"
                        disabled={busy()}
                        icon={<Icon name="close" class="size-3.5 text-text-muted hover:text-text-base" />}
                        onClick={() => removeHeader(item.id)}
                      />
                    </div>
                  )}
                </For>
              </div>
            </Show>
          </div>
        </Show>

        {/* Scope */}
        <div class="flex w-full min-w-0 flex-col gap-1.5">
          <label class="settings-v2-server-dialog-label">
            {language.t("settings.mcp.field.scope") || "Ámbito de Configuración"}
          </label>
          <SegmentedControlV2
            value={form.scope}
            disabled={busy()}
            onChange={(val) => {
              if (val === "project" || val === "global") setForm("scope", val)
            }}
          >
            <SegmentedControlItemV2 value="project">
              <span>{language.t("settings.mcp.scope.project") || "Proyecto actual"}</span>
            </SegmentedControlItemV2>
            <SegmentedControlItemV2 value="global">
              <span>{language.t("settings.mcp.scope.global") || "Global (Todos)"}</span>
            </SegmentedControlItemV2>
          </SegmentedControlV2>
        </div>

        {/* Test Connection Button & Result */}
        <div class="flex flex-col gap-2 pt-2">
          <div class="flex items-center justify-between">
            <ButtonV2
              type="button"
              variant="outline"
              size="normal"
              disabled={busy() || testing()}
              onClick={runTestConnection}
            >
              <Show when={testing()} fallback={language.t("settings.mcp.test.button") || "Probar Conexión"}>
                {language.t("settings.mcp.test.testing") || "Probando conexión..."}
              </Show>
            </ButtonV2>
          </div>

          <Show when={testResult()}>
            {(res) => (
              <div
                class="p-2.5 rounded text-12-regular flex flex-col gap-1"
                classList={{
                  "bg-surface-success-base/10 text-text-success border border-surface-success-base/30":
                    res().status === "ok",
                  "bg-surface-critical-base/10 text-state-fg-danger border border-surface-critical-base/30":
                    res().status === "error",
                }}
              >
                <div class="flex items-center gap-1.5 font-medium">
                  <Show
                    when={res().status === "ok"}
                    fallback={
                      <>
                        <Icon name="circle-x" class="size-4 shrink-0" />
                        <span>{language.t("settings.mcp.test.failed") || "Error de conexión"}</span>
                      </>
                    }
                  >
                    <Icon name="check-small" class="size-4 shrink-0" />
                    <span>
                      {language.t("settings.mcp.test.success") || "Conexión exitosa"}
                      {res().tools?.length ? ` (${res().tools?.length} herramientas detectadas)` : ""}
                    </span>
                  </Show>
                </div>
                <Show when={res().message}>
                  <span class="text-11-regular break-all">{res().message}</span>
                </Show>
                <Show when={res().tools && res().tools!.length > 0}>
                  <div class="flex flex-wrap gap-1 mt-1">
                    <For each={res().tools}>
                      {(tool) => (
                        <span class="px-1.5 py-0.5 rounded bg-surface-raised-base text-10-medium font-mono text-text-base">
                          {tool}
                        </span>
                      )}
                    </For>
                  </div>
                </Show>
              </div>
            )}
          </Show>
        </div>

        {/* Global Error Banner */}
        <Show when={error()}>
          <div class="p-2.5 rounded text-12-regular bg-surface-critical-base/10 text-state-fg-danger border border-surface-critical-base/30">
            {error()}
          </div>
        </Show>
      </DialogBody>
      <DividerV2 />
      <DialogFooter>
        <div class="flex justify-end gap-2 px-4 py-4 w-full">
          <ButtonV2 variant="ghost-muted" disabled={busy()} onClick={() => dialog.close()}>
            {language.t("common.cancel") || "Cancelar"}
          </ButtonV2>
          <ButtonV2 variant="neutral" disabled={busy() || testing()} onClick={submit}>
            <Show when={busy()} fallback={language.t("common.save") || "Guardar"}>
              {language.t("common.saving") || "Guardando..."}
            </Show>
          </ButtonV2>
        </div>
      </DialogFooter>
    </Dialog>
  )
}
