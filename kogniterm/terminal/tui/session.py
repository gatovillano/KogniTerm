"""Multisesión con pestañas para la TUI de KogniTerm.

Todas las sesiones comparten el mismo proyecto/workspace. Cada sesión tiene:

- Su propio ``thread_id`` del ``ThreadManager`` (persistencia aislada).
- Su propio ``AgentState`` (historial de mensajes aislado).
- Su propia ``interrupt_queue`` (ESC/interrupciones por pestaña).
- Su propio ``AgentInteractionManager`` + ``MetaCommandProcessor``.
- Su propio ``ChatLogWidget`` (una pestaña visual).
- Sus flags ``is_processing`` e ``input_queue`` (procesamiento en paralelo).

El ``LLMService`` y el ``CommandExecutor`` se comparten (modelo, herramientas
y PTY comunes del workspace). El enrutado de la salida de herramientas que
llega vía ``llm_service.terminal_ui`` / ``command_executor.terminal_ui`` se
resuelve con :class:`SessionContext` (thread-local fijado por el worker de
cada sesión) + :class:`RoutingUI`.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SessionContext:
    """Thread-local con el ``session_id`` que está procesando cada worker.

    El worker de ``process_agent_request`` lo fija al empezar y lo limpia al
    terminar. Así el :class:`RoutingUI` puede dirigir la salida de
    herramientas compartidas (``LLMService.terminal_ui``,
    ``CommandExecutor.terminal_ui``) a la pestaña correcta aunque el
    procesamiento ocurra en segundo plano.
    """

    _local = threading.local()

    @classmethod
    def get(cls) -> Optional[str]:
        return getattr(cls._local, "session_id", None)

    @classmethod
    def set(cls, session_id: Optional[str]) -> None:
        cls._local.session_id = session_id


@dataclass
class Session:
    """Estado de una pestaña de conversación (mismo workspace)."""

    session_id: str
    title: str
    thread_id: Optional[str] = None
    chat_widget_id: str = ""
    agent_state: Any = None
    interrupt_queue: Any = None
    interaction_manager: Any = None
    meta_processor: Any = None
    ui_proxy: Any = None
    is_processing: bool = False
    input_queue: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_terminal_tool_name: str = ""
    last_terminal_output: str = ""
    # ── Aislamiento v2 ──────────────────────────────────────────────
    # PTY/shell persistente propio (los comandos aprobados de cada pestaña
    # corren en su propio shell: cd/env independientes, sin serialización
    # global). Las tools `execute_command` ya usan PTY efímero por llamada.
    command_executor: Any = None
    # Handler de aprobaciones propio (usa el executor y la UI de la pestaña)
    approval_handler: Any = None
    # Managers pesados creados de forma perezosa (ver _ensure_session_managers)
    _managers_ready: bool = False
    # Estado de terminal interactiva por pestaña
    cursor_active: bool = False
    interactive_executor: Any = None
    # Spinner inline puesto en el widget de una pestaña en segundo plano
    inline_spinner: bool = False
    # Aprobaciones pendientes (se muestra `?` en la pestaña)
    pending_approvals: int = 0
    # ── Modo servidor ───────────────────────────────────────────────
    # Cada pestaña tiene su propia sesión remota (conversación independiente
    # en el servidor) con su propio WebSocket.
    server_session_id: Optional[str] = None
    ws_client: Any = None
    ws_task: Any = None


class _ProxyConsole:
    """Consola mínima que redirige ``print`` al widget de la sesión."""

    def __init__(self, proxy: "SessionUIProxy"):
        self._proxy = proxy
        self.is_terminal = True
        self.width = 80
        self.height = 24
        self.legacy_windows = False
        self.encoding = "utf-8"
        try:
            from rich.console import Console

            _console = Console(width=80, height=24, force_terminal=True)
            self.options = _console.options
        except Exception:
            self.options = None
        self._live_stack: list = []
        self._in_live = False

    def print(self, *args, **kwargs):
        if getattr(self, "_in_live", False):
            return
        is_streaming = kwargs.get("end") == ""
        for arg in args:
            text = str(arg)
            if is_streaming:
                self._proxy.print_stream(text)
            else:
                self._proxy.print_message(text)

    def set_live(self, live):
        self._in_live = True

    def clear_live(self):
        self._in_live = False

    def update(self, *args, **kwargs):
        pass

    def render(self, renderable, options=None):
        return []

    def render_lines(self, renderable, options=None):
        return []

    def show_cursor(self, show=True):
        pass

    @property
    def file(self):
        import io

        return io.StringIO()


class SessionUIProxy:
    """Adaptador con la misma interfaz que ``TextualTerminalUI`` pero que
    escribe siempre en el ``ChatLogWidget`` de su sesión.

    Los diálogos de aprobación/preguntas (modales globales) se delegan a la
    UI base, ya que comparten el ``approval_container`` de la app.
    """

    def __init__(
        self,
        base: Any,
        app: Any,
        get_widget: Callable[[], Any],
        interrupt_queue: "queue.Queue",
        session_id: str,
    ):
        self._base = base
        self._app = app
        self._get_widget = get_widget
        self._interrupt_queue = interrupt_queue
        self.session_id = session_id
        self.is_tui = True
        self.kb = None
        self.console = _ProxyConsole(self)
        self._stream_accumulator = ""
        self._acc_lock = threading.RLock()

    # -- compatibilidad con código que accede a .app ---------------------
    @property
    def app(self):
        return self._app

    @property
    def tui_ui(self):
        return self

    def _widget(self):
        try:
            return self._get_widget()
        except Exception:
            return None

    def _safe_call(self, func, *args, **kwargs):
        try:
            return self._base._safe_call(func, *args, **kwargs)
        except Exception:
            # Fallback: la base puede no existir en tests ligeros
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                logger.debug("SessionUIProxy._safe_call falló: %s", exc)
                return None

    # -- mensajes ---------------------------------------------------------
    def print_message(
        self,
        message: str,
        style: str = "",
        is_user_message: bool = False,
        status: str = None,
        use_bubble: bool = False,
        **kwargs,
    ):
        widget = self._widget()
        if widget is None:
            return self._base.print_message(
                message,
                style=style,
                is_user_message=is_user_message,
                status=status,
                use_bubble=use_bubble,
                **kwargs,
            )

        def _write():
            try:
                if is_user_message:
                    widget.write_user_message(message)
                else:
                    from rich.text import Text as _Text

                    if (
                        isinstance(message, str)
                        and "[" in message
                        and "]" in message
                    ):
                        try:
                            widget.write_message(_Text.from_markup(message))
                            return
                        except Exception:
                            pass
                    widget.write_agent_message(message)
            except Exception as exc:
                logger.debug("SessionUIProxy.print_message falló: %s", exc)

        self._safe_call(_write)

    def print_stream(self, text: str, **kwargs):
        self.write_stream_to_chat(text, **kwargs)

    def write_stream_to_chat(self, content: str, **kwargs):
        if not content:
            return
        widget = self._widget()
        if widget is None:
            return
        with self._acc_lock:
            if isinstance(content, str):
                self._stream_accumulator += content
                accumulated = self._stream_accumulator
            else:
                accumulated = content

        def _write():
            try:
                if isinstance(accumulated, str):
                    widget.write_stream(accumulated)
                else:
                    widget.write_stream(accumulated)
            except Exception as exc:
                logger.debug("SessionUIProxy.write_stream_to_chat falló: %s", exc)

        self._safe_call(_write)

    def update_live(self, renderable, **kwargs):
        widget = self._widget()
        if widget is None:
            return

        def _write():
            try:
                widget.write_stream(renderable)
            except Exception as exc:
                logger.debug("SessionUIProxy.update_live falló: %s", exc)

        self._safe_call(_write)

    def stop_live(self, **kwargs):
        widget = self._widget()
        if widget is None:
            return
        with self._acc_lock:
            self._stream_accumulator = ""

        def _stop():
            try:
                if hasattr(widget, "stop_stream"):
                    widget.stop_stream()
            except Exception:
                pass

        self._safe_call(_stop)

    def resume_spinner(self):
        try:
            self._base.resume_spinner()
        except Exception:
            pass

    # -- herramientas / terminal ------------------------------------------
    def update_terminal_output(self, tool_name: str, output: str, **kwargs):
        widget = self._widget()
        if widget is None:
            return
        command = kwargs.get("command", tool_name) or tool_name

        def _write():
            try:
                widget.write_stream(("__TERMINAL__", tool_name, output, command))
            except Exception as exc:
                logger.debug("SessionUIProxy.update_terminal_output falló: %s", exc)

        self._safe_call(_write)

    def update_tool_display(
        self, tool_name: str, output: str, command: str = "", max_lines=None, **kwargs
    ):
        if not output:
            return
        widget = self._widget()
        if widget is None:
            return
        if max_lines is not None:
            lines = output.splitlines()
            displayed = (
                "\n".join(lines[-max_lines:])
                if len(lines) > max_lines
                else output
            )
        else:
            displayed = output

        def _write():
            try:
                widget.write_tool_output(
                    displayed, tool_name, language=command or None
                )
            except Exception as exc:
                logger.debug("SessionUIProxy.update_tool_display falló: %s", exc)

        self._safe_call(_write)

    def update_task_tracker(self, agent_plans: dict):
        try:
            self._base.update_task_tracker(agent_plans)
        except Exception as exc:
            logger.debug("SessionUIProxy.update_task_tracker falló: %s", exc)

    def print_tool_notification(
        self, tool_name: str, action_desc: str = "", skill_name: str = "", **kwargs
    ):
        widget = self._widget()
        if widget is None:
            return

        def _write():
            try:
                widget.write_tool_notification(tool_name, action_desc, skill_name)
            except Exception as exc:
                logger.debug("SessionUIProxy.print_tool_notification falló: %s", exc)

        self._safe_call(_write)

    def print_background_task_notification(self, task_info: dict, **kwargs):
        widget = self._widget()
        if widget is None:
            return
        task_id = task_info.get("task_id", "task")
        status = task_info.get("status", "running")
        cmd = task_info.get("command", "")
        msg = f"⚙️ [Segundo Plano] Tarea **{task_id}** ({status.upper()}): `{cmd}`"

        def _write():
            try:
                widget.write_message(msg, style="cyan")
            except Exception:
                pass

        self._safe_call(_write)

    def _print_box(self, message: str, title: str, style: str, icon: str):
        widget = self._widget()
        if widget is None:
            return

        def _write():
            try:
                widget.write_message(f"{icon} [box] **{title}**: {message}", style=style)
            except Exception:
                pass

        self._safe_call(_write)

    def print_success_box(self, message: str, title: str = "Éxito", **kwargs):
        self._print_box(message, title, "green", "✅")

    def print_error_box(self, message: str, title: str = "Error", **kwargs):
        self._print_box(message, title, "red", "❌")

    def print_warning_box(self, message: str, title: str = "Advertencia", **kwargs):
        self._print_box(message, title, "yellow", "⚠️")

    def print_status(self, message: str, spinner_style: str = "dots"):
        import contextlib

        @contextlib.contextmanager
        def dummy_status():
            yield

        return dummy_status()

    def print_confirmation_panel(self, content, title, border_style):
        widget = self._widget()
        if widget is None:
            return

        def _write():
            try:
                widget.write_message(f"⚠️ [Confirma] {title}")
            except Exception:
                pass

        self._safe_call(_write)

    # -- interrupciones / terminal interactiva -----------------------------
    def get_interrupt_queue(self):
        return self._interrupt_queue

    def set_terminal_cursor(self, active: bool, executor=None):
        # Registrar siempre el estado en la sesión; reflejar en la UI global
        # solo si es la pestaña activa (para no secuestrar el input).
        try:
            app = self._app
            active_session = app.get_active_session() if hasattr(app, "get_active_session") else None
            is_active = (
                active_session is not None
                and getattr(active_session, "session_id", None) == self.session_id
            )
            try:
                session = app.get_session(self.session_id)
                if session is not None:
                    session.cursor_active = bool(active)
                    session.interactive_executor = executor if active else None
            except Exception:
                pass
            if not is_active:
                return
            self._base.set_terminal_cursor(active, executor)
        except Exception as exc:
            logger.debug("SessionUIProxy.set_terminal_cursor falló: %s", exc)

    def handle_resize(self):
        pass

    def get_terminal_dimensions(self) -> tuple:
        try:
            return self._base.get_terminal_dimensions()
        except Exception:
            import shutil

            size = shutil.get_terminal_size(fallback=(120, 30))
            return max(40, int(size.columns)), max(12, int(size.lines))

    # -- diálogos (modales globales, se delegan a la base) ------------------
    async def ask_radiolist_async(self, title, text, values, default=None):
        return await self._base.ask_radiolist_async(title, text, values, default)

    async def ask_input_async(self, title, text, password=False):
        return await self._base.ask_input_async(title, text, password)

    async def ask_message_async(self, title, text):
        return await self._base.ask_message_async(title, text)

    def ask_approval_sync(self, message, title="Aprobación Requerida", diff_content="", file_path=""):
        return self._base.ask_approval_sync(
            message=message, title=title, diff_content=diff_content, file_path=file_path
        )

    def ask_question_sync(self, question, options, title="Consulta del Agente", allow_freeform=True):
        return self._base.ask_question_sync(
            question=question, options=options, title=title, allow_freeform=allow_freeform
        )

    async def ask_approval_async(self, message, title="Aprobación Requerida", diff_content="", file_path=""):
        return await self._base.ask_approval_async(
            message=message, title=title, diff_content=diff_content, file_path=file_path
        )

    def clear_chat(self):
        """Limpia solo el widget de esta sesión (sin mostrar el splash)."""
        widget = self._widget()
        if widget is None:
            return

        def _do_clear():
            try:
                widget.clear()
            except Exception:
                pass

        self._safe_call(_do_clear)

    def print_welcome_banner(self):
        pass

    def __getattr__(self, name: str):
        # Delegación hacia la UI base para cualquier método futuro.
        base = object.__getattribute__(self, "_base")
        return getattr(base, name)


class RoutingUI:
    """UI compartida para ``LLMService`` / ``CommandExecutor``.

    Dirige cada llamada a la pestaña que la originó (vía
    :class:`SessionContext`) o, si no hay contexto, a la sesión activa
    (comportamiento legacy a través de la UI base).
    """

    def __init__(self, app: Any, base: Any):
        self._app = app
        self._base = base
        self.is_tui = True

    def _target(self):
        try:
            session_id = SessionContext.get()
            if session_id:
                session = self._app.get_session(session_id)
                if session is not None and session.ui_proxy is not None:
                    return session.ui_proxy
            active = self._app.get_active_session()
            if active is not None and active.ui_proxy is not None:
                return active.ui_proxy
        except Exception as exc:
            logger.debug("RoutingUI._target falló: %s", exc)
        return self._base

    def get_interrupt_queue(self):
        try:
            session_id = SessionContext.get()
            if session_id:
                session = self._app.get_session(session_id)
                if session is not None:
                    return session.interrupt_queue
            active = self._app.get_active_session()
            if active is not None:
                return active.interrupt_queue
        except Exception:
            pass
        return self._base.get_interrupt_queue()

    def __getattr__(self, name: str):
        target = object.__getattribute__(self, "_target")()
        return getattr(target, name)


def new_interrupt_queue() -> "queue.Queue":
    return queue.Queue()


def build_session_title(index: int, thread_title: Optional[str] = None) -> str:
    base = (thread_title or "").strip()
    if base and base.lower() not in ("nueva conversación", "nueva conversacion", ""):
        return base[:24]
    return f"Sesión {index}"
