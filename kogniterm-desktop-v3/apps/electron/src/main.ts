import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const isDev = process.env.NODE_ENV !== "production";
const WEB_URL = process.env.VITE_WEB_URL ?? "http://localhost:4444";

const HOST = process.env.KOGNITERM_HOST ?? "127.0.0.1";
const PORT = process.env.KOGNITERM_PORT ?? "8755";
const HEALTH = `http://${HOST}:${PORT}/health`;
const SERVICE_NAME = "kogniterm-server";

let win: BrowserWindow | null = null;
/** Proceso lanzado por nosotros (fallback). El del servicio del sistema no se toca. */
let spawned: ChildProcess | null = null;
/** "service" | "spawned" | "external" */
let backendOwner: "service" | "spawned" | "external" | null = null;

// El bundle de main vive en apps/electron/out/main, así que la raíz de los
// paquetes (apps/) está tres niveles arriba.
const APPS_ROOT = join(__dirname, "..", "..", "..");
const V3_ROOT = join(APPS_ROOT, "..");
const WEB_DIST = join(APPS_ROOT, "web", "dist", "index.html");
const BACKEND_SCRIPT = join(APPS_ROOT, "backend", "run.py");

// ── Utilidades ───────────────────────────────────────────────────────────────

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

/** ¿El backend responde /health? */
async function backendUp(timeoutMs = 1500): Promise<boolean> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(HEALTH, { signal: ctrl.signal });
    clearTimeout(t);
    return res.ok;
  } catch {
    return false;
  }
}

/** Espera activa hasta que /health responda. */
async function waitForBackend(attempts = 40, delayMs = 750): Promise<boolean> {
  for (let i = 0; i < attempts; i++) {
    if (await backendUp()) return true;
    await sleep(delayMs);
  }
  return false;
}

/** ¿Está registrado el servicio de systemd/launchd? */
function serviceInstalled(): boolean {
  if (process.platform === "darwin") {
    return existsSync(join(homedir(), "Library", "LaunchAgents", "com.kogniterm.server.plist"));
  }
  return existsSync(join(homedir(), ".config", "systemd", "user", `${SERVICE_NAME}.service`));
}

/** Intenta arrancar el servicio del sistema (preferido: sobrevive al cierre). */
function startService(): boolean {
  try {
    if (process.platform === "darwin") {
      const plist = join(homedir(), "Library", "LaunchAgents", "com.kogniterm.server.plist");
      const r = spawnSync("launchctl", ["start", "com.kogniterm.server"], { stdio: "ignore" });
      return r.status === 0 && existsSync(plist);
    }
    const probe = spawnSync("systemctl", ["--user", "is-enabled", SERVICE_NAME], { stdio: "ignore" });
    if (probe.status !== 0) return false;
    const r = spawnSync("systemctl", ["--user", "start", SERVICE_NAME], { stdio: "ignore" });
    return r.status === 0;
  } catch {
    return false;
  }
}

function stopService(): boolean {
  try {
    if (process.platform === "darwin") {
      return spawnSync("launchctl", ["stop", "com.kogniterm.server"], { stdio: "ignore" }).status === 0;
    }
    return spawnSync("systemctl", ["--user", "stop", SERVICE_NAME], { stdio: "ignore" }).status === 0;
  } catch {
    return false;
  }
}

/** Candidatos para lanzar el backend a mano, en orden de preferencia. */
function backendCandidates(): Array<{ cmd: string; args: string[] }> {
  const home = homedir();
  const args = ["--host", HOST, "--port", PORT];
  const out: Array<{ cmd: string; args: string[] }> = [
    // 1) venv de la instalación oficial (install.sh)
    { cmd: join(home, ".kogniterm", "venv", "bin", SERVICE_NAME), args },
    // 2) lanzador global en ~/.local/bin
    { cmd: join(home, ".local", "bin", SERVICE_NAME), args },
    // 3) venvs de desarrollo (este repo y el monorepo que lo contiene)
    { cmd: join(V3_ROOT, ".venv", "bin", SERVICE_NAME), args },
    { cmd: join(V3_ROOT, "..", ".venv", "bin", SERVICE_NAME), args },
    // 4) cualquier kogniterm-server en el PATH
    { cmd: SERVICE_NAME, args },
    // 5) script del propio cliente v3
    { cmd: "python3", args: [BACKEND_SCRIPT, ...args] },
  ];
  return out.filter((c) => c.cmd === SERVICE_NAME || existsSync(c.cmd));
}

