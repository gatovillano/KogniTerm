# KogniTerm — Arquitectura Cliente-Servidor

> **Versión**: Post-refactorización 2026-05  
> **Estado**: Producción  

---

## 1. Visión General

KogniTerm migró de una arquitectura **monolítica acoplada** (un proceso único que combinaba LLM, UI y lógica de herramientas) a una arquitectura **cliente-servidor desacoplada** con un backend persistente que expone múltiples canales de comunicación simultáneos.

```
┌─────────────────────────────────────────────────────────┐
│                   ANTES (monolítico)                    │
│                                                         │
│  kogniterm (proceso único)                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  KogniTermApp (prompt_toolkit)                   │  │
│  │  ├── LLMService       (modelo + embeddings)      │  │
│  │  ├── AgentState       (historial)                │  │
│  │  ├── TerminalUI       (rich + prompt_toolkit)    │  │
│  │  ├── FileCompleter    (autocompletado)           │  │
│  │  └── MetaCommandProcessor (comandos /slash)      │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   AHORA (cliente-servidor)               │
│                                                         │
│   SERVER (puerto 8765)          CLIENTES                │
│  ┌───────────────────┐         ┌──────────────────┐    │
│  │ FastAPI + uvicorn │◄───WS───│ KogniTermTUI     │    │
│  │ SessionPool       │◄───WS───│ (Textual)        │    │
│  │ LLMService        │◄──REST──│                  │    │
│  │ ServerUI adapter  │         └──────────────────┘    │
│  │                   │         ┌──────────────────┐    │
│  │ Canales activos:  │◄──Bot───│ Telegram Bot     │    │
│  │  - WebSocket      │◄──Hook──│ Webhook          │    │
│  │  - SSE            │◄──CLI───│ CLIAdapter       │    │
│  │  - REST           │         └──────────────────┘    │
│  └───────────────────┘                                  │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Estructura de Carpetas

```
kogniterm/
├── core/                        # Lógica de negocio (compartida)
│   ├── agents/                  # Agentes LangGraph
│   │   ├── bash_agent.py        # Grafo principal del agente
│   │   ├── code_agent.py
│   │   ├── deep_coder.py
│   │   └── researcher_agent.py
│   ├── context/                 # Indexación y búsqueda semántica
│   │   ├── codebase_indexer.py
│   │   └── vector_db_manager.py
│   ├── skills/                  # SkillManager y carga dinámica
│   ├── agent_state.py           # Estado compartido del agente
│   ├── llm_service.py           # Inicialización del LLM + embeddings
│   ├── session_manager.py       # Persistencia de sesiones en disco
│   └── command_executor.py      # Ejecución de comandos shell
│
├── server/                      # 🆕 Backend persistente (FastAPI)
│   ├── app.py                   # Aplicación FastAPI + endpoints
│   ├── session_pool.py          # Pool de sesiones (ServerUI + AgentSession)
│   ├── config.py                # Configuración dinámica de canales
│   ├── channel_adapters.py      # Telegram, Webhook, Slack, CLI adapters
│   ├── __main__.py              # Punto de entrada: `python -m kogniterm.server`
│   └── README.md                # Documentación del servidor
│
├── terminal/                    # CLI + TUI cliente
│   ├── terminal.py              # Punto de entrada principal (`kogniterm`)
│   ├── cli.py                   # Comandos CLI (config, models, keys, skills)
│   ├── file_completer.py        # 🆕 Autocompletado de archivos/comandos/Docker
│   ├── api_client.py            # Cliente REST síncrono (usado por CLI)
│   ├── api_client_tui.py        # Cliente REST/async (usado por TUI)
│   │
│   ├── tui/                     # 🆕 TUI Textual (cliente del servidor)
│   │   ├── tui_app.py           # KogniTermTUI — App Textual principal
│   │   ├── command_processor.py # Procesa comandos /slash en la TUI
│   │   └── components/          # Widgets Textual
│   │       ├── chat_log.py
│   │       ├── tool_output.py
│   │       ├── command_approval_modal.py
│   │       ├── inline_approval.py
│   │       ├── pty_terminal.py
│   │       ├── settings_modals.py
│   │       ├── status_footer.py
│   │       ├── task_tracker_panel.py
│   │       └── agent_stream.py
│   │
│   ├── agent_interaction_manager.py  # Orquestación del ciclo agente↔UI
│   ├── command_approval_handler.py   # Aprobación de herramientas (sync/async)
│   ├── meta_command_processor.py     # Comandos /slash (reset, session, theme…)
│   ├── terminal_ui.py               # Clase base TerminalUI (Rich + prompt_toolkit)
│   ├── visual_components.py         # Renderizables Rich (paneles, banners)
│   ├── themes.py                    # Sistema de temas de color
│   ├── config_manager.py            # Lectura/escritura de configuración local
│   ├── security.py                  # Scrubbing de secretos en output
│   ├── keyboard_handler.py          # Captura de teclas especiales
│   ├── message_history.py           # Historial de mensajes en disco
│   └── telegram_chatid_helper.py    # Detección de chat_id para Telegram
│
├── skills/                      # Skills del agente (bundled + external)
│   ├── bundled/                 # Skills incluidas con KogniTerm
│   └── external/                # Skills instaladas por el usuario
│
└── utils/                       # Utilidades generales
    └── logger.py
