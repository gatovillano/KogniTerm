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


def build_native_renderable(thinking: str, response: str) -> Any:
    from rich.padding import Padding
    from rich.console import Group
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.text import Text
    from kogniterm.terminal.themes import ColorPalette, Icons

    renderables = []
    if thinking:
        # En TUI: construir Panel con fondo explícito y letra opaca (gris/dim)
        thinking_content = Markdown(thinking)
        thought_panel = Panel(
            thinking_content,
            title=f"{Icons.THINKING} KogniTerm Pensando...",
            border_style=ColorPalette.GRAY_700,
            style=f"dim {ColorPalette.GRAY_500} on {ColorPalette.GRAY_900}",
            padding=(0, 4),
            expand=True
        )
        renderables.append(thought_panel)

    if response:
        if thinking:
            renderables.append(Text("\n"))  # Separación entre pensamiento y respuesta
        renderables.append(Markdown(response))

    if not renderables:
        return None

    # Mismo padding (2, 0, 1, 0) que usa la visualización local en bash_agent
    return Padding(Group(*renderables), (2, 0, 1, 0))


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
        # Acumuladores de streaming por agente: clave = agent_id o "__main__"
        self._stream_accumulators: dict = {}
        # Tiempo del último live_update (solo para agente principal)
        self._last_live_update_time = 0.0

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

        elif event_type == "stream":
            # Fragmento de texto del LLM
            agent_id = event.get("agent_id")
            text = str(data) if data else ""
            if text:
                import time
                # Solo suprimir stream del agente principal si hay live_update reciente
                if agent_id or time.time() - self._last_live_update_time > 2.0:
                    accumulated = self._get_stream_accumulator(agent_id) + text
                    self._set_stream_accumulator(accumulated, agent_id)
                    chat_log = self._get_chat_log(agent_id)
                    
                    if agent_id:
                        # Mostrar panel del subagente (no bloquea el agente principal)
                        self._app.call_from_thread(self._show_agent_panel, agent_id)

                    def write_to_log(cl=chat_log, acc=accumulated, aid=agent_id):
                        if not aid and self._app._spinner_timer:
                            self._app._stop_spinner()
                        cl.write_stream(acc)
                    self._app.call_from_thread(write_to_log)

        elif event_type == "message":
            # Mensaje completo del agente (no streaming)
            agent_id = event.get("agent_id")
            if isinstance(data, dict):
                text = data.get("text", "")
            else:
                text = str(data) if data else ""
            if text:
                chat_log = self._get_chat_log(agent_id)
                self._app.call_from_thread(chat_log.write_agent_message, text)

        elif event_type == "tool_call":
            # El agente comenzó a usar una herramienta
            agent_id = event.get("agent_id")
            self._reset_stream_accumulator(agent_id)
            if not agent_id:
                self._last_live_update_time = 0.0
            if isinstance(data, dict):
                tool_name = data.get("name", "herramienta")
                description = data.get("description", "")
                skill = data.get("skill", "")
            else:
                tool_name, description, skill = str(data), "", ""
            
            if agent_id:
                chat_log = self._get_chat_log(agent_id)
                self._app.call_from_thread(self._show_agent_panel, agent_id)
                self._app.call_from_thread(chat_log.write_tool_notification, tool_name, description, skill)
            else:
                self._app.call_from_thread(
                    self._app.tui_ui.print_tool_notification,
                    tool_name, description, skill,
                )

        elif event_type == "tool_result":
            # Salida de una herramienta
            agent_id = event.get("agent_id")
            self._reset_stream_accumulator(agent_id)
            if not agent_id:
                self._last_live_update_time = 0.0
            if isinstance(data, dict):
                output = data.get("content", "")
                tool_name = data.get("tool", "Terminal")
            else:
                output, tool_name = str(data), "Terminal"
            if output:
                if agent_id:
                    chat_log = self._get_chat_log(agent_id)
                    limit = 30
                    lines = output.splitlines()
                    displayed = "\n".join(lines[-limit:]) if len(lines) > limit else output
                    self._app.call_from_thread(chat_log.write_tool_output, displayed, tool_name)
                else:
                    self._app.call_from_thread(
                        self._app.tui_ui.update_tool_display,
                        tool_name, output,
                    )

        elif event_type == "terminal_output":
            # Salida interactiva para el panel terminal
            agent_id = event.get("agent_id")
            self._reset_stream_accumulator(agent_id)
            if not agent_id:
                self._last_live_update_time = 0.0
            if isinstance(data, dict):
                output = data.get("content", "")
                tool_name = data.get("tool", "Terminal")
            else:
                output, tool_name = str(data), "Terminal"
            if output is not None:
                if agent_id:
                    chat_log = self._get_chat_log(agent_id)
                    self._app.call_from_thread(chat_log.write_stream, ("__TERMINAL__", tool_name, output))
                else:
                    self._app.call_from_thread(
                        self._app.tui_ui.update_terminal_output,
                        tool_name, output,
                    )

        elif event_type == "set_terminal_cursor":
            active = data.get("active", False) if isinstance(data, dict) else bool(data)
            self._app.call_from_thread(
                self._app.set_terminal_cursor,
                active,
                ServerTerminalExecutorProxy(self) if active else None
            )

        elif event_type == "task_tracker":
            # Actualizar el panel de tareas
            if isinstance(data, dict):
                self._app.call_from_thread(self._app.update_task_tracker, data)

        elif event_type == "live_update":
            # Actualización de rich content (reasoning, etc.)
            agent_id = event.get("agent_id")
            chat_log = self._get_chat_log(agent_id)

            if agent_id:
                # Para subagentes: mostrar panel y enrutar
                self._app.call_from_thread(self._show_agent_panel, agent_id)
            else:
                import time
                self._last_live_update_time = time.time()

            if isinstance(data, dict):
                special_type = data.get("special_type")
                if special_type == "spinner" and not agent_id:
                    content = ("__SPINNER__", data.get("text", ""))
                    self._app.call_from_thread(lambda cl=chat_log, c=content: cl.write_stream(c))
                elif special_type == "terminal" and not agent_id:
                    content = ("__TERMINAL__", data.get("tool", ""), data.get("output", ""), data.get("command", ""))
                    self._app.call_from_thread(lambda cl=chat_log, c=content: cl.write_stream(c))
                else:
                    thinking = data.get("thinking", "")
                    response = data.get("response", "")
                    if agent_id:
                        # Para subagentes: mostrar como texto simple acumulado
                        display_text = (response or thinking or "").strip()
                        if display_text:
                            # En modo servidor, live_update envía el texto completo acumulado (buf.getvalue()).
                            # Por lo tanto, no debemos volver a sumarlo con el acumulador anterior,
                            # sino simplemente usar el display_text como el nuevo valor acumulado.
                            self._set_stream_accumulator(display_text, agent_id)
                            self._app.call_from_thread(lambda cl=chat_log, t=display_text: cl.write_stream(t))
                    else:
                        renderable = build_native_renderable(thinking, response)
                        if renderable:
                            def write_to_log(cl=chat_log, r=renderable):
                                if self._app._spinner_timer:
                                    self._app._stop_spinner()
                                cl.write_stream(r)
                            self._app.call_from_thread(write_to_log)
            else:
                text = str(data) if data else ""
                if text:
                    def write_to_log(cl=chat_log, t=text, aid=agent_id):
                        if not aid and self._app._spinner_timer:
                            self._app._stop_spinner()
                        cl.write_stream(t)
                    self._app.call_from_thread(write_to_log)

        elif event_type == "live_stop":
            # Parar el streaming actual y congelar el widget
            agent_id = event.get("agent_id")
            self._reset_stream_accumulator(agent_id)
            if not agent_id:
                self._last_live_update_time = 0.0
            chat_log = self._get_chat_log(agent_id)
            self._app.call_from_thread(chat_log.stop_stream)

        elif event_type == "approval_required":
            # El servidor necesita aprobación del usuario
            if isinstance(data, dict):
                request_id = data.get("id", "")
                message = data.get("message", "Confirmar acción")
                title = data.get("title", "Aprobación Requerida")
                diff_content = data.get("diff", data.get("diff_content", ""))
                file_path = data.get("file_path", "")
                self._app.call_from_thread(
                    self._handle_approval_request,
                    request_id, message, title, diff_content, file_path,
                )

        elif event_type == "done":
            # El agente terminó su turno
            agent_id = event.get("agent_id")
            if agent_id:
                self._reset_stream_accumulator(agent_id)
            else:
                self._last_live_update_time = 0.0
                self._stream_accumulators.clear()
                self._app.call_from_thread(self._on_agent_done)

        elif event_type == "error":
            agent_id = event.get("agent_id")
            error_msg = data.get("message", str(data)) if isinstance(data, dict) else str(data)
            if agent_id:
                self._reset_stream_accumulator(agent_id)
                chat_log = self._get_chat_log(agent_id)
                self._app.call_from_thread(
                    chat_log.write_agent_message,
                    f"❌ Error: {error_msg}"
                )
            else:
                self._last_live_update_time = 0.0
                self._stream_accumulators.clear()
                self._app.call_from_thread(
                    self._app.tui_ui.print_message,
                    f"❌ Error del servidor: {error_msg}",
                    "bold red",
                )
                self._app.call_from_thread(self._on_agent_done)

        elif event_type == "agent_panel_show":
            # El servidor indica que debe mostrarse el panel de un subagente
            if isinstance(data, dict):
                agent_id = data.get("agent_id", "")
                title = data.get("title", agent_id)
                if agent_id:
                    self._app.call_from_thread(self._show_agent_panel, agent_id, title)

        elif event_type == "agent_panel_hide":
            # El servidor indica que los paneles paralelos deben ocultarse
            self._app.call_from_thread(self._hide_agent_panels)

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

    # ── Helpers de enrutamiento a paneles ────────────────────────────────────

    def _get_chat_log(self, agent_id: str = None):
        """Retorna el ChatLogWidget para el agente indicado.
        
        Si agent_id es None o no se encuentra el panel, devuelve el chat_log principal.
        """
        if not agent_id:
            return self._app.chat_log
        # Los paneles de agentes paralelos son atributos directos de la app
        panel_attr = agent_id  # e.g. "live_display_coder"
        if hasattr(self._app, panel_attr):
            return getattr(self._app, panel_attr)
        return self._app.chat_log

    def _get_stream_accumulator(self, agent_id: str = None) -> str:
        key = agent_id or "__main__"
        return self._stream_accumulators.get(key, "")

    def _set_stream_accumulator(self, value: str, agent_id: str = None):
        key = agent_id or "__main__"
        self._stream_accumulators[key] = value

    def _reset_stream_accumulator(self, agent_id: str = None):
        key = agent_id or "__main__"
        self._stream_accumulators[key] = ""

    def _show_agent_panel(self, agent_id: str, title: str = ""):
        """Muestra el contenedor de paneles paralelos y activa la pestaña del agente.
        
        Se debe ejecutar en el hilo principal de Textual.
        """
        try:
            container = self._app.query_one("#parallel_agents_container")
            if not container.display:
                container.display = True
            # Activar la pestaña correspondiente
            # agent_id es algo como "live_display_coder" → tab_id es "tab_coder"
            tab_suffix = agent_id.replace("live_display_", "")
            tab_id = f"tab_{tab_suffix}"
            try:
                container.active = tab_id
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"[WS] Error mostrando panel del agente {agent_id}: {e}")

    def _hide_agent_panels(self):
        """Oculta el contenedor de paneles paralelos."""
        try:
            container = self._app.query_one("#parallel_agents_container")
            container.display = False
            # Restaurar paneles principales
            try:
                self._app.query_one("#live_display").display = True
            except Exception:
                pass
            try:
                self._app.query_one("#tool_display").display = True
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"[WS] Error ocultando paneles paralelos: {e}")

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
                
                logger.info(f"[WS] Aprobación del usuario recibida: {result} (approved={approved}) para request_id={request_id}")
                
                # Enviar respuesta al servidor de forma segura
                try:
                    import asyncio
                    import threading
                    if threading.current_thread() is threading.main_thread():
                        asyncio.create_task(self.send_approval(request_id, approved))
                        logger.info(f"[WS] Aprobación enviada al servidor via create_task")
                    else:
                        asyncio.run_coroutine_threadsafe(
                            self.send_approval(request_id, approved),
                            self._app.loop,
                        )
                        logger.info(f"[WS] Aprobación enviada al servidor via run_coroutine_threadsafe")
                except Exception as e:
                    logger.error(f"[WS] Error al enviar aprobación al servidor: {e}")

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
        self._last_live_update_time = 0.0
        self._stream_accumulator = ""
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

    async def send_terminal_input(self, text: str) -> None:
        """Envía caracteres ingresados por el usuario para ser inyectados en la PTY del servidor."""
        await self._send_queue.put({"type": "terminal_input", "text": text})

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


class ServerTerminalExecutorProxy:
    def __init__(self, ws_client: TUIWebSocketClient):
        self.ws_client = ws_client

    def write_input(self, data) -> None:
        if isinstance(data, bytes):
            try:
                data = data.decode('utf-8')
            except Exception:
                return
        if self.ws_client and self.ws_client.is_connected:
            asyncio.run_coroutine_threadsafe(
                self.ws_client.send_terminal_input(data),
                self.ws_client._app.loop
            )
