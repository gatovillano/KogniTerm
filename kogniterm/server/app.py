"""
KogniTerm Backend API — FastAPI app principal.

Canales disponibles:
  - WebSocket   /ws/{session_id}          → streaming bidireccional (principal)
  - SSE         /sse/{session_id}          → Server-Sent Events (clientes solo-lectura)
  - REST        POST /chat/{session_id}    → request/response síncrono
  - REST        GET  /sessions             → listar sesiones activas
  - REST        POST /sessions             → crear sesión nueva
  - REST        DELETE /sessions/{id}      → eliminar sesión
  - REST        POST /sessions/{id}/interrupt → interrumpir agente
  - REST        GET  /health              → health check

El agente permanece "despierto" entre mensajes: el historial de conversación,
el estado del grafo LangGraph y el contexto de herramientas se mantienen en
memoria por sesión hasta que la sesión es eliminada explícitamente.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from kogniterm.core.llm_service import LLMService
from kogniterm.server.session_pool import pool
from kogniterm.server.config import server_config, ChannelConfig
from kogniterm.server.channel_adapters import WebhookAdapter, SlackAdapter, CLIAdapter, TelegramAdapter

logger = logging.getLogger("kogniterm.server.app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# ── Modelos Pydantic ───────────────────────────────────────────────────────────


class MessageRequest(BaseModel):
    message: str = Field(..., description="Mensaje para el agente")
    session_id: Optional[str] = Field(default=None, description="ID de sesión existente. Si es None, se crea una nueva.")


class SessionCreateRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="ID personalizado. Si es None, se genera automáticamente.")


class InterruptRequest(BaseModel):
    reason: Optional[str] = Field(default="Usuario solicitó interrupción.")


# ── Lifespan ───────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el LLMService y el SessionPool al arrancar el servidor."""
    logger.info("🚀 Iniciando KogniTerm Server...")
    loop = asyncio.get_event_loop()

    logger.info("⚙️  Cargando LLMService...")
    llm_service = LLMService()
    pool.initialize(llm_service=llm_service, loop=loop)

    # Inicializar canales externos configurados
    active_tasks = []
    for cfg in server_config.settings.channels:
        if cfg.enabled:
            logger.info(f"📡 Iniciando canal: {cfg.name} ({cfg.type})")
            
            if cfg.type in ("telegram", "telegram_bot"):
                token = cfg.params.get("token")
                if token:
                    adapter = TelegramAdapter(token=token, session_id=cfg.name)
                    task = asyncio.create_task(adapter.start())
                    active_tasks.append((adapter, task))
                else:
                    logger.warning(f"⚠️ Canal Telegram '{cfg.name}' habilitado pero falta 'token' en params.")

    logger.info("✅ KogniTerm Server listo.")
    yield

    logger.info("🛑 Cerrando KogniTerm Server...")
    # Detener canales activos
    for adapter, task in active_tasks:
        if hasattr(adapter, "stop"):
            await adapter.stop()
        task.cancel()
    
    pool._executor.shutdown(wait=False)


