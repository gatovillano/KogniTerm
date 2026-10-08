import { contextBridge, ipcRenderer } from "electron";

export interface BackendStatus {
  up: boolean;
  url: string;
  owner: "service" | "spawned" | "external" | null;
  serviceInstalled: boolean;
  managed: boolean;
}

// El proceso main inyecta el backend resuelto con additionalArguments.
const apiArg = process.argv.find((a) => a.startsWith("--kogniterm-api="));

contextBridge.exposeInMainWorld("kogniterm", {
  version: "3.0.0",
  backend: "kogniterm/server/app.py (nativo)",
  /** URL del backend resuelta por el proceso main (sincrónica para el renderer). */
  apiBase: apiArg ? apiArg.slice("--kogniterm-api=".length) : "",
  backendStatus: (): Promise<BackendStatus> => ipcRenderer.invoke("backend:status"),
  startBackend: (): Promise<BackendStatus> => ipcRenderer.invoke("backend:start"),
  stopBackend: (): Promise<BackendStatus & { stopped: boolean }> => ipcRenderer.invoke("backend:stop"),
  /** Abre una URL en el navegador predeterminado (solo http/https/mailto). */
  openExternal: (url: string): Promise<void> => ipcRenderer.invoke("shell:open-external", url),
});
