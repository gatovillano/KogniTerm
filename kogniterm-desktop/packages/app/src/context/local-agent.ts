import type { Agent } from "@opencode-ai/sdk/v2/client"

export const DEFAULT_FALLBACK_AGENT: Agent = {
  name: "build",
  mode: "primary",
  native: true,
  description: "Agente principal de desarrollo.",
  permission: [],
  options: {},
}

export function hasCustomAgent(items: Array<{ native?: boolean }>) {
  return items.some((item) => item.native === false)
}

export function resolveAgent<T extends { name: string }>(items: T[], name?: string): T {
  return (
    items.find((item) => item.name === name) ??
    items.find((item) => item.name === "build") ??
    items[0] ??
    (DEFAULT_FALLBACK_AGENT as unknown as T)
  )
}

