import { ButtonV2 } from "@kogniterm/ui/v2/button-v2"
import { Tag } from "@kogniterm/ui/v2/badge-v2"
import { Icon as IconV2 } from "@kogniterm/ui/v2/icon"
import { IconButtonV2 } from "@kogniterm/ui/v2/icon-button-v2"
import { Switch } from "@kogniterm/ui/v2/switch-v2"
import { TextInputV2 } from "@kogniterm/ui/v2/text-input-v2"
import { Icon } from "@kogniterm/ui/icon"
import { useDialog } from "@kogniterm/ui/context/dialog"
import fuzzysort from "fuzzysort"
import { type Component, For, Show, createEffect, createMemo, createSignal, onMount } from "solid-js"
import { createStore } from "solid-js/store"
import { useLanguage } from "@/context/language"
import { useServerSDK } from "@/context/server-sdk"
import { showToast } from "@/utils/toast"
import { SettingsListV2 } from "./parts/list"
import { DialogMcpServerV2 } from "./dialog-mcp-v2"
import type { MCPServerItem } from "@/api/client"
import "./settings-v2.css"

export const SettingsMcpV2: Component = () => {
  const dialog = useDialog()
  const language = useLanguage()
  const serverSdk = useServerSDK()

  const [servers, setServers] = createSignal<MCPServerItem[]>([])
  const [loading, setLoading] = createSignal(true)
  const [store, setStore] = createStore({ filter: "" })
  const [expandedTools, setExpandedTools] = createSignal<Record<string, boolean>>({})
  const [testingServer, setTestingServer] = createSignal<string | null>(null)
  const [togglingServer, setTogglingServer] = createSignal<string | null>(null)

  const reload = async () => {
    try {
      const client = serverSdk().api.kogniTerm
      const res = await client.listMcpServers()
      const list: MCPServerItem[] = Object.entries(res ?? {}).map(([name, conf]) => ({
        ...conf,
        name,
      }))
      list.sort((a, b) => a.name.localeCompare(b.name))
      setServers(list)
    } catch {
      // Fallback: try openCode MCP list
      try {
        const client = serverSdk().api.mcp
        const res = await client.list()
        const list: MCPServerItem[] = (res?.data ?? []).map((item) => ({
          name: item.name,
          transport: "stdio",
          status: item.status?.status as any,
          error: (item.status as any)?.error,
          disabled: item.status?.status === "disabled",
        }))
        setServers(list)
      } catch {
        setServers([])
      }
    } finally {
      setLoading(false)
    }
  }

  onMount(() => {
    void reload()
  })

  // Watch for server connection changes
  createEffect(() => {
    serverSdk()
    void reload()
  })

  const filtered = createMemo(() => {
    const list = servers()
    const query = store.filter.trim()
    if (!query) return list

    return fuzzysort
      .go(query, list, {
        keys: [
          (s) => s.name,
          (s) => s.command ?? "",
          (s) => (s.args ?? []).join(" "),
          (s) => s.url ?? "",
          (s) => (s.tools ?? []).join(" "),
        ],
      })
      .map((r) => r.obj)
  })

  const connectedCount = createMemo(
    () => servers().filter((s) => s.status === "connected" && !s.disabled).length,
  )
  const totalCount = createMemo(() => servers().length)

  const openAdd = () => {
    dialog.push(() => <DialogMcpServerV2 mode="add" onSaved={() => void reload()} />)
  }

  const openEdit = (server: MCPServerItem) => {
    dialog.push(() => <DialogMcpServerV2 mode="edit" server={server} onSaved={() => void reload()} />)
  }

  const toggleServer = async (server: MCPServerItem) => {
    setTogglingServer(server.name)
    try {
      const client = serverSdk().api.kogniTerm
      await client.toggleMcpServer(server.name, server.scope ?? "project")
      await reload()
      showToast({
        variant: "success",
        title: server.disabled
          ? language.t("settings.mcp.toast.enabled") || `Servidor "${server.name}" habilitado`
          : language.t("settings.mcp.toast.disabled") || `Servidor "${server.name}" deshabilitado`,
      })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      showToast({
        variant: "error",
        title: language.t("common.requestFailed") || "Error en la solicitud",
        description: message,
      })
    } finally {
      setTogglingServer(null)
    }
  }

  const testServer = async (server: MCPServerItem) => {
    setTestingServer(server.name)
    try {
      const client = serverSdk().api.kogniTerm
      const res = await client.testMcpConnection({
        transport: server.transport,
        command: server.command,
        args: server.args,
        env: server.env,
        url: server.url,
        headers: server.headers,
      })

      if (res.status === "ok") {
        const count = res.tools?.length ?? 0
        const toolsList = res.tools?.slice(0, 4).join(", ")
        const more = count > 4 ? ` y ${count - 4} más` : ""
        showToast({
          variant: "success",
          icon: "circle-check",
          title: language.t("settings.mcp.test.success") || `Conexión con "${server.name}" exitosa`,
          description: count > 0 ? `${count} herramientas disponibles: ${toolsList}${more}` : "Servidor activo",
        })
      } else {
        showToast({
          variant: "error",
          title: language.t("settings.mcp.test.failed") || `Error al conectar con "${server.name}"`,
          description: res.message || "No se pudo establecer conexión",
        })
      }
      await reload()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      showToast({
        variant: "error",
        title: language.t("settings.mcp.test.failed") || "Fallo en la prueba",
        description: message,
      })
    } finally {
      setTestingServer(null)
    }
  }

  const deleteServer = async (server: MCPServerItem) => {
    const confirmed = window.confirm(
      language.t("settings.mcp.delete.confirm") ||
        `¿Estás seguro de que deseas eliminar el servidor MCP "${server.name}"?`,
    )
    if (!confirmed) return

    try {
      const client = serverSdk().api.kogniTerm
      await client.deleteMcpServer(server.name, server.scope ?? "project")
      await reload()
      showToast({
        variant: "success",
        icon: "circle-check",
        title: language.t("settings.mcp.toast.deleted") || `Servidor MCP "${server.name}" eliminado`,
      })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      showToast({
        variant: "error",
        title: language.t("common.requestFailed") || "Error al eliminar",
        description: message,
      })
    }
  }

  const toggleToolsExpanded = (name: string) => {
    setExpandedTools((prev) => ({
      ...prev,
      [name]: !prev[name],
    }))
  }

  const showSearch = createMemo(() => servers().length > 1)

  return (
    <>
      <div
        class="settings-v2-tab-header settings-v2-servers-header"
        classList={{ "settings-v2-tab-header--stacked": showSearch() }}
      >
        <div class="settings-v2-tab-header-row">
          <div class="flex items-center gap-2.5">
            <h2 class="settings-v2-tab-title">{language.t("settings.mcp.title") || "Servidores MCP"}</h2>
            <Show when={totalCount() > 0}>
              <Tag>
                {connectedCount()} / {totalCount()}{" "}
                {language.t("mcp.status.connected") || "conectados"}
              </Tag>
            </Show>
          </div>
          <div class="flex items-center gap-2">
            <IconButtonV2
              type="button"
              variant="ghost-muted"
              size="normal"
              title={language.t("common.reload") || "Recargar"}
              icon={<Icon name="reset" class="size-4 text-text-muted hover:text-text-base" />}
              onClick={() => void reload()}
            />
            <ButtonV2 variant="neutral" icon="plus" onClick={openAdd}>
              {language.t("settings.mcp.add.button") || "Agregar Servidor"}
            </ButtonV2>
          </div>
        </div>

        <Show when={showSearch()}>
          <div class="settings-v2-tab-search">
            <TextInputV2
              type="search"
              appearance="base"
              value={store.filter}
              onInput={(event) => setStore("filter", event.currentTarget.value)}
              placeholder={language.t("settings.mcp.search.placeholder") || "Buscar servidores MCP..."}
              spellcheck={false}
              autocorrect="off"
              autocomplete="off"
              autocapitalize="off"
            />
            <Show when={store.filter}>
              <IconButtonV2
                type="button"
                variant="ghost-muted"
                size="small"
                class="settings-v2-tab-search-clear"
                icon={<IconV2 name="close" size="large" class="text-v2-icon-icon-muted" />}
                onClick={() => setStore("filter", "")}
              />
            </Show>
          </div>
        </Show>
      </div>

      <div class="settings-v2-tab-body settings-v2-servers">
        <Show
          when={!loading()}
          fallback={
            <div class="settings-v2-servers-status">
              <span>{language.t("common.loading") || "Cargando servidores MCP..."}</span>
            </div>
          }
        >
          <Show
            when={filtered().length > 0}
            fallback={
              <div class="settings-v2-servers-status gap-3 py-12">
                <Icon name="mcp" class="size-10 text-text-weak opacity-60" />
                <div class="flex flex-col gap-1 items-center max-w-sm text-center">
                  <span class="font-medium text-text-base">
                    {store.filter
                      ? language.t("palette.empty") || "Sin resultados"
                      : language.t("dialog.mcp.empty") || "No hay servidores MCP configurados"}
                  </span>
                  <p class="text-12-regular text-text-muted">
                    {language.t("settings.mcp.empty.description") ||
                      "Los servidores MCP permiten al asistente acceder a herramientas locales o remotas como bases de datos, APIs y herramientas de sistema."}
                  </p>
                </div>
                <Show when={!store.filter}>
                  <ButtonV2 variant="neutral" icon="plus" onClick={openAdd} class="mt-2">
                    {language.t("settings.mcp.add.button") || "Agregar Servidor MCP"}
                  </ButtonV2>
                </Show>
              </div>
            }
          >
            <SettingsListV2>
              <For each={filtered()}>
                {(server) => {
                  const isConnected = () => server.status === "connected" && !server.disabled
                  const isError = () => server.status === "error" || server.status === "failed"
                  const isTesting = () => testingServer() === server.name
                  const isToggling = () => togglingServer() === server.name
                  const toolsCount = () => server.tools?.length ?? 0
                  const isExpanded = () => !!expandedTools()[server.name]

                  return (
                    <div class="settings-v2-servers-row flex-col items-stretch gap-3">
                      <div class="flex items-center justify-between gap-4 w-full">
                        {/* Server Leading Info */}
                        <div class="settings-v2-servers-lead">
                          {/* Status Dot */}
                          <div class="pt-1">
                            <div
                              classList={{
                                "size-2.5 rounded-full shrink-0 transition-colors": true,
                                "bg-icon-success-base ring-4 ring-icon-success-base/20": isConnected(),
                                "bg-icon-critical-base ring-4 ring-icon-critical-base/20": isError(),
                                "bg-border-weak-base opacity-60": server.disabled,
                                "bg-icon-warning-base animate-pulse":
                                  !server.disabled && !isConnected() && !isError(),
                              }}
                            />
                          </div>

                          {/* Server Details */}
                          <div class="settings-v2-servers-copy">
                            <div class="flex items-center gap-2 flex-wrap">
                              <span class="settings-v2-servers-name">{server.name}</span>
                              <Tag>
                                {server.transport === "sse" ? "SSE (Remoto)" : "stdio (Local)"}
                              </Tag>
                              <Show when={server.scope}>
                                <Tag class="opacity-80">
                                  {server.scope === "global" ? "Global" : "Proyecto"}
                                </Tag>
                              </Show>
                              <Show when={server.disabled}>
                                <Tag class="opacity-60">
                                  {language.t("mcp.status.disabled") || "Deshabilitado"}
                                </Tag>
                              </Show>
                              <Show when={toolsCount() > 0}>
                                <button
                                  type="button"
                                  onClick={() => toggleToolsExpanded(server.name)}
                                  class="text-11-medium px-1.5 py-0.5 rounded bg-surface-raised-base hover:bg-surface-raised-base-hover text-text-accent transition-colors flex items-center gap-1 cursor-pointer"
                                >
                                  <span>{toolsCount()} herramientas</span>
                                  <span class="text-10-regular text-text-muted">
                                    {isExpanded() ? "▲" : "▼"}
                                  </span>
                                </button>
                              </Show>
                            </div>

                            {/* Command or URL subtext */}
                            <div class="settings-v2-servers-meta flex flex-col gap-0.5 font-mono text-11-regular">
                              <Show
                                when={server.transport === "stdio"}
                                fallback={<span>{server.url}</span>}
                              >
                                <span class="truncate">
                                  $ {server.command}{" "}
                                  {Array.isArray(server.args) ? server.args.join(" ") : ""}
                                </span>
                              </Show>
                              <Show when={server.error}>
                                <span class="text-state-fg-danger font-sans">{server.error}</span>
                              </Show>
                            </div>
                          </div>
                        </div>

                        {/* Right-side Actions */}
                        <div class="settings-v2-servers-actions flex items-center gap-2">
                          {/* Test connection button */}
                          <IconButtonV2
                            type="button"
                            variant="ghost-muted"
                            size="normal"
                            title={language.t("settings.mcp.test.tooltip") || "Probar conexión"}
                            disabled={isTesting() || isToggling()}
                            icon={
                              <Icon
                                name="reset"
                                class={`size-3.5 text-text-muted hover:text-text-base ${isTesting() ? "animate-spin" : ""}`}
                              />
                            }
                            onClick={() => void testServer(server)}
                          />

                          {/* Edit button */}
                          <IconButtonV2
                            type="button"
                            variant="ghost-muted"
                            size="normal"
                            title={language.t("common.edit") || "Editar"}
                            disabled={isToggling()}
                            icon={<Icon name="edit-small-2" class="size-3.5 text-text-muted hover:text-text-base" />}
                            onClick={() => openEdit(server)}
                          />

                          {/* Delete button */}
                          <IconButtonV2
                            type="button"
                            variant="ghost-muted"
                            size="normal"
                            title={language.t("common.delete") || "Eliminar"}
                            disabled={isToggling()}
                            icon={<Icon name="trash" class="size-3.5 text-state-fg-danger hover:opacity-80" />}
                            onClick={() => void deleteServer(server)}
                          />

                          {/* Switch toggle */}
                          <div class="pl-1">
                            <Switch
                              checked={!server.disabled}
                              disabled={isToggling()}
                              onChange={() => void toggleServer(server)}
                            />
                          </div>
                        </div>
                      </div>

                      {/* Expandable Tools List */}
                      <Show when={isExpanded() && toolsCount() > 0}>
                        <div class="pl-6 pt-1 pb-2 flex flex-col gap-1.5 border-t border-border-muted/50 mt-1">
                          <span class="text-11-medium text-text-muted">
                            {language.t("settings.mcp.tools.title") || "Herramientas registradas:"}
                          </span>
                          <div class="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto pr-1">
                            <For each={server.tools}>
                              {(tool) => (
                                <span class="px-2 py-0.5 rounded bg-surface-raised-base text-11-medium font-mono text-text-base border border-border-muted">
                                  {tool}
                                </span>
                              )}
                            </For>
                          </div>
                        </div>
                      </Show>
                    </div>
                  )
                }}
              </For>
            </SettingsListV2>
          </Show>
        </Show>
      </div>
    </>
  )
}
