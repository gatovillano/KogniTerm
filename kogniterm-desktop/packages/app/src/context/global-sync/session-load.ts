import type { SessionApi } from "@opencode-ai/client/promise"
import { normalizeSessionInfo } from "@/utils/session"
import type { OpencodeClient, Session } from "@opencode-ai/sdk/v2/client"
import type { KogniTermClient } from "@/api/client"
import { isSameWorkspace, loadKogniTermWorkspaceSessions } from "@/utils/kogniterm-workspaces"

export async function loadRootSessions(input: {
  api: Pick<SessionApi, "list">
  directory: string
  limit: number
  kogniTerm?: Pick<KogniTermClient, "listThreads">
  projectID?: string
}) {
  const result = await input.api.list({
    directory: input.directory,
    parentID: null,
    limit: input.limit,
    order: "desc",
  })
  // Red de seguridad: cada proyecto muestra solo los chats de su workspace.
  // El backend Kogniterm ya filtra por `directory`, pero servidores antiguos
  // devuelven todos los hilos y hay que quedarnos con los correspondientes.
  let data: Session[] = result.data
    .map(normalizeSessionInfo)
    .filter((session) => !session.directory || isSameWorkspace(session.directory, input.directory))
  // Respaldo nativo: si la capa compat no trae nada, leer los hilos del
  // backend (`<workspace>/.kogniterm/threads/`, los mismos que ve la TUI).
  if (data.length === 0 && input.kogniTerm) {
    try {
      data = await loadKogniTermWorkspaceSessions({
        kogniTerm: input.kogniTerm,
        directory: input.directory,
        projectID: input.projectID,
      })
    } catch {
      // El backend no es Kogniterm o no hay hilos: mantener lista vacía.
    }
  }
  return {
    data,
    limit: input.limit,
    limited: true,
  } as const
}

export async function loadRootSessionsV1(input: { client: OpencodeClient; directory: string; limit: number }) {
  try {
    const result = await input.client.session.list({ directory: input.directory, roots: true, limit: input.limit })
    return { data: result.data, limit: input.limit, limited: true } as const
  } catch {
    const result = await input.client.session.list({ directory: input.directory, roots: true })
    return { data: result.data, limit: input.limit, limited: false } as const
  }
}

export function estimateRootSessionTotal(input: { count: number; limit: number; limited: boolean }) {
  if (!input.limited) return input.count
  if (input.count < input.limit) return input.count
  return input.count + 1
}
