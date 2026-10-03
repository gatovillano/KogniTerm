import { spawn, type ChildProcess } from "node:child_process"
import { existsSync } from "node:fs"
import { connect } from "node:net"
import { homedir } from "node:os"
import { resolve } from "node:path"
import { app } from "electron"

export interface SidecarOptions {
  host?: string
  port?: number
  pythonBin?: string
  timeoutMs?: number
  cwd?: string
}

export interface SidecarInstance {
  url: string
  host: string
  port: number
  process?: ChildProcess
  stop: () => Promise<void>
}

let activeSidecarProcess: ChildProcess | null = null
let currentServerUrl: string = "http://127.0.0.1:8755"

export function getSidecarUrl(): string {
  return currentServerUrl
}

function findRepoRoot(): string {
  const home = homedir() || process.env.HOME || ""
  const isPackaged = typeof app !== "undefined" && Boolean(app?.isPackaged)
  const localCandidates = [
    ...(process.env.KOGNITERM_REPO ? [process.env.KOGNITERM_REPO] : []),
    resolve(__dirname, "../../.."),
    resolve(__dirname, "../../../.."),
    process.cwd(),
    resolve(process.cwd(), ".."),
    resolve(process.cwd(), "../.."),
    "/home/gato/Proyectos/Gemini-Interpreter",
  ]
  const installedCandidates = [
    ...(home ? [resolve(home, ".kogniterm", "repo")] : []),
  ]
  const candidates = isPackaged
    ? [...installedCandidates, ...localCandidates]
    : [...localCandidates, ...installedCandidates]

  for (const dir of candidates) {
    if (dir && existsSync(resolve(dir, "kogniterm", "server", "app.py"))) {
      return dir
    }
  }
  return process.cwd()
}

/**
 * Localiza el ejecutable `kogniterm-server` instalado (preferido una vez
 * empaquetado: no depende del cwd ni del PYTHONPATH, funciona aunque la app
 * corra desde /opt, AppImage o dist).
 */
function findServerBinary(repoRoot: string): string | null {
  const home = homedir() || process.env.HOME || ""
  const isWin = process.platform === "win32"
  const binName = isWin ? "kogniterm-server.exe" : "kogniterm-server"
  const isPackaged = typeof app !== "undefined" && Boolean(app?.isPackaged)
  const localCandidates = [
    resolve(repoRoot, ".venv", isWin ? "Scripts" : "bin", binName),
    resolve(repoRoot, "venv", isWin ? "Scripts" : "bin", binName),
  ]
  const installedCandidates = [
    ...(home ? [resolve(home, ".kogniterm", "venv", isWin ? "Scripts" : "bin", binName)] : []),
    resolve(home, ".local", "bin", binName),
  ]
  const candidates = isPackaged
    ? [...installedCandidates, ...localCandidates]
    : [...localCandidates, ...installedCandidates]

  for (const candidate of candidates) {
    try {
      if (candidate && existsSync(candidate)) return candidate
    } catch {}
  }
  // Último recurso: resolver por PATH (spawn lo resuelve en POSIX).
  return binName
}

function findPythonBinary(repoRoot: string): string {
  if (process.env.KOGNITERM_PYTHON && existsSync(process.env.KOGNITERM_PYTHON)) {
    return process.env.KOGNITERM_PYTHON
  }
  if (process.env.KOGNITERM_PYTHON) {
    return process.env.KOGNITERM_PYTHON
  }

  const isWin = process.platform === "win32"
  const pyName = isWin ? "Scripts/python.exe" : "bin/python"
  const isPackaged = typeof app !== "undefined" && Boolean(app?.isPackaged)
  const home = (typeof app !== "undefined" && app?.getPath ? app.getPath("home") : "") || homedir() || process.env.HOME || ""
  const localCandidates = [
    resolve(repoRoot, ".venv", pyName),
    resolve(process.cwd(), ".venv", pyName),
    resolve(repoRoot, "venv", pyName),
    resolve(process.cwd(), "venv", pyName),
  ]
  const installedCandidates = [
    resolve(home, ".kogniterm", "venv", pyName),
  ]
  const candidates = isPackaged
    ? [...installedCandidates, ...localCandidates]
    : [...localCandidates, ...installedCandidates]

  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate
    }
  }

  return isWin ? "python" : "python3"
}

export async function isServerHealthy(url: string, timeoutMs: number = 2000): Promise<boolean> {
  const cleanUrl = url.replace(/\/+$/, "")
  const probeUrls = [`${cleanUrl}/health`, `${cleanUrl}/docs`]
  for (const probeUrl of probeUrls) {
    try {
      const res = await fetch(probeUrl, {
        method: "GET",
        signal: AbortSignal.timeout(timeoutMs),
      })
      if (res.ok || res.status === 200) {
        return true
      }
    } catch {
      // not yet responding
    }
  }
  return false
}

