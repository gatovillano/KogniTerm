# API Nativa KogniTerm (para Desktop)

Fuente de verdad: `kogniterm/server/app.py` (`create_app()`).

## Ciclo de vida del backend (Electron main: `apps/electron/src/main.ts`)

El backend es **multi-cliente** (lo comparten TUI, Web y Desktop). Dos vías:

1. **Servicio del sistema** — `install.sh` pregunta al usuario si lo registra:
   - Linux: unidad de usuario `~/.config/systemd/user/kogniterm-server.service`
     (`WantedBy=default.target`, `Restart=on-failure`) + `loginctl enable-linger`
     opcional para arrancar antes del login.
   - macOS: LaunchAgent `~/Library/LaunchAgents/com.kogniterm.server.plist`
     (`RunAtLoad` + `KeepAlive`).
   - Gestión posterior: `bash install.sh` → opción 5 (registrar / eliminar / estado).
2. **Fallback de la app** — al abrir Desktop, `ensureBackend()`:
   - Si `/health` responde → no hace nada (`owner: external`).
   - Si está apagado y el servicio existe → `systemctl --user start` (o `launchctl start`).
   - Si no hay servicio → lanza el proceso **desacoplado** (`detached` + `unref`), que
     sobrevive al cierre de la app para que quede disponible para el resto de clientes.
   - Prueba candidatos en orden y **descarta los que mueren al instante** (venv roto,
     binario ausente) en vez de esperar en balde:
     `~/.kogniterm/venv/bin/kogniterm-server` → `~/.local/bin/kogniterm-server` →
     `.venv/bin/kogniterm-server` (v3 y repo) → `kogniterm-server` del PATH →
     `python3 apps/backend/run.py`.
   - Nunca duplica instancia: por eso el conflicto de polling de Telegram entre dos
     servidores (dos desktops = dos servidores) no ocurre.

Variables de entorno: `KOGNITERM_HOST`, `KOGNITERM_PORT` (def. `8765`),
`KOGNITERM_NO_SIDECAR=1` (desactiva la gestión),
`KOGNITERM_KILL_BACKEND_ON_EXIT=1` (mata el proceso propio al salir, en vez de dejarlo).

IPC del renderer: `window.kogniterm.backendStatus()` / `startBackend()` / `stopBackend()`
(expuestos en `preload.ts`; solo disponibles en Electron, no en el navegador).

## Base URL

- TUI usa `http://127.0.0.1:8765` (`kogniterm/terminal/api_client_tui.py`).
- Desktop usa lo mismo por defecto. Override: `VITE_KOGNITERM_API`, `VITE_KOGNITERM_WS`.

## Auth

`require_token` (`app.py:290`): si `KOGNITERM_API_TOKEN` está definido se exige
`Authorization: Bearer <token>` en REST y `?token=` en WS. En local sin token, sin header.

## Endpoints REST nativos

| Método | Ruta | Uso Desktop |
|---|---|---|
| GET | `/health`, `/api/health` | health check |
| GET | `/models/available`, `/api/models/available` | lista `{providers:[{id,name,models:[]}]}` |
| GET | `/config/llm`, `/api/config/llm` | `{provider, model, api_key_masked, has_key}` |
| POST | `/config/llm`, `/api/config/llm` | body `{model?, provider?, api_key?}` — mismo que TUI `set_llm_config` |
| GET | `/sessions` | listar sesiones |
| POST | `/sessions` | crear `{session_id?, workspace_dir?}` |
| DELETE | `/sessions/{id}` | eliminar |
| POST | `/api/execute` | ejecutar comando (terminal futura) |
| GET | `/api/workspace/files` | explorador archivos (futuro) |
| POST | `/api/config/set_key` | alternativa set key |
| GET/POST/DELETE | `/api/mcp/servers...` | MCP (futuro) |

### POST /config/llm — semántica exacta (app.py:828)

- Si `model` → `set_project_config + set_global_config("default_model")`, `LITELLM_MODEL`.
- Elif `provider` → mapea a modelo por defecto:
  `google→google/gemini-1.5-flash`, `openai→openai/gpt-4o`,
  `anthropic→anthropic/claude-3-5-sonnet-20240620`,
  `openrouter→openrouter/google/gemini-2.5-flash`, `ollama→ollama/llama3`,
  `ollama_cloud→ollama_cloud/llama3:70b`, `kilocode→kilocode/kilo/auto`,
  `inception→inception/mercury-2`, `antigravity→antigravity/gemini-3-flash`.
- Si `api_key` → infiere provider del modelo si no viene, `cm.set_api_key(provider, key)`.
- Recarga `pool._llm_service` + todas las sesiones activas.

### GET /models/available — forma

```json
{ "providers": [{ "id": "google", "name": "Google", "models": ["google/gemini-1.5-flash", "..."] }] }
```

Desktop filtra por `provider` activo (igual que `_handle_models` en TUI).

- `GET /api/agents` → `{agents: [{id, name, description, engine}], default: "super_agent"}`.
  Motores conversacionales: `super_agent`, `bash_agent`, `code_agent`, `researcher_agent`.

## WebSocket `/ws/{session_id}` (app.py:2877)

Query: `?workspace_dir=&agent=&client_type=desktop&token=`.

Cliente → servidor:
```json
{"type": "message", "text": "...", "images": [], "agent": "code_agent"}
{"type": "interrupt"}
{"type": "ping"}
```

