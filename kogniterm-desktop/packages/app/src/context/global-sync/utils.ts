import type {
  AgentListOutput,
  ModelDefaultOutput,
  ModelListOutput,
  PermissionV2Request,
  ProviderListOutput,
} from "@opencode-ai/client/promise"
import type { Agent, PermissionRequest, Project, Provider, ProviderListResponse } from "@opencode-ai/sdk/v2/client"
import type { Project as CurrentProject } from "@opencode-ai/client/promise"
import { NormalizedProviderListResponse } from "@opencode-ai/session-ui/context"
export { pathKey as directoryKey, type PathKey as DirectoryKey } from "@/utils/path-key"

export const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0)

export function normalizeAgentList(input: AgentListOutput["data"] | Agent[]): Agent[] {
  if (input.every((agent) => !("request" in agent))) return input as Agent[]
  return (input as AgentListOutput["data"]).map((agent) => ({
    name: agent.id,
    description: agent.description,
    mode: agent.mode,
    hidden: agent.hidden,
    temperature:
      typeof agent.request.settings.temperature === "number" ? agent.request.settings.temperature : undefined,
    topP: typeof agent.request.settings.topP === "number" ? agent.request.settings.topP : undefined,
    color: agent.color,
    permission: agent.permissions.map((rule) => ({
      permission: rule.action,
      pattern: rule.resource,
      action: rule.effect,
    })),
    model: agent.model && { providerID: agent.model.providerID, modelID: agent.model.id },
    variant: agent.model?.variant,
    prompt: agent.system,
    options: agent.request.settings,
    steps: agent.steps,
  }))
}

export function normalizePermissionRequest(input: PermissionV2Request | PermissionRequest): PermissionRequest {
  if ("permission" in input) return input
  return {
    id: input.id,
    sessionID: input.sessionID,
    permission: input.action,
    patterns: input.resources,
    always: input.save ?? [],
    metadata: input.metadata ?? {},
    tool:
      input.source?.type === "tool" ? { messageID: input.source.messageID, callID: input.source.callID } : undefined,
  }
}

export function normalizeProviderList(
  rawProviders: ProviderListOutput["data"] | ProviderListResponse,
  models?: ModelListOutput["data"],
  defaultModel?: ModelDefaultOutput["data"],
): NormalizedProviderListResponse {
  if (!rawProviders) {
    return {
      all: new Map(),
      connected: [],
      default: {},
      defaultModel: null,
    } as any
  }

  if (typeof rawProviders === "object" && !Array.isArray(rawProviders) && Array.isArray((rawProviders as any).data)) {
    return normalizeProviderList((rawProviders as any).data, models, defaultModel)
  }

  if (!Array.isArray(rawProviders)) {
    const allProviders = Array.isArray((rawProviders as any).all) ? (rawProviders as any).all : []
    return {
      ...rawProviders,
      all: new Map(
        allProviders.map((provider: any) => [
          provider.id,
          {
            ...provider,
            models: Object.fromEntries(
              Object.entries(provider.models ?? {}).filter(([, model]: any) => model?.status !== "deprecated"),
            ),
          },
        ]),
      ),
      connected: Array.isArray((rawProviders as any).connected) ? (rawProviders as any).connected : [],
      default: (rawProviders as any).default ?? {},
    }
  }
  const providers = rawProviders
  const all = new Map<string, Provider>()

  for (const provider of providers) {
    all.set(provider.id, {
      id: provider.id,
      name: provider.name,
      source: "custom",
      env: [],
      options: provider.settings ?? {},
      models: {},
    })
  }

  for (const model of models ?? []) {
    const provider = all.get(model.providerID)
    if (!provider || model.status === "deprecated") continue
    const cost = Array.isArray(model.cost)
      ? (model.cost.find((item: any) => item.tier === undefined) ?? model.cost[0])
      : model.cost
    const caps = model.capabilities ?? { tools: true, input: ["text", "image"], output: ["text"] }
    const capsInput = Array.isArray(caps.input) ? caps.input : ["text", "image"]
    const capsOutput = Array.isArray(caps.output) ? caps.output : ["text"]
    const timeReleased = model.time?.released ?? Date.now()
    const variants = Array.isArray(model.variants) ? model.variants : []
    provider.models[model.id] = {
      id: model.id,
      providerID: model.providerID,
      api: {
        id: model.modelID ?? model.id,
        url: "",
        npm: model.package ?? provider.id,
      },
      name: model.name ?? model.id,
      family: model.family,
      capabilities: {
        temperature: false,
        reasoning: false,
        attachment: capsInput.some((item: any) => item !== "text"),
        toolcall: !!caps.tools,
        input: {
          text: capsInput.includes("text"),
          audio: capsInput.includes("audio"),
          image: capsInput.includes("image"),
          video: capsInput.includes("video"),
          pdf: capsInput.includes("pdf"),
        },
        output: {
          text: capsOutput.includes("text"),
          audio: capsOutput.includes("audio"),
          image: capsOutput.includes("image"),
          video: capsOutput.includes("video"),
          pdf: capsOutput.includes("pdf"),
        },
        interleaved: false,
      },
      cost: {
        input: cost?.input ?? 0.001,
        output: cost?.output ?? 0.002,
        cache: {
          read: cost?.cache?.read ?? 0,
          write: cost?.cache?.write ?? 0,
        },
      },
      limit: model.limit ?? { context: 128000, output: 8192 },
      status: model.status ?? "active",
      options: model.settings ?? {},
      headers: model.headers ?? {},
      release_date: new Date(timeReleased).toISOString().slice(0, 10),
      variants: Object.fromEntries(variants.map((variant: any) => [variant.id, variant.settings ?? {}])),
    }
  }

  return {
    all,
    connected: providers
      .filter((provider: any) => provider.connected !== false)
      .map((provider) => provider.id),
    defaultModel: defaultModel ? { providerID: defaultModel.providerID, modelID: defaultModel.id } : null,
    default: Object.fromEntries(
      providers.flatMap((provider) => {
        const model =
          defaultModel?.providerID === provider.id
            ? defaultModel
            : models?.find((item) => item.providerID === provider.id && item.status !== "deprecated")
        return model ? [[provider.id, model.id]] : []
      }),
    ),
  }
}

export function sanitizeProject(project: Project) {
  if (!project.icon?.url && !project.icon?.override) return project
  return {
    ...project,
    icon: {
      ...project.icon,
      url: undefined,
      override: undefined,
    },
  }
}

export function normalizeProjectInfo(project: Project | CurrentProject): Project {
  return {
    ...project,
    vcs: project.vcs === "git" ? "git" : undefined,
  }
}