export interface ServerCompatibility {
  compatible: boolean
  reason?: string
  version?: unknown
  pid?: unknown
}

async function fetchJson(url: string, timeoutMs: number): Promise<{ status: number; body?: unknown }> {
  const res = await fetch(url, {
    method: "GET",
    signal: AbortSignal.timeout(timeoutMs),
  })
  if (!res.ok) return { status: res.status }
  const contentType = res.headers.get("content-type") ?? ""
  if (!contentType.includes("application/json")) return { status: res.status }
  try {
    return { status: res.status, body: (await res.json()) as unknown }
  } catch {
    return { status: res.status }
  }
}

/**
 * Checks whether the server at `url` is a KogniTerm backend the desktop can
 * actually talk to — not just any process answering `/health`.
 *
 * Reuse is only safe when the running instance exposes the identity shape
 * (`{ healthy: true, pid: <number> }`, same rule the renderer uses to detect
 * protocol v2) and answers the session-list endpoint the desktop bootstraps
 * from. Otherwise the app connects and every SDK call fails downstream with
 * an opaque `ClientError: Transport`.
 */
export async function checkServerCompatibility(
  url: string,
  timeoutMs: number = 2000,
): Promise<ServerCompatibility> {
  const cleanUrl = url.replace(/\/+$/, "")
  const healthPaths = ["/api/health", "/health"]
  let healthBody: unknown
  for (const path of healthPaths) {
    try {
      const { status, body } = await fetchJson(`${cleanUrl}${path}`, timeoutMs)
      if (status >= 200 && status < 300 && body && typeof body === "object") {
        healthBody = body
        break
      }
    } catch {
      // try next path
    }
  }
  if (!healthBody || typeof healthBody !== "object") {
    return { compatible: false, reason: "no compatible KogniTerm health endpoint" }
  }
  const health = healthBody as Record<string, unknown>
  if (health["healthy"] !== true) {
    return { compatible: false, reason: "server reports unhealthy", version: health["version"], pid: health["pid"] }
  }
  if (typeof health["pid"] !== "number") {
    return {
      compatible: false,
      reason: "server identity missing numeric pid (not a compatible v2 backend)",
      version: health["version"],
      pid: health["pid"],
    }
  }

  // Functional probe: the desktop bootstrap lists sessions on start.
  try {
    const { status } = await fetchJson(`${cleanUrl}/api/session?limit=1&order=desc`, timeoutMs)
    if (status < 200 || status >= 300) {
      return {
        compatible: false,
        reason: `session endpoint answered ${status}`,
        version: health["version"],
        pid: health["pid"],
      }
    }
  } catch {
    return { compatible: false, reason: "session endpoint unreachable", version: health["version"], pid: health["pid"] }
  }

  return { compatible: true, version: health["version"], pid: health["pid"] }
}

function isTcpPortOccupied(host: string, port: number, timeoutMs: number = 1000): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = connect({ host, port })
    const done = (occupied: boolean) => {
      socket.destroy()
      resolve(occupied)
    }
    const timer = setTimeout(() => done(false), timeoutMs)
    socket.once("connect", () => {
      clearTimeout(timer)
      done(true)
    })
    socket.once("error", (err: NodeJS.ErrnoException) => {
      clearTimeout(timer)
      // Anything other than "nothing listening" means the port is not usable
      // for us (e.g. permission), treat it as occupied to be safe.
      done(err.code !== "ECONNREFUSED")
    })
  })
}

async function findFreePort(host: string, startPort: number, maxTries: number = 20): Promise<number | null> {
  for (let port = startPort; port < startPort + maxTries; port++) {
    if (!(await isTcpPortOccupied(host, port))) return port
  }
  return null
}

export async function stopSidecar(): Promise<void> {
  const proc = activeSidecarProcess
  if (!proc) return
  activeSidecarProcess = null

  if (proc.killed || proc.exitCode !== null) return

  return new Promise<void>((resolve) => {
    let done = false
    const finish = () => {
      if (!done) {
        done = true
        resolve()
      }
    }

    const timer = setTimeout(() => {
      try {
        proc.kill("SIGKILL")
      } catch {}
      finish()
    }, 4000)

    proc.once("exit", () => {
      clearTimeout(timer)
      finish()
    })

    try {
      proc.kill("SIGTERM")
    } catch {
      clearTimeout(timer)
      finish()
    }
  })
}

// Hook clean shutdown on Electron application quit
if (typeof app !== "undefined" && app?.on) {
  app.on("before-quit", () => {
    void stopSidecar()
  })
  app.on("will-quit", () => {
    void stopSidecar()
  })
}

