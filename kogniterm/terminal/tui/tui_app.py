import asyncio
import os
import queue
import json
import logging
import re
import uuid
from typing import Any, Optional
from textual.app import App, ComposeResult
from textual import work
from textual.widgets import (
    Input,
    ListView,
    ListItem,
    Label,
    Button,
    Static,
    TextArea,
    RichLog,
    TabbedContent,
    TabPane,
)
from textual.containers import Vertical, Horizontal
from textual import events
from langchain_core.messages import HumanMessage
import threading

logger = logging.getLogger(__name__)

# URL del servidor KogniTerm (puede sobreescribirse con KOGNITERM_SERVER_URL)
_DEFAULT_SERVER_URL = os.environ.get("KOGNITERM_SERVER_URL", "ws://127.0.0.1:8765")
_DEFAULT_SESSION_ID = os.environ.get(
    "KOGNITERM_SESSION_ID", f"tui-{uuid.uuid4().hex[:8]}"
)


try:
    from kogniterm.core.llm_service import LLMService
except Exception:
    # Permitir importar el módulo de TUI incluso si LLMService o sus dependencias
    # no están disponibles en el entorno de pruebas.
    LLMService = None
# Importar componentes opcionalmente para permitir pruebas ligeras del módulo TUI
try:
    from kogniterm.core.command_executor import CommandExecutor
except Exception:
    CommandExecutor = None
try:
    from kogniterm.core.agents.bash_agent import AgentState
except Exception:
    AgentState = None
try:
    from kogniterm.terminal.tui.components.chat_log import ChatLogWidget
except Exception:
    ChatLogWidget = None
try:
    from kogniterm.terminal.tui.components.status_footer import StatusFooter, ChatInput
except Exception:
    StatusFooter = None
    ChatInput = None
try:
    from kogniterm.terminal.tui.components.tool_output import ToolOutputWidget
except Exception:
    ToolOutputWidget = None
try:
    from kogniterm.terminal.tui.components.command_approval_modal import (
        CommandApprovalModal,
    )
except Exception:
    CommandApprovalModal = None
try:
    from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager
except Exception:
    AgentInteractionManager = None
try:
    from kogniterm.terminal.tui.session import (
        Session,
        SessionUIProxy,
        RoutingUI,
        SessionContext,
        new_interrupt_queue,
        build_session_title,
    )
except Exception:
    Session = None
    SessionUIProxy = None
    RoutingUI = None
    SessionContext = None
    new_interrupt_queue = None
    build_session_title = None
try:
    from kogniterm.terminal.command_approval_handler import CommandApprovalHandler
except Exception:
    CommandApprovalHandler = None
from textual.screen import ModalScreen
from textual.reactive import reactive
from rich.text import Text