# ── Aplicación ─────────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    application = FastAPI(
        title="KogniTerm Backend API",
        description=(
            "API persistente multi-canal para KogniTerm. "
            "El agente permanece activo entre mensajes, manteniendo contexto y herramientas."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health Check ────────────────────────────────────────────────────────────

    @application.get("/health", tags=["Sistema"])
    async def health():
        """Estado del servidor y sesiones activas."""
        sessions = pool.list_all()
        return {
            "status": "online",
            "active_sessions": len(sessions),
            "sessions": sessions,
            "configured_channels": [c.name for c in server_config.settings.channels if c.enabled]
        }

    # ── Gestión de Configuración (Canales) ──────────────────────────────────────

    @application.get("/config/channels", tags=["Configuración"])
    async def list_configured_channels():
        """Lista todos los canales configurados (activos e inactivos)."""
        return {"channels": server_config.settings.channels}

    @application.post("/config/channels", tags=["Configuración"])
    async def add_or_update_channel(cfg: ChannelConfig):
        """Añade o actualiza la configuración de un canal."""
        server_config.add_channel(cfg)
        return {"status": "ok", "channel": cfg.name}

    @application.delete("/config/channels/{name}", tags=["Configuración"])
    async def remove_channel(name: str):
        """Elimina un canal de la configuración."""
        server_config.remove_channel(name)
        return {"status": "deleted", "channel": name}

    @application.patch("/config/channels/{name}/toggle", tags=["Configuración"])
    async def toggle_channel(name: str, enabled: bool):
        """Activa o desactiva un canal sin eliminarlo."""
        server_config.toggle_channel(name, enabled)
        return {"status": "updated", "channel": name, "enabled": enabled}

    # ── Gestión de sesiones ─────────────────────────────────────────────────────

    @application.get("/sessions", tags=["Sesiones"])
    async def list_sessions():
        """Lista todas las sesiones activas con su estado."""
        return {"sessions": pool.list_all()}

    @application.post("/sessions", tags=["Sesiones"], status_code=201)
    async def create_session(req: SessionCreateRequest = SessionCreateRequest()):
        """Crea una nueva sesión de agente y la mantiene en memoria."""
        sid = req.session_id or pool.new_session_id()
        session = pool.get_or_create(sid)
        return {"session_id": session.session_id, "created_at": session.created_at.isoformat()}

    @application.delete("/sessions/{session_id}", tags=["Sesiones"])
    async def delete_session(session_id: str):
        """Elimina una sesión y libera su memoria."""
        deleted = pool.delete(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Sesión '{session_id}' no encontrada.")
        return {"deleted": session_id}

    @application.post("/sessions/{session_id}/interrupt", tags=["Sesiones"])
    async def interrupt_session(session_id: str, req: InterruptRequest = InterruptRequest()):
        """Interrumpe el agente en ejecución para la sesión dada."""
        session = pool.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Sesión '{session_id}' no encontrada.")
        session.interrupt()
        return {"interrupted": session_id, "reason": req.reason}

    # ── Canal REST (síncrono, para integraciones simples) ──────────────────────

    @application.post("/chat/{session_id}", tags=["Chat"])
    async def chat_rest(session_id: str, req: MessageRequest):
        """
        Envía un mensaje y espera la respuesta completa (bloqueante).
        Útil para bots/CLI que no soportan streaming.
        """
        session = pool.get_or_create(session_id)
        if session.is_running:
            raise HTTPException(status_code=409, detail="El agente ya está procesando un mensaje en esta sesión.")

        # Cola temporal para recolectar todos los eventos de esta invocación
        collected: list = []
        done_event = asyncio.Event()

        async def collector():
            async for event in session.ui.events():
                collected.append(event)
                if event["type"] in ("done", "error"):
                    done_event.set()
                    break

        collect_task = asyncio.create_task(collector())
        await session.send(req.message, pool._executor)
        done_event.set()  # Asegurar que collector termine
        await asyncio.sleep(0.1)
        collect_task.cancel()

        # Extraer texto de respuesta del AI desde los eventos
        text_chunks = [e["data"] for e in collected if e["type"] == "stream"]
        full_text = "".join(text_chunks)

        return {
            "session_id": session_id,
            "response": full_text,
            "events": collected,
        }

    # ── Canal SSE (Server-Sent Events) para clientes solo-lectura ─────────────

    @application.get("/sse/{session_id}", tags=["Chat"])
    async def chat_sse(session_id: str, message: str):
        """
        Envía un mensaje y recibe la respuesta como Server-Sent Events.
        Ideal para integraciones web unidireccionales.
        
        Parámetro: ?message=<texto>
        """
        session = pool.get_or_create(session_id)

        async def event_generator() -> AsyncIterator[str]:
            send_task = asyncio.create_task(session.send(message, pool._executor))

            async for event in session.ui.events():
                # Formato SSE: "data: <json>\n\n"
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event["type"] in ("done", "error"):
                    break

            await asyncio.sleep(0)  # Ceder el loop
            send_task.cancel()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Canal WebSocket (bidireccional, streaming completo) ───────────────────

    @application.websocket("/ws/{session_id}")
    async def websocket_chat(websocket: WebSocket, session_id: str):
        """
        Canal WebSocket bidireccional.

        Protocolo de mensajes cliente → servidor (JSON):
          {"type": "message",    "text": "..."}    → enviar mensaje al agente
          {"type": "interrupt"}                    → interrumpir ejecución actual
          {"type": "ping"}                         → keep-alive

        Protocolo servidor → cliente (JSON):
          {"type": "stream",       "data": "...", "ts": "..."}  → chunk de texto
          {"type": "tool_start",   "data": {...}, "ts": "..."}  → inicio de herramienta
          {"type": "tool_output",  "data": {...}, "ts": "..."}  → salida de herramienta
          {"type": "live_update",  "data": "...", "ts": "..."}  → actualización visual
          {"type": "task_tracker", "data": {...}, "ts": "..."}  → progreso de tareas
          {"type": "message",      "data": {...}, "ts": "..."}  → mensaje del agente
          {"type": "done",         "data": {...}, "ts": "..."}  → fin de ciclo
          {"type": "error",        "data": {...}, "ts": "..."}  → error
          {"type": "pong",         "data": {},    "ts": "..."}  → respuesta keep-alive
        """
        await websocket.accept()
        session = pool.get_or_create(session_id)
        logger.info(f"[WS] Cliente conectado a sesión {session_id}")

        # Enviar estado inicial
        await websocket.send_json({
            "type": "connected",
            "data": session.to_dict(),
        })

        # Tarea A: relay de eventos del agente → cliente WS
        async def relay_events():
            try:
                async for event in session.ui.events():
                    await websocket.send_json(event)
            except Exception as exc:
                logger.warning(f"[WS:{session_id}] relay_events terminado: {exc}")

        relay_task = asyncio.create_task(relay_events())

        # Tarea B: recibir mensajes del cliente
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "data": "JSON inválido."})
                    continue

                msg_type = data.get("type", "message")

                if msg_type == "message":
                    text = data.get("text", "").strip()
                    if not text:
                        continue
                    if session.is_running:
                        await websocket.send_json({
                            "type": "error",
                            "data": "El agente ya está procesando. Usa 'interrupt' primero."
                        })
                        continue
                    # Ejecutar el agente en background sin bloquear el loop WS
                    asyncio.create_task(session.send(text, pool._executor))

                elif msg_type == "interrupt":
                    session.interrupt()
                    await websocket.send_json({"type": "info", "data": "Interrupción enviada."})

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong", "data": {}})

                else:
                    await websocket.send_json({"type": "error", "data": f"Tipo de mensaje desconocido: {msg_type}"})

        except WebSocketDisconnect:
            logger.info(f"[WS] Cliente desconectado de sesión {session_id}")
        except Exception as exc:
            logger.error(f"[WS:{session_id}] Error inesperado: {exc}")
        finally:
            relay_task.cancel()
            try:
                await relay_task
            except asyncio.CancelledError:
                pass

    return application


app = create_app()


# ── Entry point ────────────────────────────────────────────────────────────────

def run_server(host: str = "0.0.0.0", port: int = 8765, reload: bool = False):
    """Lanza el servidor KogniTerm."""
    uvicorn.run(
        "kogniterm.server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