```

---

## 3. Componentes Clave del Servidor

### 3.1 `SessionPool` y `AgentSession`

El corazón del backend. Mantiene agentes **siempre activos** entre mensajes.

```
SessionPool (singleton)
├── _sessions: Dict[session_id → AgentSession]
├── _llm_service: LLMService       # Un único LLM compartido
├── _executor: ThreadPoolExecutor  # 20 workers para agentes paralelos
└── get_or_create(session_id)      # Thread-safe

AgentSession
├── session_id: str
├── agent_state: AgentState        # Historial de mensajes
├── ui: ServerUI                   # Adaptador sin pantalla
├── manager: AgentInteractionManager
├── interrupt_queue: queue.Queue
└── send(message, executor)        # Ejecuta el agente en hilo worker
```

### 3.2 `ServerUI` — Adaptador sin pantalla

`ServerUI` extiende `TerminalUI` y **captura** todos los eventos del agente (streams, herramientas, aprobaciones) convirtiéndolos en eventos JSON que se envían a los consumidores via `asyncio.Queue`.

```python
# Arquitectura de eventos
ServerUI._push(event_type, data)
    └→ asyncio.Queue (por sesión)
        ├→ WebSocket relay_task  (TUI / desktop)
        ├→ SSE generator         (clientes web)
        └→ TelegramAdapter.send_message()
```

### 3.3 Protocolo WebSocket

El canal principal entre la TUI y el servidor.

**Cliente → Servidor:**
```json
{ "type": "message",           "text": "..." }
{ "type": "interrupt" }
{ "type": "approval_response", "id": "...", "approved": true }
{ "type": "start_indexing" }
{ "type": "ping" }
```

**Servidor → Cliente:**
```json
{ "type": "connected",    "data": { "session_id": "...", "persistent": true } }
{ "type": "chunk",        "data": { "content": "..." },    "ts": "..." }
{ "type": "stream",       "data": "...",                   "ts": "..." }
{ "type": "tool_call",    "data": { "name": "...", ... },  "ts": "..." }
{ "type": "tool_result",  "data": { "content": "...", ... } }
{ "type": "approval_required", "data": { "id": "...", "message": "..." } }
{ "type": "task_tracker", "data": { ... } }
{ "type": "done",         "data": { "session_id": "..." } }
{ "type": "error",        "data": "..." }
{ "type": "pong",         "data": {} }
```

---

## 4. Canales Disponibles

| Canal | Endpoint | Protocolo | Caso de uso |
|---|---|---|---|
| **WebSocket** | `/ws/{session_id}` | WS bidireccional | TUI, desktop apps |
| **SSE** | `/sse/{session_id}?message=...` | HTTP streaming | Clientes web uni-dir |
| **REST** | `POST /chat/{session_id}` | HTTP sync | Bots, integr. simples |
| **Telegram** | — | Bot API polling | Canal conversacional |
| **Webhook** | configurable | HTTP POST | Integraciones externas |
| **CLI** | `CLIAdapter` | interno | Línea de comandos |

---

## 5. Gestión de Canales

Los canales se configuran en `.kogniterm/server_config.json` y se gestionan via:

```bash
# Wizard interactivo (recomendado)
kogniterm config telegram

