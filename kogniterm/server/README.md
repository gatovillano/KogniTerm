# KogniTerm Server — API Backend Persistente Multi-Canal

Convierte el motor de KogniTerm en un **servicio backend siempre activo**,
manteniendo el agente "despierto" entre mensajes y disponible desde múltiples
canales simultáneos.

---

## Arquitectura

```
┌─────────────────────────────────────────────────┐
│              KogniTerm Server (FastAPI)          │
│                                                  │
│  ┌───────────┐  ┌─────────┐  ┌───────────────┐  │
│  │ WebSocket │  │   SSE   │  │  REST /chat   │  │
│  └─────┬─────┘  └────┬────┘  └──────┬────────┘  │
│        │             │              │            │
│        └─────────────┴──────────────┘            │
│                       │                          │
│              ┌────────▼────────┐                 │
│              │   SessionPool   │  (memoria)      │
│              └────────┬────────┘                 │
│                       │ get_or_create(session_id) │
│              ┌────────▼────────┐                 │
│              │  AgentSession   │  ×N sesiones    │
│              │  ┌───────────┐  │                 │
│              │  │ ServerUI  │  │  sin pantalla   │
│              │  │ (adapter) │  │                 │
│              │  └─────┬─────┘  │                 │
│              │        │events  │                 │
│              │  ┌─────▼─────┐  │                 │
│              │  │AgentInter │  │                 │
│              │  │action     │  │  LangGraph      │
│              │  │Manager    │  │                 │
│              │  └───────────┘  │                 │
│              └─────────────────┘                 │
└─────────────────────────────────────────────────┘
```

---

## Inicio rápido

```bash
# Desde el directorio del proyecto, con el venv activo:
python -m kogniterm.server

# Opciones:
python -m kogniterm.server --host 0.0.0.0 --port 8765
python -m kogniterm.server --reload   # hot-reload para desarrollo

# O si está instalado como paquete:
kogniterm-server --port 8765
```

El servidor arranca en: `http://0.0.0.0:8765`  
Documentación interactiva: `http://localhost:8765/docs`

---

## Canales disponibles

### 🔌 WebSocket (recomendado — streaming bidireccional)

```
ws://localhost:8765/ws/<session_id>
```

**Protocolo cliente → servidor:**
```json
{"type": "message",   "text": "..."}   // enviar mensaje
{"type": "interrupt"}                  // interrumpir agente
{"type": "ping"}                       // keep-alive
```

**Protocolo servidor → cliente:**
```json
{"type": "stream",       "data": "chunk de texto...", "ts": "..."}
{"type": "tool_start",   "data": {"tool": "bash", "description": "..."}, "ts": "..."}
{"type": "tool_output",  "data": {"tool": "bash", "output": "..."}, "ts": "..."}
{"type": "task_tracker", "data": {...planes...}, "ts": "..."}
{"type": "done",         "data": {"session_id": "..."}, "ts": "..."}
{"type": "error",        "data": {"message": "..."}, "ts": "..."}
```

**Ejemplo (Python):**
```python
import asyncio, websockets, json

async def chat():
    async with websockets.connect("ws://localhost:8765/ws/mi-sesion") as ws:
        await ws.recv()  # mensaje "connected"
        await ws.send(json.dumps({"type": "message", "text": "Hola!"}))
        async for msg in ws:
            event = json.loads(msg)
            if event["type"] == "stream":
                print(event["data"], end="", flush=True)
            if event["type"] == "done":
                break

asyncio.run(chat())
```

---

### 📡 SSE — Server-Sent Events (streaming unidireccional)

```
GET http://localhost:8765/sse/<session_id>?message=<texto>
```

Ideal para integraciones web donde el cliente solo lee.

**Ejemplo (curl):**
```bash
curl -N "http://localhost:8765/sse/mi-sesion?message=hola"
```

---

### 📨 REST (síncrono, para integraciones simples)

```
POST http://localhost:8765/chat/<session_id>
Content-Type: application/json

{"message": "¿Cuál es el directorio actual?"}
```

Responde cuando el agente termina completamente.

---

## Gestión de sesiones

```bash
# Listar sesiones activas
GET /sessions

# Crear sesión con ID personalizado
POST /sessions
{"session_id": "slack-user-123"}

# Eliminar sesión
DELETE /sessions/<session_id>

# Interrumpir agente en ejecución
POST /sessions/<session_id>/interrupt

# Estado del servidor
GET /health
```

---

## Adaptadores de canal (`channel_adapters.py`)

Para integrar con servicios externos, usa los adaptadores predefinidos:

```python
from kogniterm.server.channel_adapters import CLIAdapter, WebhookAdapter, SlackAdapter

# CLI interactiva (para pruebas)
adapter = CLIAdapter(session_id="dev")
await adapter.interactive_loop()

# Webhook genérico (Slack incoming webhooks, n8n, Zapier...)
adapter = WebhookAdapter(
    webhook_url="https://hooks.slack.com/services/...",
    session_id="slack-bot",
    filter_types=["stream", "done", "error"]
)
await adapter.send_message("Analiza los logs del sistema")

# Slack Bolt
from slack_bolt.async_app import AsyncApp
slack_app = AsyncApp(token="xoxb-...")
adapter = SlackAdapter(slack_app=slack_app, channel="#ops", session_id="slack-ops")
await adapter.send_message("¿Hay algún proceso que consuma mucha CPU?")
```

---

## Cliente de prueba

```bash
# WebSocket (default)
python -m kogniterm.server.test_client --mode ws --message "lista los archivos"

# SSE
python -m kogniterm.server.test_client --mode sse --message "¿cuánta RAM libre hay?"

# REST
python -m kogniterm.server.test_client --mode rest --message "hola"

# Health check
python -m kogniterm.server.test_client --mode health
```

---

## Crear un adaptador personalizado

```python
from kogniterm.server.channel_adapters import ChannelAdapter

class TelegramAdapter(ChannelAdapter):
    def __init__(self, bot, chat_id, session_id=None):
        super().__init__(session_id)
        self.bot = bot
        self.chat_id = chat_id
        self._buffer = []

    async def send_to_channel(self, event: dict) -> None:
        if event["type"] == "stream":
            self._buffer.append(event["data"])
        elif event["type"] == "done":
            text = "".join(self._buffer).strip()
            self._buffer.clear()
            if text:
                await self.bot.send_message(self.chat_id, text)
```

---

## Estructura de archivos

```
kogniterm/server/
├── __init__.py           # Exporta app y create_app
├── __main__.py           # Entry point: python -m kogniterm.server
├── app.py                # FastAPI app + endpoints + lifespan
├── session_pool.py       # Pool global de sesiones + ServerUI adapter
├── channel_adapters.py   # Adaptadores: CLI, Webhook, Slack, ...
├── test_client.py        # Cliente de prueba multi-canal
└── README.md             # Esta documentación
```
