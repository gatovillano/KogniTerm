import { spawn, type ChildProcess } from "node:child_process"
import { existsSync } from "node:fs"
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
let currentServerUrl: string = "http://127.0.0.1:8765"

export function getSidecarUrl(): string {
  return currentServerUrl
}

function findRepoRoot(): string {
  const current = process.cwd()
  const candidates = [
    current,
    resolve(current, ".."),
    resolve(current, "../.."),
  ]
  for (const dir of candidates) {
    if (existsSync(resolve(dir, "kogniterm"))) {
      return dir
    }
  }
  return current
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
  const candidates = [
    resolve(repoRoot, ".venv", pyName),
    resolve(process.cwd(), ".venv", pyName),
    resolve(repoRoot, "venv", pyName),
    resolve(process.cwd(), "venv", pyName),
  ]

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
  const port = options?.port ?? (process.env.KOGNITERM_PORT ? Number(process.env.KOGNITERM_PORT) : 8765)
  const url = `http://${host}:${port}`
  currentServerUrl = url
  const timeoutMs = options?.timeoutMs ?? 30000

  // 1. Probe if KogniTerm Server is already running
  if (await isServerHealthy(url, 2000)) {
    console.log(`[sidecar] KogniTerm server is already running at ${url}`)
    return {
      url,
      host,
      port,
      stop: () => stopSidecar(),
    }
  }

  // 2. Spawn subprocess python -m kogniterm.server --host 127.0.0.1 --port 8765
  const repoRoot = options?.cwd ?? findRepoRoot()
  const pythonBin = options?.pythonBin ?? findPythonBinary(repoRoot)

  console.log(`[sidecar] Spawning KogniTerm Server (${pythonBin} -m kogniterm.server --host ${host} --port ${port}) in ${repoRoot}`)

  const childEnv = {
    ...process.env,
    PYTHONUNBUFFERED: "1",
    KOGNITERM_ALLOWED_ORIGINS: "*",
    PYTHONPATH: [repoRoot, process.env.PYTHONPATH].filter(Boolean).join(":"),
  }

  const child = spawn(
    pythonBin,
    ["-m", "kogniterm.server", "--host", host, "--port", String(port)],
    {
      cwd: repoRoot,
      env: childEnv,
      stdio: ["ignore", "pipe", "pipe"],
    }
  )

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
      throw new Error(`KogniTerm server exited prematurely with code ${exitCode}`)
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
