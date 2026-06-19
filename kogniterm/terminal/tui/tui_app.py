import asyncio
import os
import queue
import json
import logging
from typing import Any, Optional
from textual.app import App, ComposeResult
from textual import work
from textual.widgets import Input, ListView, ListItem, Label, Button, Static, TextArea, RichLog, TabbedContent, TabPane
from textual.containers import Vertical, Horizontal
from textual import events
from langchain_core.messages import HumanMessage
import threading

logger = logging.getLogger(__name__)

# URL del servidor KogniTerm (puede sobreescribirse con KOGNITERM_SERVER_URL)
_DEFAULT_SERVER_URL = os.environ.get("KOGNITERM_SERVER_URL", "ws://127.0.0.1:8765")
_DEFAULT_SESSION_ID = os.environ.get("KOGNITERM_SESSION_ID", "tui-default")


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
    from kogniterm.terminal.tui.components.command_approval_modal import CommandApprovalModal
except Exception:
    CommandApprovalModal = None
try:
    from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager
except Exception:
    AgentInteractionManager = None
try:
    from kogniterm.terminal.command_approval_handler import CommandApprovalHandler
except Exception:
    CommandApprovalHandler = None
from .components.task_tracker_panel import TaskTrackerPanelWidget
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
                        arg = arg.decode('utf-8')
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
        self.tooltip = "Haz clic o usa TAB para capturar teclado y enviar comandos directos"