# ─── Modal de confirmación para indexación ─────────────────────────────────────
class IndexingConfirmModal(ModalScreen[bool]):
    """Modal simple con botones Sí/No."""

    CSS = """
    IndexingConfirmModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.8);
    }
    #modal-box {
        width: 70;
        max-width: 90;
        height: auto;
        background: #1f2937;
        border: solid #4b5563;
        padding: 1 2;
    }
    #modal-title {
        color: #f9fafb;
        text-style: bold;
        width: 100%;
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
    }
    #modal-message {
        color: #d1d5db;
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 2;
        text-wrap: wrap;
    }
    #modal-buttons {
        width: 100%;
        height: 3;
        align: center middle;
    }
    #modal-buttons Button {
        margin: 0 2;
        min-width: 14;
    }
    """

    def __init__(self, title: str, message: str):
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Static(self._title, id="modal-title")
            yield Static(self._message, id="modal-message")
            with Horizontal(id="modal-buttons"):
                yield Button("Sí", id="btn-yes", variant="success")
                yield Button("No", id="btn-no", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_key(self, event: events.Key) -> None:
        if event.key in ("y", "Y", "enter"):
            self.dismiss(True)
        elif event.key in ("n", "escape"):
            self.dismiss(False)


class DummyConsole:
    def __init__(self, tui_ui):
        self.tui_ui = tui_ui
        self.is_terminal = True
        self.width = 80
        self.height = 24
        self.legacy_windows = False
        self.encoding = "utf-8"
        from rich.console import Console

        _console = Console(width=80, height=24, force_terminal=True)
        self.options = _console.options
        self._live_stack = []

    def print(self, *args, **kwargs):
        # Si estamos en modo live, ignoramos los prints regulares para evitar
        # inundar el chat log con estados intermedios. El streaming se maneja via update_live.
        if getattr(self, "_in_live", False):
            return

        # Determinar si es un print con end="" (streaming)
        is_streaming = kwargs.get("end") == ""

        # Support printing directly to the ChatLog instead of standard output
        for arg in args:
            if isinstance(arg, (str, bytes)):
                from rich.text import Text

                try:
                    if isinstance(arg, bytes):
                        arg = arg.decode("utf-8")
                    # No usar markup en streaming para evitar problemas de parsing parcial
                    if not is_streaming:
                        arg = Text.from_markup(arg)
                except Exception:
                    pass

            if is_streaming:
                self.tui_ui._safe_call(self.tui_ui.app.chat_log.write_stream, str(arg))
            else:
                self.tui_ui._safe_call(self.tui_ui.app.chat_log.write_message, arg)

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


class TerminalPanel(Static):
    """Widget de panel de terminal que permite recibir el foco para interacción directa."""

    can_focus = True

    def on_mount(self):
        self.tooltip = (
            "Haz clic o usa TAB para capturar teclado y enviar comandos directos"
        )


class SessionTabButton(Button):
    """Botón de pestaña que avisa a la app del hover (marquesina del título)."""

    def __init__(self, *args, session_id: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self._tab_session_id = session_id

    def on_enter(self, event: events.Enter) -> None:
        try:
            app = self.app
            if hasattr(app, "_tab_hover_enter"):
                app._tab_hover_enter(self._tab_session_id)
        except Exception:
            pass

    def on_leave(self, event: events.Leave) -> None:
        try:
            app = self.app
            if hasattr(app, "_tab_hover_leave"):
                app._tab_hover_leave(self._tab_session_id)
        except Exception:
            pass


class TextualTerminalUI:
    """Adaptador para que la lógica existente escriba en el ChatLog Textual."""

    def __init__(self, textual_app):
        self.app = textual_app
        self.interrupt_queue = queue.Queue()
        self.console = DummyConsole(self)
        self.kb = None
        self.is_tui = True
        self._stream_accumulators = {}
        self._last_live_update_time = 0.0

    def _get_stream_accumulator(self, panel_id: str = None) -> str:
        key = panel_id or "__main__"
        return self._stream_accumulators.get(key, "")

    def _set_stream_accumulator(self, value: str, panel_id: str = None):
        key = panel_id or "__main__"
        self._stream_accumulators[key] = value

    def _reset_stream_accumulator(self, panel_id: str = None):
        key = panel_id or "__main__"
        self._stream_accumulators[key] = ""

    def _safe_call(self, func, *args, **kwargs):
        """Call a function safely depending on whether we are in the main thread or not."""
        if threading.current_thread() is threading.main_thread():
            func(*args, **kwargs)
        else:
            self.app.call_from_thread(func, *args, **kwargs)

    def _get_chat_log(self, panel_id: str = None):
        """Retorna el ChatLogWidget para el panel indicado, o el chat_log principal."""
        if not panel_id:
            return self.app.chat_log
        if hasattr(self.app, panel_id):
            return getattr(self.app, panel_id)
        try:
            return self.app.query_one(f"#{panel_id}")
        except Exception:
            return self.app.chat_log

    def print_message(
        self,
        message: str,
        style: str = "",
        is_user_message: bool = False,
        status: str = None,
        use_bubble: bool = False,
        **kwargs,
    ):
        panel_id = kwargs.get("panel_id")
        target_log = self._get_chat_log(panel_id)
        if is_user_message:
            self._safe_call(target_log.write_user_message, message)
        else:
            # Si el mensaje contiene markup Rich (ej. [#color]texto[/#color]), lo convertimos
            # a un objeto Text para que RichLog (que tiene markup=False) lo renderice correctamente.
            from rich.text import Text

            if isinstance(message, str) and ("[" in message and "]" in message):
                try:
                    renderable = Text.from_markup(message)
                    self._safe_call(target_log.write_message, renderable)
                    return
                except Exception:
                    # Si el markup de Rich falla (ej. corchetes como [Error: ...]), limpiamos tags Rich y escribimos el texto limpio
                    clean_msg = re.sub(
                        r'\[/?(dim|italic|bold|reverse|underline|cyan|red|green|yellow|blue|magenta|white|black)(?:\s+[a-z0-9_#-]+)*\]|\[/\]',
                        '',
                        message,
                        flags=re.IGNORECASE
                    )
                    self._safe_call(target_log.write_agent_message, clean_msg)
                    return
            self._safe_call(target_log.write_agent_message, message)

    def print_stream(self, text: str, **kwargs):
        """
        Imprime un fragmento de texto en la consola sin añadir nueva línea,
        y limpia el buffer inmediatamente (streaming real).
        """
        self.write_stream_to_chat(text, **kwargs)

    def write_stream_to_chat(self, content: str, **kwargs):
        """Imprime contenido en streaming directamente al chat log con manejo de cursor."""
        if not content:
            return

        panel_id = kwargs.get("panel_id")
        import time
        # Solo suprimir stream del agente principal si hay live_update reciente
        if panel_id or time.time() - self._last_live_update_time > 2.0:
            accumulated = self._get_stream_accumulator(panel_id) + content
            self._set_stream_accumulator(accumulated, panel_id)

            if panel_id:
                def _update_panel():
                    try:
                        panel = self._get_chat_log(panel_id)
                        # ChatLogWidget (VerticalScroll) usa write_stream; Static/ToolOutputWidget usa update
                        from kogniterm.terminal.tui.components.chat_log import ChatLogWidget

                        if isinstance(panel, ChatLogWidget):
                            panel.write_stream(accumulated)
                        elif hasattr(panel, "update"):
                            panel.update(accumulated)
                    except Exception:
                        pass

                self._safe_call(_update_panel)
                return

            # Limpiar el cursor previo si existe antes de escribir nuevo texto
            if self.app._cursor_active:
                # RichLog no permite borrar caracteres individuales fácilmente,
                # pero podemos escribir el contenido nuevo y el cursor se moverá al final.
                pass

            self._safe_call(self.app.chat_log.write_stream, accumulated)

    def update_live(self, renderable, **kwargs):
        """Actualiza el contenido en streaming."""
        panel_id = kwargs.get("panel_id")
        import time
        if not panel_id:
            self._last_live_update_time = time.time()
        self._safe_call(self.app.update_live_display, renderable, panel_id)

    def update_terminal_output(self, tool_name: str, output: str, **kwargs):
        """Actualiza específicamente la terminal con soporte de cursor."""
        # Optional panel routing if supported
        command = kwargs.get("command", tool_name)
        self._safe_call(
            self.app.update_terminal_output, tool_name, output, command=command
        )

    def update_tool_display(
        self, tool_name: str, output: str, command: str = "", max_lines=None, **kwargs
    ):
        """Escribe la salida final de una herramienta en el chat log de la TUI o de un panel."""
        if not output or not getattr(self, "app", None):
            return

        panel_id = kwargs.get("panel_id")
        target_log = self._get_chat_log(panel_id)

        def _save_and_update():
            self.app._last_terminal_tool_name = tool_name
            self.app._last_terminal_output = output

        self._safe_call(_save_and_update)

        # Truncar solo si se especificó explícitamente un límite
        if max_lines is not None:
            lines = output.splitlines()
            if len(lines) > max_lines:
                displayed = "\n".join(lines[-max_lines:])
            else:
                displayed = output
        else:
            displayed = output

        self._safe_call(
            target_log.write_tool_output,
            displayed,
            tool_name,
            language=command or None,
        )

    def update_task_tracker(self, agent_plans: dict):
        """Actualiza el panel de seguimiento de tareas."""
        self._safe_call(self.app.update_task_tracker, agent_plans)

    def stop_live(self, **kwargs):
        """Finaliza el streaming y consolida el mensaje."""
        panel_id = kwargs.get("panel_id")
        self._reset_stream_accumulator(panel_id)
        if not panel_id:
            self._last_live_update_time = 0.0
        if panel_id:
            # Si hay panel_id, detener streaming en ese panel específico
            def _stop():
                try:
                    panel = self._get_chat_log(panel_id)
                    if hasattr(panel, "stop_stream"):
                        panel.stop_stream()
                except Exception:
                    pass

            self._safe_call(_stop)
            return
        self._safe_call(self.app.hide_live_display)

    def resume_spinner(self):
        """Reactiva el spinner de procesamiento si el agente está procesando.
        Se usa cuando las herramientas terminan y el LLM aún no ha respondido.
        """
        self._safe_call(self.app._resume_spinner)

    def print_tool_notification(
        self, tool_name: str, action_desc: str = "", skill_name: str = "", **kwargs
    ):
        """Muestra notificación de herramienta ejecutándose, alineada a la izquierda o en panel."""
        panel_id = kwargs.get("panel_id")
        target_log = self._get_chat_log(panel_id)
        self._safe_call(
            target_log.write_tool_notification, tool_name, action_desc, skill_name
        )

    def print_background_task_notification(self, task_info: dict, **kwargs):
        """Notifica sobre el estado o cambio de una tarea en segundo plano."""
        panel_id = kwargs.get("panel_id")
        target_log = self._get_chat_log(panel_id)
        task_id = task_info.get("task_id", "task")
        status = task_info.get("status", "running")
        cmd = task_info.get("command", "")
        msg = f"⚙️ [Segundo Plano] Tarea **{task_id}** ({status.upper()}): `{cmd}`"
        self._safe_call(target_log.write_message, msg, style="cyan")

    def print_success_box(self, message: str, title: str = "Éxito", **kwargs):
        panel_id = kwargs.get("panel_id")
        target_log = self._get_chat_log(panel_id)
        self._safe_call(
            target_log.write_message, f"✅ [box] **{title}**: {message}", style="green"
        )

    def print_error_box(self, message: str, title: str = "Error", **kwargs):
        panel_id = kwargs.get("panel_id")
        target_log = self._get_chat_log(panel_id)
        self._safe_call(
            target_log.write_message, f"❌ [box] **{title}**: {message}", style="red"
        )

    def print_warning_box(self, message: str, title: str = "Advertencia", **kwargs):
        panel_id = kwargs.get("panel_id")
        target_log = self._get_chat_log(panel_id)
        self._safe_call(
            target_log.write_message, f"⚠️ [box] **{title}**: {message}", style="yellow"
        )

    def print_status(self, message: str, spinner_style: str = "dots"):
        import contextlib

        @contextlib.contextmanager
        def dummy_status():
            yield

        return dummy_status()

    def print_confirmation_panel(self, content, title, border_style):
        self._safe_call(self.app.chat_log.write_message, f"⚠️ [Confirma] {title}")

    def get_interrupt_queue(self):
        return self.interrupt_queue

    def set_terminal_cursor(self, active: bool, executor=None):
        """Activa o desactiva el cursor visual de terminal en la TUI."""
        self._safe_call(self.app.set_terminal_cursor, active, executor)

    def handle_resize(self):
        pass

    def get_terminal_dimensions(self) -> tuple[int, int]:
        """Retorna las dimensiones actuales del widget de chat/terminal."""
        try:
            log = self.app.chat_log
            if log and log.size.width > 0:
                # Restamos márgenes para evitar wrapping prematuro en Textual
                cols = max(40, log.size.width - 2)
                rows = max(12, log.size.height - 2)
                return cols, rows
        except Exception:
            pass
        # Fallback a shutil si no está disponible
        import shutil
        size = shutil.get_terminal_size(fallback=(120, 30))
        return max(40, int(size.columns)), max(12, int(size.lines))

    async def ask_radiolist_async(self, title, text, values, default=None):
        from .components.settings_modals import TextualRadioListModal

        return await self.app.push_screen_wait(
            TextualRadioListModal(title, text, values, default)
        )

    async def ask_input_async(self, title, text, password=False):
        from .components.settings_modals import TextualInputModal

        return await self.app.push_screen_wait(TextualInputModal(title, text, password))

    async def ask_message_async(self, title, text):
        from .components.settings_modals import TextualMessageModal

        return await self.app.push_screen_wait(TextualMessageModal(title, text))

    def ask_approval_sync(
        self,
        message: str,
        title: str = "Aprobación Requerida",
        diff_content: str = "",
        file_path: str = "",
    ) -> bool:
        """
        Pide aprobación al usuario de forma SÍNCRONA (bloqueando el hilo que llama).
        Útil para el hilo del agente que espera la respuesta del usuario.
        """
        return self.app.ask_for_approval_sync(
            message=message,
            title=title,
            diff_content=diff_content,
            file_path=file_path,
        )

    def ask_question_sync(
        self,
        question: str,
        options: list,
        title: str = "Consulta del Agente",
        allow_freeform: bool = True,
    ) -> str:
        """Pide al usuario que seleccione una opción usando el modal gráfico de forma SÍNCRONA."""
        return self.app.ask_question_sync(
            question=question,
            options=options,
            title=title,
            allow_freeform=allow_freeform,
        )

    async def ask_approval_async(
        self,
        message: str,
        title: str = "Aprobación Requerida",
        diff_content: str = "",
        file_path: str = "",
    ) -> bool:
        """Pide aprobación al usuario usando un modal en la TUI de forma asíncrona."""
        return await self.app.ask_for_approval_async(
            message=message,
            title=title,
            diff_content=diff_content,
            file_path=file_path,
        )

    def clear_chat(self):
        """Limpia visualmente el chat log y vuelve a mostrar la pantalla de bienvenida (splash)."""

        def _do_clear():
            self.app.chat_log.clear()
            try:
                splash = self.app.query_one("#splash_overlay")
                splash.display = True
                self.app._splash_visible = True
                try:
                    splash_input = self.app.query_one("#splash_chat_input")
                    splash_input.value = ""
                    splash_input.focus()
                except Exception:
                    pass
                try:
                    bottom_container = self.app.query_one("#bottom_container")
                    bottom_container.display = False
                except Exception:
                    pass
            except Exception:
                self._do_print_banner()

        self._safe_call(_do_clear)

    def print_welcome_banner(self):
        """Programa el banner para ejecutarse después del primer layout (dimensiones reales)."""
        self.app.call_after_refresh(self._do_print_banner)

    def _do_print_banner(self):
        """Escribe el banner centrado usando padding manual con ancho real del widget."""
        banner_text = (
            "░█░█░█▀█░█▀▀░█▀█░▀█▀░▀█▀░█▀▀░█▀▄░█▄█\n"
            "░█▀▄░█░█░█░█░█░█░░█░░░█░░█▀▀░█▀▄░█░█\n"
            "░▀░▀░▀▀▀░▀▀▀░▀░▀░▀▀▀░░▀░░▀▀▀░▀░▀░▀░▀"
        )

        from rich.text import Text
        from kogniterm.terminal.themes import ColorPalette

        log = self.app.chat_log

        # Ancho real del widget (ya tiene dimensiones tras el primer layout)
        widget_w = log.size.width
        if widget_w <= 0:
            import shutil

            widget_w = shutil.get_terminal_size().columns
        # El RichLog tiene padding: 0 1, descontar 2 cols (1 cada lado)
        available_w = max(widget_w - 2, 20)

        # Medir el ancho del banner (la línea más larga)
        banner_lines = banner_text.split("\n")
        banner_w = max(len(line) for line in banner_lines)

        # Calcular el padding izquierdo para centrar
        left_pad = max((available_w - banner_w) // 2, 0)

        color = ColorPalette.PRIMARY

        # Construir el bloque completo como un único objeto Text para evitar
        # que Rich/Textual renderice múltiples fragmentos por separado (esto
        # puede producir 'franjas' visuales en algunos terminales tras limpiar).
        padded_lines = [" " * left_pad + line for line in banner_lines]
        combined = "\n".join(padded_lines)

        # Escribir el banner como un único Text
        banner_text_obj = Text(combined, style=color)

        # Escribir línea en blanco superior, luego el banner y otra línea vacía
        log.write("")
        log.write(banner_text_obj)
        log.write("")
        log.scroll_end(animate=False)


class QueueDisplay(Static):
    """
    Muestra la cola de mensajes que están esperando a ser procesados.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.display = False
        self.can_focus = False

    def update_queue(self, messages: list):
        if not messages:
            self.update("")
            self.display = False
        else:
            self.display = True

            # Limitar número de mensajes mostrados si hay demasiados
            max_show = 3
            display_msgs = messages[:max_show]

            # Truncar cada mensaje si es muy largo y reemplazar saltos de línea por espacios
            max_len = 60
            text_lines = []
            for i, m in enumerate(display_msgs):
                m_single = m.replace("\n", " ").replace("\r", "")
                if len(m_single) > max_len:
                    m_single = m_single[:max_len] + "..."

                prefix = "⏳ En cola: " if i == 0 else "⏳ "
                line_text = Text(prefix)
                line_text.append(m_single, style="italic")
                text_lines.append(line_text)

            if len(messages) > max_show:
                more_text = Text(f" ... y {len(messages) - max_show} más", style="dim")
                text_lines.append(more_text)

            content = Text("\n").join(text_lines)
            self.update(content)


class KogniTermTUI(App):
    """Aplicación principal de Textual para KogniTerm."""

    # El ratón se activa por defecto para permitir interacciones con botones.
    # Se puede desactivar con %mouse para permitir selección nativa de la terminal.
    mouse_support = True

    CSS = """
    Screen {
        background: #1e1e1e;
        color: white;
        layers: base approval splash popup overlay;
    }

    /* ── CHAT MODE (base layer) ─────────────────── */
    #approval_container {
        layer: approval;
        dock: bottom;
        height: auto;
        width: 100%;
        layout: vertical;
        align-horizontal: center;
        background: #1e1e1e;
        border-top: none; /* Linea divisora erradicada */
        margin-bottom: 9; /* Ajustado de 7 a 9 por el incremento del input_container */
    }


    #chat_container {
        height: 1fr;
        width: 100%;
        align-horizontal: center;
        background: transparent;
    }

    #chat_log {

        width: 85%;
        max-width: 180;
        min-width: 60;
        height: auto;
        max-height: 1fr;
        padding: 0;
        background: transparent;
        color: white;
        scrollbar-size: 1 1; /* Scrollbar angosto de 1 celda */
        border: none;
    }


    #bottom_container {
        dock: bottom;
        height: auto;
        width: 100%;
        layout: vertical;
        align: center bottom;
        background: transparent;
        padding-bottom: 2;
        display: none;
    }

    /* Contenedor para paneles paralelos con pestañas (call_agents_parallel) */
    #parallel_agents_container {
        width: 85%;
        max-width: 180;
        min-width: 60;
        height: 24; /* Altura fija para contener las pestañas + contenido */
        align: center bottom;
        padding: 0;
        margin: 0;
        background: transparent;
        display: none; /* activarse dinámicamente desde el skill */
    }

    /* Paneles internos del contenedor paralelo */
    #parallel_agents_container ChatLogWidget {
        width: 100%;
        height: 100%;
        margin: 0;
        padding: 0 1;
        background: transparent;
        overflow-y: scroll;
        border: none;
    }

    #parallel_agents_container TabPane {
        height: 1fr;
        background: transparent;
    }

    #parallel_agents_container ContentSwitcher {
        background: transparent;
    }

    #queue_display {
        width: 85%;
        max-width: 180;
        min-width: 60;
        height: auto;
        background: transparent;
        color: #d1d5db;
        border: none;
        padding: 0 4;
        margin-bottom: 0;
        display: none;
    }

    #input_container {
        width: 85%;
        max-width: 180;
        min-width: 60;
        height: auto;
        min-height: 3;
        background: #2a2a2a;
        margin: 0 0 1 0;
        padding: 1 4 2 4;
        layout: horizontal;
    }

    ChatInput {
        width: 1fr;
        height: auto;
        min-height: 2;
        border: none !important;
        background: transparent !important;
        padding: 0;
        margin: 0;
        color: $text;
    }
    ChatInput .text-area--cursor-line,
    ChatInput .text-area--background,
    ChatInput .text-area--selection {
        background: transparent !important;
    }
    ChatInput:focus {
        background: transparent !important;
        border: none !important;
        outline: none !important;
    }
    StatusFooter {
        width: 85%;
        max-width: 180;
        min-width: 60;
        height: 1;
        padding: 0;
        margin: 0;
        layout: horizontal;
    }
    #footer_left {
        width: 1fr;
        content-align: left top;
        padding: 0;
    }
    #footer_middle {
        width: 1fr;
        content-align: center top;
        padding: 0;
    }
    #footer_right {
        width: 1fr;
        content-align: right top;
        padding: 0;
        display: block;
    }
    TerminalPanel {
        width: 85%;
        max-width: 180;
        min-width: 60;
        border: solid #4b5563;
        background: #000000;
        height: auto;
        min-height: 0;
        max-height: 100%;
        margin: 0 4 1 4;
        padding: 0;
        content-align: left top;
        text-align: left;
        overflow-y: scroll;
        scrollbar-gutter: stable;
        display: none;
    }

    TerminalPanel:focus {
        border: none;
    }

    TerminalPanel.interactive {
        border-left: tall #10b981;
        padding-left: 2;
    }

    #command_popup {
        position: absolute;
        layer: popup;
        height: auto;
        max-height: 45;
        background: #1e1e2e;
        border: tall #3b82f6;
        padding: 0;
        display: none;
    }

    #command_popup ListView {
        background: transparent;
        border: none;
        padding: 0;
    }

    #command_popup ListItem {
        background: transparent;
        padding: 0 1;
        color: #e2e8f0;
    }

    #command_popup ListItem:hover,
    #command_popup ListItem.-highlight {
        background: #3b82f6 30%;
        color: white;
    }

    /* ── BARRA DE PROGRESO DE INDEXACIÓN ────────── */
    #indexing_progress_container {
        dock: bottom;
        height: 2;
        width: 100%;
        background: #11111b;
        border-top: solid #374151;
        display: none;
    }
    #indexing_label {
        width: 100%;
        height: 1;
        color: #9ca3af;
        text-align: center;
        background: transparent;
    }

    /* ── BARRA DE SESIONES (pestañas superiores, mismo workspace) ─── */
    #sessions_bar {
        dock: top;
        height: 2;
        width: 100%;
        background: transparent;
        border-bottom: solid #374151;
        layout: horizontal;
        padding: 0 1;
    }
    #sessions_list {
        width: 1fr;
        height: 1;
        layout: horizontal;
        background: transparent;
        padding: 0;
    }
    .session-tab-wrap {
        width: auto;
        height: 1;
        layout: horizontal;
        background: transparent;
    }
    .session-tab {
        width: auto;
        min-width: 16;
        max-width: 36;
        height: 1;
        margin: 0;
        padding: 0 1 0 2;
        background: transparent;
        color: #9ca3af;
        border: none;
    }
    .session-tab:hover {
        background: #ffffff 10%;
    }
    .session-close {
        width: 3;
        min-width: 3;
        height: 1;
        margin: 0 1 0 0;
        padding: 0;
        background: transparent;
        color: #6b7280;
        border: none;
    }
    .session-close:hover {
        background: #ef4444 45%;
        color: #ffffff;
        text-style: bold;
    }
    .session-tab.--active {
        background: #3b82f6;
        color: white;
        text-style: bold;
    }
    .session-tab.--busy {
        color: #fbbf24;
    }
    .session-tab.--active.--busy {
        background: #3b82f6;
        color: #fef3c7;
    }
    #new_session_btn {
        width: auto;
        min-width: 3;
        height: 1;
        margin: 0;
        background: transparent;
        color: #10b981;
        border: none;
        text-style: bold;
    }
    #new_session_btn:hover {
        background: #10b981 30%;
    }
    #sessions_content {
        height: 1fr;
        width: 100%;
        align-horizontal: center;
        background: transparent;
    }
    .session-chat {
        width: 85%;
        max-width: 180;
        min-width: 60;
        height: 1fr;
        padding: 0;
        background: transparent;
        color: white;
        scrollbar-size: 1 1; /* Scrollbar angosto de 1 celda */
        border: none;
    }

    #live_display {
        /* Alinear texto al centro */
        text-align: center;
        content-align: center middle;
        padding-left: 0;
        margin-bottom: 1;
        border: none;
        background: transparent;
    }


    /* ── SPLASH OVERLAY (splash layer) ─────────────── */
    #splash_overlay {
        layer: splash;
        width: 100%;
        height: 100%;
        align: center middle;
        background: #1e1e1e;
    }
    #splash_inner {
        width: 80%;
        max-width: 100;
        height: auto;
        align: center middle;
    }
    #splash_title {
        width: 100%;
        content-align: center middle;
        text-align: center;
        margin-bottom: 2;
        background: transparent;
    }
    #splash_input_row {
        width: 100%;
        height: 3;
        background: #2a2a2a;
        margin-bottom: 0;
        padding: 1 4 0 4;
        align-horizontal: left;
    }
    ToolOutputWidget {
        width: 85%;
        max-width: 180;
        min-width: 60;
        height: auto;
        min-height: 5;
        max-height: 100%;
        border: solid #4b5563; /* gray */
        margin: 0 4 1 4;
        background: transparent !important;
    }

    #tool_display {
        display: none;
    }
    #chat_log ToolOutputWidget {
        width: 100%;
        max-width: 100%;
        margin: 0 0 1 0;
    }
    ChatInput#splash_chat_input {
        width: 1fr;
        height: 1;
        min-height: 1;
        max-height: 1;
        border: none;
        padding: 0;
        background: transparent !important;
        display: block;
    }
    ChatInput#splash_chat_input:focus {
        border: none;
        background: transparent !important;
    }
    #splash_model_info {
        width: 100%;
        height: 2;
        padding: 0 4;
        background: #2a2a2a;
        margin-bottom: 2;
        content-align: left top;
    }
    #splash_shortcuts {
        width: 100%;
        content-align: center middle;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        llm_service=None,
        command_executor=None,
        agent_state=None,
        workspace_directory=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.llm_service = llm_service
        self.command_executor = command_executor
        self.agent_state = agent_state
        self.workspace_directory = workspace_directory
        self.tui_ui = TextualTerminalUI(self)
        self._splash_visible = True  # controla si el splash está activo

        # Asignar el terminal_ui después de inicializarlo
        if self.command_executor:
            self.command_executor.terminal_ui = self.tui_ui
        if self.llm_service:
            self.llm_service.terminal_ui = self.tui_ui
            self.llm_service.interrupt_queue = self.tui_ui.get_interrupt_queue()
        # ── Multisesión con pestañas (mismo workspace/proyecto) ──────────
        # Cada sesión tiene su propio thread, AgentState, cola de
        # interrupción, interaction manager y ChatLogWidget. El LLMService y
        # el CommandExecutor se comparten. Ver session.py.
        self._sessions = {}
        self._session_order = []
        self._active_session_id = None
        self._session_counter = 0
        self._session_id_prefix = "s"
        self._is_processing_queue = False
        # Spinner animado en las etiquetas de las pestañas ocupadas
        self._session_spinner_frame = 0
        self._session_spinner_timer = None
        # Marquesina del título al pasar el ratón por una pestaña
        self._hover_tab_id = None
        self._marquee_tick = 0
        self._marquee_timer = None
        self._marquee_width = 20
        self._marquee_dwell = 4
        # Estado interno del spinner animado
        self._spinner_frame = 0
        self._spinner_timer = None
        self._last_live_renderable = None
        self._spinner_paused = (
            False  # Flag para saber si el spinner fue pausado por streaming
        )

        try:
            from kogniterm.core.thread_manager import ThreadManager

            self.thread_manager = ThreadManager(
                self.workspace_directory or os.getcwd()
            )
        except Exception:
            self.thread_manager = None

        # Inyectar thread_manager en llm_service para que cada mutación del
        # historial se persista también en el hilo activo de ThreadManager.
        if self.thread_manager and self.llm_service:
            try:
                self.llm_service.set_thread_manager(self.thread_manager)
            except Exception:
                pass

        # Auto-crear un hilo para esta sesión si no hay ninguno activo.
        # Así, desde el primer mensaje, la conversación queda guardada y
        # puede recuperarse con /resume sin necesidad de hacer /thread save.
        if self.thread_manager and not self.thread_manager.get_current_thread_id():
            try:
                self.thread_manager.create_thread(title="Nueva conversación")
            except Exception:
                pass

        try:
            from kogniterm.core.session_manager import SessionManager

            self.session_manager = SessionManager(
                self.workspace_directory or os.getcwd(),
                thread_manager=self.thread_manager,
            )
        except Exception:
            self.session_manager = None

        try:
            from kogniterm.terminal.meta_command_processor import MetaCommandProcessor

            self.meta_command_processor = MetaCommandProcessor(
                self.llm_service, self.agent_state, self.tui_ui, self
            )
        except Exception:
            self.meta_command_processor = None

        try:
            from kogniterm.terminal.tui.command_processor import TUICommandProcessor

            self.command_processor = TUICommandProcessor(self)
        except Exception:
            self.command_processor = None

        # Inicializar CommandApprovalHandler solo si el componente está disponible
        try:
            if CommandApprovalHandler is not None:
                self.command_approval_handler = CommandApprovalHandler(
                    self.llm_service,
                    self.command_executor,
                    None,
                    self.tui_ui,
                    self.agent_state,
                    self.llm_service.get_tool("file_update")
                    if self.llm_service
                    else None,
                    (
                        self.llm_service.get_tool("advanced_file_editor")
                        or self.llm_service.get_tool("advanced_file_editor_tool")
                    )
                    if self.llm_service
                    else None,
                    self.llm_service.get_tool("file_operations")
                    if self.llm_service
                    else None,
                )
            else:
                self.command_approval_handler = None
        except Exception:
            self.command_approval_handler = None

        # Inicializar AgentInteractionManager si está disponible
        try:
            if AgentInteractionManager is not None:
                self.agent_interaction_manager = AgentInteractionManager(
                    self.llm_service,
                    self.agent_state,
                    self.tui_ui,
                    self.tui_ui.get_interrupt_queue() if self.tui_ui else None,
                    self.command_approval_handler,
                )
            else:
                self.agent_interaction_manager = None
        except Exception:
            self.agent_interaction_manager = None

        # Atributos para interactividad de terminal y cursor
        self.interactive_executor = None
        self._cursor_active = False
        self._cursor_frame = 0
        self._cursor_timer = None
        self._last_terminal_tool_name = ""
        self._last_terminal_output = ""
        self._completion_input = None  # Input widget para autocompletado
        self._tool_panel_explicitly_shown = False

        # ── Modo híbrido cliente-servidor ──────────────────────────────────────
        # Cuando _server_mode es True, todos los mensajes del usuario se envían
        # al servidor KogniTerm vía WebSocket. Si el servidor no está disponible
        # al arranque, permanecemos en modo local (False) sin cambiar nada.
        self._server_mode: bool = False
        self._ws_client: Optional["TUIWebSocketClient"] = None  # type: ignore[name-defined]
        self._ws_task: Optional[asyncio.Task] = None
        self._server_url: str = _DEFAULT_SERVER_URL
        self._session_id: str = _DEFAULT_SESSION_ID

    BINDINGS = [
        ("ctrl+t", "toggle_mouse", "Mouse Tracking"),
        ("shift+tab", "toggle_auto_approve", "Auto-aprobación"),
        ("ctrl+n", "new_session", "Nueva sesión"),
        ("ctrl+w", "close_session", "Cerrar sesión"),
        # ctrl+pageup/pagedown no los emite la mayoría de terminales;
        # alt+left/right sí (ESC[1;3D / ESC[1;3C).
        ("ctrl+pageup", "prev_session", "Sesión anterior"),
        ("ctrl+pagedown", "next_session", "Sesión siguiente"),
        ("alt+left", "prev_session", "Sesión anterior"),
        ("alt+right", "next_session", "Sesión siguiente"),
    ]

    # ── Propiedades de compatibilidad multisesión ─────────────────────
    # `chat_log`, `is_processing` y `_input_queue` reflejan la sesión
    # activa para que todo el código legacy (spinners, ws_client,
    # meta-comandos, tests) siga funcionando sin cambios.

    @property
    def chat_log(self):
        override = self.__dict__.get("_chat_log_override")
        if override is not None:
            return override
        session = self.get_active_session()
        if session is not None:
            widget = self._session_widget(session)
            if widget is not None:
                return widget
        return None

    @chat_log.setter
    def chat_log(self, value):
        self.__dict__["_chat_log_override"] = value

    @property
    def is_processing(self) -> bool:
        session = self.get_active_session()
        if session is not None:
            return bool(session.is_processing)
        return bool(self.__dict__.get("_is_processing_fallback", False))

    @is_processing.setter
    def is_processing(self, value: bool):
        session = self.get_active_session()
        if session is not None:
            session.is_processing = bool(value)
        else:
            self.__dict__["_is_processing_fallback"] = bool(value)

    @property
    def _input_queue(self) -> list:
        session = self.get_active_session()
        if session is not None:
            return session.input_queue
        fallback = self.__dict__.get("_input_queue_fallback")
        if fallback is None:
            fallback = []
            self.__dict__["_input_queue_fallback"] = fallback
        return fallback

    @_input_queue.setter
    def _input_queue(self, value: list):
        session = self.get_active_session()
        if session is not None:
            session.input_queue = list(value or [])
        else:
            self.__dict__["_input_queue_fallback"] = list(value or [])

    def _build_splash_title(self) -> str:
        """Retorna el título ASCII para el splash centrado como markup Rich."""
        from kogniterm.terminal.themes import ColorPalette

        c = ColorPalette.PRIMARY
        lines = [
            "░█░█░█▀█░█▀▀░█▀█░▀█▀░▀█▀░█▀▀░█▀▄░█▄█",
            "░█▀▄░█░█░█░█░█░█░░█░░░█░░█▀▀░█▀▄░█░█",
            "░▀░▀░▀▀▀░▀▀▀░▀░▀░▀▀▀░░▀░░▀▀▀░▀░▀░▀░▀",
        ]
        return "\n".join(f"[{c}]{line}[/{c}]" for line in lines)

    def compose(self) -> ComposeResult:
        from textual.widgets import Static
        from textual.containers import Vertical

        # ── Base layer: chat interface ──────────────────────
        with Vertical(id="chat_container"):
            # Barra superior de pestañas de sesión (mismo workspace) + botón "+"
            with Horizontal(id="sessions_bar"):
                with Horizontal(id="sessions_list"):
                    pass
                yield Button(
                    "+", id="new_session_btn", tooltip="Nueva sesión (Ctrl+N)"
                )
            # Contenido: un ChatLogWidget por sesión (solo visible la activa)
            with Vertical(id="sessions_content"):
                pass

        self.approval_container = Vertical(id="approval_container")
        yield self.approval_container

        self.command_popup = ListView(id="command_popup")
        yield self.command_popup

        with Vertical(id="bottom_container"):
            # Panel de queue (mensajes en espera)
            self.queue_display = QueueDisplay(id="queue_display")
            yield self.queue_display

            # live_display ahora es un TerminalPanel enfocalbe
            self.live_display = TerminalPanel(id="live_display")
            yield self.live_display

            # Contenedor para paneles paralelos con pestañas (vacío por defecto,
            # se puebla dinámicamente por call_agents_parallel)
            yield TabbedContent(id="parallel_agents_container")

            # Nota: tracker_container se yield fuera de bottom_container (ver abajo)

            with Horizontal(id="input_container"):
                self.chat_input = ChatInput(id="chat_input")
                yield self.chat_input
            self.status_footer = StatusFooter(model_name=self.llm_service.model_name)
            yield self.status_footer

        # Barra de progreso de indexación (docked bottom of screen)
        with Vertical(id="indexing_progress_container"):
            yield Static("", id="indexing_label", markup=True)

        # ── Splash overlay ──────────────────────────────────
        with Vertical(id="splash_overlay"):
            with Vertical(id="splash_inner"):
                yield Static(
                    self._build_splash_title(),
                    id="splash_title",
                    markup=True,
                )
                # Input box con borde izquierdo
                with Horizontal(id="splash_input_row"):
                    yield ChatInput(
                        id="splash_chat_input",
                    )
                # Info modelo (segunda línea del input box)
                yield Static("", id="splash_model_info", markup=True)
                # Hints de teclado
                yield Static(
                    "[dim]/models[/dim] modelo  [dim]/provider[/dim] proveedor  [dim]/mcp[/dim] mcp  [dim]/theme[/dim] tema  [dim]esc[/dim] interrumpir",
                    id="splash_shortcuts",
                    markup=True,
                )

    def update_status_footer(self, model_name: str):
        """Actualiza la información en la barra de estado inferior y el splash."""
        if hasattr(self, "status_footer"):
            self.status_footer.update_model(model_name)

        # También actualizar el splash si está visible
        try:
            model_info = self.query_one("#splash_model_info", Static)
            display_model = model_name.split("/")[-1]
            from kogniterm.terminal.themes import ColorPalette

            model_info.update(
                f"[{ColorPalette.TEXT_PRIMARY}]{display_model}[/{ColorPalette.TEXT_PRIMARY}]"
            )
        except Exception:
            pass

    def on_mount(self):
        import asyncio

        self.loop = asyncio.get_running_loop()

        from kogniterm.terminal.config_manager import ConfigManager

        config_manager = ConfigManager()
        saved_theme = config_manager.get_config("theme") or "default"
        self.apply_theme(saved_theme, persist=False)

        # Restaurar estado de auto-aprobación persistido
        try:
            saved_auto_approve = bool(config_manager.get_config("auto_approve"))
            self._auto_approve_all = saved_auto_approve
            if saved_auto_approve:
                # Sincronizar approval_handler y footer tras el primer render
                self.call_after_refresh(lambda: self.set_auto_approve_all(True))
        except Exception:
            self._auto_approve_all = False

        # Actualizar info del modelo en el splash y enfocar el input del splash
        self.call_after_refresh(self._setup_splash)

        # Inicializar multisesión (pestaña inicial del mismo workspace).
        # Se hace de forma síncrona en el hilo de la app para que el primer
        # mensaje siempre tenga una sesión y un widget válidos.
        try:
            self._init_sessions()
        except Exception as e:
            logger.error(f"Error inicializando sesiones: {e}", exc_info=True)

        # El ratón se maneja en el mount para asegurar que las secuencias se envíen.
        # force_on/off evita spam de mensajes en el inicio.
        self.call_after_refresh(
            lambda: self.action_toggle_mouse(
                force_on=self.mouse_support, force_off=not self.mouse_support
            )
        )

        # Check if workspace needs indexing and prompt user
        self.call_after_refresh(self._check_workspace_index)

        # ── Intento de conexión al servidor (modo híbrido) ──────────────────
        # Lanzamos el probe en background para no bloquear el arranque de la TUI.
        self._ws_task = asyncio.create_task(self._try_server_connect())

    # ── Lógica de modo servidor ────────────────────────────────────────────────

    async def _try_server_connect(self) -> None:
        """
        Prueba si el servidor KogniTerm está disponible y, si es así, activa
        el modo servidor iniciando un cliente WebSocket por pestaña (cada
        pestaña tiene su propia sesión remota y conversación independiente).
        """
        from kogniterm.terminal.tui.ws_client import probe_server

        available = await probe_server(self._server_url)
        if not available:
            logger.info("[Híbrido] Servidor no disponible. Usando modo local.")
            return

        logger.info("[Híbrido] Servidor disponible. Activando modo servidor.")
        self._server_mode = True
        # Conectar todas las pestañas existentes (normalmente solo la inicial)
        try:
            for session in self.list_sessions():
                self._ensure_session_client(session)
        except Exception as exc:
            logger.debug(f"No se pudieron conectar clientes de sesión: {exc}")
        # Alias legacy: cliente de la sesión activa
        self._sync_legacy_ws_alias()

        # Sincronizar el modelo activo del servidor con la TUI
        try:
            from kogniterm.terminal.api_client_tui import get_llm_config
            server_config = await get_llm_config()
            server_model = server_config.get("model")
            if server_model:
                self.update_status_footer(server_model)
        except Exception as ex:
            logger.warning(f"No se pudo sincronizar el modelo inicial del servidor: {ex}")

    def _session_server_id(self, session) -> str:
        """ID de sesión remota estable para la pestaña (conversación propia)."""
        try:
            if getattr(session, "server_session_id", None):
                return session.server_session_id
            sid = f"{self._session_id}-{session.session_id}"
            session.server_session_id = sid
            return sid
        except Exception:
            return self._session_id

    def _ensure_session_client(self, session):
        """Crea (si falta) el WebSocket de la pestaña y su tarea de conexión."""
        if session is None:
            return None
        try:
            client = getattr(session, "ws_client", None)
            if client is not None and not getattr(client, "_stopped", False):
                return client
            from kogniterm.terminal.tui.ws_client import TUIWebSocketClient

            client = TUIWebSocketClient(
                self, self._server_url, self._session_server_id(session),
                tab_id=session.session_id,
            )
            session.ws_client = client
            try:
                loop = asyncio.get_running_loop()
                session.ws_task = loop.create_task(client.run())
            except RuntimeError:
                # Sin loop activo (tests): se conectará al enviar
                session.ws_task = None
            self._sync_legacy_ws_alias()
            return client
        except Exception as exc:
            logger.debug(f"No se pudo crear WS client para pestaña: {exc}")
            return None

    def _sync_legacy_ws_alias(self):
        """Alias legacy: _ws_client/_ws_task apuntan a la pestaña activa."""
        try:
            active = self.get_active_session()
            if active is not None and getattr(active, "ws_client", None) is not None:
                self._ws_client = active.ws_client
                self._ws_task = getattr(active, "ws_task", None)
        except Exception:
            pass

    def _any_session_connected(self) -> bool:
        try:
            for session in self.list_sessions():
                client = getattr(session, "ws_client", None)
                if client is not None and bool(getattr(client, "is_connected", False)):
                    return True
        except Exception:
            pass
        return False

    def _on_tab_disconnect(self, tab_id: str, reason: str = "") -> None:
        """Aviso de desconexión de una pestaña (hilo de la app).

        Solo cae a modo local global si ninguna pestaña sigue conectada;
        si no, avisa localmente en la pestaña (su reconnect loop reintenta).
        """
        session = self.get_session(tab_id)
        if session is None:
            return
        if self._any_session_connected():
            try:
                session.ui_proxy.print_message(
                    "⚠️ Conexión al servidor perdida en esta pestaña. Reintentando…",
                    style="yellow",
                )
            except Exception:
                pass
            return
        # Sin pestañas conectadas: fallback global legacy
        self.switch_to_local_mode()

    def _on_tab_reconnect(self, tab_id: str) -> None:
        """Una pestaña recuperó su WebSocket (hilo de la app).

        No imprime nada: la desconexión ya notificó al usuario y el
        reconnect loop es silencioso (evita spam en el log de la pestaña).
        """
        if not self._server_mode:
            self.switch_to_server_mode()
        self._sync_legacy_ws_alias()

    async def _send_to_server(self, text: str, session=None) -> None:
        """Envía un mensaje al servidor vía el WebSocket DE LA PESTAÑA."""
        if session is None:
            session = self.get_active_session()
        client = None
        try:
            if self._server_mode and session is not None:
                client = self._ensure_session_client(session)
        except Exception:
            client = None
        try:
            connected = bool(client is not None and client.is_connected)
        except Exception:
            connected = False
        if not connected:
            # Sin conexión en esta pestaña: procesar en local sin tumbar
            # el modo global (el reconnect loop de la pestaña reintenta).
            logger.warning("[Híbrido] WS de pestaña no conectado. Fallback local.")
            self.process_agent_request(text, getattr(session, "session_id", None))
            return

        # _send_to_server ya corre en el loop de Textual (desde _handle_input_async),
        # por lo que podemos llamar métodos de UI directamente.
        session.is_processing = True
        try:
            self._start_spinner_for_session(session.session_id)
        except Exception:
            pass
        await client.send_message(text)

    def switch_to_local_mode(self) -> None:
        """Cambia la TUI al modo local autónomo."""
        if self._server_mode:
            self._server_mode = False
            # Desactivar cursor de terminal interactiva si estuviera activo
            self.set_terminal_cursor(False)
            self.tui_ui.print_message(
                "🔌 Conexión al servidor perdida. Cambiando al modo local autónomo.",
                "yellow",
            )
            # Actualizar barra de estado con el modelo local
            self.update_status_footer(self.llm_service.model_name)

    def switch_to_server_mode(self) -> None:
        """Cambia la TUI al modo servidor activo."""
        if not self._server_mode:
            self._server_mode = True
            self.tui_ui.print_message(
                "🔗 Conectado al servidor KogniTerm (modo servidor activo).",
                "green",
            )

    # ── Workspace indexing check ───────────────────────────────────────────────

    def _check_workspace_index(self):
        """Comprueba en background si el workspace está indexado.

        Abrir ChromaDB puede tardar varios segundos (carga del modelo de
        embeddings en el primer uso), así que NUNCA se hace en el event loop:
        bloquea el loop y la TUI parece colgada al arrancar. El diálogo se
        muestra desde el hilo de la app cuando haya respuesta.
        """
        if self.workspace_directory is None:
            self.workspace_directory = os.getcwd()

        def _worker():
            needs_index = False
            try:
                from kogniterm.core.context.vector_db_manager import VectorDBManager

                vdb = VectorDBManager(self.workspace_directory)
                try:
                    needs_index = not vdb.is_indexed()
                finally:
                    try:
                        vdb.close()
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"No se pudo comprobar el estado de indexación: {e}")
                return
            if needs_index:
                self.call_from_thread(self._prompt_workspace_index)

        try:
            threading.Thread(
                target=_worker, daemon=True, name="kogniterm-index-check"
            ).start()
        except Exception as e:
            logger.debug(f"No se pudo lanzar el chequeo de indexación: {e}")

    def _prompt_workspace_index(self):
        """Muestra el modal de indexación (debe correr en el hilo de la app)."""
        try:
            self.push_screen(
                IndexingConfirmModal(
                    title="Inicializar contexto del proyecto",
                    message="¿Desea inicializar el espacio de trabajo para este proyecto? Esto generará la memoria de contexto (.kogniterm/llm_context.md) mediante investigación autónoma e indexará el código para búsquedas inteligentes. (Equivale a ejecutar el comando /init)",
                ),
                self._on_indexing_confirmation,
            )
        except Exception as e:
            logger.error(f"No se pudo mostrar el modal de indexación: {e}")

    def _on_indexing_confirmation(self, should_index: bool):
        """Handle response from indexing confirmation modal."""
        if should_index:
            # Transition to chat screen first so they can see everything
            self._splash_visible = False
            try:
                self.query_one("#splash_overlay").display = False
                self.query_one("#bottom_container").display = True
                self.query_one("#chat_input", ChatInput).focus()
            except Exception:
                pass

            self._start_indexing()
            try:
                self._start_deep_research_investigation(force=False)
            except Exception as e:
                logger.error(
                    f"Error starting deep research from modal confirmation: {e}"
                )

    def _start_indexing(self):
        """Begin the indexing process."""

        # Mostrar barra de progreso en la parte inferior
        def show_ui():
            try:
                self.query_one("#indexing_progress_container").display = True
                self.query_one("#indexing_label").update(
                    "[#9ca3af]Indexando...[/#9ca3af]"
                )
            except Exception as e:
                logger.error(f"Error showing indexing progress: {e}")

        show_ui()  # Llamada directa en el hilo principal (no requiere call_from_thread)
        self.run_worker(self._do_indexing)

    def call_from_thread(self, callback, *args, **kwargs):
        """Thread-safe and main-thread-safe version of call_from_thread.

        If called from the main thread / app thread, it schedules the callback
        using call_next. Otherwise, it delegates to super().call_from_thread.
        """
        import threading

        if (
            threading.current_thread() is threading.main_thread()
            or getattr(self, "_thread_id", None) == threading.get_ident()
        ):
            self.call_next(callback, *args, **kwargs)
        else:
            super().call_from_thread(callback, *args, **kwargs)

    def _call_on_app_thread(self, func, *args, **kwargs):
        """Schedule a callback on Textual's app thread from any worker context."""
        self.call_from_thread(func, *args, **kwargs)

    async def _do_indexing(self):
        """Worker that performs indexing."""
        project_path = self.workspace_directory
        try:
            from kogniterm.core.context.codebase_indexer import CodebaseIndexer

            indexer = CodebaseIndexer(project_path)
            chunks = await indexer.index_project(
                project_path,
                show_progress=False,
                progress_callback=self._indexing_progress_callback,
            )
            if chunks:
                from kogniterm.core.context.vector_db_manager import VectorDBManager

                vdb = VectorDBManager(project_path)
                vdb.clear_collection()
                vdb.add_chunks(chunks)
                vdb.close()
                self._indexing_complete(len(chunks))
            else:
                self._indexing_complete(0)
        except Exception as e:
            self._indexing_failed(str(e))

    def _indexing_progress_callback(self, current: int, total: int, description: str):
        """Handle progress updates from indexing."""
        if total == 0:
            return
        self._show_indexing_progress(current, total, description)

    def _show_indexing_progress(self, current: int, total: int, description: str):
        """Update the progress bar at the bottom of the screen."""

        def update_ui():
            try:
                self.query_one("#indexing_progress_container").display = True
                pct = int((current / total) * 100)
                label = self.query_one("#indexing_label")
                # Barra visual: ■■■■■■░░░░
                filled = pct // 10
                empty = 10 - filled
                bar_text = (
                    f"{'[#3b82f6]■[/#3b82f6]' * filled}{'[#374151]░[/#374151]' * empty}"
                )
                label.update(f"Indexando {bar_text} {pct}%  {description}")
            except Exception as e:
                logger.error(f"Error updating indexing progress UI: {e}")

        self._call_on_app_thread(update_ui)

    def _indexing_complete(self, num_chunks: int):
        """Called when indexing completes."""

        def complete_ui():
            try:
                self.query_one("#indexing_progress_container").display = True
                label = self.query_one("#indexing_label")
                if num_chunks > 0:
                    label.update(
                        "[green]■■■■■■■■■■ 100%  Indexación completada.[/green]"
                    )
                else:
                    label.update(
                        "[yellow]Indexación completada: no se encontraron archivos relevantes.[/yellow]"
                    )
            except Exception as e:
                logger.error(f"Error updating indexing completion UI: {e}")

        self._call_on_app_thread(complete_ui)

        # Ocultar después de 3 segundos
        def hide():
            import time

            time.sleep(3)

            def hide_ui():
                try:
                    self.query_one("#indexing_progress_container").display = False
                except Exception:
                    pass

            self._call_on_app_thread(hide_ui)

        threading.Thread(target=hide, daemon=True).start()

    def _indexing_failed(self, error_msg: str):
        """Called when indexing fails."""

        def fail_ui():
            try:
                self.query_one("#indexing_progress_container").display = True
                label = self.query_one("#indexing_label")
                label.update(f"[red]Error en la indexación: {error_msg}[/red]")
            except Exception as e:
                logger.error(f"Error updating indexing failure UI: {e}")

        self._call_on_app_thread(fail_ui)

        def hide():
            import time

            time.sleep(5)

            def hide_ui():
                try:
                    self.query_one("#indexing_progress_container").display = False
                except Exception:
                    pass

            self._call_on_app_thread(hide_ui)

        threading.Thread(target=hide, daemon=True).start()

    @work(thread=True)
    def _start_deep_research_investigation(self, force: bool = False):
        """Worker that runs the DeepResearcher in the background."""
        try:
            self.tui_ui.print_message(
                "🤖 Iniciando investigación local con DeepResearcher...", style="yellow"
            )

            # 1. Asegurar que las herramientas críticas estén cargadas en el LLMService
            if hasattr(self.llm_service, "skill_manager"):
                for skill in ["file_operations", "codebase_search", "task_tracker"]:
                    try:
                        if skill not in self.llm_service.skill_manager.loaded_skills:
                            self.llm_service.skill_manager.load_skill(skill)
                    except Exception:
                        pass

            # 2. Crear el DeepResearcher
            from kogniterm.core.agents.deep_researcher import create_deep_researcher

            app = create_deep_researcher(
                llm_service=self.llm_service,
                terminal_ui=self.tui_ui,
                interrupt_queue=self.tui_ui.interrupt_queue,
            )

            # 3. Formular la consulta
            query = (
                "Realiza una investigación profunda y exhaustiva del proyecto local para generar su Memoria Contextual. "
                "Revisa la estructura de directorios, los archivos de configuración (como pyproject.toml, package.json, etc.), "
                "los módulos del core en el código fuente, los archivos de test y el README.md. "
                "Debes recopilar suficiente información para estructurar el informe final (llm_context.md) con las siguientes secciones exactas:\n"
                "1. # Memoria Contextual del Proyecto: propósito principal, tecnologías clave y alcance del proyecto.\n"
                "2. ## Arquitectura y Módulos Clave: explicación de la estructura de carpetas, responsabilidades de los módulos y flujo de ejecución.\n"
                "3. ## Comandos del Proyecto: comandos útiles de bash/npm/pytest para instalación, ejecución y pruebas.\n"
                "4. ## Convenciones y Reglas de Desarrollo: estilo de código, patrones de diseño, decisiones y reglas obligatorias."
            )

            from langchain_core.messages import HumanMessage
            from kogniterm.core.agents.deep_researcher import DeepResearchState

            initial_state = DeepResearchState()
            initial_state.messages = [HumanMessage(content=query)]

            # Ejecutar el grafo de LangGraph
            final_state = app.invoke(initial_state)

            # 4. Procesar el resultado
            if final_state and "messages" in final_state and final_state["messages"]:
                last_msg = final_state["messages"][-1]
                content = getattr(last_msg, "content", "")
                if content:
                    # Limpiar marcadores de pensamiento/razonamiento
                    import re

                    cleaned_content = content.strip()
                    cleaned_content = re.sub(
                        r"<thought>.*?</thought>",
                        "",
                        cleaned_content,
                        flags=re.DOTALL | re.IGNORECASE,
                    )
                    cleaned_content = re.sub(
                        r"<thinking>.*?</thinking>",
                        "",
                        cleaned_content,
                        flags=re.DOTALL | re.IGNORECASE,
                    )
                    cleaned_content = cleaned_content.replace("__THINKING__:", "")
                    cleaned_content = cleaned_content.replace("__THINKING__", "")
                    cleaned_content = cleaned_content.strip()

                    if cleaned_content:
                        if cleaned_content.startswith("## 🔬 Informe de Deep Research"):
                            cleaned_content = cleaned_content.replace(
                                "## 🔬 Informe de Deep Research\n\n", ""
                            )
                        elif cleaned_content.startswith(
                            "## 🔬 Informe de Investigación"
                        ):
                            cleaned_content = cleaned_content.replace(
                                "## 🔬 Informe de Investigación\n\n", ""
                            )

                        header = "<!-- Generado por KogniTerm DeepResearcher -->\n"
                        if not (
                            cleaned_content.startswith("# Memoria Contextual")
                            or cleaned_content.startswith("<!--")
                        ):
                            cleaned_content = header + cleaned_content

                        # Escribir la memoria local
                        from kogniterm.core.context.project_memory_builder import (
                            ProjectMemoryBuilder,
                        )

                        builder = ProjectMemoryBuilder(self.workspace_directory)
                        builder.write_memory_file(cleaned_content)

                        self.tui_ui.print_message(
                            "✅ Memoria contextual del proyecto guardada exitosamente en .kogniterm/llm_context.md",
                            style="green",
                        )
                        self.tui_ui.print_message(
                            "✨ ¡Inicialización completada con éxito!",
                            style="bold green",
                        )
                        return

            self.tui_ui.print_message(
                "⚠️ DeepResearcher finalizó sin generar un reporte válido.",
                style="yellow",
            )

        except Exception as e:
            import traceback

            error_trace = traceback.format_exc()
            logger.error(f"Error executing DeepResearcher in TUI: {e}\n{error_trace}")
            self.tui_ui.print_message(
                f"❌ Error durante la investigación de DeepResearcher: {e}", style="red"
            )

    def action_toggle_mouse(self, force_off: bool = False, force_on: bool = False):
        """Alterna el soporte de ratón en tiempo de ejecución o lo fuerza."""
        if force_off:
            self.mouse_support = False
        elif force_on:
            self.mouse_support = True
        else:
            self.mouse_support = not self.mouse_support

        try:
            # En Textual 0.40+, el soporte de ratón se maneja mejor a través de las propiedades
            # de la aplicación, pero para compatibilidad con selección nativa en terminales
            # que no soportan Shift+Click, permitimos este toggle.
            if not force_on and not force_off:
                status = "ACTIVADO" if self.mouse_support else "DESACTIVADO"
                self.tui_ui.print_message(
                    f"🖱️ Ratón {status} (Selección nativa habilitada si está desactivado)",
                    style="cyan",
                )
        except Exception:
            pass

    def _setup_splash(self):
        """Configura el splash tras el primer layout (dimensiones y colores reales)."""
        from kogniterm.terminal.themes import ColorPalette

        p = ColorPalette

        # Actualizar título con el color actual del tema
        try:
            title_widget = self.query_one("#splash_title")
            title_widget.styles.background = "transparent"
            title_widget.update(self._build_splash_title())
        except Exception:
            pass

        # Quitar coloreado del borde izquierdo del input y model_info (eliminado)
        try:
            input_row = self.query_one("#splash_input_row")
            input_row.styles.background = p.GRAY_800
        except Exception:
            pass

        try:
            model_info = self.query_one("#splash_model_info")
            model_info.styles.background = p.GRAY_800
            # Mostrar modo y modelo
            display_model = self.llm_service.model_name.split("/")[-1]
            model_info.update(f"[{p.TEXT_PRIMARY}]{display_model}[/{p.TEXT_PRIMARY}]")
        except Exception:
            pass

        try:
            shortcuts = self.query_one("#splash_shortcuts")
            shortcuts.styles.color = p.TEXT_MUTED
        except Exception:
            pass

        try:
            splash_overlay = self.query_one("#splash_overlay")
            splash_overlay.styles.background = p.GRAY_900
        except Exception:
            pass

        # Enfocar el input del splash
        try:
            # Buscar el widget por id en lugar de por tipo Input, ya que el
            # `ChatInput` es un `TextArea` y puede no coincidir con `Input`.
            splash_input = self.query_one("#splash_chat_input")
            splash_input.focus()
        except Exception:
            pass

    async def on_input_changed(self, event: Input.Changed):
        value = event.value
        if not value:
            self.command_popup.display = False
            self._completion_input = None
            return

        # Obtener el suggester para acceder a las listas cacheadas
        suggester = getattr(event.input, "suggester", None)

        # Determinar qué estamos buscando basándonos en el último carácter o palabra
        words = value.split()
        if not words:
            self.command_popup.display = False
            self._completion_input = None
            return

        current_word = words[-1]
        trigger = None
        search_term = ""

        stripped = value.lstrip()
        if stripped.startswith("%"):
            trigger = "%"
            search_term = stripped
        elif stripped.startswith("/"):
            trigger = "/"
            search_term = stripped
        elif "@" in current_word:
            trigger = "@"
            search_term = current_word.split("@")[-1]
        elif "#" in current_word:
            trigger = "#"
            search_term = current_word.split("#")[-1]
        elif ":" in current_word:
            trigger = ":"
            search_term = current_word.split(":")[-1]

        if trigger:
            self.command_popup.display = True
            self._completion_input = event.input  # Guardar referencia al input
            await self.command_popup.clear()

            # Posicionar el popup horizontalmente donde está el cursor del input
            self._reposition_popup(event.input, value)

            matches = []
            if trigger in ("%", "/"):
                if trigger == "%":
                    commands = [
                        "%help",
                        "%models",
                        "%provider",
                        "%mcp",
                        "%agy-login",
                        "%reset",
                        "%undo",
                        "%compress",
                        "%theme",
                        "%init",
                        "%keys",
                        "%session",
                        "%new",
                        "%tabs",
                        "%switch",
                        "%rename",
                        "%close",
                        "%resume",
                        "%salir",
                        "%mouse",
                        "%embeddings",
                        "%tema",
                        "%exit",
                        "%quit",
                        "%skills",
                        "%instructions",
                        "%insights",
                        "%reasoning",
                        "%summarize",
                        "%summarymodel",
                    ]
                else:
                    commands = [
                        "/help",
                        "/models",
                        "/provider",
                        "/mcp",
                        "/agy-login",
                        "/reset",
                        "/undo",
                        "/compress",
                        "/theme",
                        "/init",
                        "/keys",
                        "/session",
                        "/new",
                        "/tabs",
                        "/switch",
                        "/rename",
                        "/close",
                        "/resume",
                        "/salir",
                        "/mouse",
                        "/embeddings",
                        "/tema",
                        "/exit",
                        "/quit",
                        "/skills",
                        "/instructions",
                        "/insights",
                        "/reasoning",
                        "/summarize",
                        "/summarymodel",
                    ]
                matches = [cmd for cmd in commands if cmd.startswith(search_term)]
            elif trigger == "@" and suggester:
                from kogniterm.terminal.tui.components.status_footer import (
                    KogniTermSuggester,
                )

                if isinstance(suggester, KogniTermSuggester):
                    raw_matches = suggester.search_files(search_term, max_results=40)
                    matches = [
                        {
                            "name": path,
                            "display": f"{path}  [dim]{meta}[/dim]",
                        }
                        for _, path, meta in raw_matches
                    ]
            elif trigger == ":" and suggester:
                from kogniterm.terminal.tui.components.status_footer import (
                    KogniTermSuggester,
                )

                if isinstance(suggester, KogniTermSuggester):
                    containers = getattr(suggester, "_cached_containers", []) or []
                    matches = [
                        c
                        for c in containers
                        if search_term.lower() in c["name"].lower()
                    ][:12]

            # Si hay un único match y es exacto, no mostrar autocompletado
            if len(matches) == 1:
                match = matches[0]
                match_text = match["name"] if isinstance(match, dict) else match
                if match_text.lower() == search_term.lower():
                    matches = []

            for match in matches:
                # match puede ser string (comandos %) o dict (contenedores/archivos)
                if isinstance(match, dict):
                    display = match.get("display", f"{match['name']} ({match.get('status', '')})")
                    command_text = match["name"]
                else:
                    display = match
                    command_text = match
                item = ListItem(Label(display))
                item.command_text = command_text
                self.command_popup.append(item)

            if not matches:
                self.command_popup.display = False
                self._completion_input = None
            else:
                self._reposition_popup(event.input, value)
        else:
            self.command_popup.display = False
            self._completion_input = None

    async def on_text_area_changed(self, event: TextArea.Changed):
        """Handler para TextArea (ChatInput) - diferente API que Input.Changed."""
        value = event.text_area.text
        if not value:
            self.command_popup.display = False
            self._completion_input = None
            return

        # Obtener el suggester para acceder a las listas cacheadas
        suggester = getattr(event.text_area, "suggester", None)

        # Determinar qué estamos buscando basándonos en el último carácter o palabra
        words = value.split()
        if not words:
            self.command_popup.display = False
            self._completion_input = None
            return

        current_word = words[-1]
        trigger = None
        search_term = ""

        stripped = value.lstrip()
        if stripped.startswith("%"):
            trigger = "%"
            search_term = stripped
        elif stripped.startswith("/"):
            trigger = "/"
            search_term = stripped
        elif "@" in current_word:
            trigger = "@"
            search_term = current_word.split("@")[-1]
        elif "#" in current_word:
            trigger = "#"
            search_term = current_word.split("#")[-1]
        elif ":" in current_word:
            trigger = ":"
            search_term = current_word.split(":")[-1]

        if trigger:
            self.command_popup.display = True
            self._completion_input = event.text_area  # Guardar referencia al input
            await self.command_popup.clear()

            # Posicionar el popup horizontalmente donde está el cursor del input
            self._reposition_popup(event.text_area, value)

            matches = []
            if trigger in ("%", "/"):
                if trigger == "%":
                    commands = [
                        "%help",
                        "%models",
                        "%provider",
                        "%mcp",
                        "%agy-login",
                        "%reset",
                        "%undo",
                        "%compress",
                        "%theme",
                        "%init",
                        "%keys",
                        "%session",
                        "%new",
                        "%tabs",
                        "%switch",
                        "%rename",
                        "%close",
                        "%resume",
                        "%salir",
                        "%mouse",
                        "%embeddings",
                        "%tema",
                        "%exit",
                        "%quit",
                        "%skills",
                        "%instructions",
                        "%insights",
                        "%reasoning",
                        "%summarize",
                        "%summarymodel",
                    ]
                else:
                    commands = [
                        "/help",
                        "/models",
                        "/provider",
                        "/mcp",
                        "/agy-login",
                        "/reset",
                        "/undo",
                        "/compress",
                        "/theme",
                        "/init",
                        "/keys",
                        "/session",
                        "/new",
                        "/tabs",
                        "/switch",
                        "/rename",
                        "/close",
                        "/resume",
                        "/salir",
                        "/mouse",
                        "/embeddings",
                        "/tema",
                        "/exit",
                        "/quit",
                        "/skills",
                        "/instructions",
                        "/insights",
                        "/reasoning",
                        "/summarize",
                        "/summarymodel",
                    ]
                matches = [cmd for cmd in commands if cmd.startswith(search_term)]
            elif trigger == "@" and suggester:
                from kogniterm.terminal.tui.components.status_footer import (
                    KogniTermSuggester,
                )

                if isinstance(suggester, KogniTermSuggester):
                    raw_matches = suggester.search_files(search_term, max_results=40)
                    matches = [
                        {
                            "name": path,
                            "display": f"{path}  [dim]{meta}[/dim]",
                        }
                        for _, path, meta in raw_matches
                    ]
            elif trigger == "#":
                skills_info = []
                if hasattr(self, 'llm_service') and hasattr(self.llm_service, 'skill_manager') and self.llm_service.skill_manager:
                    sm = self.llm_service.skill_manager
                    skills_info = sm.get_procedural_skills() if hasattr(sm, 'get_procedural_skills') else sm.list_skills(procedural_only=True)
                matches = [
                    {
                        "name": s["name"],
                        "display": f"📋 #{s['name']}  [dim]{s.get('description', '')[:40]}[/dim]",
                    }
                    for s in skills_info
                    if s["name"].lower().startswith(search_term.lower())
                ][:20]
            elif trigger == ":" and suggester:
                from kogniterm.terminal.tui.components.status_footer import (
                    KogniTermSuggester,
                )

                if isinstance(suggester, KogniTermSuggester):
                    containers = getattr(suggester, "_cached_containers", []) or []
                    # containers es lista de dicts: {'name': ..., 'status': ..., 'image': ...}
                    matches = [
                        c
                        for c in containers
                        if search_term.lower() in c["name"].lower()
                    ][:12]  # Limitar a 12

            # Si hay un único match y es exacto, no mostrar autocompletado
            if len(matches) == 1:
                match = matches[0]
                match_text = match["name"] if isinstance(match, dict) else match
                if match_text.lower() == search_term.lower():
                    matches = []

            for match in matches:
                # match puede ser string (comandos %) o dict (contenedores/archivos)
                if isinstance(match, dict):
                    display = match.get("display", f"{match['name']} ({match.get('status', '')})")
                    command_text = match["name"]
                else:
                    display = match
                    command_text = match
                item = ListItem(Label(display))
                item.command_text = command_text
                self.command_popup.append(item)

            if not matches:
                self.command_popup.display = False
                self._completion_input = None
            else:
                self._reposition_popup(event.text_area, value)
        else:
            self.command_popup.display = False

    def _reposition_popup(self, input_widget, current_value: str) -> None:
        """Posiciona el popup justo encima del input activo ocupando el ancho completo de su contenedor."""
        try:
            screen_w = self.size.width

            target_region = input_widget.region
            try:
                container = self.query_one("#input_container")
                if container and container.visible and container.region.width > 0:
                    target_region = container.region
            except Exception:
                pass

            popup_w = max(30, min(target_region.width, screen_w))
            popup_x = target_region.x
            if popup_x + popup_w > screen_w:
                popup_x = max(0, screen_w - popup_w)

            # Posición Y: justo encima del borde superior del contenedor (target_region.y)
            items_count = len(self.command_popup.children)
            available_h_above = max(5, target_region.y - 1)
            popup_max_h = min(44, available_h_above)
            popup_h = min(popup_max_h, max(4, items_count + 2))
            popup_y = max(0, target_region.y - popup_h)

            self.command_popup.styles.height = popup_h
            self.command_popup.styles.width = popup_w
            self.command_popup.styles.offset = (popup_x, popup_y)
        except Exception:
            pass

    def _apply_completion(
        self, selected_text: str, input_widget: Input, current_val: str
    ):
        """Aplica la completación al input y cierra el popup."""
        if current_val.lstrip().startswith("%"):
            input_widget.value = selected_text + " "
        else:
            words = current_val.split()
            if words:
                last_word = words[-1]
                prefix = ""
                if "@" in last_word:
                    prefix = last_word.split("@")[0] + "@"
                elif "#" in last_word:
                    prefix = last_word.split("#")[0] + "#"
                elif ":" in last_word:
                    prefix = last_word.split(":")[0] + ":"
                suffix = "" if selected_text.endswith("/") else " "
                words[-1] = prefix + selected_text
                input_widget.value = " ".join(words) + suffix
        input_widget.cursor_position = len(input_widget.value)
        input_widget.focus()
        self.command_popup.display = False
        self._completion_input = None

    def on_list_view_selected(self, event: ListView.Selected):
        """Maneja selección con Enter o clic en el popup."""
        if event.list_view.id != "command_popup":
            return
        if event.item and hasattr(event.item, "command_text"):
            selected_text = event.item.command_text
            # Usar el input guardado
            input_widget = self._completion_input
            if not input_widget or not hasattr(input_widget, "value"):
                try:
                    input_widget = self.query_one("#chat_input")
                except:
                    input_widget = None
            if input_widget and hasattr(input_widget, "value"):
                self._apply_completion(selected_text, input_widget, input_widget.value)
            event.prevent_default()

    def on_key(self, event: events.Key):
        # 0. Atajos de pestañas: siempre tienen prioridad (incluso con PTY activo)
        if event.key in ("ctrl+n", "ctrl+w", "ctrl+pageup", "ctrl+pagedown", "alt+left", "alt+right"):
            try:
                if event.key == "ctrl+n":
                    self.action_new_session()
                elif event.key == "ctrl+w":
                    self.action_close_session()
                elif event.key in ("ctrl+pagedown", "alt+right"):
                    self.action_next_session()
                elif event.key in ("ctrl+pageup", "alt+left"):
                    self.action_prev_session()
            except Exception:
                pass
            event.prevent_default()
            event.stop()
            return

        # 1. Prioridad: Si el panel de terminal está enfocado, enviar teclas al PTY
        # Importación local para evitar circulares
        try:
            from kogniterm.terminal.tui.components.tool_output import ToolOutputWidget

            focused_widget = self.focused
            is_terminal_focused = isinstance(
                focused_widget, (TerminalPanel, ToolOutputWidget)
            )
        except ImportError:
            is_terminal_focused = False
            focused_widget = None

        is_interactive_mode = False
        if focused_widget and is_terminal_focused:
            _focus_exec = self.get_active_executor()
            if (
                (_focus_exec and getattr(_focus_exec, "process", None))
                or (self._server_mode and self.interactive_executor)
                or getattr(self, "interactive_executor", None)
                or getattr(self, "_cursor_active", False)
            ):
                is_interactive_mode = True

        if is_interactive_mode:
            # Si es escape, devolver foco al input y continuar con la interrupción si se está procesando
            if event.key == "escape":
                try:
                    self.query_one("#chat_input").focus()
                except:
                    pass
                if not self.is_processing:
                    return

            # Mapeo de teclas de Textual a secuencias PTY
            key_map = {
                "up": "\x1b[A",
                "down": "\x1b[B",
                "right": "\x1b[C",
                "left": "\x1b[D",
                "enter": "\r",
                "return": "\r",
                "space": " ",
                "tab": "\t",
                "backspace": "\x7f",
                "home": "\x1b[H",
                "end": "\x1b[F",
                "delete": "\x1b[3~",
                "pageup": "\x1b[5~",
                "pagedown": "\x1b[6~",
                "shift+tab": "\x1b[Z",
                "f1": "\x1bOP",
                "f2": "\x1bOQ",
                "f3": "\x1bOR",
                "f4": "\x1bOS",
                "f5": "\x1b[15~",
                "f6": "\x1b[17~",
                "f7": "\x1b[18~",
                "f8": "\x1b[19~",
                "f9": "\x1b[20~",
                "f10": "\x1b[21~",
                "f11": "\x1b[23~",
                "f12": "\x1b[24~",
            }

            # Executor de la pestaña a la que pertenece el widget enfocado
            # (cada pestaña tiene su propio shell persistente).
            _focus_session = self._session_for_widget(focused_widget)
            if _focus_session is not None and getattr(_focus_session, "interactive_executor", None):
                executor = _focus_session.interactive_executor
            else:
                executor = getattr(self, "interactive_executor", None) or self.get_active_executor()

            # Manejar Ctrl+Letra
            if event.key.startswith("ctrl+"):
                char = event.key.split("+")[1]
                if len(char) == 1:
                    # 'a' es 1, 'b' es 2... 'z' es 26
                    code = ord(char.lower()) - ord("a") + 1
                    if executor and hasattr(executor, "write_input"):
                        executor.write_input(bytes([code]))
                        event.prevent_default()
                        return

            to_send = key_map.get(event.key, event.character)
            if to_send:
                if executor and hasattr(executor, "write_input"):
                    executor.write_input(to_send)
                    event.prevent_default()
                    return

        if event.key == "escape":
            if self.is_processing:
                # Interrumpir la SESIÓN ACTIVA (cada pestaña tiene su cola y
                # su propio WebSocket en modo servidor)
                _esc_session = self.get_active_session()
                _esc_queue = None
                _esc_ws = None
                if _esc_session is not None:
                    _esc_queue = getattr(_esc_session, "interrupt_queue", None)
                    _esc_ws = getattr(_esc_session, "ws_client", None)
                    try:
                        if _esc_session.agent_state is not None:
                            _esc_session.agent_state.stop_requested = True
                    except Exception:
                        pass
                try:
                    _esc_connected = bool(
                        self._server_mode and _esc_ws is not None and _esc_ws.is_connected
                    )
                except Exception:
                    _esc_connected = False
                if _esc_connected:
                    # Modo servidor: enviar interrupción al backend de ESTA pestaña
                    # Usar call_later de Textual para programar la coroutine de
                    # forma segura en el event loop, evitando excepciones silenciosas.
                    self.call_later(_esc_ws.send_interrupt)
                    # También señalar la cola local como respaldo por si el
                    # WebSocket tarda en entregar la señal al hilo del agente.
                    try:
                        (_esc_queue or self.tui_ui.get_interrupt_queue()).put_nowait(True)
                    except Exception:
                        pass
                else:
                    # Modo local: usar la cola de interrupción de la sesión activa
                    try:
                        (_esc_queue or self.tui_ui.get_interrupt_queue()).put(True)
                    except Exception:
                        pass
                try:
                    (_esc_session.ui_proxy if _esc_session is not None else self.tui_ui).print_message(
                        "⏳ Solicitando interrupción...", style="yellow"
                    )
                except Exception:
                    pass
                event.prevent_default()
                return
            elif self.command_popup.display:
                self.command_popup.display = False
                self._completion_input = None
                event.prevent_default()
                return

        if self.command_popup.display:
            if event.key == "down":
                self.command_popup.action_cursor_down()
                event.prevent_default()
            elif event.key == "up":
                self.command_popup.action_cursor_up()
                event.prevent_default()
            elif event.key == "enter":
                if self.command_popup.highlighted_child:
                    item = self.command_popup.highlighted_child
                    if hasattr(item, "command_text"):
                        selected_text = item.command_text
                        input_widget = self._completion_input
                        if not input_widget or not hasattr(input_widget, "value"):
                            try:
                                input_widget = self.query_one("#chat_input")
                            except:
                                input_widget = None
                        if input_widget and hasattr(input_widget, "value"):
                            self._apply_completion(
                                selected_text, input_widget, input_widget.value
                            )
                        self.command_popup.display = False
                        event.prevent_default()

    def on_input_submitted(self, event: Input.Submitted):
        user_input = event.value
        if not user_input.strip():
            return

        # Si el input proviene de un modal u otro widget que no sea del chat, ignorar
        if getattr(event.input, "id", None) not in ("chat_input", "splash_chat_input"):
            return

        # Si el submit viene del splash, transición al modo chat
        if event.input.id == "splash_chat_input" or (getattr(self, "_splash_visible", False) is True):
            # Añadir al historial persistente ANTES de cambiar de pantalla
            if hasattr(event.input, "add_to_history"):
                event.input.add_to_history(user_input.strip())

            # Sincronizar historial desde el almacenamiento persistente
            try:
                main_input = self.query_one("#chat_input", ChatInput)
                main_input.refresh_history()
            except:
                pass

            event.input.value = ""
            self._transition_to_chat(user_input)
            return

        # Para el chat normal, añadir al historial solo si el input es del chat
        if getattr(event.input, "id", None) in ("chat_input", "splash_chat_input") and hasattr(event.input, "add_to_history"):
            event.input.add_to_history(user_input.strip())

        # Redirigir input si hay un proceso interactivo activo o la terminal está enfocada
        is_interact_mode = getattr(self, "_cursor_active", False) is True
        try:
            from kogniterm.terminal.tui.components.tool_output import ToolOutputWidget

            is_terminal_focused = isinstance(
                getattr(self, "focused", None), (TerminalPanel, ToolOutputWidget)
            )
        except Exception:
            is_terminal_focused = False

        cmd_exec = self.get_active_executor()
        proc = getattr(cmd_exec, "process", None) if cmd_exec else None
        is_proc_running = proc is not None and getattr(proc, "poll", lambda: None)() is None

        if (is_interact_mode or is_terminal_focused or is_proc_running) and cmd_exec and proc:
            cmd_exec.write_input(user_input + "\n")
            event.input.value = ""
            return

        # (El fallback anterior fue removido para evitar secuestro de input con shell persistente)

        event.input.value = ""
        # Asegurar que el input mantenga el foco tras enviarse/limpiarse
        try:
            event.input.focus()
        except Exception:
            pass

        # Sesión de origen: la pestaña activa en el momento del envío.
        # Cada pestaña tiene su propia cola y su propio flag de procesado
        # para permitir trabajo en paralelo.
        try:
            _submit_session = self.get_active_session()
            _submit_sid = _submit_session.session_id if _submit_session else None
            _busy = bool(_submit_session.is_processing) if _submit_session is not None else bool(getattr(self, "is_processing", False))
        except Exception:
            _submit_session, _submit_sid, _busy = None, None, bool(getattr(self, "is_processing", False))

        # Bloquear nuevo input si ESA pestaña ya procesa
        # PERO permitir encolar mensajes para mejor UX
        if _busy is True:
            try:
                (_submit_session.input_queue if _submit_session is not None else self._input_queue).append(user_input)
            except Exception:
                pass
            if hasattr(self, "queue_display"):
                try:
                    self.queue_display.update_queue(self._input_queue)
                except Exception:
                    pass
            return

        rw = getattr(self, "run_worker", None)
        if rw is not None:
            try:
                rw(self._handle_input_async(user_input, _submit_sid))
            except Exception:
                pass

    def on_chat_input_submitted(self, event):
        user_input = getattr(event, "value", "")
        if not user_input.strip():
            return

        # Limpiar el input inmediatamente
        if hasattr(event, "input"):
            if hasattr(event.input, "clear"):
                event.input.clear()
            elif hasattr(event.input, "text"):
                event.input.text = ""
            elif hasattr(event.input, "value"):
                event.input.value = ""

        # Si el submit viene del splash, transición al modo chat
        if getattr(self, "_splash_visible", False) is True:
            self._transition_to_chat(user_input)
            return

        # Para chat normal, añadir al historial
        if hasattr(event.input, "add_to_history"):
            event.input.add_to_history(user_input.strip())

        # Redirigir si hay terminal interactiva activa
        is_interact_mode = getattr(self, "_cursor_active", False) is True
        try:
            from kogniterm.terminal.tui.components.tool_output import ToolOutputWidget
            is_terminal_focused = isinstance(
                getattr(self, "focused", None), (TerminalPanel, ToolOutputWidget)
            )
        except Exception:
            is_terminal_focused = False

        cmd_exec = self.get_active_executor()
        proc = getattr(cmd_exec, "process", None) if cmd_exec else None
        is_proc_running = proc is not None and getattr(proc, "poll", lambda: None)() is None

        if (is_interact_mode or is_terminal_focused or is_proc_running) and cmd_exec and proc:
            cmd_exec.write_input(user_input + "\n")
            return

        # Sesión de origen: la pestaña activa en el momento del envío
        try:
            _submit_session = self.get_active_session()
            _submit_sid = _submit_session.session_id if _submit_session else None
            _busy = bool(_submit_session.is_processing) if _submit_session is not None else bool(getattr(self, "is_processing", False))
        except Exception:
            _submit_session, _submit_sid, _busy = None, None, bool(getattr(self, "is_processing", False))

        # Bloquear nuevo input si ESA pestaña ya procesa (encolar en su cola)
        if _busy is True:
            try:
                (_submit_session.input_queue if _submit_session is not None else self._input_queue).append(user_input)
            except Exception:
                pass
            if hasattr(self, "queue_display"):
                try:
                    self.queue_display.update_queue(self._input_queue)
                except Exception:
                    pass
            return

        # Despachar al worker asíncrono
        self.run_worker(self._handle_input_async(user_input, _submit_sid))

    def _transition_to_chat(self, first_message: str):
        """Oculta el splash y activa el modo chat con el primer mensaje."""
        self._splash_visible = False
        # Ocultar splash
        splash = self.query_one("#splash_overlay")
        splash.display = False
        # Mostrar el contenedor inferior del chat
        try:
            self.query_one("#bottom_container").display = True
        except:
            pass
        # Enfocar el ChatInput del chat (buscar por tipo, no por id)
        try:
            chat_input = self.query_one("#chat_input", ChatInput)
            chat_input.focus()
        except Exception:
            pass
        # Procesar el primer mensaje en worker
        self.run_worker(self._handle_input_async(first_message))

    async def _handle_input_async(self, user_input: str, session_id: Optional[str] = None):
        """Procesa la entrada del usuario de forma asíncrona en un worker.

        El ``session_id`` fija la pestaña de origen para que cada sesión
        procese en paralelo con su propio historial y su propio widget.
        Si es None, se usa la sesión activa en el momento del envío.
        """
        session = self.get_session(session_id) if session_id else self.get_active_session()
        if session is None:
            try:
                session = self._ensure_active_session()
            except Exception:
                session = None
            if session is None:
                return

        # 0. Asegurar managers de la sesión bajo demanda.
        # OJO: la construcción es pesada (system prompt + runners de agente) y
        # no puede hacerse en el event loop o la UI se congela. Se delega a un
        # hilo y se espera sin bloquear el loop.
        try:
            if not getattr(session, "_managers_ready", False):
                await asyncio.to_thread(self._ensure_session_managers, session)
        except Exception as exc:
            logger.debug(f"_ensure_session_managers: {exc}")

        # 0b. Comandos de pestañas/sesión (no se reflejan como mensaje)
        try:
            if await self._handle_session_command(user_input, session):
                return
        except Exception as e:
            logger.error(f"Error procesando comando de sesión: {e}", exc_info=True)

        # 1. Intentar procesar comando desde TUICommandProcessor (modales interactivos en worker)
        cmd_proc = getattr(self, "command_processor", None)
        if cmd_proc and hasattr(cmd_proc, "process_command"):
            try:
                if await cmd_proc.process_command(user_input):
                    return
            except Exception as e:
                logger.error(f"Error procesando comando TUI: {e}", exc_info=True)

        try:
            session.ui_proxy.print_message(user_input, is_user_message=True)
        except Exception:
            pass

        # Título provisional inmediato con la petición (el LLM lo sustituirá
        # al terminar el turno). Se hace tras descartar que sea un comando.
        try:
            if not (user_input or "").strip().startswith(("/", "%")):
                self._provisional_title_from_request(session, user_input)
        except Exception:
            pass

        # Meta-comandos con el processor de ESTA sesión (su AgentState + su UI).
        meta_proc = getattr(session, "meta_processor", None) or self.meta_command_processor
        if meta_proc:
            try:
                if await meta_proc.process_meta_command(user_input):
                    return
            except Exception as e:
                logger.error(f"Error procesando meta-comando: {e}", exc_info=True)
                try:
                    session.ui_proxy.print_message(f"Error ejecutando comando: {e}", style="red")
                except Exception:
                    pass
                return

        # ── Decisión híbrida: servidor vs local ────────────────────────────────
        # En modo servidor cada pestaña usa su propio WebSocket/sesión remota.
        _srv_client = None
        try:
            if self._server_mode and session is not None:
                _srv_client = getattr(session, "ws_client", None) or self._ensure_session_client(session)
        except Exception:
            _srv_client = None
        try:
            _srv_connected = bool(_srv_client is not None and _srv_client.is_connected)
        except Exception:
            _srv_connected = False
        if _srv_connected:
            # Intentar via WebSocket; si falla, caer al modo local automáticamente
            await self._send_to_server(user_input, session)
        else:
            self.process_agent_request(user_input, session.session_id)

    # ── Comandos de pestañas ──────────────────────────────────────────
    # Aceptan prefijo / o %. Se interceptan antes que cualquier otro
    # procesador para no contaminar historiales ni hilos.

    SESSION_COMMANDS = (
        "new", "tabs", "sessions", "switch", "rename", "close", "tab",
    )

    async def _handle_session_command(self, user_input: str, session) -> bool:
        """Procesa /new /tabs /switch /rename /close (+ intercepta /reset,
        /resume y /session para que operen sobre la pestaña activa).

        Devuelve True si el comando fue consumido.
        """
        text = (user_input or "").strip()
        if not text or text[0] not in ("/", "%"):
            return False
        parts = text.split()
        cmd = parts[0][1:].lower()
        args = parts[1:]

        if cmd in self.SESSION_COMMANDS:
            if cmd == "new":
                self.create_session(title=" ".join(args) if args else None)
            elif cmd in ("tabs", "sessions"):
                self._print_sessions_list(session)
            elif cmd in ("switch", "tab"):
                self._cmd_switch_session(args, session)
            elif cmd == "rename":
                if args:
                    self.rename_session(" ".join(args), session.session_id)
                else:
                    session.ui_proxy.print_message("Uso: `/rename <título>`", style="yellow")
            elif cmd == "close":
                target = self._resolve_session_arg(args, session) if args else session
                self.close_session(target.session_id if target else session.session_id)
            return True

        if cmd == "reset":
            self._reset_session(session)
            return True

        if cmd == "resume":
            await self._resume_into_session(session, args[0] if args else None)
            return True

        if cmd == "session":
            await self._handle_session_subcommand(session, args)
            return True

        return False

    def _resolve_session_arg(self, args: list, current):
        """Resuelve '2' o parte del título a una sesión."""
        if not args:
            return current
        key = " ".join(args).strip().lower()
        sessions = self.list_sessions()
        if key.isdigit():
            idx = int(key) - 1
            if 0 <= idx < len(sessions):
                return sessions[idx]
            return None
        for s in sessions:
            if key in (s.title or "").lower() or key == s.session_id.lower():
                return s
        matches = [s for s in sessions if key in (s.title or "").lower()]
        return matches[0] if len(matches) == 1 else None

    def _cmd_switch_session(self, args: list, current):
        target = self._resolve_session_arg(args, current)
        if target is None:
            try:
                current.ui_proxy.print_message(
                    "Uso: `/switch <nº|título>`. Ver `/tabs`.", style="yellow"
                )
            except Exception:
                pass
            return
        self.switch_session(target.session_id)

    def _print_sessions_list(self, current):
        sessions = self.list_sessions()
        lines = ["[bold cyan]📑 Pestañas (mismo proyecto):[/bold cyan]"]
        for idx, s in enumerate(sessions):
            markers = []
            if s.session_id == current.session_id:
                markers.append("← activa")
            if s.is_processing:
                markers.append("● procesando")
            suffix = f" ({', '.join(markers)})" if markers else ""
            lines.append(f"  [bold]{idx + 1}.[/bold] {s.title}{suffix}")
        lines.append("[dim]/new [título] · /switch <nº> · /rename <título> · /close [nº][/dim]")
        try:
            current.ui_proxy.print_message("\n".join(lines))
        except Exception:
            pass

    def _reset_session(self, session):
        """Limpia la pestaña activa (su AgentState e historial) sin tocar las demás."""
        try:
            if session.agent_state is not None and hasattr(session.agent_state, "reset"):
                session.agent_state.reset()
            if getattr(self, "llm_service", None) is not None and session.session_id == self._active_session_id:
                try:
                    from kogniterm.core.agents.bash_agent import get_system_message

                    self.llm_service.conversation_history = [get_system_message(self.llm_service)]
                    session.agent_state.messages = list(self.llm_service.conversation_history)
                    try:
                        self.llm_service._save_history(self.llm_service.conversation_history)
                    except Exception:
                        pass
                except Exception:
                    pass
            widget = self._session_widget(session)
            if widget is not None:
                widget.clear()
            session.input_queue.clear()
            try:
                session.ui_proxy.print_message(
                    f"🧹 **{session.title}** limpiada. Historial reiniciado.",
                    style="green",
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error en _reset_session: {e}", exc_info=True)

    async def _resume_into_session(self, session, query: Optional[str]):
        """Carga un thread persistido en la pestaña indicada."""
        tm = getattr(self, "thread_manager", None)
        if tm is None:
            try:
                session.ui_proxy.print_message("Thread manager no disponible.", style="red")
            except Exception:
                pass
            return
        try:
            threads = tm.list_threads()
        except Exception:
            threads = []
        # Filtrar al workspace actual (las pestañas son del mismo proyecto)
        try:
            ws = os.path.abspath(self.workspace_directory or os.getcwd())
            if threads:
                filtered = [t for t in threads if os.path.abspath(t.get("workspace_dir") or "") == ws]
                if filtered:
                    threads = filtered
        except Exception:
            pass
        if not threads:
            try:
                session.ui_proxy.print_message("No hay hilos guardados para retomar.", style="yellow")
            except Exception:
                pass
            return
        thread_id = None
        if query:
            try:
                exact = tm.get_thread(query)
            except Exception:
                exact = None
            if exact:
                thread_id = exact.id
            else:
                try:
                    matches = tm.find_threads(query)
                except Exception:
                    matches = []
                if len(matches) == 1:
                    thread_id = matches[0].get("id")
                elif len(matches) > 1:
                    threads = matches
        if not thread_id:
            options = []
            for t in threads[:20]:
                label = f"{t.get('title', t.get('id', ''))} — {str(t.get('updated_at', ''))[:19]} ({t.get('message_count', 0)} msgs)"
                options.append((t.get("id", ""), label))
            try:
                thread_id = await session.ui_proxy.ask_radiolist_async(
                    title="Retomar hilo",
                    text="Selecciona el hilo a cargar en esta pestaña:",
                    values=options,
                )
            except Exception:
                thread_id = None
            if not thread_id:
                try:
                    session.ui_proxy.print_message("Selección cancelada.", style="dim")
                except Exception:
                    pass
                return
        try:
            thread = tm.get_thread(thread_id)
        except Exception:
            thread = None
        if thread is None:
            try:
                session.ui_proxy.print_message(f"No se pudo cargar el hilo '{thread_id}'.", style="red")
            except Exception:
                pass
            return
        history = list(thread.messages or [])
        session.thread_id = thread.id
        try:
            session.title = (thread.title or session.title)[:40]
        except Exception:
            pass
        if session.agent_state is not None:
            try:
                session.agent_state.reset()
                session.agent_state.messages = list(history)
            except Exception:
                session.agent_state.messages = list(history)
        try:
            tm.set_current_thread_id(thread.id)
        except Exception:
            pass
        self._render_history_into_session(session, history)
        self._refresh_session_tabs()
        try:
            session.ui_proxy.print_message(
                f"▶️ Hilo **{thread.title}** cargado en **{session.title}** ({len(history)} mensajes).",
                style="green",
            )
        except Exception:
            pass

    async def _handle_session_subcommand(self, session, args: list):
        """Versión por pestaña de `/session` (mismo workspace)."""
        tm = getattr(self, "thread_manager", None)
        if tm is None:
            try:
                session.ui_proxy.print_message("Thread manager no disponible.", style="red")
            except Exception:
                pass
            return
        sub = args[0].lower() if args else "list"
        rest = args[1:] if len(args) > 1 else []
        if sub == "list":
            try:
                threads = tm.list_threads()
            except Exception:
                threads = []
            if not threads:
                session.ui_proxy.print_message("No hay hilos guardados.", style="yellow")
                return
            lines = ["[bold cyan]🧵 Hilos guardados:[/bold cyan]"]
            for t in threads[:20]:
                mark = " ← pestaña actual" if t.get("id") == session.thread_id else ""
                lines.append(
                    f"  • [bold]{t.get('title', '')}[/bold] `{(t.get('id', '')[:8])}` "
                    f"({t.get('message_count', 0)} msgs){mark}"
                )
            session.ui_proxy.print_message("\n".join(lines))
        elif sub == "new":
            self.create_session(title=" ".join(rest) if rest else None)
        elif sub == "load":
            if not rest:
                session.ui_proxy.print_message("Uso: `/session load <thread_id>`", style="yellow")
                return
            await self._resume_into_session(session, rest[0])
        elif sub == "save":
            target = rest[0] if rest else (session.thread_id or "hilo")
            history = list(session.agent_state.messages or []) if session.agent_state else []
            try:
                thread = tm.get_thread(target)
                if thread is None:
                    thread = tm.create_thread(thread_id=target, title=target, messages=history)
                    saved = thread is not None
                else:
                    thread.messages = history
                    saved = tm.save_thread(thread, llm_service=getattr(self, "llm_service", None))
                session.ui_proxy.print_message(
                    f"Hilo '{target}' guardado. ✅" if saved else f"Error guardando '{target}'. ❌",
                    style="green" if saved else "red",
                )
            except Exception as e:
                session.ui_proxy.print_message(f"Error guardando hilo: {e}", style="red")
        elif sub == "delete":
            if not rest:
                session.ui_proxy.print_message("Uso: `/session delete <thread_id>`", style="yellow")
                return
            try:
                ok = tm.delete_thread(rest[0])
                session.ui_proxy.print_message(
                    f"Hilo '{rest[0]}' eliminado. 🗑️" if ok else f"No se pudo eliminar '{rest[0]}'.",
                    style="green" if ok else "red",
                )
            except Exception as e:
                session.ui_proxy.print_message(f"Error eliminando hilo: {e}", style="red")
        else:
            session.ui_proxy.print_message(
                "Subcomandos: `list`, `save`, `load`, `new`, `delete`. También: `/new /tabs /switch /rename /close /resume /reset`.",
                style="yellow",
            )

    def apply_theme(self, theme_name: str, persist: bool = True):
        """Aplica un tema visual a la aplicación Textual.

        Args:
            theme_name: Nombre del tema a aplicar.
            persist: Si True, guarda el tema en config global. Usar False al
                     cargar al inicio para no sobreescribir la preferencia guardada.
        """
        from kogniterm.terminal.themes import ColorPalette, set_kogniterm_theme

        # 1. Aplicar tema a nivel de lógica (paleta global)
        set_kogniterm_theme(theme_name)
        p = ColorPalette

        # 2. Textual native dark mode (afecta a los widgets nativos)
        self.dark = theme_name != "light"

        # 3. Aplicar colores a contenedores principales
        bg_color = p.GRAY_900 if self.dark else p.PRIMARY_LIGHTEST

        self.screen.styles.background = bg_color
        self.styles.background = bg_color

        try:
            chat_container = self.query_one("#chat_container")
            chat_container.styles.background = bg_color
        except Exception:
            pass

        # 3b. Barra de pestañas: fondo transparente, borde y colores con el tema
        try:
            sessions_bar = self.query_one("#sessions_bar")
            sessions_bar.styles.background = "transparent"
            sessions_bar.styles.border_bottom = ("solid", p.GRAY_700)
        except Exception:
            pass
        try:
            new_btn = self.query_one("#new_session_btn")
            new_btn.styles.background = "transparent"
            new_btn.styles.color = p.SUCCESS
        except Exception:
            pass
        # Reaplicar los colores de cada pestaña con la paleta nueva
        try:
            self._refresh_session_tabs()
        except Exception:
            pass

        # 4. Estilizar los LOGS (uno por pestaña) y sus SCROLLBARS
        _logs = []
        try:
            for _s in self.list_sessions():
                _w = self._session_widget(_s)
                if _w is not None:
                    _logs.append(_w)
        except Exception:
            pass
        if not _logs and self.chat_log is not None:
            _logs = [self.chat_log]
        for log in _logs:
            log.styles.background = "transparent"
            log.styles.color = p.TEXT_PRIMARY
            log.styles.scrollbar_color = p.GRAY_600
            log.styles.scrollbar_color_hover = p.PRIMARY
            log.styles.scrollbar_color_active = p.PRIMARY_LIGHT

        # 5. Estilizar contenedores secundarios
        self.approval_container.styles.background = bg_color
        self.live_display.styles.background = bg_color
        self.live_display.styles.color = p.TEXT_PRIMARY

        bottom_container = self.query_one("#bottom_container")
        bottom_container.styles.background = bg_color

        input_bg = p.GRAY_800 if self.dark else p.GRAY_200

        # 6. Estilizar el INPUT CONTAINER
        try:
            input_container = self.query_one("#input_container")
            input_container.styles.background = input_bg
            input_container.styles.border = None
            input_container.styles.border_left = ("tall", p.PRIMARY)
        except Exception:
            pass

        # 7. Estilizar todos los inputs
        for inp in self.query(ChatInput):
            inp.styles.color = p.TEXT_PRIMARY
            inp.styles.background = "transparent"
            inp.show_cursor_line = False
            inp.cursor_line_style = ""

        # 8. Estilizar STATUS FOOTER
        for sf in self.query(StatusFooter):
            sf.styles.background = "transparent"
            sf.styles.border = None
            sf.styles.border_left = None
            sf.styles.color = p.TEXT_SECONDARY

        # 9. Splash overlay (si aún está visible)
        if self._splash_visible:
            try:
                self.query_one("#splash_overlay").styles.background = bg_color
                self.query_one("#splash_input_row").styles.border_left = (
                    "tall",
                    p.PRIMARY,
                )
                self.query_one("#splash_input_row").styles.background = p.GRAY_800
                self.query_one("#splash_model_info").styles.border_left = (
                    "tall",
                    p.PRIMARY,
                )
                self.query_one("#splash_model_info").styles.background = p.GRAY_800
                self.query_one("#splash_title").update(self._build_splash_title())
            except Exception:
                pass

        # 10. Persistir solo si el usuario eligió activamente el tema
        if persist:
            from kogniterm.terminal.config_manager import ConfigManager

            cm = ConfigManager()
            # Guardar en config global
            cm.set_global_config("theme", theme_name)
            # Si existe config local del proyecto, actualizarlo también para
            # evitar que override silenciosamente la preferencia del usuario
            if cm.PROJECT_CONFIG_FILE.exists():
                cm.set_project_config("theme", theme_name)

        # 11. Forzar refresh
        self.refresh()

    def write_stream_to_chat(self, content: str):
        """Método para escribir streaming desde hilos externos."""
        # Si recibimos contenido, pausamos el spinner de procesamiento inferior
        # (no lo detenemos definitivamente - puede reactivarse tras herramientas)
        if self.live_display.display:
            try:
                self._spinner_paused = True  # Marcar como pausado, no definitivo
                self.call_from_thread(self._stop_spinner)
            except Exception:
                pass
        self.chat_log.write_stream(content)

    # Frames del spinner braille animado
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def _start_spinner(self):
        """Inicia la animación del spinner en live_display (ejecutar desde main thread)."""
        from kogniterm.terminal.themes import ColorPalette

        self._spinner_frame = 0
        self.live_display.display = True  # Asegurar que sea visible
        self.live_display.update(
            Text(
                f"{self.SPINNER_FRAMES[0]} Procesando...",
                style=f"bold {ColorPalette.PRIMARY}",
            )
        )
        if self._spinner_timer:
            self._spinner_timer.stop()
        self._spinner_timer = self.set_interval(0.12, self._tick_spinner)
        # Scroll del chat_log a su propio fondo para que el contenido existente
        # quede anclado abajo (justo encima del live_display)
        self.chat_log.scroll_end(animate=False)

    def _tick_spinner(self):
        """Avanza un frame del spinner (ejecutado por el timer del main thread)."""
        # IMPORTANTE: Si el timer ya no existe o no estamos procesando, salir.
        # Esto evita que el spinner sobrescriba contenido real que acaba de llegar
        # por una colisión de eventos en el loop principal.
        if not self.is_processing or self._spinner_timer is None:
            self._stop_spinner()
            return

        self._spinner_frame = (self._spinner_frame + 1) % len(self.SPINNER_FRAMES)
        from kogniterm.terminal.themes import ColorPalette

        frame = self.SPINNER_FRAMES[self._spinner_frame]

        # Asegurar visibilidad si estamos animando
        if not self.live_display.display:
            self.live_display.display = True

        self.live_display.update(
            Text(f"{frame} Procesando...", style=f"bold {ColorPalette.PRIMARY}")
        )

    def _stop_spinner(self):
        """Detiene el spinner y limpia la referencia al timer."""
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None

        # Ocultar el live_display si no estamos en modo interactivo (terminal)
        if not self._cursor_active:
            self.live_display.display = False

        # Cuando se detiene el spinner, finalizamos cualquier stream en el log
        self.chat_log.stop_stream()

        # Enfocar el input principal para permitir seguir escribiendo tras el fin de la respuesta
        # Solo lo hacemos si no estamos en un modo que requiera foco en otro lado (como terminal interactiva)
        if not self._cursor_active:
            try:
                self.query_one("#chat_input", ChatInput).focus()
            except Exception:
                pass

    def _resume_spinner(self):
        """Reactiva el spinner de procesamiento si was paused for streaming.
        Se llama desde tool_executor cuando las herramientas terminan y el LLM aún no responde.
        """
        if not self._spinner_paused:
            return
        if self._spinner_timer is not None:
            # Ya está activo
            return
        self._spinner_paused = False
        # Reiniciar el spinner como si fuera la primera vez
        self._start_spinner()

    def get_active_executor(self):
        """Executor del shell persistente de la pestaña activa.

        Cada pestaña tiene su propio CommandExecutor (shell persistente
        independiente). Puede no existir todavía si los managers se están
        creando en segundo plano: en ese caso cae al global legacy.
        """
        try:
            session = self.get_active_session()
            if session is not None and getattr(session, "command_executor", None) is not None:
                return session.command_executor
        except Exception:
            pass
        return getattr(self, "command_executor", None)

    def _session_for_widget(self, widget):
        """Resuelve a qué pestaña pertenece un widget (subiendo por padres)."""
        try:
            node = widget
            wanted = {s.chat_widget_id for s in self.list_sessions() if s.chat_widget_id}
            while node is not None:
                if getattr(node, "id", None) in wanted:
                    for s in self.list_sessions():
                        if s.chat_widget_id == node.id:
                            return s
                    return None
                node = getattr(node, "parent", None)
        except Exception:
            pass
        return None

    def set_terminal_cursor(self, active: bool, executor=None, session_id: Optional[str] = None):
        """Activa o desactiva el simulador de cursor en el chat log.

        El estado se registra por pestaña (`session_id` explícito, contexto
        del worker o activa). Solo la pestaña activa refleja el estado en la
        UI global (placeholder, timer de parpadeo).
        """
        session = None
        try:
            if session_id:
                session = self.get_session(session_id)
            if session is None and SessionContext is not None:
                session = self.get_session(SessionContext.get())
            if session is None:
                session = self.get_active_session()
        except Exception:
            session = None
        if session is not None:
            try:
                session.cursor_active = bool(active)
                session.interactive_executor = executor if active else None
            except Exception:
                pass
            try:
                if session.session_id != self._active_session_id:
                    # Pestaña en fondo: registrar sin tocar la UI global
                    return
            except Exception:
                pass

        self.interactive_executor = executor if active else None
        self._cursor_active = active

        # Cambiar placeholder del input para indicar modo
        try:
            chat_input = self.query_one(ChatInput)
            if active:
                chat_input.placeholder = "Terminal Interactiva (Escribe abajo o HAZ CLIC en el panel para modo directo)..."
                chat_input.styles.color = "#10b981"  # Verde esmeralda para modo activo
                self.live_display.add_class("interactive")
            else:
                chat_input.placeholder = "Escribe un mensaje..."
                chat_input.styles.color = "white"
                self.live_display.remove_class("interactive")
        except:
            pass

        if active and not self._cursor_timer:
            self._cursor_timer = self.set_interval(0.5, self._update_cursor)
        elif not active and self._cursor_timer:
            self._cursor_timer.stop()
            self._cursor_timer = None
            # Limpiar rastro de cursor (RichLog es append-only, así que simplemente dejamos de imprimirlo)

    def _update_cursor(self):
        """Actualiza el parpadeo del cursor redibujando la terminal."""
        if not self._cursor_active:
            return

        self._cursor_frame = (self._cursor_frame + 1) % 2

        # Redibujar la terminal con el nuevo estado del frame si hay algo guardado
        if self._last_terminal_tool_name:
            self.update_terminal_output(
                self._last_terminal_tool_name, self._last_terminal_output
            )

    @work(thread=True)
    def process_agent_request(self, user_input: str, session_id: Optional[str] = None):
        # Resolver la pestaña de origen (paralelismo: cada sesión procesa
        # con su propio AgentState, interaction manager y UI).
        session = self.get_session(session_id) if session_id else self.get_active_session()
        if session is None or getattr(session, "agent_state", None) is None:
            # Fallback legacy (sin multisesión disponible)
            self._process_agent_request_legacy(user_input)
            return

        # Managers pesados listos (por si se invoca este worker directamente)
        try:
            if not getattr(session, "_managers_ready", False):
                self._ensure_session_managers(session)
        except Exception:
            pass

        if SessionContext is not None:
            SessionContext.set(session.session_id)
        session.is_processing = True
        try:
            self._refresh_session_tabs()
        except Exception:
            pass
        # Drenar cualquier señal de interrupción residual de ESTA sesión
        iq = getattr(session, "interrupt_queue", None)
        if iq is not None:
            while not iq.empty():
                try:
                    iq.get_nowait()
                except Exception:
                    break
        if hasattr(self, "llm_service") and self.llm_service:
            try:
                self.llm_service.stop_generation_flag = False
            except Exception:
                pass

        # Mostrar spinner (global si está activa, inline si está en fondo)
        try:
            self.call_from_thread(self._start_spinner_for_session, session.session_id)
        except Exception:
            pass
        # Añadir el mensaje del usuario al historial de ESTA sesión
        try:
            session.agent_state.add_message(HumanMessage(content=user_input))
        except Exception as exc:
            logger.error(f"No se pudo añadir mensaje a la sesión: {exc}")

        agent_state = session.agent_state
        interaction_manager = getattr(session, "interaction_manager", None) or self.agent_interaction_manager
        session_ui = getattr(session, "ui_proxy", None) or self.tui_ui
        # Handler de aprobaciones de ESTA pestaña (su executor + su UI).
        approval_handler = (
            getattr(session, "approval_handler", None) or self.command_approval_handler
        )

        try:
            while True:
                try:
                    if interaction_manager is None:
                        raise RuntimeError("Interaction manager no disponible para esta sesión.")
                    # Invoke agent synchronously in this thread
                    final_state = interaction_manager.invoke_agent(
                        user_input
                    )
                except Exception as e:
                    import traceback

                    error_trace = traceback.format_exc()
                    logger.error(f"Error crítico en invoke_agent: {e}\n{error_trace}")
                    try:
                        session_ui.print_message(
                            f"❌ Error crítico al invocar al agente: {str(e)}",
                            style="bold red",
                        )
                    except Exception:
                        pass
                    break

                agent_state.messages = final_state.get(
                    "messages", agent_state.messages
                )
                agent_state.command_to_confirm = final_state.get(
                    "command_to_confirm"
                )
                agent_state.tool_pending_confirmation = final_state.get(
                    "tool_pending_confirmation", agent_state.tool_pending_confirmation
                )
                agent_state.tool_args_pending_confirmation = final_state.get(
                    "tool_args_pending_confirmation", agent_state.tool_args_pending_confirmation
                )
                agent_state.file_update_diff_pending_confirmation = final_state.get(
                    "file_update_diff_pending_confirmation", agent_state.file_update_diff_pending_confirmation
                )
                # También recuperar el tool_call_id para poder crear el ToolMessage correcto
                tool_call_id_for_cmd = (
                    final_state.get("tool_call_id_to_confirm") or agent_state.tool_call_id_to_confirm or "execute_command"
                )
                # DIAGNOSTIC LOG
                logger.info(
                    "[DIAG] tui_app: final_state keys=%s, file_diff=%s, tool_pend=%s, session=%s",
                    list(final_state.keys()) if isinstance(final_state, dict) else type(final_state).__name__,
                    final_state.get('file_update_diff_pending_confirmation') if isinstance(final_state, dict) else 'N/A',
                    final_state.get('tool_pending_confirmation') if isinstance(final_state, dict) else 'N/A',
                    session.session_id,
                )
                logger.info(
                    "[DIAG] tui_app: after sync - agent_state.file_diff=%s, agent_state.tool_pend=%s",
                    agent_state.file_update_diff_pending_confirmation,
                    agent_state.tool_pending_confirmation,
                )
                # 2. SECCIÓN DE CONFIRMACIONES (Bash y Skills)
                # -------------------------------------------------------------

                # Caso A: Comando de terminal (Bash)
                if agent_state.command_to_confirm:
                    command = agent_state.command_to_confirm

                    if command and approval_handler:
                        approval_result = approval_handler.handle_command_approval(
                            command_to_execute=command
                        )
                        approved = approval_result.get("approved", False)
                    else:
                        approved = self.ask_for_approval_sync(
                            message=f"¿Ejecutar comando: {command}?",
                            title="Confirmación de Comando",
                            diff_content=command,
                            file_path="bash",
                        )

                    # Limpiar estado de confirmación tras procesar
                    agent_state.command_to_confirm = None
                    agent_state.tool_call_id_to_confirm = None

                    # Si fue aprobado, imprimir advertencia visual de que se completó
                    if not approved:
                        try:
                            session_ui.print_warning_box(
                                "Comando cancelado por el usuario."
                            )
                        except Exception:
                            pass

                    user_input = None
                    continue  # Volver al inicio del bucle para que el agente procese el resultado

                # Caso B: Confirmación de Skill (file_operations, advanced_file_editor, etc.)
                elif (
                    agent_state.tool_pending_confirmation
                    or agent_state.file_update_diff_pending_confirmation
                ):
                    tool_name = agent_state.tool_pending_confirmation
                    diff_info = agent_state.file_update_diff_pending_confirmation

                    # Extraer info del diff
                    message = "Confirmación de herramienta requerida."
                    diff_content = None
                    file_path = None

                    if isinstance(diff_info, dict):
                        message = diff_info.get(
                            "action_description", diff_info.get("message", message)
                        )
                        diff_content = diff_info.get("diff")
                        if not diff_content:
                            diff_content = diff_info.get("code_preview") or diff_info.get("code") or (diff_info.get("args") or {}).get("code")
                        file_path = diff_info.get("path")
                        if not file_path and (diff_info.get("operation") == "python_executor" or tool_name == "python_executor"):
                            file_path = "python_script.py"
                    elif isinstance(diff_info, str):
                        diff_content = diff_info

                    if approval_handler:
                        approval_result = approval_handler.handle_command_approval(
                            command_to_execute="",  # No es un comando bash
                            raw_tool_output=diff_info
                            if isinstance(diff_info, dict)
                            else {
                                "status": "requires_confirmation",
                                "diff": diff_content,
                                "path": file_path,
                                "operation": tool_name,
                            },
                            tool_name=tool_name,
                            original_tool_args=agent_state.tool_args_pending_confirmation,
                        )
                        approved = approval_result.get("approved", False)
                    else:
                        approved = self.ask_for_approval_sync(
                            message=message,
                            title=f"Confirmación: {tool_name}",
                            diff_content=diff_content,
                            file_path=file_path,
                        )

                    # Desencolar/avanzar la confirmación actual
                    agent_state.pop_pending_confirmation()

                    if not approved:
                        try:
                            session_ui.print_warning_box(
                                "Acción cancelada por el usuario."
                            )
                        except Exception:
                            pass

                    user_input = None
                    continue  # Volver al inicio del bucle

                # Sin confirmaciones pendientes: salir del loop
                break
        except Exception as e:
            import traceback

            error_trace = traceback.format_exc()
            logger.error(f"Error fatal en process_agent_request: {e}\n{error_trace}")
            # Mostrar error al usuario
            try:
                session_ui.print_message(
                    f"❌ Error fatal en el hilo del agente: {str(e)}", style="bold red"
                )
            except Exception:
                pass
        finally:
            session.is_processing = False
            # Persistir el historial de ESTA sesión en su propio thread
            try:
                if getattr(self, "thread_manager", None) is not None and session.thread_id:
                    self.thread_manager.save_thread_messages(
                        session.thread_id, list(agent_state.messages or [])
                    )
            except Exception as exc:
                logger.debug(f"No se pudo persistir sesión {session.session_id}: {exc}")
            if SessionContext is not None:
                SessionContext.set(None)
            # Asegurar que el spinner se detenga siempre al terminar
            try:
                self.call_from_thread(self._on_session_finished, session.session_id)
            except Exception:
                pass

    def _process_agent_request_legacy(self, user_input: str):
        """Ruta original mono-sesión (fallback si no hay sesiones)."""
        self.is_processing = True
        if hasattr(self, "tui_ui") and hasattr(self.tui_ui, "interrupt_queue"):
            iq = self.tui_ui.interrupt_queue
            while iq and not iq.empty():
                try:
                    iq.get_nowait()
                except Exception:
                    break
        if hasattr(self, "llm_service") and self.llm_service:
            self.llm_service.stop_generation_flag = False
        self.call_from_thread(self._start_spinner)
        try:
            self.agent_state.add_message(HumanMessage(content=user_input))
        except Exception:
            pass
        try:
            final_state = self.agent_interaction_manager.invoke_agent(user_input)
            self.agent_state.messages = final_state.get("messages", self.agent_state.messages)
        except Exception as e:
            import traceback

            logger.error(f"Error crítico en invoke_agent: {e}\n{traceback.format_exc()}")
            try:
                self.tui_ui.print_message(f"❌ Error crítico al invocar al agente: {e}", style="bold red")
            except Exception:
                pass
        finally:
            self.is_processing = False
            try:
                self.call_from_thread(self._stop_spinner)
            except Exception:
                pass
            try:
                self.call_from_thread(self._process_queue)
            except Exception:
                pass

    def _process_queue(self, session_id: Optional[str] = None):
        """Procesa el siguiente mensaje en la cola de la sesión si está libre."""
        session = self.get_session(session_id) if session_id else self.get_active_session()
        if session is None:
            # Fallback legacy sobre la cola global
            if self._input_queue and not self.is_processing:
                next_message = self._input_queue.pop(0)
                if hasattr(self, "queue_display"):
                    self.queue_display.update_queue(self._input_queue)
                self.run_worker(self._handle_input_async(next_message))
            return
        if session.input_queue and not session.is_processing:
            next_message = session.input_queue.pop(0)
            if session.session_id == self._active_session_id and hasattr(self, "queue_display"):
                try:
                    self.queue_display.update_queue(session.input_queue)
                except Exception:
                    pass
            # Drenar interrupciones de ESTA sesión antes de lanzar el mensaje
            iq = getattr(session, "interrupt_queue", None)
            if iq is not None:
                while not iq.empty():
                    try:
                        iq.get_nowait()
                    except Exception:
                        break
            if hasattr(self, "llm_service") and self.llm_service:
                try:
                    self.llm_service.stop_generation_flag = False
                except Exception:
                    pass
            # Volver a llamar a handle_input_async para el siguiente mensaje
            self.run_worker(self._handle_input_async(next_message, session.session_id))

    async def push_screen_wait(self, screen) -> Any:
        """Helper asíncrono para pushear una pantalla y esperar su resultado."""
        future = asyncio.get_running_loop().create_future()

        def callback(result: Any) -> None:
            if not future.done():
                future.set_result(result)

        try:
            self.push_screen(screen, callback)
        except Exception:
            self.call_after_refresh(lambda: self.push_screen(screen, callback))
        return await future

    def set_auto_approve_all(self, active: bool = True) -> None:
        """Activa o desactiva la auto-aprobación global para todas las acciones y actualiza la UI."""
        self._auto_approve_all = active
        try:
            from kogniterm.terminal.config_manager import ConfigManager
            ConfigManager().set_project_config("auto_approve", active)
        except Exception:
            pass
        if hasattr(self, "command_approval_handler") and self.command_approval_handler:
            self.command_approval_handler.auto_approve = active
        # Propagar a los handlers de todas las pestañas
        try:
            for session in self.list_sessions():
                handler = getattr(session, "approval_handler", None)
                if handler is not None:
                    try:
                        handler.auto_approve = active
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            from kogniterm.terminal.tui.components.status_footer import StatusFooter
            footer = self.query_one(StatusFooter)
            footer.set_auto_approve(active)
        except Exception:
            pass

    def action_toggle_auto_approve(self) -> None:
        """Conmuta el estado de auto-aprobación mediante atajo de teclado (Shift+Tab)."""
        current = getattr(self, "_auto_approve_all", False)
        self.set_auto_approve_all(not current)
        status = "activada ⚡" if not current else "desactivada"
        self.notify(f"Auto-aprobación {status}", severity="info" if not current else "warning")

    def _approval_host(self, session_id: Optional[str] = None):
        """Resuelve (host_widget, session) para montar una aprobación.

        Cada pestaña recibe sus aprobaciones inline en su propio chat log,
        permitiendo decisiones en paralelo. Fallback al contenedor global.
        """
        session = None
        try:
            if session_id:
                session = self.get_session(session_id)
            if session is None and SessionContext is not None:
                session = self.get_session(SessionContext.get())
            if session is None:
                session = self.get_active_session()
        except Exception:
            session = None
        if session is not None:
            try:
                widget = self._session_widget(session)
                if widget is not None:
                    return widget, session
            except Exception:
                pass
        if hasattr(self, "approval_container"):
            return self.approval_container, session
        return self, session

    def _track_approval(self, session, delta: int):
        """Contador de aprobaciones pendientes (se refleja en la pestaña)."""
        if session is None:
            return
        try:
            session.pending_approvals = max(0, int(getattr(session, "pending_approvals", 0)) + delta)
        except Exception:
            pass
        try:
            self._refresh_session_tabs()
        except Exception:
            pass

    async def ask_for_approval_async(
        self,
        message: str,
        title: str = "Aprobación Requerida",
        diff_content: str = "",
        file_path: str = "",
        session_id: Optional[str] = None,
    ) -> bool:
        """Versión asíncrona de ask_for_approval que no bloquea el event loop."""
        if getattr(self, "_auto_approve_all", False):
            return True

        from .components.inline_approval import InlineApprovalWidget

        future = asyncio.get_event_loop().create_future()
        resolved: dict = {}

        def _on_decided(result):
            try:
                self._track_approval(resolved.get("session"), -1)
            except Exception:
                pass
            if not future.done():
                future.set_result(result)

        def mount_widget():
            # Resolver aquí (hilo de la app): host = chat log de la pestaña
            host, session = self._approval_host(session_id)
            resolved["session"] = session
            self._track_approval(session, +1)
            widget = InlineApprovalWidget(
                message=message,
                title=title,
                diff_content=diff_content or None,
                file_path=file_path or None,
                callback=_on_decided,
            )
            host.mount(widget)

            try:
                if hasattr(host, "scroll_end"):
                    host.scroll_end(animate=False)
                else:
                    self.chat_log.scroll_end(animate=False)
            except Exception:
                pass
            try:
                widget.focus()
            except Exception:
                pass

        # Puesto que es asíncrono y se llama desde el loop, podemos montar directo
        mount_widget()

        raw_result = await future
        if raw_result == "accept_all":
            self.set_auto_approve_all(True)
        return raw_result in (True, "accept", "accept_all")

    async def ask_for_input_async(
        self, title: str, text: str, password: bool = False
    ) -> str:
        """Versión asíncrona de ask_for_input que no bloquea el event loop."""
        from .components.settings_modals import TextualInputModal

        return await self.push_screen_wait(
            TextualInputModal(title, text, password=password)
        )

    def ask_for_approval_sync(
        self,
        message: str,
        title: str = "Aprobación Requerida",
        diff_content: str = "",
        file_path: str = "",
        session_id: Optional[str] = None,
    ) -> bool:
        """Muestra un InlineApprovalWidget en la pestaña y bloquea hasta decidir.

        Cada pestaña recibe sus aprobaciones inline en su propio chat log,
        permitiendo decisiones en paralelo sin secuestrar otras pestañas.

        Devuelve True si el usuario acepta (Aceptar o Aceptar siempre), False si cancela.
        El resultado 'accept_all' se guarda en self._auto_approve_all para omitir futuras
        confirmaciones en esta sesión.
        """
        # Atajo: si el usuario eligió "Aceptar siempre" antes, aprobar directamente
        if getattr(self, "_auto_approve_all", False):
            return True

        import concurrent.futures
        from .components.inline_approval import InlineApprovalWidget

        future: concurrent.futures.Future = concurrent.futures.Future()
        resolved: dict = {}

        def _on_decided(result):
            try:
                self._track_approval(resolved.get("session"), -1)
            except Exception:
                pass
            if not future.done():
                future.set_result(result)

        def mount_widget():
            # Resolver aquí (hilo de la app): host = chat log de la pestaña.
            # SessionContext (fijado por el worker de la sesión) dirige al
            # tab correcto aunque varias pestañas pidan aprobación a la vez.
            host, session = self._approval_host(session_id)
            resolved["session"] = session
            try:
                self._track_approval(session, +1)
            except Exception:
                pass
            widget = InlineApprovalWidget(
                message=message,
                title=title,
                diff_content=diff_content or None,
                file_path=file_path or None,
                callback=_on_decided,
            )
            # Montar en el chat log de la pestaña (fallback: contenedor global)
            host.mount(widget)

            try:
                if hasattr(host, "scroll_end"):
                    host.scroll_end(animate=False)
                else:
                    self.chat_log.scroll_end(animate=False)
            except Exception:
                pass
            # Enfocar el widget para que capture teclado (solo si está visible)
            try:
                widget.focus()
            except Exception:
                pass

        if (
            threading.current_thread() is threading.main_thread()
            or getattr(self, "_thread_id", None) == threading.get_ident()
        ):
            mount_widget()
        else:
            self.call_from_thread(mount_widget)

        raw_result = future.result()  # Bloquea hasta decisión del usuario

        if raw_result == "accept_all":
            self.set_auto_approve_all(True)
        return raw_result in (True, "accept", "accept_all")

    def ask_for_input_sync(self, title: str, text: str, password: bool = False) -> str:
        """Helper para pedir una entrada de texto mediante Modal de forma síncrona."""
        import concurrent.futures

        future = concurrent.futures.Future()

        def push_screen_callback():
            from .components.settings_modals import TextualInputModal

            def result_callback(result: str):
                future.set_result(result)

            self.call_after_refresh(
                lambda: self.push_screen(
                    TextualInputModal(title, text, password=password), result_callback
                )
            )

        if (
            threading.current_thread() is threading.main_thread()
            or getattr(self, "_thread_id", None) == threading.get_ident()
        ):
            push_screen_callback()
        else:
            self.call_from_thread(push_screen_callback)

        return future.result()

    def ask_question_sync(
        self,
        question: str,
        options: list,
        title: str = "Consulta del Agente",
        allow_freeform: bool = True,
    ) -> str:
        """Muestra un QuestionSelectorModal y bloquea el hilo del agente hasta que el usuario responda."""
        import concurrent.futures
        from .components.question_selector_modal import QuestionSelectorModal

        future: concurrent.futures.Future = concurrent.futures.Future()

        def push_modal():
            def on_dismiss(result: Optional[str]):
                res = result if result is not None else "Cancelado por el usuario."
                if not future.done():
                    future.set_result(res)

            self.push_screen(
                QuestionSelectorModal(
                    question=question,
                    options=options,
                    title=title,
                    allow_freeform=allow_freeform,
                ),
                callback=on_dismiss,
            )

        if (
            threading.current_thread() is threading.main_thread()
            or getattr(self, "_thread_id", None) == threading.get_ident()
        ):
            push_modal()
        else:
            self.call_from_thread(push_modal)

        return future.result()

    # ── Multisesión con pestañas (mismo workspace/proyecto) ──────────
    # Todas las sesiones comparten workspace_directory, LLMService y
    # CommandExecutor. Cada una aísla thread, AgentState, interrupt_queue,
    # interaction manager y ChatLogWidget para permitir procesamiento en
    # paralelo (una puede responder mientras otra sigue trabajando).

    def get_session(self, session_id: Optional[str]):
        if not session_id:
            return None
        try:
            return self._sessions.get(session_id)
        except Exception:
            return None

    def get_active_session(self):
        try:
            if self._active_session_id:
                session = self._sessions.get(self._active_session_id)
                if session is not None:
                    return session
            if self._session_order:
                return self._sessions.get(self._session_order[0])
        except Exception:
            pass
        return None

    def list_sessions(self) -> list:
        try:
            return [self._sessions[sid] for sid in self._session_order if sid in self._sessions]
        except Exception:
            return []

    def _session_widget(self, session):
        if session is None or not getattr(session, "chat_widget_id", None):
            return None
        try:
            return self.query_one(f"#{session.chat_widget_id}", ChatLogWidget)
        except Exception:
            return None

    def _init_sessions(self):
        """Crea la pestaña inicial y enruta las UIs compartidas.

        Se llama una vez desde on_mount (hilo de la app). Es idempotente.
        """
        if getattr(self, "_sessions_ready", False) and self._session_order:
            return
        # Enrutar la salida de herramientas compartidas (LLMService y
        # CommandExecutor) hacia la pestaña que originó cada llamada.
        try:
            if RoutingUI is not None and SessionContext is not None:
                router = RoutingUI(self, self.tui_ui)
                if getattr(self, "llm_service", None) is not None:
                    try:
                        self.llm_service.terminal_ui = router
                    except Exception:
                        pass
                if getattr(self, "command_executor", None) is not None:
                    try:
                        self.command_executor.terminal_ui = router
                    except Exception:
                        pass
                try:
                    if (
                        getattr(self, "command_approval_handler", None) is not None
                        and hasattr(self.command_approval_handler, "terminal_ui")
                    ):
                        self.command_approval_handler.terminal_ui = router
                except Exception:
                    pass
        except Exception as exc:
            logger.debug(f"No se pudo instalar el RoutingUI: {exc}")
        self._ensure_active_session()
        self._sessions_ready = True

    def _ensure_active_session(self):
        """Devuelve la sesión activa, creando la inicial si aún no existe."""
        session = self.get_active_session()
        if session is not None:
            # Asegurar que su widget existe (p. ej. tras recargas en tests)
            if self._session_widget(session) is None:
                try:
                    self._mount_session_widget(session)
                except Exception:
                    pass
            return session
        return self.create_session(title="Sesión 1", _initial=True)

    def _create_session_state(self, title: str):
        """Crea el estado lógico de una sesión (sin tocar el DOM).

        Solo trabajo barato: thread, AgentState, cola y proxy de UI. Los
        managers pesados (CommandExecutor, approval handler,
        AgentInteractionManager, MetaCommandProcessor) se crean de forma
        perezosa con :meth:`_ensure_session_managers`, para no bloquear el
        arranque de la TUI ni la creación de pestañas.
        """
        from kogniterm.core.agent_state import AgentState as CoreAgentState

        self._session_counter += 1
        session_id = f"s{self._session_id_prefix}{self._session_counter}"
        widget_id = f"session-chat-{session_id}"

        # Thread persistente dentro del MISMO workspace
        thread_id = None
        thread_title = title
        try:
            if getattr(self, "thread_manager", None) is not None:
                if self._session_counter == 1:
                    # Reutilizar el hilo auto-creado en __init__ para no duplicar
                    thread_id = self.thread_manager.get_current_thread_id()
                if not thread_id:
                    thread = self.thread_manager.create_thread(title=thread_title)
                    thread_id = thread.id if thread else None
                if thread_id:
                    try:
                        self.thread_manager.set_current_thread_id(thread_id)
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug(f"No se pudo crear thread para {session_id}: {exc}")

        # AgentState propio (historial aislado)
        if self._session_counter == 1 and getattr(self, "agent_state", None) is not None:
            agent_state = self.agent_state
        else:
            agent_state = CoreAgentState()
            # El interaction manager inserta el system message al construirse;
            # si eso falla (entorno de tests), lo añadimos manualmente.
            try:
                if getattr(self, "llm_service", None) is not None:
                    from kogniterm.core.agents.bash_agent import get_system_message

                    agent_state.messages.append(get_system_message(self.llm_service))
            except Exception:
                pass

        interrupt_q = None
        if self._session_counter == 1 and getattr(self, "tui_ui", None) is not None:
            try:
                interrupt_q = self.tui_ui.get_interrupt_queue()
            except Exception:
                interrupt_q = None
        if interrupt_q is None:
            try:
                interrupt_q = new_interrupt_queue() if new_interrupt_queue else queue.Queue()
            except Exception:
                interrupt_q = queue.Queue()

        session = Session(
            session_id=session_id,
            title=thread_title,
            thread_id=thread_id,
            chat_widget_id=widget_id,
            agent_state=agent_state,
            interrupt_queue=interrupt_q,
        )

        # Proxy de UI hacia el widget de esta pestaña
        try:
            if SessionUIProxy is not None:
                session.ui_proxy = SessionUIProxy(
                    base=self.tui_ui,
                    app=self,
                    get_widget=lambda s=session: self._session_widget(s),
                    interrupt_queue=interrupt_q,
                    session_id=session_id,
                )
            else:
                session.ui_proxy = self.tui_ui
        except Exception:
            session.ui_proxy = self.tui_ui

        # ── PTY/shell + managers: perezosos ───────────────────────────
        # El trabajo pesado (CommandExecutor, CommandApprovalHandler,
        # AgentInteractionManager, MetaCommandProcessor) NO se hace aquí para
        # no bloquear el arranque de la TUI. Se construye bajo demanda con
        # _ensure_session_managers().
        # La primera pestaña reutiliza las instancias globales de __init__
        # (ya creadas antes de arrancar la UI) y solo las reconecta a su
        # proxy de UI, de modo que no hay coste adicional de inicio.
        if self._session_counter == 1:
            session.command_executor = getattr(self, "command_executor", None)
            session.approval_handler = getattr(self, "command_approval_handler", None)
            session.interaction_manager = getattr(self, "agent_interaction_manager", None)
            session.meta_processor = getattr(self, "meta_command_processor", None)
            # Solo están listos si las instancias globales existen de verdad
            # (p.ej. en tests sin executor/handler hay que construirlos).
            if (
                session.command_executor is not None
                and session.approval_handler is not None
                and session.interaction_manager is not None
            ):
                session._managers_ready = True
                self._rewire_global_managers_to_session(session)

        self._sessions[session_id] = session
        self._session_order.append(session_id)
        return session

    def _rewire_global_managers_to_session(self, session) -> None:
        """Apunta los managers globales de __init__ al proxy de la sesión 1.

        Así el proceso de la primera pestaña (incluido en segundo plano)
        escribe siempre en su propio widget, sin crear objetos nuevos.
        """
        proxy = getattr(session, "ui_proxy", None)
        if proxy is None:
            return
        targets = [
            getattr(self, "agent_interaction_manager", None),
            getattr(self, "meta_command_processor", None),
            getattr(self, "command_approval_handler", None),
        ]
        mgr = getattr(self, "agent_interaction_manager", None)
        for name in ("bash_agent_app", "super_agent_app", "learning_agent_app", "active_agent_app"):
            targets.append(getattr(mgr, name, None))
        for obj in targets:
            if obj is None:
                continue
            try:
                if hasattr(obj, "terminal_ui"):
                    obj.terminal_ui = proxy
            except Exception:
                pass
        # El handler global debe usar el executor de la sesión
        handler = getattr(self, "command_approval_handler", None)
        if handler is not None and session.command_executor is not None:
            try:
                handler.command_executor = session.command_executor
            except Exception:
                pass

    def _build_session_managers_worker(self, session_id: str) -> None:
        """Hilo en background: crea los managers pesados de la sesión."""
        session = self.get_session(session_id)
        if session is None:
            return
        try:
            self._ensure_session_managers(session)
        except Exception as exc:
            logger.error(f"No se pudieron crear managers de {session_id}: {exc}", exc_info=True)

    def _ensure_session_managers(self, session) -> None:
        """Construye (una sola vez) los managers pesados de la sesión.

        Se llama bajo demanda: al enviar un mensaje y en background al crear
        una pestaña. Nunca en el arranque de la app.
        """
        if session is None:
            return
        try:
            if getattr(session, "_managers_ready", False):
                return
        except Exception:
            pass
        proxy = getattr(session, "ui_proxy", None) or self.tui_ui
        agent_state = getattr(session, "agent_state", None)
        interrupt_q = getattr(session, "interrupt_queue", None)

        # 1. CommandExecutor propio (shell persistente de la pestaña).
        #    La sesión 1 reutiliza el global ya creado.
        if getattr(session, "command_executor", None) is None:
            try:
                from kogniterm.core.command_executor import CommandExecutor as _CE

                ex = _CE()
                try:
                    ex.terminal_ui = proxy
                except Exception:
                    pass
                ws = getattr(self, "workspace_directory", None) or getattr(
                    getattr(self, "command_executor", None), "workspace_directory", None
                )
                if ws:
                    try:
                        ex.set_workspace_directory(ws)
                    except Exception:
                        pass
                session.command_executor = ex
            except Exception as exc:
                logger.debug(f"No se pudo crear CommandExecutor de {session.session_id}: {exc}")
                session.command_executor = getattr(self, "command_executor", None)

        # 2. CommandApprovalHandler propio (usa executor + UI de la pestaña)
        if getattr(session, "approval_handler", None) is not None:
            # Handler heredado (p.ej. el global de __init__): reapuntarlo al
            # executor/UI de esta pestaña para que no ejecute en otro shell.
            try:
                if session.command_executor is not None and getattr(
                    session.approval_handler, "command_executor", None
                ) is not session.command_executor:
                    session.approval_handler.command_executor = session.command_executor
                if hasattr(session.approval_handler, "terminal_ui"):
                    session.approval_handler.terminal_ui = proxy
            except Exception:
                pass
        else:
            try:
                from kogniterm.terminal.command_approval_handler import (
                    CommandApprovalHandler as _CAH,
                )

                _g = getattr(self, "command_approval_handler", None)
                session.approval_handler = _CAH(
                    self.llm_service,
                    session.command_executor,
                    None,
                    proxy,
                    agent_state,
                    getattr(_g, "file_update_tool", None),
                    getattr(_g, "advanced_file_editor_tool", None),
                    getattr(_g, "file_operations_tool", None),
                )
                try:
                    session.approval_handler.auto_approve = bool(
                        getattr(_g, "auto_approve", getattr(self, "_auto_approve_all", False))
                    )
                except Exception:
                    pass
            except Exception as exc:
                logger.debug(f"No se pudo crear approval handler de {session.session_id}: {exc}")
                session.approval_handler = getattr(self, "command_approval_handler", None)

        # 3. AgentInteractionManager + MetaCommandProcessor propios
        if getattr(session, "interaction_manager", None) is None:
            try:
                if AgentInteractionManager is not None and getattr(self, "llm_service", None) is not None:
                    session.interaction_manager = AgentInteractionManager(
                        self.llm_service,
                        agent_state,
                        proxy,
                        interrupt_q,
                        session.approval_handler
                        or getattr(self, "command_approval_handler", None),
                    )
            except Exception as exc:
                logger.debug(f"No se pudo crear interaction manager de {session.session_id}: {exc}")
                session.interaction_manager = getattr(self, "agent_interaction_manager", None)
        if getattr(session, "meta_processor", None) is None:
            try:
                from kogniterm.terminal.meta_command_processor import MetaCommandProcessor

                session.meta_processor = MetaCommandProcessor(
                    self.llm_service, agent_state, proxy, self
                )
            except Exception as exc:
                logger.debug(f"No se pudo crear meta processor de {session.session_id}: {exc}")
                session.meta_processor = getattr(self, "meta_command_processor", None)

        try:
            session._managers_ready = True
        except Exception:
            pass
        # El executor puede haberse creado tarde: refrescar barra de estado
        try:
            self._refresh_session_tabs()
        except Exception:
            pass

    def _mount_session_widget(self, session):
        """Monta el ChatLogWidget de la sesión en #sessions_content."""
        if ChatLogWidget is None:
            return None
        existing = self._session_widget(session)
        if existing is not None:
            return existing
        try:
            container = self.query_one("#sessions_content")
        except Exception:
            return None
        widget = ChatLogWidget(id=session.chat_widget_id, classes="session-chat")
        try:
            container.mount(widget)
        except Exception as exc:
            logger.debug(f"No se pudo montar widget de {session.session_id}: {exc}")
            return None
        # Solo la pestaña activa es visible
        try:
            widget.display = session.session_id == self._active_session_id
        except Exception:
            pass
        return widget

    def create_session(self, title: Optional[str] = None, _initial: bool = False):
        """Crea una pestaña nueva (mismo workspace) y cambia a ella."""
        if Session is None:
            return None
        sessions = self.list_sessions()
        if title is None or not str(title).strip():
            try:
                title = build_session_title(len(sessions) + 1) if build_session_title else f"Sesión {len(sessions) + 1}"
            except Exception:
                title = f"Sesión {len(sessions) + 1}"
        session = self._create_session_state(str(title).strip())
        try:
            self._mount_session_widget(session)
        except Exception:
            pass
        self.switch_session(session.session_id)
        # En modo servidor, la pestaña nueva abre su propia sesión remota
        try:
            if self._server_mode:
                self._ensure_session_client(session)
        except Exception:
            pass
        # Managers pesados en segundo plano: crear una pestaña no debe
        # bloquear la UI (suele tardar por system prompt + agentes).
        # La sesión inicial NO se pre-construye: en el caso normal ya tiene
        # los managers globales de __init__, y si faltan se construyen al
        # enviar el primer mensaje (evita ruido en el arranque).
        try:
            if not getattr(session, "_managers_ready", False) and self._session_counter > 1:
                th = threading.Thread(
                    target=self._build_session_managers_worker,
                    args=(session.session_id,),
                    daemon=True,
                    name=f"kogniterm-session-managers-{session.session_id}",
                )
                th.start()
        except Exception:
            pass
        if not _initial:
            try:
                session.ui_proxy.print_message(
                    f"🆕 **{session.title}** — mismo proyecto/workspace.",
                    style="dim",
                )
            except Exception:
                pass
        return session

    def switch_session(self, session_id: str) -> bool:
        """Muestra la pestaña indicada y sincroniza el contexto legacy."""
        session = self.get_session(session_id)
        if session is None:
            return False
        # Asegurar widget montado
        try:
            if self._session_widget(session) is None:
                self._mount_session_widget(session)
        except Exception:
            pass
        self._active_session_id = session.session_id
        # Alias legacy de WS hacia la pestaña activa
        try:
            self._sync_legacy_ws_alias()
        except Exception:
            pass
        # Visibilidad: solo la activa
        try:
            for sid in self._session_order:
                s = self._sessions.get(sid)
                if s is None:
                    continue
                w = self._session_widget(s)
                if w is not None:
                    w.display = sid == session.session_id
        except Exception:
            pass
        # Sincronizar contexto legacy (thread actual + historial global) para
        # que los meta-comandos y el modo servidor operen sobre esta pestaña.
        try:
            if getattr(self, "thread_manager", None) is not None and session.thread_id:
                self.thread_manager.set_current_thread_id(session.thread_id)
        except Exception:
            pass
        try:
            if getattr(self, "llm_service", None) is not None and session.agent_state is not None:
                self.llm_service.conversation_history = list(session.agent_state.messages or [])
        except Exception:
            pass
        try:
            if hasattr(self, "queue_display"):
                self.queue_display.update_queue(session.input_queue)
        except Exception:
            pass
        self._refresh_session_tabs()
        try:
            widget = self._session_widget(session)
            if widget is not None:
                widget.scroll_end(animate=False)
        except Exception:
            pass
        # Reflejar el estado interactivo de la pestaña en la UI global
        # (cada pestaña conserva su propio cursor/executor).
        try:
            self.interactive_executor = getattr(session, "interactive_executor", None)
            self._cursor_active = bool(getattr(session, "cursor_active", False))
            chat_input = self.query_one("#chat_input", ChatInput)
            if self._cursor_active:
                chat_input.placeholder = "Terminal Interactiva (Escribe abajo o HAZ CLIC en el panel para modo directo)..."
                chat_input.styles.color = "#10b981"
                try:
                    self.live_display.add_class("interactive")
                except Exception:
                    pass
            else:
                chat_input.placeholder = "Escribe un mensaje..."
                chat_input.styles.color = "white"
                try:
                    self.live_display.remove_class("interactive")
                except Exception:
                    pass
            chat_input.focus()
        except Exception:
            try:
                self.query_one("#chat_input", ChatInput).focus()
            except Exception:
                pass
        return True

    def close_session(self, session_id: Optional[str] = None) -> bool:
        """Cierra una pestaña (no elimina su thread persistido)."""
        session = self.get_session(session_id) if session_id else self.get_active_session()
        if session is None:
            return False
        if len(self._session_order) <= 1:
            try:
                session.ui_proxy.print_message(
                    "⚠️ No se puede cerrar la última pestaña. Usa `/reset` para limpiar.",
                    style="yellow",
                )
            except Exception:
                pass
            return False
        if session.is_processing:
            try:
                session.ui_proxy.print_message(
                    "⏳ La pestaña está procesando. Pulsa `esc` para interrumpir antes de cerrarla.",
                    style="yellow",
                )
            except Exception:
                pass
            return False
        # Persistir por si acaso (el thread queda disponible en /resume)
        try:
            if getattr(self, "thread_manager", None) is not None and session.thread_id:
                self.thread_manager.save_thread_messages(
                    session.thread_id, list(session.agent_state.messages or [])
                )
        except Exception:
            pass
        # Detener el WebSocket de la pestaña (modo servidor)
        try:
            _sess_ws = getattr(session, "ws_client", None)
            if _sess_ws is not None:
                try:
                    _sess_ws.stop()
                except Exception:
                    pass
            _ws_task = getattr(session, "ws_task", None)
            if _ws_task is not None:
                try:
                    _ws_task.cancel()
                except Exception:
                    pass
            session.ws_client = None
            session.ws_task = None
        except Exception:
            pass
        try:
            widget = self._session_widget(session)
            if widget is not None:
                widget.remove()
        except Exception:
            pass
        try:
            self._session_order.remove(session.session_id)
            self._sessions.pop(session.session_id, None)
        except Exception:
            pass
        # Activar vecina (el refresh de pestañas elimina el botón obsoleto)
        if self._active_session_id == session.session_id:
            neighbor = self._session_order[-1] if self._session_order else None
            if neighbor:
                self.switch_session(neighbor)
                return True
        self._refresh_session_tabs()
        return True

    def rename_session(self, new_title: str, session_id: Optional[str] = None) -> bool:
        session = self.get_session(session_id) if session_id else self.get_active_session()
        if session is None or not new_title or not str(new_title).strip():
            return False
        session.title = str(new_title).strip()[:40]
        try:
            if getattr(self, "thread_manager", None) is not None and session.thread_id:
                self.thread_manager.rename_thread(session.thread_id, session.title)
        except Exception:
            pass
        self._refresh_session_tabs()
        return True

    # Frames del spinner animado en la etiqueta de la pestaña
    SESSION_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # ── Título de la conversación (naming por LLM) ───────────────────

    GENERIC_TITLES = {
        "Nueva conversación",
        "Nueva Conversación",
        "Conversación sin título",
        "Conversación",
        "",
    }

    def _title_is_generic(self, title: Optional[str]) -> bool:
        t = (title or "").strip()
        if not t:
            return True
        if t in self.GENERIC_TITLES:
            return True
        # "Sesión N" es el nombre provisional de una pestaña nueva
        return bool(re.match(r"^Sesión \d+$", t)) or t in ("Session", "session")

    def _apply_session_title(self, session_id: Optional[str], title: str):
        """Aplica a una pestaña un título nuevo (del LLM o del servidor)."""
        try:
            session = self.get_session(session_id) if session_id else self.get_active_session()
            if session is None:
                return
            clean = " ".join(str(title or "").split())[:60]
            if not clean or clean == session.title:
                return
            session.title = clean
            self._refresh_session_tabs()
        except Exception as exc:
            logger.debug(f"_apply_session_title falló: {exc}")

    def _provisional_title_from_request(self, session, user_input: str):
        """Título provisional inmediato con las primeras palabras de la petición.

        Marca el título como "fallback" para que el LLM pueda sustituirlo
        después (mismo criterio que usa el servidor).
        """
        try:
            if session is None or not self._title_is_generic(session.title):
                return
            text = " ".join(str(user_input or "").split())
            if not text:
                return
            # Quitar prefijos de comando por si vinieran
            for pref in ("/", "%"):
                if text.startswith(pref):
                    text = text[1:].lstrip()
            if not text:
                return
            session.title = text[:40]
            try:
                if getattr(self, "thread_manager", None) is not None and session.thread_id:
                    self.thread_manager.rename_thread(
                        session.thread_id, session.title, source="fallback"
                    )
            except Exception:
                pass
            self._refresh_session_tabs()
        except Exception as exc:
            logger.debug(f"_provisional_title_from_request falló: {exc}")

    def _request_llm_title(self, session_id: str):
        """Pide al LLM un título para la conversación (en background).

        En local el worker del agente corre en un hilo sin event loop, así que
        `schedule_title_generation` no puede agendar nada: lo ejecutamos aquí
        con su propio loop y aplicamos el resultado a la pestaña.
        """
        session = self.get_session(session_id)
        if session is None:
            return
        tm = getattr(self, "thread_manager", None)
        llm = getattr(self, "llm_service", None)
        if tm is None or llm is None or not session.thread_id:
            return

        def _worker():
            try:
                messages = list(session.agent_state.messages or [])
                title = asyncio.run(
                    tm.generate_title_if_needed(session.thread_id, messages, llm)
                )
                if title:
                    self.call_from_thread(self._apply_session_title, session_id, title)
            except Exception as exc:
                logger.debug(f"No se pudo generar título LLM para {session_id}: {exc}")

        try:
            threading.Thread(
                target=_worker, daemon=True, name=f"kogniterm-title-{session_id}"
            ).start()
        except Exception:
            pass

    def _sync_session_title_from_thread(self, session_id: str):
        """Relee el título del hilo y lo refleja en la pestaña (respaldo).

        Solo aplica si la pestaña aún tiene un título genérico: nunca pisa un
        título del servidor/LLM ya asignado con uno local más viejo.
        """
        try:
            session = self.get_session(session_id)
            tm = getattr(self, "thread_manager", None)
            if session is None or tm is None or not session.thread_id:
                return
            if not self._title_is_generic(session.title):
                return
            meta = tm.get_thread_metadata(session.thread_id) or {}
            title = (meta.get("title") or "").strip()
            if title and title != session.title:
                session.title = title
                self._refresh_session_tabs()
        except Exception:
            pass

    def _tab_prefix(self, session) -> str:
        """Prefijo de la etiqueta (`? ` / spinner / vacío), compartido por la
        etiqueta estática y la marquesina."""
        try:
            if int(getattr(session, "pending_approvals", 0) or 0) > 0:
                return "? "
            if session.is_processing:
                frames = self.SESSION_SPINNER_FRAMES
                return f"{frames[self._session_spinner_frame % len(frames)]} "
        except Exception:
            pass
        return ""

    def _session_tab_label(self, session, idx: int, total: int) -> str:
        label = session.title or f"Sesión {idx + 1}"
        # Si no cabe, se corta y se marca con "..." para que se note
        max_len = 20
        if len(label) > max_len:
            label = label[: max_len - 3].rstrip() + "..."
        return self._tab_prefix(session) + label

    def _update_tab_labels(self):
        """Recalcula y aplica las etiquetas de las pestañas (hilo de la app).

        La pestaña bajo el ratón la gobierna la marquesina y se salta aquí.
        """
        try:
            sessions = self.list_sessions()
        except Exception:
            return
        for idx, s in enumerate(sessions):
            try:
                if s.session_id == self._hover_tab_id:
                    continue
                btn = self.query_one(f"#session-tab-{s.session_id}", Button)
                btn.label = self._session_tab_label(s, idx, len(sessions))
            except Exception:
                continue

    def _tab_hover_enter(self, session_id: str):
        """El ratón entra en una pestaña: arranca la marquesina si no cabe."""
        try:
            session = self.get_session(session_id)
            if session is None:
                return
            full = session.title or ""
            if len(full) <= self._marquee_width:
                return  # cabe entero, no hay nada que desplazar
            self._hover_tab_id = session_id
            self._marquee_tick = 0
            self._start_marquee_timer()
        except Exception:
            pass

    def _tab_hover_leave(self, session_id: str):
        """El ratón sale de la pestaña: se restaura su etiqueta estática."""
        try:
            if self._hover_tab_id != session_id:
                return
            self._hover_tab_id = None
            self._stop_marquee_timer()
            self._update_tab_labels()
        except Exception:
            pass

    def _start_marquee_timer(self):
        try:
            if self._marquee_timer is None:
                self._marquee_timer = self.set_interval(0.25, self._tick_tab_marquee)
        except Exception:
            self._marquee_timer = None

    def _stop_marquee_timer(self):
        try:
            if self._marquee_timer is not None:
                self._marquee_timer.stop()
        except Exception:
            pass
        self._marquee_timer = None

    def _tick_tab_marquee(self):
        """Desplaza la ventana visible del título (ping-pong con pausas)."""
        try:
            import threading as _th

            if _th.current_thread() is not _th.main_thread():
                return
            session = self.get_session(self._hover_tab_id) if self._hover_tab_id else None
            if session is None:
                self._stop_marquee_timer()
                return
            full = session.title or ""
            width = self._marquee_width
            if len(full) <= width:
                self._stop_marquee_timer()
                self._update_tab_labels()
                return
            self._marquee_tick += 1
            span = len(full) - width
            dwell = self._marquee_dwell
            cycle = 2 * span + 2 * dwell
            t = self._marquee_tick % cycle
            if t < dwell:
                off = 0
            elif t < dwell + span:
                off = t - dwell
            elif t < 2 * dwell + span:
                off = span
            else:
                off = span - (t - (2 * dwell + span))
            btn = self.query_one(f"#session-tab-{session.session_id}", Button)
            btn.label = self._tab_prefix(session) + full[off : off + width]
        except Exception:
            pass

    def _tick_session_spinners(self):
        """Avanza un frame del spinner de las pestañas ocupadas."""
        try:
            if threading.current_thread() is not threading.main_thread():
                return
            self._session_spinner_frame += 1
            self._update_tab_labels()
        except Exception:
            pass

    def _sync_session_spinner_timer(self):
        """Arranca/para el timer del spinner según haya pestañas ocupadas."""
        try:
            any_busy = any(s.is_processing for s in self.list_sessions())
        except Exception:
            return
        if any_busy and self._session_spinner_timer is None:
            try:
                self._session_spinner_timer = self.set_interval(
                    0.12, self._tick_session_spinners
                )
            except Exception:
                self._session_spinner_timer = None
        elif not any_busy and self._session_spinner_timer is not None:
            try:
                self._session_spinner_timer.stop()
            except Exception:
                pass
            self._session_spinner_timer = None
            self._session_spinner_frame = 0
            # Quitar el spinner de las etiquetas
            self._update_tab_labels()

    def _style_session_tab(self, btn, wrap, session) -> None:
        """Aplica a una pestaña los colores del tema activo.

        Inactiva = texto secundario sobre fondo transparente; activa = PRIMARY
        con texto de contraste; ocupada = WARNING; y la X de cierre en gris
        (o rojo si la pestaña está ocupada).
        """
        try:
            from kogniterm.terminal.themes import ColorPalette as P

            is_active = session.session_id == self._active_session_id
            is_busy = bool(session.is_processing) or int(
                getattr(session, "pending_approvals", 0) or 0
            ) > 0
            contrast = "#ffffff" if self.dark else getattr(P, "GRAY_900", "#111827")

            if is_active:
                btn.styles.background = P.PRIMARY
                btn.styles.color = contrast
            else:
                btn.styles.background = "transparent"
                # Solo color: un borde en un botón de 1 fila se comería el
                # alto y dejaría el nombre invisible.
                btn.styles.color = P.WARNING if is_busy else P.TEXT_SECONDARY

            try:
                close_btn = wrap.query_one(
                    f"#session-close-{session.session_id}", Button
                )
                close_btn.styles.background = "transparent"
                close_btn.styles.color = (
                    P.ERROR if is_busy else getattr(P, "GRAY_500", "#6b7280")
                )
            except Exception:
                pass
        except Exception as exc:
            logger.debug(f"_style_session_tab falló: {exc}")

    def _refresh_session_tabs(self):
        """Actualiza la barra de pestañas reutilizando widgets existentes.

        Cada pestaña es un contenedor `session-wrap-<id>` con dos botones:
        la etiqueta (`session-tab-<id>`, cambia de pestaña) y la X de cierre
        (`session-close-<id>`). Reutilizar en lugar de recrear evita
        colisiones de IDs duplicados y bucles de layout: solo se monta o
        destruye cuando cambia el número de sesiones.

        Llamar desde el hilo de la app.
        """
        def _do_refresh():
            try:
                tabs = self.query_one("#sessions_list")
            except Exception:
                return
            sessions = self.list_sessions()
            wanted_ids = {s.session_id for s in sessions}
            try:
                existing = {}
                for child in list(tabs.children):
                    cid = getattr(child, "id", "") or ""
                    if cid.startswith("session-wrap-"):
                        existing[cid[len("session-wrap-"):]] = child
                # Eliminar pestañas de sesiones que ya no existen
                for sid, child in existing.items():
                    if sid not in wanted_ids:
                        try:
                            child.remove()
                        except Exception:
                            pass
                # Actualizar o crear
                for idx, s in enumerate(sessions):
                    label = self._session_tab_label(s, idx, len(sessions))
                    wrap = existing.get(s.session_id)
                    btn = None
                    if wrap is None:
                        try:
                            wrap = Horizontal(
                                id=f"session-wrap-{s.session_id}",
                                classes="session-tab-wrap",
                            )
                            # El contenedor debe estar montado antes de
                            # colgarle hijos (Textual lo exige).
                            tabs.mount(wrap)
                            btn = SessionTabButton(
                                label,
                                id=f"session-tab-{s.session_id}",
                                classes="session-tab",
                                tooltip=f"{s.title} ({idx + 1}/{len(sessions)})",
                                session_id=s.session_id,
                            )
                            close_btn = Button(
                                "×",
                                id=f"session-close-{s.session_id}",
                                classes="session-close",
                                tooltip=f"Cerrar {s.title}",
                            )
                            wrap.mount(btn)
                            wrap.mount(close_btn)
                        except Exception as exc:
                            logger.debug(f"No se pudo montar pestaña {s.session_id}: {exc}")
                            continue
                    else:
                        try:
                            btn = wrap.query_one(f"#session-tab-{s.session_id}", Button)
                        except Exception:
                            btn = None
                        if btn is not None:
                            # Button.label es un reactive (Button.render() lo
                            # usa); Static.update() no cambiaría la etiqueta.
                            try:
                                btn.label = label
                            except Exception:
                                try:
                                    btn.update(label)
                                except Exception:
                                    pass
                            try:
                                btn.tooltip = f"{s.title} ({idx + 1}/{len(sessions)})"
                            except Exception:
                                pass
                    if btn is None:
                        continue
                    try:
                        is_active = s.session_id == self._active_session_id
                        _busy = bool(s.is_processing) or int(
                            getattr(s, "pending_approvals", 0) or 0
                        ) > 0
                        btn.set_class(is_active, "--active")
                        btn.set_class(_busy, "--busy")
                        if "session-tab" not in btn.classes:
                            btn.add_class("session-tab")
                    except Exception:
                        pass
                    # Colores según el tema activo
                    try:
                        self._style_session_tab(btn, wrap, s)
                    except Exception:
                        pass
            except Exception as exc:
                logger.debug(f"_refresh_session_tabs falló: {exc}")
            # El spinner de las pestañas solo corre mientras haya trabajo
            try:
                self._sync_session_spinner_timer()
            except Exception:
                pass
        try:
            import threading as _th

            if _th.current_thread() is _th.main_thread():
                _do_refresh()
            else:
                self.call_from_thread(_do_refresh)
        except Exception:
            try:
                _do_refresh()
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Botón '+' y clics en pestañas (no interfiere con otros botones)."""
        try:
            btn_id = getattr(event.button, "id", "") or ""
        except Exception:
            return
        if btn_id == "new_session_btn":
            try:
                self.create_session()
                try:
                    self.query_one("#chat_input", ChatInput).focus()
                except Exception:
                    pass
            except Exception as exc:
                logger.error(f"Error creando sesión: {exc}", exc_info=True)
            event.prevent_default()
            event.stop()
            return
        if btn_id.startswith("session-close-"):
            sid = btn_id[len("session-close-"):]
            try:
                self.close_session(sid)
            except Exception as exc:
                logger.error(f"Error cerrando sesión {sid}: {exc}", exc_info=True)
            event.prevent_default()
            event.stop()
            return
        if btn_id.startswith("session-tab-"):
            sid = btn_id[len("session-tab-"):]
            try:
                self.switch_session(sid)
            except Exception as exc:
                logger.error(f"Error cambiando de sesión: {exc}", exc_info=True)
            event.prevent_default()
            event.stop()
            return

    def action_new_session(self) -> None:
        """Ctrl+N: nueva pestaña en el mismo workspace."""
        try:
            self.create_session()
        except Exception as exc:
            logger.error(f"action_new_session falló: {exc}", exc_info=True)

    def action_close_session(self) -> None:
        """Ctrl+W: cerrar la pestaña activa."""
        try:
            self.close_session()
        except Exception as exc:
            logger.error(f"action_close_session falló: {exc}", exc_info=True)

    def action_next_session(self) -> None:
        """Ctrl+PgDn: siguiente pestaña."""
        try:
            if len(self._session_order) < 2:
                return
            idx = self._session_order.index(self._active_session_id) if self._active_session_id in self._session_order else -1
            self.switch_session(self._session_order[(idx + 1) % len(self._session_order)])
        except Exception as exc:
            logger.debug(f"action_next_session falló: {exc}")

    def action_prev_session(self) -> None:
        """Ctrl+PgUp: pestaña anterior."""
        try:
            if len(self._session_order) < 2:
                return
            idx = self._session_order.index(self._active_session_id) if self._active_session_id in self._session_order else 0
            self.switch_session(self._session_order[(idx - 1) % len(self._session_order)])
        except Exception as exc:
            logger.debug(f"action_prev_session falló: {exc}")

    def _spinner_active_for_session(self, session_id: str) -> bool:
        """¿Hay un spinner realmente activo para esa pestaña?

        Se usa para NO detener el stream del chat en cada fragmento de texto:
        `_stop_spinner()` implica `chat_log.stop_stream()`.
        """
        try:
            session = self.get_session(session_id)
            if session is None:
                return False
            if session.session_id == self._active_session_id:
                return self._spinner_timer is not None
            return bool(getattr(session, "inline_spinner", False))
        except Exception:
            return False

    def _start_spinner_for_session(self, session_id: str):
        """Spinner global si la sesión está activa; inline si está en fondo."""
        session = self.get_session(session_id)
        if session is None:
            return
        if session_id == self._active_session_id:
            try:
                self._start_spinner()
            except Exception:
                pass
        else:
            widget = self._session_widget(session)
            if widget is not None:
                try:
                    widget.write_stream(("__SPINNER__", "Procesando..."))
                    session.inline_spinner = True
                except Exception:
                    pass
        self._refresh_session_tabs()

    def _stop_spinner_for_session(self, session_id: str):
        session = self.get_session(session_id)
        if session is None:
            return
        if session_id == self._active_session_id:
            try:
                self._stop_spinner()
            except Exception:
                pass
        else:
            # Solo cerrar el stream si este turno puso un spinner inline:
            # `stop_stream()` corta el widget en curso y, de llamarse en cada
            # fragmento, duplica la respuesta en el chat.
            if getattr(session, "inline_spinner", False):
                session.inline_spinner = False
                widget = self._session_widget(session)
                if widget is not None:
                    try:
                        widget.stop_stream()
                    except Exception:
                        pass
        self._refresh_session_tabs()

    def _on_session_finished(self, session_id: str):
        """Limpieza UI al terminar un worker de sesión (hilo de la app)."""
        self._stop_spinner_for_session(session_id)
        # El hilo pudo ser renombrado en el meanwhile (servidor o LLM en local)
        try:
            self._sync_session_title_from_thread(session_id)
        except Exception:
            pass
        # En local no hay event loop en el worker: pedimos el título aquí
        try:
            session = self.get_session(session_id)
            if session is not None and not getattr(self, "_server_mode", False):
                self._request_llm_title(session_id)
        except Exception:
            pass
        try:
            self._process_queue(session_id)
        except Exception:
            pass

    def _render_history_into_session(self, session, history: list):
        """Pinta un historial cargado en el widget de la sesión."""
        from langchain_core.messages import HumanMessage as _HM, AIMessage as _AM, ToolMessage as _TM

        widget = self._session_widget(session)
        if widget is None or not history:
            return
        try:
            widget.clear()
        except Exception:
            pass
        for msg in history:
            try:
                content = getattr(msg, "content", "")
                if isinstance(msg, _HM) or getattr(msg, "type", None) == "human":
                    if content:
                        widget.write_user_message(content)
                elif isinstance(msg, _AM) or getattr(msg, "type", None) == "ai":
                    reasoning = ""
                    try:
                        if isinstance(getattr(msg, "additional_kwargs", None), dict):
                            reasoning = msg.additional_kwargs.get("reasoning_content", "")
                    except Exception:
                        pass
                    if reasoning:
                        try:
                            from kogniterm.terminal.visual_components import create_thought_bubble

                            widget.write(create_thought_bubble(reasoning))
                        except Exception:
                            pass
                    if content and isinstance(content, str):
                        widget.write_agent_message(content)
                elif isinstance(msg, _TM) or getattr(msg, "type", None) == "tool":
                    if content:
                        widget.write_tool_output(str(content), getattr(msg, "name", None) or "tool")
            except Exception as exc:
                logger.debug(f"Error renderizando mensaje en sesión: {exc}")
        try:
            widget.scroll_end(animate=False)
        except Exception:
            pass

    @staticmethod
    def _pane_id(agent_id: str) -> str:
        """Genera un ID de TabPane seguro para Textual (sin guiones bajos)."""
        return f"pane-{agent_id.replace('_', '-')}"

    def add_agent_tab(self, agent_id: str, title: str) -> ChatLogWidget:
        """Añade dinámicamente una pestaña para un subagente y retorna su ChatLogWidget."""
        tabbed_content = self.query_one("#parallel_agents_container", TabbedContent)
        pane_id = self._pane_id(agent_id)

        # Verificar si ya existe
        try:
            widget = self.query_one(f"#live_display_{agent_id}", ChatLogWidget)
            return widget
        except Exception:
            pass

        widget = ChatLogWidget(id=f"live_display_{agent_id}")
        pane = TabPane(title, widget, id=pane_id)

        # add_pane debe ejecutarse en el thread principal
        if threading.current_thread() is threading.main_thread():
            tabbed_content.add_pane(pane)
        else:
            self.call_from_thread(tabbed_content.add_pane, pane)

        return widget

    def remove_agent_tab(self, agent_id: str):
        """Elimina una pestaña de subagente por su id."""
        tabbed_content = self.query_one("#parallel_agents_container", TabbedContent)
        pane_id = self._pane_id(agent_id)

        def _remove():
            try:
                tabbed_content.remove_pane(pane_id)
            except Exception:
                pass

        if threading.current_thread() is threading.main_thread():
            _remove()
        else:
            self.call_from_thread(_remove)

    def update_agent_tab_title(self, agent_id: str, new_title: str):
        """Actualiza el título visible de una pestaña de subagente."""
        tabbed_content = self.query_one("#parallel_agents_container", TabbedContent)
        pane_id = self._pane_id(agent_id)

        def _update():
            try:
                pane = tabbed_content.get_pane(pane_id)
                pane.title = new_title
                # Buscar el widget Tab correspondiente para cambiar su label
                for tab in tabbed_content.query("Tab"):
                    if tab.id == f"tab-{pane_id}" or getattr(tab, "pane_id", None) == pane_id:
                        tab.label = new_title
                        break
            except Exception as e:
                logger.warning("No se pudo actualizar el título de la pestaña %s: %s", agent_id, e)

        if threading.current_thread() is threading.main_thread():
            _update()
        else:
            self.call_from_thread(_update)


    def activate_parallel_container(self) -> None:
        """Muestra el TabbedContent de agentes paralelos."""
        try:
            self.query_one("#bottom_container").display = True
        except Exception:
            pass
        try:
            self.query_one("#parallel_agents_container").display = True
        except Exception:
            pass
        self.refresh(layout=True)

    def deactivate_parallel_container(self) -> None:
        """Oculta el TabbedContent de agentes paralelos."""
        try:
            self.query_one("#parallel_agents_container").display = False
        except Exception:
            pass
        self.refresh(layout=True)

    def update_live_display(self, renderable, panel_id=None):
        """Actualiza el widget de streaming en tiempo real directamente en el chat log."""
        if panel_id:
            try:
                panel = self.query_one(f"#{panel_id}")
                # NO forzar panel.display = True aquí - la visibilidad se controla
                # explícitamente por el usuario con Ctrl+O (action_toggle_tool_panel)
                # Manejo especial para terminales en paneles dedicados
                from kogniterm.terminal.tui.components.chat_log import ChatLogWidget

                if isinstance(renderable, tuple) and renderable[0] == "__TERMINAL__":
                    tool_name = renderable[1]
                    output = renderable[2]
                    command = renderable[3] if len(renderable) >= 4 else tool_name
                    if hasattr(panel, "update_content"):
                        panel.update_content(output, command=command)
                    elif isinstance(panel, ChatLogWidget):
                        panel.write_stream(("__TERMINAL__", tool_name, output, command))
                    else:
                        panel.update(output)
                elif isinstance(panel, ChatLogWidget):
                    # ChatLogWidget (VerticalScroll) no tiene update(); usar write_stream
                    panel.write_stream(renderable)
                else:
                    panel.update(renderable)
                return
            except Exception:
                pass
        # Detener spinner INMEDIATAMENTE cuando llega contenido real.
        if self._spinner_timer:
            self._stop_spinner()
        self._last_live_renderable = renderable
        # Enviar al chat log para streaming en sitio
        self.chat_log.write_stream(renderable)
        # Opcional: auto-scroll si el usuario está cerca del final
        try:
            log = self.chat_log
            if log.scroll_y >= log.max_scroll_y - 1:
                log.scroll_end(animate=False)
        except Exception:
            pass

    def update_terminal_output(
        self, tool_name: str, output: str, show_cursor: bool = None, command: str = ""
    ):
        """
        Actualiza el panel de terminal con soporte para cursor parpadeante.
        """
        # Guardar para el timer de parpadeo
        self._last_terminal_tool_name = tool_name
        self._last_terminal_output = output

        if show_cursor is None:
            # Pestañeo: visible en frame 0, invisible en frame 1
            show_cursor = self._cursor_active and (self._cursor_frame == 0)

        # El comando a mostrar en el título: preferir el argumento explícito, si no el tool_name
        # Si es el nombre genérico de la herramienta de ejecución, usamos un indicador más claro
        if not command or command == "execute_command":
            display_command = "bash" if tool_name == "execute_command" else tool_name
        else:
            display_command = command

        # Pasamos el output crudo con una tupla marcadora para que ChatLogWidget instancie el ToolOutputWidget
        # Tupla de 4 elementos: (__TERMINAL__, tool_name, output, display_command)
        self.update_live_display(
            ("__TERMINAL__", tool_name, output, display_command)
        )

    def update_task_tracker(self, agent_plans: dict):
        """Muestra el estado de las tareas en el flujo de chat usando un panel verde."""
        if not agent_plans:
            return

        from rich.table import Table
        from rich.text import Text
        from rich.console import Group
        from rich.panel import Panel
        from kogniterm.terminal.themes import ColorPalette
        from kogniterm.terminal.tui.components.chat_log import ChatLogWidget

        # Obtener todos los ChatLogWidgets en la aplicación
        all_logs = list(self.query(ChatLogWidget))

        # Agrupar los bloques de tareas por su ChatLogWidget destino
        log_to_blocks = {}

        for agent_name, tasks in agent_plans.items():
            if not tasks:
                continue

            header = Text.from_markup(
                f"[bold {ColorPalette.SECONDARY}]● {agent_name}[/bold {ColorPalette.SECONDARY}]"
            )
            table = Table(
                expand=True, box=None, show_header=False, padding=(0, 1), title=None
            )
            table.add_column("Status")
            table.add_column("Task")

            for task in tasks:
                status = task.get("status", "pending")
                task_text = task.get("task", "")

                if status == "done":
                    style = "strike #525252"
                    status_icon = "✅"
                elif status == "in-progress":
                    style = "bold cyan"
                    status_icon = "🔄"
                else:
                    style = "white"
                    status_icon = "⏳"

                table.add_row(status_icon, f"[{style}]{task_text}[/]")

            block = Group(header, table)

            # Buscar el ChatLogWidget correspondiente a este agente
            target_log = None
            normalized_name = agent_name.lower().replace(" ", "_")
            for log_widget in all_logs:
                widget_id = (log_widget.id or "").lower()
                if widget_id != "chat_log" and (
                    normalized_name in widget_id or widget_id in normalized_name
                ):
                    target_log = log_widget
                    break

            if not target_log:
                target_log = self.chat_log

            if target_log not in log_to_blocks:
                log_to_blocks[target_log] = []
            log_to_blocks[target_log].append(block)

        # Para cada log_widget, construir y escribir/actualizar su panel
        for log_widget, blocks in log_to_blocks.items():
            if blocks:
                panel = Panel(
                    Group(*blocks),
                    border_style="green",
                    title="[bold green]Task Tracker[/bold green]",
                    title_align="left",
                    expand=True,
                )
                if hasattr(log_widget, "write_task_tracker"):
                    log_widget.write_task_tracker(panel)
                else:
                    log_widget.write_message(panel)

    def action_toggle_tool_panel(self):
        """Método obsoleto de alternancia del panel de herramientas."""
        pass

    def hide_live_display(self):
        """Finaliza el streaming en el chat log."""
        # Asegurar que el spinner se detenga
        self._stop_spinner()

        # Ocultar paneles dedicados si estaban visibles
        try:
            self.live_display.display = False
        except Exception:
            pass

        # NOTA: Ya no movemos contenido del live_display al log porque EL STREAMING SUCEDE EN EL LOG.
        # Solo marcamos el fin del stream actual en el ChatLogWidget.
        self.chat_log.stop_stream()

        self._last_live_renderable = None

        # Reset de estado de terminal para evitar fugas visuales
        self._last_terminal_tool_name = ""
        self._last_terminal_output = ""

        # Scroll al final
        self.chat_log.scroll_end(animate=False)


# Alias para retrocompatibilidad
TUIApp = KogniTermTUI