Servidor → cliente:
```json
{"type": "connected", "data": {"config": {"model": "...", "agent": "super_agent"}, "is_new": true, ...}}
{"type": "agent_changed", "data": {"agent": "code_agent"}}
{"type": "stream", "data": "chunk..."}
{"type": "tool_start", "data": {...}}
{"type": "tool_output", "data": {...}}
{"type": "message", "data": {...}}
{"type": "done", "data": {...}}
{"type": "error", "data": "..."}
{"type": "pong", "data": {}}
```

Desktop acumula `stream` en el mensaje assistant en curso y cierra con `done`.
`interrupt` equivale al botón Stop.

### Aprobaciones y preguntas (el worker se bloquea hasta responder)

Servidor → cliente:
```json
{"type": "approval_required", "data": {"id": "uuid", "title": "...", "message": "...", "diff_content": "...", "file_path": "..."}}
{"type": "question_required", "data": {"id": "uuid", "title": "...", "question": "...", "options": ["..."], "allow_freeform": true}}
```

Cliente → servidor (vía principal, igual que la TUI en `ws_client.send_approval`):
```json
{"type": "approval_response", "id": "uuid", "approved": true}
{"type": "question_response", "id": "uuid", "selected": "..."}
```

Fallback REST (si el WS falla):
- `POST /session/{id}/permission/{req}/reply` body `{"reply": "once"}` (aprueba) o `{"reply": "denied"}` (rechaza).
- `POST /session/{id}/question/{req}/reply` body `{"reply": "texto elegido"}`.

Desktop (`lib/session.ts` + `lib/approvals.ts` + `components/ApprovalDialog.tsx`):
responde por WS, muestra modal bloqueante con mensaje/diff/archivo y botones
Aceptar / Rechazar / Aceptar siempre (auto-aprobación en memoria por pestaña,
como `accept_all` de la TUI). Sin esto, el agente queda colgado esperando.

## Terminal lateral del usuario (shell PTY) — `lib/pty.ts`, `components/TerminalPanel.tsx`

Sidebar derecho con shell real por pestaña (xterm.js). Todo lo nativo del shell
funciona: passwords (`read -s`), flechas/historial, `Ctrl+C`, autocompletado,
resaltado de sintaxis, bracketed paste.

- `GET /api/pty/shells` — shells disponibles.
- `POST /api/pty` `{directory?, title?}` — crea PTY (opcional; el frontend no lo usa).
- `WS /api/pty/{id}/connect?client_type=desktop&directory=<workspace>` — texto crudo
  bidireccional. **El servidor auto-crea el PTY con el id de la URL si no existe**
  (`pty_manager.handle_websocket`), así que recargar la página reanuda el mismo shell.
- `POST /api/pty/{id}` `{size:{cols,rows}}` — resize (lo envía el `ResizeObserver`).
- `GET /api/pty/{id}` — estado. `DELETE /api/pty/{id}` — matar shell.
- Las rutas `/api/*` envuelven la respuesta en `{data: ...}`; `ptyReq` lo desenvuelve.
- Id estable por pestaña: `v3-term-{sessionId}`.
- El directorio se resuelve con `GET /api/workspace/status?session_id=...` → `{path}`
  y se pasa como `directory` al auto-crear.

## Terminal inline del agente — `components/AgentTerminal.tsx`

El shell lateral es otro PTY. Cuando el worker ejecuta un comando aprobado, v3 muestra la
salida con ANSI en una xterm dentro del chat y envía la entrada al worker:

- `terminal_output` `{content|output, tool, command, tool_call_id?}`: crea/actualiza la terminal del comando actual.
- `live_update` con `special_type: terminal`: actualiza el mismo snapshot acumulado.
- `set_terminal_cursor` `{active}`: marca la terminal como interactiva y le da foco al empezar.
- `done`, `live_stop` y `error`: cierran la terminal activa.
- Entrada: `{type: "terminal_input", "text": "..."}` por el WS de la sesión `/ws/{id}`.
  Incluye contraseñas, confirmaciones, flechas, `Ctrl+C`.

## MCP (`components/MCPPanel.tsx`, pestaña 5 · MCP en Ajustes)

- `GET /api/mcp/servers` → `{nombre: {transport, command?, args?, url?, disabled?, status, tools[], error?}}`.
- `POST /api/mcp/servers` body `{name, config, scope}` — stdio `{transport:"stdio", command, args[], env?}` o sse `{transport:"sse", url}`. Recarga el manager en servidor.
- `DELETE /api/mcp/servers/{name}?scope=` y `POST .../toggle?scope=` — scope `project` (.kogniterm/config.json) o `global` (~/.kogniterm).
- `POST /api/mcp/test-connection` body = config sin guardar (para "probar sin guardar").

## Referencias TUI (paridad)

- `kogniterm/terminal/tui/command_processor.py`: `_handle_models`, `_handle_provider`, `_handle_keys`, `_handle_theme`, `_handle_mcp`.
- `kogniterm/terminal/tui/components/settings_modals.py`: `TextualRadioListModal`, `TextualInputModal`.
- `kogniterm/terminal/config_manager.py`: `get_api_key/set_api_key`, `default_model`.
- `kogniterm/core/multi_provider_manager.py`: 9 providers + `set_preferred_provider`.