class TextualTerminalUI:
    """Adaptador para que la lógica existente escriba en el ChatLog Textual."""
    def __init__(self, textual_app):
        self.app = textual_app
        self.interrupt_queue = queue.Queue()
        self.console = DummyConsole(self)
        self.kb = None
        self.is_tui = True
        
    def _safe_call(self, func, *args, **kwargs):
        """Call a function safely depending on whether we are in the main thread or not."""
        if threading.current_thread() is threading.main_thread():
            func(*args, **kwargs)
        else:
            self.app.call_from_thread(func, *args, **kwargs)

    def print_message(self, message: str, style: str = "", is_user_message: bool = False, status: str = None, use_bubble: bool = False):
        if is_user_message:
            self._safe_call(self.app.chat_log.write_user_message, message)
        else:
            # Si el mensaje contiene markup Rich (ej. [#color]texto[/#color]), lo convertimos
            # a un objeto Text para que RichLog (que tiene markup=False) lo renderice correctamente.
            from rich.text import Text
            if isinstance(message, str) and ('[' in message and ']' in message):
                try:
                    renderable = Text.from_markup(message)
                    self._safe_call(self.app.chat_log.write_message, renderable)
                    return
                except Exception:
                    pass  # Fallback a write_agent_message si el markup falla
            self._safe_call(self.app.chat_log.write_agent_message, message)

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
        if panel_id:
            def _update_panel():
                try:
                    panel = self.app.query_one(f"#{panel_id}")
                    # Usually streaming text to a panel is for replacing its content or rendering it (Rich renderable)
                    panel.update(content)
                except Exception:
                    pass
            self._safe_call(_update_panel)
            return
            
        # Limpiar el cursor previo si existe antes de escribir nuevo texto
        if self.app._cursor_active:
             # RichLog no permite borrar caracteres individuales fácilmente,
             # pero podemos escribir el contenido nuevo y el cursor se moverá al final.
             pass

        self._safe_call(self.app.chat_log.write_stream, content)
        
        # El cursor se redibujará en el siguiente tick del timer si está activo

    def update_live(self, renderable, **kwargs):
        """Actualiza el contenido en streaming."""
        panel_id = kwargs.get("panel_id")
        self._safe_call(self.app.update_live_display, renderable, panel_id)

    def update_terminal_output(self, tool_name: str, output: str, **kwargs):
        """Actualiza específicamente la terminal con soporte de cursor."""
        # Optional panel routing if supported
        command = kwargs.get("command", tool_name)
        self._safe_call(self.app.update_terminal_output, tool_name, output, command=command)
    def update_tool_display(self, tool_name: str, output: str, command: str = "", max_lines=None, **kwargs):
        """Escribe la salida final de una herramienta en el chat log de la TUI."""
        if not output or not getattr(self, "app", None):
            return

        # Guardar en el app para que Ctrl+O pueda recuperarlo y actualizar dinámicamente si está visible
        def _save_and_update():
            self.app._last_terminal_tool_name = tool_name
            self.app._last_terminal_output = output
            if getattr(self.app, "_tool_panel_explicitly_shown", False):
                display_command = command or tool_name
                self.app.update_live_display(("__TERMINAL__", tool_name, output, display_command), panel_id="tool_display")

        self._safe_call(_save_and_update)

        # Default: mostrar las últimas 30 líneas si no se especifica otro límite
        limit = max_lines if max_lines is not None else 30
        lines = output.splitlines()
        if len(lines) > limit:
            displayed = "\n".join(lines[-limit:])
        else:
            displayed = output

        self._safe_call(
            self.app.chat_log.write_tool_output,
            displayed,
            tool_name,
            language=command or None,
        )

    def update_task_tracker(self, agent_plans: dict):
        """Actualiza el panel de seguimiento de tareas."""
        self._safe_call(self.app.update_task_tracker, agent_plans)

    def stop_live(self, **kwargs):
        """Finaliza el streaming y consolida el mensaje."""
        if kwargs.get("panel_id"): return
        self._safe_call(self.app.hide_live_display)

    def resume_spinner(self):
        """Reactiva el spinner de procesamiento si el agente está procesando.
        Se usa cuando las herramientas terminan y el LLM aún no ha respondido.
        """
        self._safe_call(self.app._resume_spinner)

    def print_tool_notification(self, tool_name: str, action_desc: str = "", skill_name: str = "", **kwargs):
        """Muestra notificación de herramienta ejecutándose, alineada a la izquierda."""
        if kwargs.get("panel_id"): return
        self._safe_call(self.app.chat_log.write_tool_notification, tool_name, action_desc, skill_name)

    def print_success_box(self, message: str, title: str = "Éxito"):
        self._safe_call(self.app.chat_log.write_message, f"✅ [box] **{title}**: {message}", style="green")

    def print_error_box(self, message: str, title: str = "Error"):
        self._safe_call(self.app.chat_log.write_message, f"❌ [box] **{title}**: {message}", style="red")

    def print_warning_box(self, message: str, title: str = "Advertencia"):
        self._safe_call(self.app.chat_log.write_message, f"⚠️ [box] **{title}**: {message}", style="yellow")

    def print_status(self, message: str, spinner_style: str = "dots"):
        import contextlib
        @contextlib.contextmanager
        def dummy_status(): yield
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

    async def ask_radiolist_async(self, title, text, values, default=None):
        from .components.settings_modals import TextualRadioListModal
        return await self.app.push_screen_wait(TextualRadioListModal(title, text, values, default))

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
        """Limpia visualmente el chat log y vuelve a mostrar el banner de bienvenida."""
        def _do_clear():
            self.app.chat_log.clear()
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
        banner_lines = banner_text.split('\n')
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
            
            # El mensaje en cursiva con un emoji de reloj de arena al inicio
            content = "\n".join(f"⏳ [italic]{m}[/italic]" for m in display_msgs)
            
            if len(messages) > max_show:
                content += f"\n [dim]... y {len(messages) - max_show} más[/dim]"
                
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
    #tracker_container {
        height: auto;
        width: 85%;
        max-width: 180;
        margin: 0;
        padding: 0;
        display: none; /* Oculto por defecto */
        align-horizontal: center;
    }

    #task_tracker_panel {
        width: 100%;
        height: auto;
        margin: 0;
        padding: 0;
        border: solid $secondary;
    }

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
        display: none; /* activarse dinámicamente desde el skill */
    }

    /* Paneles internos del contenedor paralelo */
    #parallel_agents_container ChatLogWidget {
        width: 100%;
        height: 100%;
        margin: 0;
        padding: 0 1;
        background: #1a1a1a;
        overflow-y: scroll;
        border: none;
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
        max-height: 30;
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
        width: 44;
        layer: popup;
        height: auto;
        max-height: 14;
        background: #1e1e2e;
        border: tall #3b82f6 20%;
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
        height: 2;
        width: 85%;
        max-width: 180;
        min-width: 60;
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
    #indexing_bar {
        width: 100%;
        height: 1;
        background: transparent;
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
        max-height: 30;
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

    def __init__(self, llm_service=None, command_executor=None, agent_state=None, workspace_directory=None, **kwargs):
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
        self.is_processing = False
        self._input_queue = []  # Cola para mensajes cuando el agente está ocupado
        self._is_processing_queue = False
        # Estado interno del spinner animado
        self._spinner_frame = 0
        self._spinner_timer = None
        self._last_live_renderable = None
        self._spinner_paused = False  # Flag para saber si el spinner fue pausado por streaming
        
        try:
            from kogniterm.core.session_manager import SessionManager
            self.session_manager = SessionManager(self.workspace_directory or os.getcwd())
        except Exception:
            self.session_manager = None
        
        try:
            from kogniterm.terminal.meta_command_processor import MetaCommandProcessor
            self.meta_command_processor = MetaCommandProcessor(self.llm_service, self.agent_state, self.tui_ui, self)
        except Exception:
            self.meta_command_processor = None
        
        # Inicializar CommandApprovalHandler solo si el componente está disponible
        try:
            if CommandApprovalHandler is not None:
                self.command_approval_handler = CommandApprovalHandler(
                    self.llm_service,
                    self.command_executor,
                    None,
                    self.tui_ui,
                    self.agent_state,
                    self.llm_service.get_tool("file_update") if self.llm_service else None,
                    self.llm_service.get_tool("advanced_file_editor") if self.llm_service else None,
                    self.llm_service.get_tool("file_operations") if self.llm_service else None
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
                    self.command_approval_handler
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
        ("ctrl+b", "toggle_sidebar", "Toggle Sidebar"),
        ("ctrl+o", "toggle_tool_panel", "Toggle Tool Panel"),
    ]

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
            self.chat_log = ChatLogWidget(id="chat_log")
            yield self.chat_log
            
        self.approval_container = Vertical(id="approval_container")
        yield self.approval_container
        
        self.command_popup = ListView(id="command_popup")
        yield self.command_popup
        
        with Vertical(id="bottom_container"):
            # Panel de queue (mensajes en espera)
            self.queue_display = QueueDisplay(id="queue_display")
            yield self.queue_display

            # Panel de tools (terminal dedicada a herramientas) y panel principal de live
            if ToolOutputWidget:
                self.tool_display = ToolOutputWidget("", "Terminal", id="tool_display")
            else:
                self.tool_display = TerminalPanel(id="tool_display")
            yield self.tool_display

            # live_display ahora es un TerminalPanel enfocalbe
            self.live_display = TerminalPanel(id="live_display")
            yield self.live_display

            # Contenedor para paneles paralelos (inactivo por defecto)
            # Contenedor para paneles paralelos con pestañas (inactivo por defecto)
            with TabbedContent(id="parallel_agents_container"):
                with TabPane("DeepCoder", id="tab_coder"):
                    self.live_display_coder = ChatLogWidget(id="live_display_coder")
                    yield self.live_display_coder
                with TabPane("DeepResearcher", id="tab_researcher"):
                    self.live_display_researcher = ChatLogWidget(id="live_display_researcher")
                    yield self.live_display_researcher

            with Vertical(id="tracker_container"):
                self.task_tracker_panel = TaskTrackerPanelWidget(id="task_tracker_panel")
                yield self.task_tracker_panel

            # Barra de progreso de indexación (docked bottom, above input)
            with Vertical(id="indexing_progress_container"):
                yield Static("", id="indexing_bar", markup=True)
                yield Static("", id="indexing_label", markup=True)

            with Horizontal(id="input_container"):
                self.chat_input = ChatInput(id="chat_input")
                yield self.chat_input
            self.status_footer = StatusFooter(model_name=self.llm_service.model_name)
            yield self.status_footer

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
                    "[dim]/models[/dim] modelo  [dim]/provider[/dim] proveedor  [dim]/theme[/dim] tema  [dim]esc[/dim] interrumpir",
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
            model_info.update(f"[{ColorPalette.TEXT_PRIMARY}]{display_model}[/{ColorPalette.TEXT_PRIMARY}]")
        except Exception:
            pass

    def on_mount(self):
        import asyncio
        self.loop = asyncio.get_running_loop()
        
        from kogniterm.terminal.config_manager import ConfigManager
        config_manager = ConfigManager()
        saved_theme = config_manager.get_config("theme") or "default"
        self.apply_theme(saved_theme, persist=False)
        # Actualizar info del modelo en el splash y enfocar el input del splash
        self.call_after_refresh(self._setup_splash)
        
        # El ratón se maneja en el mount para asegurar que las secuencias se envíen.
        # force_on/off evita spam de mensajes en el inicio.
        self.call_after_refresh(lambda: self.action_toggle_mouse(force_on=self.mouse_support, force_off=not self.mouse_support))
        
        # Check if workspace needs indexing and prompt user
        self.call_after_refresh(self._check_workspace_index)

        # ── Intento de conexión al servidor (modo híbrido) ──────────────────
        # Lanzamos el probe en background para no bloquear el arranque de la TUI.
        self._ws_task = asyncio.create_task(self._try_server_connect())

    # ── Lógica de modo servidor ────────────────────────────────────────────────

    async def _try_server_connect(self) -> None:
        """
        Prueba si el servidor KogniTerm está disponible y, si es así, activa
        el modo servidor iniciando el cliente WebSocket persistente.
        """
        from kogniterm.terminal.tui.ws_client import probe_server, TUIWebSocketClient
        available = await probe_server(self._server_url)
        if not available:
            logger.info("[Híbrido] Servidor no disponible. Usando modo local.")
            return

        logger.info("[Híbrido] Servidor disponible. Activando modo servidor.")
        self._server_mode = True
        self._ws_client = TUIWebSocketClient(self, self._server_url, self._session_id)
        # Crear tarea de conexión persistente en el loop de Textual
        self._ws_task = asyncio.create_task(self._ws_client.run())

    async def _send_to_server(self, text: str) -> None:
        """Envía un mensaje al servidor vía WebSocket y actualiza el estado."""
        if not self._ws_client or not self._ws_client.is_connected:
            # El servidor puede haberse desconectado; caer al modo local
            logger.warning("[Híbrido] WS no conectado. Fallback a modo local.")
            self._server_mode = False
            self.process_agent_request(text)
            return

        # _send_to_server ya corre en el loop de Textual (desde _handle_input_async),
        # por lo que podemos llamar métodos de UI directamente.
        self.is_processing = True
        self._start_spinner()
        await self._ws_client.send_message(text)

    # ── Workspace indexing check ───────────────────────────────────────────────

    def _check_workspace_index(self):
        """Check if the workspace is indexed; if not, prompt user to index."""
        if self.workspace_directory is None:
            self.workspace_directory = os.getcwd()
        try:
            from kogniterm.core.context.vector_db_manager import VectorDBManager
            vdb = VectorDBManager(self.workspace_directory)
            if not vdb.is_indexed():
                # Show confirmation modal
                self.push_screen(
                    IndexingConfirmModal(
                        title="Inicializar contexto del proyecto",
                        message="¿Desea inicializar el espacio de trabajo para este proyecto? Esto generará la memoria de contexto (.kogniterm/llm_context.md) mediante investigación autónoma e indexará el código para búsquedas inteligentes. (Equivale a ejecutar el comando /init)"
                    ),
                    self._on_indexing_confirmation
                )
            vdb.close()
        except Exception as e:
            logger.error(f"Error checking index status: {e}")

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
                logger.error(f"Error starting deep research from modal confirmation: {e}")

    def _start_indexing(self):
        """Begin the indexing process."""
        # Mostrar barra de progreso en la parte inferior
        def show_ui():
            try:
                self.query_one("#indexing_progress_container").display = True
                self.query_one("#indexing_label").update("[#9ca3af]Indexando...[/#9ca3af]")
                self.query_one("#indexing_bar").update("")
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
                progress_callback=self._indexing_progress_callback
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
                bar_text = f"{'[#3b82f6]■[/#3b82f6]' * filled}{'[#374151]░[/#374151]' * empty}"
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
                    label.update("[green]■■■■■■■■■■ 100%  Indexación completada.[/green]")
                else:
                    label.update("[yellow]Indexación completada: no se encontraron archivos relevantes.[/yellow]")
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
            self.tui_ui.print_message("🤖 Iniciando investigación local con DeepResearcher...", style="yellow")
            
            # 1. Asegurar que las herramientas críticas estén cargadas en el LLMService
            if hasattr(self.llm_service, 'skill_manager'):
                for skill in ['file_operations', 'codebase_search', 'task_tracker']:
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
                interrupt_queue=self.tui_ui.interrupt_queue
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
            if final_state and 'messages' in final_state and final_state['messages']:
                last_msg = final_state['messages'][-1]
                content = getattr(last_msg, 'content', '')
                if content:
                    # Limpiar marcadores de pensamiento/razonamiento
                    import re
                    cleaned_content = content.strip()
                    cleaned_content = re.sub(r'<thought>.*?</thought>', '', cleaned_content, flags=re.DOTALL | re.IGNORECASE)
                    cleaned_content = re.sub(r'<thinking>.*?</thinking>', '', cleaned_content, flags=re.DOTALL | re.IGNORECASE)
                    cleaned_content = cleaned_content.replace('__THINKING__:', '')
                    cleaned_content = cleaned_content.replace('__THINKING__', '')
                    cleaned_content = cleaned_content.strip()
                    
                    if cleaned_content:
                        if cleaned_content.startswith("## 🔬 Informe de Deep Research"):
                            cleaned_content = cleaned_content.replace("## 🔬 Informe de Deep Research\n\n", "")
                        elif cleaned_content.startswith("## 🔬 Informe de Investigación"):
                            cleaned_content = cleaned_content.replace("## 🔬 Informe de Investigación\n\n", "")
                            
                        header = "<!-- Generado por KogniTerm DeepResearcher -->\n"
                        if not (cleaned_content.startswith("# Memoria Contextual") or cleaned_content.startswith("<!--")):
                            cleaned_content = header + cleaned_content
                        
                        # Escribir la memoria local
                        from kogniterm.core.context.project_memory_builder import ProjectMemoryBuilder
                        builder = ProjectMemoryBuilder(self.workspace_directory)
                        builder.write_memory_file(cleaned_content)
                        
                        self.tui_ui.print_message("✅ Memoria contextual del proyecto guardada exitosamente en .kogniterm/llm_context.md", style="green")
                        self.tui_ui.print_message("✨ ¡Inicialización completada con éxito!", style="bold green")
                        return
            
            self.tui_ui.print_message("⚠️ DeepResearcher finalizó sin generar un reporte válido.", style="yellow")
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error executing DeepResearcher in TUI: {e}\n{error_trace}")
            self.tui_ui.print_message(f"❌ Error durante la investigación de DeepResearcher: {e}", style="red")

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
                self.tui_ui.print_message(f"🖱️ Ratón {status} (Selección nativa habilitada si está desactivado)", style="cyan")
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
            model_info.update(
                f"[{p.TEXT_PRIMARY}]{display_model}[/{p.TEXT_PRIMARY}]"
            )
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
                    commands = ["%help", "%models", "%provider", "%agy-login", "%reset", "%undo", "%compress", "%theme", "%init", "%keys", "%session", "%resume", "%salir", "%mouse", "%embeddings", "%tema", "%exit", "%quit", "%skills", "%instructions", "%insights", "%reasoning", "%summarize", "%summarymodel"]
                else:
                    commands = ["/help", "/models", "/provider", "/agy-login", "/reset", "/undo", "/compress", "/theme", "/init", "/keys", "/session", "/resume", "/salir", "/mouse", "/embeddings", "/tema", "/exit", "/quit", "/skills", "/instructions", "/insights", "/reasoning", "/summarize", "/summarymodel"]
                matches = [cmd for cmd in commands if cmd.startswith(search_term)]
            elif trigger == "@" and suggester:
                from kogniterm.terminal.tui.components.status_footer import KogniTermSuggester
                if isinstance(suggester, KogniTermSuggester):
                    files = suggester.cached_files_list
                    matches = [f for f in files if search_term.lower() in f.lower()][:15] # Limitar a 15
            elif trigger == ":" and suggester:
                from kogniterm.terminal.tui.components.status_footer import KogniTermSuggester
                if isinstance(suggester, KogniTermSuggester):
                    containers = getattr(suggester, "_cached_containers", []) or []
                    # containers es lista de dicts: {'name': ..., 'status': ..., 'image': ...}
                    matches = [c for c in containers if search_term.lower() in c['name'].lower()][:12]  # Limitar a 12

            # Si hay un único match y es exacto, no mostrar autocompletado
            if len(matches) == 1:
                match = matches[0]
                match_text = match['name'] if isinstance(match, dict) else match
                if match_text.lower() == search_term.lower():
                    matches = []

            for match in matches:
                # match puede ser string (comandos %) o dict (contenedores)
                if isinstance(match, dict):
                    display = f"{match['name']} ({match['status']})"
                    command_text = match['name']
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
                    commands = ["%help", "%models", "%provider", "%agy-login", "%reset", "%undo", "%compress", "%theme", "%init", "%keys", "%session", "%resume", "%salir", "%mouse", "%embeddings", "%tema", "%exit", "%quit", "%skills", "%instructions", "%insights", "%reasoning", "%summarize", "%summarymodel"]
                else:
                    commands = ["/help", "/models", "/provider", "/agy-login", "/reset", "/undo", "/compress", "/theme", "/init", "/keys", "/session", "/resume", "/salir", "/mouse", "/embeddings", "/tema", "/exit", "/quit", "/skills", "/instructions", "/insights", "/reasoning", "/summarize", "/summarymodel"]
                matches = [cmd for cmd in commands if cmd.startswith(search_term)]
            elif trigger == "@" and suggester:
                from kogniterm.terminal.tui.components.status_footer import KogniTermSuggester
                if isinstance(suggester, KogniTermSuggester):
                    files = suggester.cached_files_list
                    matches = [f for f in files if search_term.lower() in f.lower()][:15] # Limitar a 15
            elif trigger == ":" and suggester:
                from kogniterm.terminal.tui.components.status_footer import KogniTermSuggester
                if isinstance(suggester, KogniTermSuggester):
                    containers = getattr(suggester, "_cached_containers", []) or []
                    # containers es lista de dicts: {'name': ..., 'status': ..., 'image': ...}
                    matches = [c for c in containers if search_term.lower() in c['name'].lower()][:12]  # Limitar a 12

            # Si hay un único match y es exacto, no mostrar autocompletado
            if len(matches) == 1:
                match = matches[0]
                match_text = match['name'] if isinstance(match, dict) else match
                if match_text.lower() == search_term.lower():
                    matches = []

            for match in matches:
                # match puede ser string (comandos %) o dict (contenedores)
                if isinstance(match, dict):
                    display = f"{match['name']} ({match['status']})"
                    command_text = match['name']
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
            self.command_popup.display = False
            self._completion_input = None

    def _reposition_popup(self, input_widget, current_value: str) -> None:
        """Posiciona el popup justo encima del input activo (funciona tanto en splash como en chat)."""
        try:
            screen_w = self.size.width

            # Usar SIEMPRE la región del widget activo, no del #input_container
            # (que puede estar oculto durante el splash)
            input_region = input_widget.region

            # Posición X: inicio del widget + pequeño indent para alinear con el texto
            popup_w = 44  # ancho del popup definido en CSS
            popup_x = input_region.x + 2
            # No salirse por la derecha
            if popup_x + popup_w > screen_w:
                popup_x = max(0, screen_w - popup_w)

            # Posición Y: justo ENCIMA del input
            popup_max_h = 14  # max-height en CSS
            popup_y = max(0, input_region.y - popup_max_h)

            self.command_popup.styles.offset = (popup_x, popup_y)
        except Exception:
            pass

    def _apply_completion(self, selected_text: str, input_widget: Input, current_val: str):
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
                elif ":" in last_word:
                    prefix = last_word.split(":")[0] + ":"
                words[-1] = prefix + selected_text
                input_widget.value = " ".join(words) + " "
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
        # 1. Prioridad: Si el panel de terminal está enfocado, enviar teclas al PTY
        # Importación local para evitar circulares
        try:
            from kogniterm.terminal.tui.components.tool_output import ToolOutputWidget
            focused_widget = self.focused
            is_terminal_focused = isinstance(focused_widget, (TerminalPanel, ToolOutputWidget))
        except ImportError:
            is_terminal_focused = False
            focused_widget = None

        if focused_widget and is_terminal_focused and self.command_executor and self.command_executor.process:
            # Si es escape, devolver foco al input
            if event.key == "escape":
                try:
                    self.query_one("#chat_input").focus()
                except:
                    pass
                return
            
            # Mapeo de teclas de Textual a secuencias PTY
            key_map = {
                "right": "\x1b[C",
                "left": "\x1b[D",
                "home": "\x1b[H",
                "end": "\x1b[F",
                "delete": "\x1b[3~",
                "pageup": "\x1b[5~",
                "pagedown": "\x1b[6~",
            }
            
            # Manejar Ctrl+Letra
            if event.key.startswith("ctrl+"):
                char = event.key.split("+")[1]
                if len(char) == 1:
                    # 'a' es 1, 'b' es 2... 'z' es 26
                    code = ord(char.lower()) - ord('a') + 1
                    self.interactive_executor.write_input(bytes([code]))
                    event.prevent_default()
                    return

            to_send = key_map.get(event.key, event.character)
            if to_send:
                self.interactive_executor.write_input(to_send)
                event.prevent_default()
                return

        if event.key == "escape":
            if self.is_processing:
                if self._server_mode and self._ws_client and self._ws_client.is_connected:
                    # Modo servidor: enviar interrupción al backend
                    asyncio.run_coroutine_threadsafe(
                        self._ws_client.send_interrupt(), self.loop
                    )
                else:
                    # Modo local: usar la cola de interrupción estándar
                    self.tui_ui.get_interrupt_queue().put(True)
                self.tui_ui.print_message("⏳ Solicitando interrupción...", style="yellow")
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
                            self._apply_completion(selected_text, input_widget, input_widget.value)
                        event.prevent_default()
            elif event.key == "up":
                self.command_popup.action_cursor_up()
                event.prevent_default()
            elif event.key == "enter":
                if self.command_popup.highlighted_child:
                    item = self.command_popup.highlighted_child
                    if hasattr(item, "command_text"):
                        selected_text = item.command_text
                        input_widget = self.focused
                        current_val = input_widget.value
                        
                        # Determinar si estamos reemplazando una palabra parcial (@ o :)
                        # o si es un comando mágico (%)
                        if current_val.lstrip().startswith("%"):
                            # Reemplazo total para comandos mágicos
                            input_widget.value = selected_text + " "
                        else:
                            # Reemplazo inteligente de la última palabra para @ y :
                            words = current_val.split()
                            if words:
                                last_word = words[-1]
                                prefix = ""
                                if "@" in last_word: prefix = last_word.split("@")[0] + "@"
                                elif ":" in last_word: prefix = last_word.split(":")[0] + ":"
                                
                                # Reconstruir el valor
                                words[-1] = prefix + selected_text
                                input_widget.value = " ".join(words) + " "
                        
                        input_widget.cursor_position = len(input_widget.value)
                        input_widget.focus()
                    self.command_popup.display = False
                    event.prevent_default()

    def on_input_submitted(self, event: Input.Submitted):
        user_input = event.value
        if not user_input.strip():
            return
        
        # Si el submit viene del splash, transición al modo chat
        if event.input.id == "splash_chat_input" or self._splash_visible:
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
        
        # Para el chat normal, añadir al historial
        if hasattr(event.input, "add_to_history"):
            event.input.add_to_history(user_input.strip())
        
        # Redirigir input si el foco está en una terminal O si el modo interactivo está forzado
        is_interact_mode = self._cursor_active
        try:
            from kogniterm.terminal.tui.components.tool_output import ToolOutputWidget
            is_terminal_focused = isinstance(self.focused, (TerminalPanel, ToolOutputWidget))
        except:
            is_terminal_focused = False

        if (is_interact_mode or is_terminal_focused) and self.command_executor and self.command_executor.process:
            self.command_executor.write_input(user_input + "\n")
            event.input.value = ""
            return
        
        # (El fallback anterior fue removido para evitar secuestro de input con shell persistente)

        event.input.value = ""
        # Asegurar que el input mantenga el foco tras enviarse/limpiarse
        try:
            event.input.focus()
        except Exception:
            pass

        
        # Bloquear nuevo input si ya hay una petición en curso
        # PERO permitir encolar mensajes para mejor UX
        if self.is_processing:
            self._input_queue.append(user_input)
            if hasattr(self, "queue_display"):
                self.queue_display.update_queue(self._input_queue)
            return
        
        self.run_worker(self._handle_input_async(user_input))

    # Algunos widgets (p.ej. `ChatInput`) emiten su propio `Submitted` message
    # (clase interna `Submitted`). Textual despacha esos mensajes como
    # `on_<widget_snake>_submitted`, por lo que implementamos el handler que
    # reencamina al mismo procesamiento usado para `Input.Submitted`.
    def on_chat_input_submitted(self, event):
        return self.on_input_submitted(event)

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
        # Procesar el primer mensaje
        self.run_worker(self._handle_input_async(first_message))

    async def _handle_input_async(self, user_input: str):
        """Procesa la entrada del usuario de forma asíncrona en un worker."""
        self.chat_log.write_user_message(user_input)
        
        if await self.meta_command_processor.process_meta_command(user_input):
            return

        # ── Decisión híbrida: servidor vs local ────────────────────────────────
        if self._server_mode and self._ws_client:
            # Intentar via WebSocket; si falla, caer al modo local automáticamente
            await self._send_to_server(user_input)
        else:
            self.process_agent_request(user_input)

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
        self.dark = (theme_name != "light")
        
        # 3. Aplicar colores a contenedores principales
        bg_color = p.GRAY_900 if self.dark else p.PRIMARY_LIGHTEST
        
        self.screen.styles.background = bg_color
        self.styles.background = bg_color
        
        try:
            chat_container = self.query_one("#chat_container")
            chat_container.styles.background = bg_color
        except Exception:
            pass
        
        # 4. Estilizar el LOG y sus SCROLLBARS
        log = self.chat_log
        log.styles.background = "transparent"
        log.styles.color = p.TEXT_PRIMARY
        log.styles.scrollbar_color = p.GRAY_600
        log.styles.scrollbar_color_hover = p.PRIMARY
        log.styles.scrollbar_color_active = p.PRIMARY_LIGHT
        
        # 5. Estilizar contenedores secundarios
        self.approval_container.styles.background = bg_color
        self.live_display.styles.background = bg_color
        self.live_display.styles.color = p.TEXT_PRIMARY

        tool_panel_bg = p.GRAY_800 if self.dark else p.GRAY_200
        self.tool_display.styles.background = tool_panel_bg
        self.tool_display.styles.color = p.TEXT_PRIMARY

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
                self.query_one("#splash_input_row").styles.border_left = ("tall", p.PRIMARY)
                self.query_one("#splash_input_row").styles.background = p.GRAY_800
                self.query_one("#splash_model_info").styles.border_left = ("tall", p.PRIMARY)
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
        self.live_display.display = True # Asegurar que sea visible
        self.live_display.update(
            Text(f"{self.SPINNER_FRAMES[0]} Procesando...", style=f"bold {ColorPalette.PRIMARY}")
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

    def set_terminal_cursor(self, active: bool, executor=None):
        """Activa o desactiva el simulador de cursor en el chat log."""
        self.interactive_executor = executor if active else None
        self._cursor_active = active
        
        # Cambiar placeholder del input para indicar modo
        try:
            chat_input = self.query_one(ChatInput)
            if active:
                chat_input.placeholder = "Terminal Interactiva (Escribe abajo o HAZ CLIC en el panel para modo directo)..."
                chat_input.styles.color = "#10b981" # Verde esmeralda para modo activo
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
            self.update_terminal_output(self._last_terminal_tool_name, self._last_terminal_output)

    @work(thread=True)
    def process_agent_request(self, user_input: str):
        self.is_processing = True
        # Mostrar spinner animado mientras el LLM procesa
        self.call_from_thread(self._start_spinner)
        # Añadir el mensaje del usuario al historial
        self.agent_state.add_message(HumanMessage(content=user_input))

        try:
            while True:
                try:
                    # Invoke agent synchronously in this thread
                    final_state = self.agent_interaction_manager.invoke_agent(user_input)
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    logger.error(f"Error crítico en invoke_agent: {e}\n{error_trace}")
                    self.tui_ui.print_message(f"❌ Error crítico al invocar al agente: {str(e)}", style="bold red")
                    break
                
                self.agent_state.messages = final_state.get('messages', self.agent_state.messages)
                self.agent_state.command_to_confirm = final_state.get('command_to_confirm')
                # También recuperar el tool_call_id para poder crear el ToolMessage correcto
                tool_call_id_for_cmd = final_state.get('tool_call_id_to_confirm') or 'execute_command'
                # 2. SECCIÓN DE CONFIRMACIONES (Bash y Skills)
                # -------------------------------------------------------------
                
                # Caso A: Comando de terminal (Bash)
                if self.agent_state.command_to_confirm:
                    command = self.agent_state.command_to_confirm
                    
                    # Bloquear el hilo worker hasta que el usuario decida en la TUI
                    approved = self.ask_for_approval_sync(
                        message=f"¿Ejecutar comando: {command}?",
                        title="Confirmación de Comando",
                        diff_content=command,
                        file_path="bash"
                    )
                    
                    if command:
                    # Llamada síncrona al handler (corre en el worker thread)
                        self.command_approval_handler.handle_command_approval(
                            command_to_execute=command,
                            auto_approve=approved
                        )
                    # El handler ya se encarga de actualizar el estado del agente
                
                    # Limpiar estado de confirmación tras procesar
                    self.agent_state.command_to_confirm = None
                    self.agent_state.tool_call_id_to_confirm = None
                    
                    # Si fue aprobado, imprimir advertencia visual de que se completó
                    if not approved:
                        self.tui_ui.print_warning_box("Comando cancelado por el usuario.")
                    
                    user_input = None
                    continue # Volver al inicio del bucle para que el agente procese el resultado

                # Caso B: Confirmación de Skill (file_operations, advanced_file_editor, etc.)
                elif self.agent_state.tool_pending_confirmation or self.agent_state.file_update_diff_pending_confirmation:
                    tool_name = self.agent_state.tool_pending_confirmation
                    diff_info = self.agent_state.file_update_diff_pending_confirmation
                    
                    # Extraer info del diff
                    message = "Confirmación de herramienta requerida."
                    diff_content = None
                    file_path = None
                    
                    if isinstance(diff_info, dict):
                        message = diff_info.get("action_description", diff_info.get("message", message))
                        diff_content = diff_info.get("diff")
                        file_path = diff_info.get("path")
                    elif isinstance(diff_info, str):
                        diff_content = diff_info

                    # Bloquear el hilo worker hasta que el usuario decida en la TUI
                    approved = self.ask_for_approval_sync(
                        message=message,
                        title=f"Confirmación: {tool_name}",
                        diff_content=diff_content,
                        file_path=file_path
                    )
                    
                    # Llamar al handler síncrono desde el hilo worker
                    self.command_approval_handler.handle_command_approval(
                        command_to_execute="", # No es un comando bash
                        raw_tool_output=diff_info if isinstance(diff_info, dict) else {"status": "requires_confirmation", "diff": diff_content, "path": file_path, "operation": tool_name},
                        auto_approve=approved,
                        tool_name=tool_name,
                        original_tool_args=self.agent_state.tool_args_pending_confirmation
                    )
                    
                    # Limpiar estado de confirmación
                    self.agent_state.reset_tool_confirmation()
                    self.agent_state.tool_call_id_to_confirm = None
                    
                    if not approved:
                        self.tui_ui.print_warning_box("Acción cancelada por el usuario.")
                    
                    user_input = None
                    continue # Volver al inicio del bucle
                
                # Sin confirmaciones pendientes: salir del loop
                break
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error fatal en process_agent_request: {e}\n{error_trace}")
            # Mostrar error al usuario
            self.tui_ui.print_message(f"❌ Error fatal en el hilo del agente: {str(e)}", style="bold red")
        finally:
            self.is_processing = False
            # Asegurar que el spinner se detenga siempre al terminar
            self.call_from_thread(self._stop_spinner)
            # Procesar el siguiente mensaje en la cola si existe
            self.call_from_thread(self._process_queue)

    def _process_queue(self):
        """Procesa el siguiente mensaje en la cola si el agente está libre."""
        if self._input_queue and not self.is_processing:
            next_message = self._input_queue.pop(0)
            if hasattr(self, "queue_display"):
                self.queue_display.update_queue(self._input_queue)
            # Volver a llamar a handle_input_async para el siguiente mensaje
            self.run_worker(self._handle_input_async(next_message))

    async def push_screen_wait(self, screen) -> Any:
        """Helper asíncrono para pushear una pantalla y esperar su resultado."""
        future = asyncio.get_running_loop().create_future()
        def callback(result: Any) -> None:
            if not future.done():
                future.set_result(result)
        
        self.call_after_refresh(lambda: self.push_screen(screen, callback))
        return await future

    async def ask_for_approval_async(
        self,
        message: str,
        title: str = "Aprobación Requerida",
        diff_content: str = "",
        file_path: str = "",
    ) -> bool:
        """Versión asíncrona de ask_for_approval que no bloquea el event loop."""
        if getattr(self, "_auto_approve_all", False):
            return True

        from .components.inline_approval import InlineApprovalWidget
        future = asyncio.get_event_loop().create_future()

        def mount_widget():
            widget = InlineApprovalWidget(
                message=message,
                title=title,
                diff_content=diff_content or None,
                file_path=file_path or None,
                callback=lambda result: future.set_result(result) if not future.done() else None,
            )
            if hasattr(self, "approval_container"):
                self.approval_container.mount(widget)
            else:
                self.mount(widget)
            
            self.chat_log.scroll_end(animate=False)
            widget.focus()

        # Puesto que es asíncrono y se llama desde el loop, podemos montar directo
        mount_widget()
        
        raw_result = await future
        if raw_result == "accept_all":
            self._auto_approve_all = True
        return raw_result in ("accept", "accept_all")

    async def ask_for_input_async(self, title: str, text: str, password: bool = False) -> str:
        """Versión asíncrona de ask_for_input que no bloquea el event loop."""
        from .components.settings_modals import TextualInputModal
        return await self.push_screen_wait(TextualInputModal(title, text, password=password))

    def ask_for_approval_sync(
        self,
        message: str,
        title: str = "Aprobación Requerida",
        diff_content: str = "",
        file_path: str = "",
    ) -> bool:
        """Muestra un InlineApprovalWidget en el chat y bloquea hasta que el usuario decide.

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

        def mount_widget():
            widget = InlineApprovalWidget(
                message=message,
                title=title,
                diff_content=diff_content or None,
                file_path=file_path or None,
                callback=lambda result: future.set_result(result) if not future.done() else None,
            )
            # Montar en approval_container para que aparezca después del log
            if hasattr(self, "approval_container"):
                self.approval_container.mount(widget)
            else:
                self.mount(widget) # Fallback retrocompatible
            
            self.chat_log.scroll_end(animate=False)
            # Enfocar el widget para que capture teclado
            widget.focus()

        if (
            threading.current_thread() is threading.main_thread()
            or getattr(self, "_thread_id", None) == threading.get_ident()
        ):
            mount_widget()
        else:
            self.call_from_thread(mount_widget)

        raw_result = future.result()  # Bloquea hasta decisión del usuario

        if raw_result == "accept_all":
            self._auto_approve_all = True
        return raw_result in ("accept", "accept_all")

    def ask_for_input_sync(self, title: str, text: str, password: bool = False) -> str:
        """Helper para pedir una entrada de texto mediante Modal de forma síncrona."""
        import concurrent.futures
        future = concurrent.futures.Future()
        
        def push_screen_callback():
            from .components.settings_modals import TextualInputModal
            def result_callback(result: str):
                future.set_result(result)
            self.call_after_refresh(lambda: self.push_screen(TextualInputModal(title, text, password=password), result_callback))
            
        if (
            threading.current_thread() is threading.main_thread()
            or getattr(self, "_thread_id", None) == threading.get_ident()
        ):
            push_screen_callback()
        else:
            self.call_from_thread(push_screen_callback)

        return future.result()

    def add_agent_tab(self, agent_id: str, title: str) -> ChatLogWidget:
        """Añade dinámicamente una pestaña para un subagente y retorna su ChatLogWidget."""
        tabbed_content = self.query_one("#parallel_agents_container", TabbedContent)
        
        # Verificar si ya existe
        try:
            widget = self.query_one(f"#live_display_{agent_id}", ChatLogWidget)
            return widget
        except Exception:
            pass
            
        widget = ChatLogWidget(id=f"live_display_{agent_id}")
        pane = TabPane(title, widget, id=f"pane_{agent_id}")
        
        # add_pane debe ejecutarse en el thread principal
        if threading.current_thread() is threading.main_thread():
            tabbed_content.add_pane(pane)
        else:
            self.call_from_thread(tabbed_content.add_pane, pane)
            
        return widget

    def remove_agent_tab(self, agent_id: str):
        """Elimina una pestaña de subagente por su id."""
        tabbed_content = self.query_one("#parallel_agents_container", TabbedContent)
        
        def _remove():
            try:
                tabbed_content.remove_pane(f"pane_{agent_id}")
            except Exception:
                pass
                
        if threading.current_thread() is threading.main_thread():
            _remove()
        else:
            self.call_from_thread(_remove)

    def update_live_display(self, renderable, panel_id=None):
        """Actualiza el widget de streaming en tiempo real directamente en el chat log."""
        if panel_id:
            try:
                panel = self.query_one(f"#{panel_id}")
                # NO forzar panel.display = True aquí - la visibilidad se controla
                # explícitamente por el usuario con Ctrl+O (action_toggle_tool_panel)
                # Manejo especial para terminales en paneles dedicados
                if isinstance(renderable, tuple) and renderable[0] == "__TERMINAL__":
                    tool_name = renderable[1]
                    output = renderable[2]
                    command = renderable[3] if len(renderable) >= 4 else tool_name
                    if hasattr(panel, "update_content"):
                        panel.update_content(output, command=command)
                    else:
                        panel.update(output)
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
            current_scroll = log.scroll_position
            # En VerticalScroll el scroll es algo diferente, pero scroll_end funciona igual
            self.chat_log.scroll_end(animate=False)
        except Exception:
            pass
        

    def update_terminal_output(self, tool_name: str, output: str, show_cursor: bool = None, command: str = ""):
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
        # Siempre enviamos al panel tool_display, independientemente de si está visible
        self.update_live_display(("__TERMINAL__", tool_name, output, display_command), panel_id="tool_display")
        
        # Si el panel de herramientas no está visible, lo enviamos al chat log para visualización inline
        if not getattr(self, "_tool_panel_explicitly_shown", False):
            self.update_live_display(("__TERMINAL__", tool_name, output, display_command))

    def update_task_tracker(self, agent_plans: dict):
        """Actualiza los datos del task tracker y muestra el panel si hay tareas."""
        if hasattr(self, "task_tracker_panel"):
            self.task_tracker_panel.update_tasks(agent_plans)
            
            # Mostrar/Ocultar el contenedor del tracker
            tracker = self.query_one("#tracker_container")
            if agent_plans and self.task_tracker_panel.display:
                tracker.display = True
            else:
                tracker.display = False

    def action_toggle_sidebar(self):
        """Alterna la visibilidad del tracker manualmente."""
        tracker = self.query_one("#tracker_container")
        tracker.display = not tracker.display

    def action_toggle_tool_panel(self):
        """Alterna la visibilidad del panel de herramientas (tool_display) manualmente."""
        self._tool_panel_explicitly_shown = not getattr(self, "_tool_panel_explicitly_shown", False)
        self.tool_display.display = self._tool_panel_explicitly_shown
        
        if self.tool_display.display:
            # Si se acaba de mostrar y tenemos salida de herramienta anterior guardada,
            # la cargamos en el panel de herramientas para que no esté vacío.
            if self._last_terminal_output:
                tool_name = self._last_terminal_tool_name or "Terminal"
                command = "bash" if tool_name == "execute_command" else tool_name
                if hasattr(self.tool_display, "update_content"):
                    self.tool_display.update_content(self._last_terminal_output, command=command)
                else:
                    self.tool_display.update(self._last_terminal_output)
            else:
                if hasattr(self.tool_display, "update_content"):
                    self.tool_display.update_content("No hay salida de herramientas disponible aún.", command="Ayuda")
                else:
                    self.tool_display.update("No hay salida de herramientas disponible aún.")
            # Enfocar el panel si es visible para permitir scrolling con teclado
            self.tool_display.focus()
        else:
            # Si se oculta, devolver el foco a la entrada de chat
            try:
                chat_input = self.query_one("#chat_input", ChatInput)
                chat_input.focus()
            except Exception:
                pass

    def hide_live_display(self):
        """Finaliza el streaming en el chat log."""
        # Asegurar que el spinner se detenga
        self._stop_spinner()
        
        # Ocultar paneles dedicados si estaban visibles
        try:
            if not getattr(self, "_tool_panel_explicitly_shown", False):
                self.tool_display.display = False
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
