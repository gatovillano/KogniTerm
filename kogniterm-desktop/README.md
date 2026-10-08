# KogniTerm Desktop — App nativa

App de escritorio oficial de KogniTerm: **Electron + SolidJS + Tailwind + Vite**
contra el backend 100% `kogniterm/server/app.py` (sin dependencias `@opencode-ai/*`).

Se lanza con:

```bash
kogniterm desktop            # producción (compila si falta el build)
kogniterm desktop --dev      # desarrollo (Vite + Electron Dev)
kogniterm desktop --build    # fuerza la recompilación antes de iniciar
kogniterm desktop --logs     # muestra los logs en la terminal actual
```

## Estructura

```
kogniterm-desktop/
├── apps/
│   ├── backend/        # shim que reutiliza kogniterm.server.app:create_app
│   │   ├── run.py
│   │   └── requirements.txt
│   ├── web/            # SolidJS + Tailwind + Vite (Tabs + Chat + Provider/Model/Keys)
│   └── electron/       # shell Electron (main/preload), carga apps/web
├── docs/
│   └── API_NATIVA.md
└── scripts/
    ├── dev-backend.sh
    └── dev.sh
```

## Backend nativo (reusado, no duplicado)

- `GET /health`, `GET /models/available`, `GET /config/llm`, `POST /config/llm`
- `GET /sessions`, `POST /sessions`, `DELETE /sessions/{id}`
- `WS /ws/{session_id}` — protocolo: cliente `{type:message|interrupt|ping}`,
  servidor `{type:connected|stream|tool_start|tool_output|message|done|error|pong}`
- Ver `docs/API_NATIVA.md` y `kogniterm/server/app.py`.

```bash
# backend (puerto 8755 por defecto)
bash scripts/dev-backend.sh
# o:
python3 apps/backend/run.py --port 8755
```

## Web

```bash
npm install
npm run dev:web   # http://localhost:4444 → backend http://127.0.0.1:8755
```

Variables: `VITE_KOGNITERM_API=http://127.0.0.1:8755`, `VITE_KOGNITERM_WS=ws://127.0.0.1:8755`.

## Electron

```bash
npm run dev:electron
```

Carga la URL de Vite en dev y `apps/web/dist` en prod.

## Funcionalidades

- [x] Tabs (sesiones múltiples, crear/cerrar/renombrar, persistencia localStorage)
- [x] Chat streaming nativo por WS (`stream`, `message`, `done`, `tool_start/output`)
- [x] Selector de agentes nativo en el input (`GET /api/agents`, `super_agent`, `bash_agent`, `code_agent`, `researcher_agent`)
- [x] Modal Proveedor (9 proveedores TUI: google, openai, anthropic, openrouter, ollama, ollama_cloud, kilocode, inception, antigravity)
- [x] Modal Modelo (lista desde `GET /models/available` filtrada por proveedor activo)
- [x] Modal Keys (`POST /config/llm` con `provider` + `api_key`, password input)
- [x] Terminal lateral con shell real por pestaña (`POST /api/pty`, WS `/api/pty/{id}/connect`)
- [x] Terminal inline interactiva para comandos del agente (`terminal_output`, `set_terminal_cursor`, `terminal_input`)
- [ ] Siguiente: theme, files (parity TUI completa)
