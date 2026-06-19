"""
ws_client.py — Cliente WebSocket para KogniTermTUI

Implementa la conexión persistente al servidor KogniTerm (FastAPI) y enruta
los eventos JSON recibidos a los widgets correspondientes de la TUI Textual.

Estrategia híbrida:
    - Si el servidor está disponible en server_url, toda la lógica de agente
      se delega al backend (modo server).
    - Si la conexión falla o el servidor no está corriendo, la TUI opera en
      modo local (monolítico), sin cambios en el comportamiento existente.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Optional

logger = logging.getLogger("kogniterm.tui.ws_client")

if TYPE_CHECKING:
    from kogniterm.terminal.tui.tui_app import KogniTermTUI

# Tiempo de espera máximo para el probe de disponibilidad del servidor (segundos)
_SERVER_PROBE_TIMEOUT = 2.0
# Intervalo de reintento de reconexión (segundos)
_RECONNECT_DELAY = 5.0


async def probe_server(server_url: str) -> bool:
    """
    Comprueba si el servidor KogniTerm está disponible haciendo un GET /health.
    Retorna True si responde correctamente dentro del timeout.
    """
    try:
        import httpx
        health_url = server_url.replace("ws://", "http://").replace("wss://", "https://")
        # Extraer base URL hasta /ws si la URL incluye esa ruta
        if "/ws" in health_url:
            health_url = health_url.split("/ws")[0]
        health_url = health_url.rstrip("/") + "/health"
        async with httpx.AsyncClient(timeout=_SERVER_PROBE_TIMEOUT) as client:
            resp = await client.get(health_url)
            return resp.status_code == 200
    except Exception as exc:
        logger.debug(f"Probe al servidor falló: {exc}")
        return False


class TUIWebSocketClient:
    """
    Gestiona el ciclo de vida del cliente WebSocket desde la TUI.

    Uso:
        client = TUIWebSocketClient(app, server_url, session_id)
        asyncio.create_task(client.run())           # Conectar y escuchar
        await client.send_message("Hola agente")   # Enviar mensaje
        await client.send_interrupt()              # Interrumpir agente
        await client.send_approval(id, approved)   # Responder aprobación
    """

    def __init__(self, app: "KogniTermTUI", server_url: str, session_id: str):
        self._app = app
        self._server_url = server_url  # e.g. "ws://127.0.0.1:8765"
        self._session_id = session_id
        self._ws = None
        self._connected = False
        self._stopped = False
        self._send_queue: asyncio.Queue = asyncio.Queue()

    # ── Propiedades públicas ────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Punto de entrada del bucle de conexión ──────────────────────────────────

    async def run(self) -> None:
        """
        Bucle principal: conecta al WebSocket y reconecta automáticamente
        si la conexión se pierde. Se detiene cuando self._stopped es True.
        """
        while not self._stopped:
            try:
                await self._connect_and_run()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if self._stopped:
                    break
                logger.warning(f"[WS] Conexión perdida: {exc}. Reintentando en {_RECONNECT_DELAY}s…")
                self._connected = False
                self._app.call_from_thread(
                    self._app.tui_ui.print_message,
                    f"⚠️  Conexión al servidor perdida. Reintentando en {_RECONNECT_DELAY:.0f}s…",
                    "yellow",
                )
                await asyncio.sleep(_RECONNECT_DELAY)

    async def _connect_and_run(self) -> None:
        """Establece la conexión y ejecuta los dos loops concurrentes."""
        try:
            import websockets
        except ImportError:
            raise RuntimeError(
                "La librería 'websockets' no está instalada. "
                "Ejecuta: pip install websockets"
            )

        ws_url = f"{self._server_url}/ws/{self._session_id}"
        logger.info(f"[WS] Conectando a {ws_url} …")

        async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
            self._ws = ws
            self._connected = True
            logger.info("[WS] Conectado al servidor KogniTerm.")

            # Mostrar indicador en la TUI
            self._app.call_from_thread(
                self._app.tui_ui.print_message,
                "🔗 Conectado al servidor KogniTerm (modo servidor activo).",
                "green",
            )

            # Correr recepción y envío de forma concurrente
            receive_task = asyncio.create_task(self._receive_loop(ws))
            send_task = asyncio.create_task(self._send_loop(ws))

            done, pending = await asyncio.wait(
                [receive_task, send_task],
                return_when=asyncio.FIRST_EXCEPTION,
            )
            for task in pending:
                task.cancel()
            # Propagar la excepción del task que falló
            for task in done:
                exc = task.exception()
                if exc:
                    raise exc

    # ── Bucles internos ─────────────────────────────────────────────────────────

    async def _receive_loop(self, ws) -> None:
        """Recibe mensajes del servidor y los despacha a la TUI."""
        async for raw in ws:
            if self._stopped:
                break
            try:
                event = json.loads(raw)
                self._route_event(event)
            except json.JSONDecodeError:
                logger.warning(f"[WS] Mensaje no-JSON recibido: {raw[:100]}")

    async def _send_loop(self, ws) -> None:
        """Envía mensajes encolados al servidor."""
        while not self._stopped:
            payload = await self._send_queue.get()
            try:
                await ws.send(json.dumps(payload, ensure_ascii=False))
            except Exception as exc:
                logger.warning(f"[WS] Error al enviar mensaje: {exc}")
            finally:
                self._send_queue.task_done()

    # ── Enrutamiento de eventos ────────────────────────────────────────────────

    def _route_event(self, event: dict) -> None:
        """
        Mapea los eventos JSON del servidor a acciones en los widgets de la TUI.
        Todos los métodos de widgets de Textual deben llamarse desde el hilo
        principal usando call_from_thread.
        """
        event_type = event.get("type", "")
        data = event.get("data", {})

        if event_type == "connected":
            # El servidor confirmó la conexión — actualizar info del modelo si aplica
            config = data.get("config", {}) if isinstance(data, dict) else {}
            model = config.get("model")
            if model:
                self._app.call_from_thread(self._app.update_status_footer, model)

        elif event_type in ("stream", "chunk"):
            # Fragmento de texto del LLM
            if isinstance(data, dict):
                text = data.get("content", "")
            else:
                text = str(data) if data else ""
            if text:
                self._app.call_from_thread(self._app.chat_log.write_stream, text)

        elif event_type == "message":
            # Mensaje completo del agente (no streaming)
            if isinstance(data, dict):
                text = data.get("text", "")
            else:
                text = str(data) if data else ""
            if text:
                self._app.call_from_thread(self._app.chat_log.write_agent_message, text)

        elif event_type == "tool_call":
            # El agente comenzó a usar una herramienta
            if isinstance(data, dict):
                tool_name = data.get("name", "herramienta")
                description = data.get("description", "")
                skill = data.get("skill", "")
            else:
                tool_name, description, skill = str(data), "", ""
            self._app.call_from_thread(
                self._app.tui_ui.print_tool_notification,
                tool_name, description, skill,
            )

        elif event_type == "tool_result":
            # Salida de una herramienta
            if isinstance(data, dict):
                output = data.get("content", "")
                tool_name = data.get("tool", "Terminal")
            else:
                output, tool_name = str(data), "Terminal"
            if output:
                self._app.call_from_thread(
                    self._app.tui_ui.update_tool_display,
                    tool_name, output,
                )

        elif event_type == "terminal_output":
            # Salida interactiva para el panel terminal
            if isinstance(data, dict):
                output = data.get("content", "")
                tool_name = data.get("tool", "Terminal")
            else:
                output, tool_name = str(data), "Terminal"
            if output:
                self._app.call_from_thread(
                    self._app.tui_ui.update_terminal_output,
                    tool_name, output,
                )

        elif event_type == "task_tracker":
            # Actualizar el panel de tareas
            if isinstance(data, dict):
                self._app.call_from_thread(self._app.update_task_tracker, data)

        elif event_type == "live_update":
            # Actualización de rich content (reasoning, etc.)
            text = str(data) if data else ""
            if text:
                self._app.call_from_thread(self._app.chat_log.write_stream, text)

        elif event_type == "approval_required":
            # El servidor necesita aprobación del usuario
            if isinstance(data, dict):
                request_id = data.get("id", "")
                message = data.get("message", "Confirmar acción")
                title = data.get("title", "Aprobación Requerida")
                diff_content = data.get("diff_content", "")
                file_path = data.get("file_path", "")
                self._app.call_from_thread(
                    self._handle_approval_request,
                    request_id, message, title, diff_content, file_path,
                )

        elif event_type == "done":
            # El agente terminó su turno
            self._app.call_from_thread(self._on_agent_done)

        elif event_type == "error":
            error_msg = data.get("message", str(data)) if isinstance(data, dict) else str(data)
            self._app.call_from_thread(
                self._app.tui_ui.print_message,
                f"❌ Error del servidor: {error_msg}",
                "bold red",
            )
            self._app.call_from_thread(self._on_agent_done)

        elif event_type == "indexing_progress":
            if isinstance(data, dict):
                self._app.call_from_thread(
                    self._app._show_indexing_progress,
                    data.get("current", 0),
                    data.get("total", 1),
                    data.get("description", ""),
                )

        elif event_type == "indexing_complete":
            chunks = data.get("chunks", 0) if isinstance(data, dict) else 0
            self._app.call_from_thread(self._app._indexing_complete, chunks)

        elif event_type == "indexing_error":
            error_msg = data.get("message", "Error desconocido") if isinstance(data, dict) else str(data)
            self._app.call_from_thread(self._app._indexing_failed, error_msg)

        elif event_type in ("pong", "info"):
            # Keep-alive y mensajes informativos — ignorar silenciosamente
            pass

        else:
            logger.debug(f"[WS] Evento no manejado: {event_type}")

    # ── Helpers de eventos complejos ───────────────────────────────────────────

    def _handle_approval_request(
        self,
        request_id: str,
        message: str,
        title: str,
        diff_content: str,
        file_path: str,
    ) -> None:
        """
        Monta el InlineApprovalWidget y envía la respuesta al servidor
        cuando el usuario decide. Se ejecuta en el hilo principal de Textual.
        """
        try:
            from kogniterm.terminal.tui.components.inline_approval import InlineApprovalWidget
            import concurrent.futures

            def callback(result: str) -> None:
                approved = result in ("accept", "accept_all")
                if result == "accept_all":
                    self._app._auto_approve_all = True
                # Enviar respuesta al servidor en un coroutine seguro
                asyncio.run_coroutine_threadsafe(
                    self.send_approval(request_id, approved),
                    self._app.loop,
                )

            widget = InlineApprovalWidget(
                message=message,
                title=title,
                diff_content=diff_content or None,
                file_path=file_path or None,
                callback=callback,
            )
            if hasattr(self._app, "approval_container"):
                self._app.approval_container.mount(widget)
            else:
                self._app.mount(widget)
            self._app.chat_log.scroll_end(animate=False)
            widget.focus()
        except Exception as exc:
            logger.error(f"[WS] Error montando widget de aprobación: {exc}")

    def _on_agent_done(self) -> None:
        """Limpia el estado de procesamiento cuando el agente termina."""
        self._app.is_processing = False
        self._app._stop_spinner()
        self._app._process_queue()

    # ── API pública para enviar mensajes ───────────────────────────────────────

    async def send_message(self, text: str) -> None:
        """Envía un mensaje de usuario al agente en el servidor."""
        await self._send_queue.put({"type": "message", "text": text})

    async def send_interrupt(self) -> None:
        """Interrumpe la ejecución actual del agente en el servidor."""
        await self._send_queue.put({"type": "interrupt"})

    async def send_approval(self, request_id: str, approved: bool) -> None:
        """Responde a una solicitud de aprobación pendiente en el servidor."""
        await self._send_queue.put({
            "type": "approval_response",
            "id": request_id,
            "approved": approved,
        })

    async def send_ping(self) -> None:
        """Envía un ping de keep-alive."""
        await self._send_queue.put({"type": "ping"})

    def stop(self) -> None:
        """Detiene el cliente y cierra la conexión."""
        self._stopped = True
        self._connected = False
        if self._ws:
            try:
                asyncio.run_coroutine_threadsafe(self._ws.close(), asyncio.get_event_loop())
            except Exception:
                pass