/**
 * Arranca el backend como proceso nuestro (desacoplado: sobrevive al cierre).
 * Un candidato que muere de inmediato (venv roto, binario ausente) no cuenta:
 * se descarta y se prueba el siguiente, en vez de esperar en balde.
 */
async function spawnBackend(): Promise<boolean> {
  for (const { cmd, args } of backendCandidates()) {
    let child: ChildProcess;
    try {
      child = spawn(cmd, args, {
        detached: true,
        stdio: "ignore",
        env: { ...process.env, PYTHONUNBUFFERED: "1" },
      });
    } catch {
      continue;
    }
    child.unref();

    const dead = () => child.exitCode !== null || child.signalCode !== null;

    // Margen inicial: si muere enseguida (o sana rápido), decidimos ya.
    for (let i = 0; i < 6; i++) {
      await sleep(500);
      if (dead()) break;
      if (await backendUp()) {
        spawned = child;
        console.log(`[v3-electron] backend sano: ${cmd} ${args.join(" ")}`);
        return true;
      }
    }

    if (dead()) {
      console.warn(`[v3-electron] candidato descartado (murió al inicio): ${cmd}`);
      continue;
    }

    // Sigue vivo: le damos más margen a /health (arranque lento: venv, índices…).
    if (await waitForBackend(24, 750)) {
      spawned = child;
      console.log(`[v3-electron] backend sano: ${cmd} ${args.join(" ")}`);
      return true;
    }

    console.warn(`[v3-electron] ${cmd} no respondió /health; se detiene y se prueba otro candidato`);
    try {
      child.kill("SIGTERM");
    } catch {
      /* ya no está */
    }
  }
  return false;
}

/**
 * Garantiza que el backend esté disponible.
 * Prioridad: ya está arriba > servicio del sistema > proceso propio.
 * Nunca duplica: si el servicio existe se usa, así evitamos el conflicto de
 * polling de Telegram entre dos instancias.
 */
async function ensureBackend(): Promise<void> {
  if (process.env.KOGNITERM_NO_SIDECAR === "1") {
    console.log("[v3-electron] KOGNITERM_NO_SIDECAR=1 — no se gestiona el backend");
    return;
  }

  if (await backendUp()) {
    backendOwner = "external";
    console.log(`[v3-electron] backend ya activo en ${HEALTH}`);
    return;
  }

  console.log("[v3-electron] backend apagado — intentando arrancarlo…");

  if (serviceInstalled() && startService()) {
    if (await waitForBackend()) {
      backendOwner = "service";
      console.log("[v3-electron] backend arrancado vía servicio del sistema");
      return;
    }
  }

  if (await spawnBackend()) {
    backendOwner = "spawned";
    console.log("[v3-electron] backend arrancado en segundo plano por la app");
    return;
  }

  console.error("[v3-electron] no se pudo arrancar el backend");
}
/** Corta el proceso que lanzamos nosotros (nunca el del servicio). */
function stopSpawnedBackend(): boolean {
  if (backendOwner !== "spawned" || !spawned?.pid) return false;
  try {
    process.kill(spawned.pid, "SIGTERM");
    spawned = null;
    backendOwner = null;
    return true;
  } catch {
    return false;
  }
}

async function backendStatus() {
  const up = await backendUp();
  return {
    up,
    url: `http://${HOST}:${PORT}`,
    owner: backendOwner,
    serviceInstalled: serviceInstalled(),
    managed: backendOwner === "spawned",
  };
}

