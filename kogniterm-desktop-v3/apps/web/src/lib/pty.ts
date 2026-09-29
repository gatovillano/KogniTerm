/* Cliente PTY nativo — shell interactivo real (bash/zsh) por pestaña.
 *  REST: POST /api/pty (crear), GET /api/pty/{id}, POST /api/pty/{id} {size}, DELETE.
 *  WS:   /api/pty/{id}/connect — texto crudo en ambos sentidos (xterm-ready).
 *  El servidor auto-crea el PTY con el id de la URL si no existe (reattach tras reload).
 */
import { apiRoot, token } from "./api";

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const t = token();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

async function ptyReq<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiRoot()}${path}`, { ...init, headers: headers() });
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} → ${res.status}`);
  const body = await res.json();
  // las rutas /api/* envuelven en {data: ...}
  return (body && typeof body === "object" && "data" in body ? body.data : body) as T;
}

export interface PTYInfo {
  id: string;
  title?: string;
  status?: string;
  wsPath?: string;
}

/** Id estable por pestaña: reconectar reengancha el mismo shell. */
export function ptyIdForTab(tabId: string): string {
  return `v3-term-${tabId}`.slice(0, 64);
}

export function ptyWsUrl(ptyId: string, directory?: string): string {
  const root0 = apiRoot();
  let root: string;
  if (root0.startsWith("http")) {
    root = root0.replace(/^http/, "ws");
  } else {
    root = (import.meta as any).env?.DEV ? "ws://127.0.0.1:8765" : `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}`;
  }
  const dir = directory ? `&directory=${encodeURIComponent(directory)}` : "";
  return `${root}/api/pty/${encodeURIComponent(ptyId)}/connect?client_type=desktop${dir}`;
}

export const ptyApi = {
  create: (directory?: string, title?: string) =>
    ptyReq<PTYInfo>("/api/pty", {
      method: "POST",
      body: JSON.stringify({ directory, title }),
    }),
  get: (ptyId: string) => ptyReq<PTYInfo | { id: string; status: string }>(`/api/pty/${encodeURIComponent(ptyId)}`),
  resize: (ptyId: string, cols: number, rows: number) =>
    ptyReq(`/api/pty/${encodeURIComponent(ptyId)}`, {
      method: "POST",
      body: JSON.stringify({ size: { cols, rows } }),
    }).catch(() => {}),
  kill: (ptyId: string) =>
    ptyReq(`/api/pty/${encodeURIComponent(ptyId)}`, { method: "DELETE" }).catch(() => {}),
  shells: () => ptyReq<Array<{ path: string; name: string }>>("/api/pty/shells").catch(() => []),
};