# Subcomandos rápidos
kogniterm config telegram status
kogniterm config telegram enable
kogniterm config telegram disable

# API REST del servidor
GET  /config/channels
POST /config/channels       # { name, type, enabled, params }
DELETE /config/channels/{name}
PATCH /config/channels/{name}/toggle?enabled=true
```

**Formato de `server_config.json`:**
```json
{
  "channels": [
    {
      "name": "mi_bot",
      "type": "telegram_bot",
      "enabled": true,
      "params": {
        "token": "...",
        "chat_id": 123456789
      }
    }
  ]
}
```

---

## 6. Flujo de un Mensaje

```
Usuario (TUI)
  │
  │  WS: { "type": "message", "text": "resume este archivo" }
  ▼
KogniTermTUI.on_ws_message()
  │
  │  asyncio.create_task(session.send(text, executor))
  ▼
AgentSession.send()
  ├── Meta-comandos (/reset, /undo, /resume) → respondidos directo
  └── Flujo normal:
        ui._push("user_message", ...)
        loop.run_in_executor(executor, manager.invoke_agent, message)
          │
          ▼
        AgentInteractionManager.invoke_agent()
          │  (hilo worker, no bloquea el loop asyncio)
          ▼
        bash_agent_app.invoke(agent_state)
          ├── LLM genera respuesta → ServerUI.print_stream() → _push("chunk", ...)
          ├── LLM llama herramienta → ServerUI.print_tool_notification() → _push("tool_call", ...)
          ├── Herramienta ejecuta → ServerUI.update_terminal_output() → _push("tool_result", ...)
          └── Herramienta necesita aprobación → ServerUI.ask_approval_sync() → bloquea hilo worker
                │
                │  _push("approval_required", { "id": "...", "message": "..." })
                │  threading.Event.wait()
                │
                │  (TUI envía WS: { "type": "approval_response", "id": "...", "approved": true })
                │  ServerUI.handle_approval_response() → threading.Event.set()
                │
                └── Continúa ejecución
          │
          ui._push("done", { "session_id": ... })
          session_manager.save_session(...)
  │
  │  relay_task envía todos los eventos via WS al cliente
  ▼
KogniTermTUI (renderiza en tiempo real)
```

---

## 7. Endpoints REST Completos

### Sesiones
| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/sessions` | Listar sesiones activas |
| `POST` | `/sessions` | Crear nueva sesión |
| `DELETE` | `/sessions/{id}` | Eliminar sesión |
| `POST` | `/api/sessions/{id}/close` | Notificar cierre (guarda estado) |
| `POST` | `/sessions/{id}/interrupt` | Interrumpir agente |

### Chat
| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/chat/{session_id}` | Chat REST síncrono |
| `GET` | `/sse/{session_id}` | Chat vía SSE |
| `WS` | `/ws/{session_id}` | Chat WebSocket |
| `WS` | `/ws/chat` | Alias para `tui-default` |
| `POST` | `/api/chat/message` | Endpoint compat. desktop |

### Configuración
| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/config/channels` | Listar canales |
| `POST` | `/config/channels` | Añadir/actualizar canal |
| `DELETE` | `/config/channels/{name}` | Eliminar canal |
| `PATCH` | `/config/channels/{name}/toggle` | Activar/desactivar |
| `GET` | `/config/llm` | Ver config LLM actual |
| `POST` | `/config/llm` | Cambiar modelo/provider/key |
| `GET` | `/models/available` | Listar modelos disponibles |

### Sistema / Desktop
| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del servidor |
| `GET` | `/api/workspace/status` | Estado de indexación |
| `POST` | `/api/workspace/index` | Trigger indexación |
| `POST` | `/api/execute` | Ejecutar comando shell |
| `POST` | `/api/files/list` | Listar directorio |

---

## 8. Iniciar el Sistema