// ── IPC ──────────────────────────────────────────────────────────────────────

ipcMain.handle("backend:status", () => backendStatus());
ipcMain.handle("backend:start", async () => {
  if (await backendUp()) return backendStatus();
  if (serviceInstalled() && startService()) {
    if (await waitForBackend()) {
      backendOwner = "service";
      return backendStatus();
    }
  }
  if (await spawnBackend()) {
    backendOwner = "spawned";
    return backendStatus();
  }
  return backendStatus();
});
ipcMain.handle("backend:stop", async () => {
  let stopped = false;
  if (stopSpawnedBackend()) stopped = true;
  else if (backendOwner === "service" && serviceInstalled()) stopped = stopService();
  return { ...(await backendStatus()), stopped };
});

// ── Ventana ──────────────────────────────────────────────────────────────────

async function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 860,
    backgroundColor: "#0d1117",
    title: "KogniTerm v3",
    webPreferences: {
      // Preload en CJS: el contexto sandboxed de Electron no admite ESM.
      preload: join(__dirname, "..", "preload", "preload.cjs"),
      contextIsolation: true,
      // El renderer necesita saber a qué backend conectarse (KOGNITERM_PORT lo
      // resuelve el proceso main). Sin esto, apuntaría siempre a 8755.
      additionalArguments: [`--kogniterm-api=http://${HOST}:${PORT}`],
    },
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: "deny" };
  });

  // Traza del renderer a stdout (KOGNITERM_DEBUG_RENDERER=1) para diagnosticar
  // pantallas en blanco / errores de carga.
  if (process.env.KOGNITERM_DEBUG_RENDERER === "1") {
    win.webContents.on("console-message", (_e, level, message, line, sourceId) => {
      if (level >= 2) console.log(`[renderer] ${message} (${(sourceId || "").split("/").pop()}:${line})`);
    });
    win.webContents.on("did-fail-load", (_e, code, desc, url) => {
      console.error(`[renderer] did-fail-load ${code} ${desc} ${url}`);
    });
    win.webContents.on("preload-error", (_e, file, err) => {
      console.error(`[renderer] preload-error ${file}: ${err.message}`);
    });
  }

  if (isDev) {
    try {
      await win.loadURL(WEB_URL);
    } catch {
      // Sin el dev server de apps/web no hay nada que cargar: explica en vez de
      // dejar una ventana en negro.
      await win.loadURL(
        `data:text/html;charset=utf-8,${encodeURIComponent(
          `<body style="background:#0d1117;color:#e6edf3;font:14px system-ui;padding:40px;line-height:1.6">
             <h2 style="color:#f59e0b">No se pudo cargar la interfaz (${WEB_URL})</h2>
             <p>Arranca el servidor de desarrollo en otra terminal:</p>
             <pre style="background:#161b22;border:1px solid #30363d;border-radius:6px;padding:12px">npm run dev:web</pre>
             <p>O bien compila la interfaz y relanza Electron en modo producción.</p>
           </body>`,
        )}`,
      );
      return;
    }
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    if (!existsSync(WEB_DIST)) {
      dialog.showErrorBox(
        "KogniTerm v3",
        `No se encontró la interfaz compilada en:\n${WEB_DIST}\n\nEjecuta primero: npm run build --workspace=@kogniterm-v3/web`,
      );
    }
    await win.loadFile(WEB_DIST);
  }
}

app.whenReady().then(async () => {
  // La ventana abre igual aunque el backend tarde o falle: la UI muestra el error.
  void ensureBackend();
  await createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) void createWindow();
  });
});

app.on("window-all-closed", () => {
  // El backend NO se detiene: si es del servicio debe seguir, y si lo lanzamos
  // nosotros queda disponible para el resto de clientes. Se para desde la UI.
  if (process.platform !== "darwin") app.quit();
});

process.on("exit", () => {
  if (process.env.KOGNITERM_KILL_BACKEND_ON_EXIT === "1") stopSpawnedBackend();
});
