import type { Project, Session } from "@opencode-ai/sdk/v2/client"
import {
  threadIdOf,
  threadMessageCountOf,
  threadWorkspaceOf,
  type KogniTermClient,
  type KogniTermThread,
  type KogniTermWorkspace,
} from "@/api/client"

/**
 * Adaptador entre la lógica de workspaces/hilos del backend Kogniterm
 * (ThreadManager: `<workspace>/.kogniterm/threads/<id>/`) y los conceptos
 * Project/Session que espera el desktop (heredado de opencode).
 *
 * - Cada workspace conocido (`GET /api/workspaces`) es un proyecto.
 * - Cada hilo (`GET /api/threads`) es un chat asociado a su workspace
 *   vía `workspace_dir`, igual que la TUI muestra con `/session list`.
 */

export function normalizeWorkspacePath(path: string): string {
  return path.replace(/\/+$/, "") || "/"
}

export function isSameWorkspace(a: string | undefined, b: string | undefined): boolean {
  if (!a || !b) return false
  return normalizeWorkspacePath(a) === normalizeWorkspacePath(b)
}

export function workspaceProjectId(path: string): string {
  let hash = 0
  const clean = normalizeWorkspacePath(path)
  for (let i = 0; i < clean.length; i++) {
    hash = (hash * 31 + clean.charCodeAt(i)) | 0
  }
  return `ws-local-${Math.abs(hash).toString(16)}`
}

export function workspaceToProject(workspace: KogniTermWorkspace): Project {
  const now = Date.now()
  return {
    id: workspace.id || workspaceProjectId(workspace.path),
    worktree: workspace.path,
    name: workspace.name,
    sandboxes: [],
    time: { created: now, updated: now },
  }
}

function threadTimeMs(value: string | undefined, fallback: number): number {
  if (!value) return fallback
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? fallback : parsed
}

export function threadToSession(thread: KogniTermThread, projectID?: string): Session {
  const id = threadIdOf(thread)
  const directory = threadWorkspaceOf(thread)
  const now = Date.now()
  const updated = threadTimeMs(thread.updated_at, now)
  const created = threadTimeMs(thread.created_at, updated)
  return {
    id,
    slug: id,
    projectID: projectID ?? "",
    directory,
    title: thread.title || "Chat Session",
    version: "",
    cost: 0,
    tokens: { input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } },
    time: { created, updated },
  }
}

/**
 * Registra una carpeta como workspace en el backend para que sus hilos
 * (los mismos que ve la TUI) se incluyan en `GET /api/threads` y
 * `GET /api/project`. No falla si el backend no es Kogniterm.
 */
export async function ensureWorkspaceRegistered(
  kogniTerm: Pick<KogniTermClient, "addWorkspace"> | undefined,
  directory: string,
): Promise<KogniTermWorkspace | undefined> {
  if (!kogniTerm || !directory) return undefined
  try {
    const result = await kogniTerm.addWorkspace(directory)
    return result.workspace
  } catch {
    return undefined
  }
}

/**
 * Vía nativa para cargar los chats de un workspace: lee los hilos del
 * backend y devuelve solo los asociados a `directory`. Se usa como
 * respaldo cuando la capa compat no devuelve sesiones para el proyecto.
 */
export async function loadKogniTermWorkspaceSessions(input: {
  kogniTerm: Pick<KogniTermClient, "listThreads">
  directory: string
  projectID?: string
}): Promise<Session[]> {
  const result = await input.kogniTerm.listThreads({
    workspaceDirs: [input.directory],
    filterOnly: true,
  })
  return (result.threads ?? [])
    .filter((thread) => !!threadIdOf(thread))
    .filter((thread) => isSameWorkspace(threadWorkspaceOf(thread), input.directory))
    .map((thread) => threadToSession(thread, input.projectID))
}

export type { KogniTermThread, KogniTermWorkspace }
export { threadMessageCountOf }