```bash
# 1. Iniciar el servidor backend (siempre primero)
kogniterm-server
# o equivalente:
python -m kogniterm.server

# 2. Iniciar la TUI (se conecta automáticamente al servidor)
kogniterm

# 3. Configurar Telegram (opcional)
kogniterm config telegram
```

> **Nota**: La TUI espera el servidor en `http://127.0.0.1:8765`. Si el servidor
> no está disponible al iniciar, la TUI muestra un splash screen y reintenta la
> conexión periódicamente.

---

## 9. Archivos Eliminados / Migrados en la Refactorización

| Archivo | Estado | Reemplazado por |
|---|---|---|
| `terminal/kogniterm_app.py` | ❌ **Eliminado** | `terminal/tui/tui_app.py` (Textual) + `terminal/file_completer.py` |
| `terminal/api_client.py` (port 8000) | ✅ **Corregido** | Puerto actualizado a `8765` |
| `server/session_pool.py` (bloque /undo duplicado) | ✅ **Corregido** | Dead code eliminado |
| `terminal/terminal.py` (import KogniTermApp) | ✅ **Corregido** | Import muerto eliminado |
| `terminal/cli.py` (CLIHandler sin config_manager) | ✅ **Corregido** | `ConfigManager` instanciado en `__init__` |

---

## 10. Decisiones de Diseño

### ¿Por qué `TerminalUI` sigue siendo la clase base?
`ServerUI` extiende `TerminalUI` para reutilizar la interfaz que todos los agentes del core ya conocen (`print_stream`, `print_message`, `ask_approval_sync`, etc.). Cambiar la firma de los agentes sería una refactorización mayor innecesaria — el adaptador de servidor simplemente sobreescribe cada método para enrutar los eventos a la `asyncio.Queue`.

### ¿Por qué `ThreadPoolExecutor` y no `asyncio` puro para el agente?
LangGraph y gran parte del stack de herramientas (subprocess, ChromaDB, llamadas síncronas a LLM) son síncronos. Ejecutar el agente en un hilo worker via `loop.run_in_executor()` evita bloquear el event loop de FastAPI, permitiendo atender múltiples sesiones simultáneamente.

### ¿Por qué la sesión TUI se llama `tui-default`?
Por convención: la TUI siempre usa el mismo `session_id` fijo (`tui-default`), lo que permite reconectar después de un reinicio de la TUI y recuperar el historial de conversación completo del servidor sin configuración adicional.

---

## 11. Tareas Pendientes

### 🔴 Alta prioridad — Inversión de dependencias

`server/` y `core/` importan de `terminal/`, invirtiendo el flujo correcto de capas:

```
# Debería ser:   core/ ← server/ ← terminal/
# Actualmente:
server/session_pool.py → kogniterm.terminal.terminal_ui
server/session_pool.py → kogniterm.terminal.agent_interaction_manager
core/agents/*.py       → kogniterm.terminal.visual_components
core/agents/*.py       → kogniterm.terminal.terminal_ui
```

**Solución**: Crear `kogniterm/ui/` con los módulos compartidos (`terminal_ui`, `visual_components`, `themes`, `security`, `agent_interaction_manager`) para que `server/` y `core/` importen de `ui/` en lugar de `terminal/`. Terminal pasaría a ser un cliente puro (solo HTTP, sin imports Python del servidor).

**Impacto estimado**: ~15 archivos con cambios de import. No rompe funcionalidad.  
**Bloquea**: empaquetar `kogniterm-server` como distribución independiente de la TUI.

---

### 🟡 Media prioridad

- **Duplicación `api_client.py` / `api_client_tui.py`**: mismas llamadas, uno síncrono (`requests`) y otro async (`httpx`). Unificar en un único cliente con variantes sync/async.
- **Sesiones no sincronizadas**: `MetaCommandProcessor` guarda sesiones localmente; el servidor tiene su propio pool en memoria. Los comandos `/session` de la TUI deberían pasar por el endpoint REST del servidor.
- **Endpoint `/sessions/{id}/interrupt` no implementado**: declarado en el docstring de `app.py` pero sin handler. La interrupción solo funciona via WebSocket (`{ "type": "interrupt" }`).