export async function initSidecar(options?: SidecarOptions): Promise<SidecarInstance> {
  const host = options?.host ?? process.env.KOGNITERM_HOST ?? "127.0.0.1"
  const requestedPort = options?.port ?? (process.env.KOGNITERM_PORT ? Number(process.env.KOGNITERM_PORT) : 8755)
  const timeoutMs = options?.timeoutMs ?? 30000

  // 1. If something already listens on the requested port, reuse it only when
  // it is a compatible KogniTerm backend. Otherwise fall through and spawn our
  // own instance on the next free port — never hijack an unknown server.
  let port = requestedPort
  if (await isTcpPortOccupied(host, port)) {
    const requestedUrl = `http://${host}:${port}`
    const compat = await checkServerCompatibility(requestedUrl, 2000)
    if (compat.compatible) {
      currentServerUrl = requestedUrl
      console.log(`[sidecar] Reusing compatible KogniTerm server at ${requestedUrl} (pid ${String(compat.pid)})`)
      return {
        url: requestedUrl,
        host,
        port,
        stop: () => stopSidecar(),
      }
    }
    console.warn(`[sidecar] Port ${port} is occupied by an incompatible server (${compat.reason ?? "unknown"}); looking for a free port`)
    const freePort = await findFreePort(host, port + 1)
    if (freePort === null) {
      throw new Error(
        `Port ${port} is occupied by an incompatible server (${compat.reason ?? "unknown"}) and no free port was found nearby`,
      )
    }
    port = freePort
  }

  const url = `http://${host}:${port}`
  currentServerUrl = url

  // 2. Spawn del backend. Preferir el binario `kogniterm-server` instalado
  // (funciona empaquetado); si no existe, caer a `python -m kogniterm.server`
  // con el repo detectado.
  const repoRoot = options?.cwd ?? findRepoRoot()
  const serverBin = findServerBinary(repoRoot)

  let cmd: string
  let cmdArgs: string[]
  let spawnCwd: string
  if (serverBin && serverBin !== "kogniterm-server" && serverBin !== "kogniterm-server.exe") {
    cmd = serverBin
    cmdArgs = ["--host", host, "--port", String(port)]
    // El venv del instalador ya trae el paquete; el cwd es irrelevante.
    spawnCwd = repoRoot
    console.log(`[sidecar] Spawning KogniTerm Server (${cmd} --host ${host} --port ${port})`)
  } else {
    const pythonBin = options?.pythonBin ?? findPythonBinary(repoRoot)
    cmd = pythonBin
    cmdArgs = ["-m", "kogniterm.server", "--host", host, "--port", String(port)]
    spawnCwd = repoRoot
    console.log(`[sidecar] Spawning KogniTerm Server (${pythonBin} -m kogniterm.server --host ${host} --port ${port}) in ${repoRoot}`)
  }

  const childEnv = {
    ...process.env,
    PYTHONUNBUFFERED: "1",
    KOGNITERM_ALLOWED_ORIGINS: "*",
    PYTHONPATH: [repoRoot, process.env.PYTHONPATH].filter(Boolean).join(":"),
  }

  const child = spawn(
    cmd,
    cmdArgs,
    {
      cwd: spawnCwd,
      env: childEnv,
      stdio: ["ignore", "pipe", "pipe"],
    }
  )
  child.once("error", (err) => {
    console.error(`[sidecar] Failed to spawn backend (${cmd}): ${String(err)}`)
  })

  activeSidecarProcess = child

  child.stdout?.on("data", (chunk: Buffer) => {
    const text = chunk.toString("utf8").trimEnd()
    if (text) console.log(`[kogniterm-server] ${text}`)
  })

  child.stderr?.on("data", (chunk: Buffer) => {
    const text = chunk.toString("utf8").trimEnd()
    if (text) console.warn(`[kogniterm-server] ${text}`)
  })

  let childExited = false
  let exitCode: number | null = null
  child.once("exit", (code) => {
    childExited = true
    exitCode = code
    if (activeSidecarProcess === child) {
      activeSidecarProcess = null
    }
  })

  // 3. Poll until healthy
  const startTime = Date.now()
  while (Date.now() - startTime < timeoutMs) {
    if (childExited) {
      throw new Error(
        `KogniTerm server exited prematurely with code ${exitCode} (cmd: ${cmd} ${cmdArgs.join(" ")} in ${spawnCwd}). ` +
          `Si la app está empaquetada, instala el backend con install.sh (deja el repo en ~/.kogniterm/repo y el venv en ~/.kogniterm/venv) ` +
          `o define KOGNITERM_REPO / KOGNITERM_PYTHON.`,
      )
    }
    if (await isServerHealthy(url, 1000)) {
      console.log(`[sidecar] KogniTerm server is ready at ${url}`)
      return {
        url,
        host,
        port,
        process: child,
        stop: () => stopSidecar(),
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 300))
  }

  await stopSidecar()
  throw new Error(`Timed out waiting for KogniTerm server to start at ${url} (${timeoutMs}ms)`)
}
