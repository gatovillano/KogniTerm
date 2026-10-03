import { ButtonV2 } from "@kogniterm/ui/v2/button-v2"
import { Icon } from "@kogniterm/ui/v2/icon"
import { KeybindV2 } from "@kogniterm/ui/v2/keybind-v2"
import { TooltipV2 } from "@kogniterm/ui/v2/tooltip-v2"
import { useParams } from "@solidjs/router"
import { createMemo } from "solid-js"
import { useCommand } from "@/context/command"
import { useLanguage } from "@/context/language"
import { usePermission } from "@/context/permission"
import { useSDK } from "@/context/sdk"
import { showToast } from "@/utils/toast"

export function PromptAutoApproveToggle(props: { class?: string }) {
  const params = useParams()
  const permission = usePermission()
  const sdk = useSDK()
  const language = useLanguage()
  const command = useCommand()

  const sessionID = () => params.id
  const active = createMemo(() => {
    const id = sessionID()
    if (id) return permission.isAutoAccepting(id, sdk().directory)
    return permission.isAutoAcceptingDirectory(sdk().directory)
  })

  const toggle = (e: MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const id = sessionID()
    if (id) permission.toggleAutoAccept(id, sdk().directory)
    else permission.toggleAutoAcceptDirectory(sdk().directory)

    const nextState = id
      ? permission.isAutoAccepting(id, sdk().directory)
      : permission.isAutoAcceptingDirectory(sdk().directory)

    showToast({
      title: nextState
        ? language.t("toast.permissions.autoaccept.on.title")
        : language.t("toast.permissions.autoaccept.off.title"),
      description: nextState
        ? language.t("toast.permissions.autoaccept.on.description")
        : language.t("toast.permissions.autoaccept.off.description"),
    })
  }

  const keybindParts = createMemo(() => {
    const parts = command.keybindParts("permissions.autoaccept")
    return parts.length > 0 ? parts : ["Shift", "Mod", "A"]
  })

  const tooltipTitle = () =>
    active()
      ? language.t("command.permissions.autoaccept.disable")
      : language.t("command.permissions.autoaccept.enable")

  return (
    <TooltipV2
      placement="top"
      gutter={4}
      value={
        <>
          {tooltipTitle()}
          <KeybindV2 keys={keybindParts()} variant="neutral" />
        </>
      }
    >
      <ButtonV2
        variant={active() ? "neutral" : "ghost-muted"}
        size="normal"
        style={{ height: "28px" }}
        class={`min-w-0 px-2 justify-start ![font-weight:440] group transition-all duration-150 ${props.class ?? ""}`}
        classList={{
          "!text-text-primary !bg-surface-elevated/80 border border-border-highlight/30": active(),
        }}
        onClick={toggle}
        data-action="prompt-auto-approve"
        aria-pressed={active()}
        aria-label={tooltipTitle()}
      >
        <span class="flex items-center gap-1.5 leading-none">
          <Icon
            name="shield"
            class="size-3.5 shrink-0 transition-colors duration-150"
            classList={{
              "text-text-primary": active(),
              "opacity-60 group-hover:opacity-100": !active(),
            }}
          />
          <span class="text-11-medium font-medium tracking-tight">
            {active() ? "Auto" : "Ask"}
          </span>
        </span>
      </ButtonV2>
    </TooltipV2>
  )
}
