import asyncio
import os
import queue
import json
import logging
from typing import Any
from textual.app import App, ComposeResult
from textual import work
from textual.widgets import Input, ListView, ListItem, Label, ProgressBar
from textual.containers import Vertical, Horizontal
from textual import events
from langchain_core.messages import HumanMessage
import threading

logger = logging.getLogger(__name__)


from kogniterm.core.llm_service import LLMService
from kogniterm.core.command_executor import CommandExecutor
from kogniterm.core.agents.bash_agent import AgentState
from kogniterm.terminal.tui.components.chat_log import ChatLogWidget
from kogniterm.terminal.tui.components.status_footer import StatusFooter, ChatInput
from kogniterm.terminal.tui.components.command_approval_modal import CommandApprovalModal
from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager
from kogniterm.terminal.command_approval_handler import CommandApprovalHandler


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

    def print_stream(self, text: str):
        """
        Imprime un fragmento de texto en la consola sin añadir nueva línea,
        y limpia el buffer inmediatamente (streaming real).
        """
        self.write_stream_to_chat(text)

    def write_stream_to_chat(self, content: str):
        """Imprime contenido en streaming directamente al chat log con manejo de cursor."""
        if not content:
            return
            
        # Limpiar el cursor previo si existe antes de escribir nuevo texto
        if self.app._cursor_active:
             # RichLog no permite borrar caracteres individuales fácilmente,
             # pero podemos escribir el contenido nuevo y el cursor se moverá al final.
             pass

        self._safe_call(self.app.chat_log.write_stream, content)
        
        # El cursor se redibujará en el siguiente tick del timer si está activo

    def update_live(self, renderable):
        """Actualiza el contenido en streaming."""
        self._safe_call(self.app.update_live_display, renderable)

    def update_terminal_output(self, tool_name: str, output: str):
        """Actualiza específicamente la terminal con soporte de cursor."""
        self._safe_call(self.app.update_terminal_output, tool_name, output)

    def stop_live(self):
        """Finaliza el streaming y consolida el mensaje."""
        self._safe_call(self.app.hide_live_display)

    def print_tool_notification(self, tool_name: str, action_desc: str = ""):
        """Muestra notificación de herramienta ejecutándose, alineada a la izquierda."""
        self._safe_call(self.app.chat_log.write_tool_notification, tool_name, action_desc)

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
            "██╗  ██╗ ██████╗  ██████╗ ███╗   ██╗██╗████████╗███████╗██████╗ ███╗   ███╗\n"
            "██║ ██╔╝██╔═══██╗██╔════╝ ████╗  ██║██║╚══██╔══╝██╔════╝██╔══██╗████╗ ████║\n"
            "█████╔╝ ██║   ██║██║  ███╗██╔██╗ ██║██║   ██║   █████╗  ██████╔╝██╔████╔██║\n"
            "██╔═██╗ ██║   ██║██║   ██║██║╚██╗██║██║   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║\n"
            "██║  ██╗╚██████╔╝╚██████╔╝██║ ╚████║██║   ██║   ███████╗██║  ██║██║ ╚═╝ ██║\n"
            "╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝"
        )

        from rich.text import Text
        from rich.console import Group
        from rich.padding import Padding
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

        # Escribir línea en blanco superior
        log.write("")

        # Escribir cada línea del banner con padding exacto
        for line in banner_lines:
            t = Text(" " * left_pad + line, style=color)
            log.write(t)

        log.write("")
        log.scroll_end(animate=False)

class KogniTermTUI(App):
    """Aplicación principal de Textual para KogniTerm."""
    
    # El ratón se activa por defecto para permitir interacciones con botones.
    # Se puede desactivar con %mouse para permitir selección nativa de la terminal.
    mouse_support = True
    
    CSS = """
    Screen {
        background: #1e1e1e;
        color: white;
        layers: base approval splash popup;
    }

    /* ── CHAT MODE (base layer) ─────────────────── */
    #chat_container {
        height: 1fr;
        width: 100%;
        layout: vertical;
        background: transparent;
    }

    #approval_container {
        layer: approval;
        dock: bottom;
        height: auto;
        width: 100%;
        layout: vertical;
        background: #1e1e1e;
        border-top: none; /* Linea divisora erradicada */
        margin-bottom: 7; /* Justo encima del bottom_container */
    }
    #chat_container {
        width: 100%;
        height: 1fr;
        align-horizontal: center;
    }
    
    #chat_log {
        width: 85%;
        max-width: 180;
        min-width: 60;
        height: 1fr;
        padding: 0;
        background: transparent;
        color: white;
        scrollbar-size: 0 0; /* Oculta visualmente la barra de scroll */
        border: none;
    }


    #bottom_container {
        dock: bottom;
        height: auto;
        padding: 0 0 2 0;
        background: transparent;
        display: none;
        align-horizontal: center; /* Centrar hijos horizontalmente */
    }
    #input_container {
        width: 85%; /* Ligeramente más ancho */
        max-width: 180; 
        min-width: 60;
        height: 3;
        background: #2a2a2a;
        margin: 2 0 1 0; /* Lados en 0 porque lo centra el padre */
        padding: 1 4 0 4;
        layout: horizontal;
    }

    ChatInput {
        width: 1fr;
        height: 1;
        min-height: 1;
        border: none !important;
        background: transparent !important;
        padding: 0;
        margin: 0;
        color: $text;
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
        height: 2;
        padding: 0;
        margin: 0 0 2 0; /* Margen inferior. Lados 0 porque está centrado. */
        layout: horizontal;
    }
    #footer_left {
        width: 1fr;
        content-align: left top;
        padding: 0;
    }
     #footer_right {
         width: 1fr;
         content-align: right top;
         padding: 0;
         display: block;
     }
     #indexing_progress {
         width: 85%;
         max-width: 180;
         height: 1;
         display: none;
     }
     #command_popup {
         layer: popup;
         dock: bottom;
         margin-bottom: 7;
         width: 30;
         height: auto;
         max-height: 10;
         background: #2a2a2a;
         border: solid #4b5563;
         display: none;
     }
    #live_display {
        width: 85%;
        max-width: 180;
        min-width: 60;
        background: transparent;
        color: white;
        padding: 0;
        margin: 0;
        display: none;
        height: auto;
        max-height: 25;
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
    }
    ChatInput#splash_chat_input {
        width: 1fr;
        height: 1;
        border: none;
        padding: 0;
        background: transparent;
    }
    ChatInput#splash_chat_input:focus {
        border: none;
        background: transparent;
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

    def __init__(self, llm_service, command_executor, agent_state, workspace_directory=None, **kwargs):
        super().__init__(**kwargs)
        self.llm_service = llm_service
        self.command_executor = command_executor
        self.agent_state = agent_state
        self.workspace_directory = workspace_directory
        self.tui_ui = TextualTerminalUI(self)
        self._splash_visible = True  # controla si el splash está activo
        
        # Asignar el terminal_ui después de inicializarlo
        self.command_executor.terminal_ui = self.tui_ui
        self.llm_service.terminal_ui = self.tui_ui
        self.llm_service.interrupt_queue = self.tui_ui.get_interrupt_queue()
        self.is_processing = False
        # Estado interno del spinner animado
        self._spinner_frame = 0
        self._spinner_timer = None
        self._last_live_renderable = None
        
        from kogniterm.core.session_manager import SessionManager
        self.session_manager = SessionManager(self.workspace_directory or os.getcwd())
        
        from kogniterm.terminal.meta_command_processor import MetaCommandProcessor
        self.meta_command_processor = MetaCommandProcessor(self.llm_service, self.agent_state, self.tui_ui, self)
        
        self.command_approval_handler = CommandApprovalHandler(
            self.llm_service,
            self.command_executor,
            None,
            self.tui_ui,
            self.agent_state,
            self.llm_service.get_tool("file_update"),
            self.llm_service.get_tool("advanced_file_editor"),
            self.llm_service.get_tool("file_operations")
        )
        
        self.agent_interaction_manager = AgentInteractionManager(
            self.llm_service,
            self.agent_state,
            self.tui_ui,
            self.tui_ui.get_interrupt_queue(),
            self.command_approval_handler
        )
        
        # Atributos para interactividad de terminal y cursor
        self.interactive_executor = None
        self._cursor_active = False
        self._cursor_frame = 0
        self._cursor_timer = None
        self._last_terminal_tool_name = ""
        self._last_terminal_output = ""

    BINDINGS = [
        ("ctrl+t", "toggle_mouse", "Mouse Tracking"),
    ]

    def _build_splash_title(self) -> str:
        """Retorna el título ASCII para el splash centrado como markup Rich."""
        from kogniterm.terminal.themes import ColorPalette
        c = ColorPalette.PRIMARY
        lines = [
            "██╗  ██╗ ██████╗  ██████╗ ███╗   ██╗██╗████████╗███████╗██████╗ ███╗   ███╗",
            "██║ ██╔╝██╔═══██╗██╔════╝ ████╗  ██║██║╚══██╔══╝██╔════╝██╔══██╗████╗ ████║",
            "█████╔╝ ██║   ██║██║  ███╗██╔██╗ ██║██║   ██║   █████╗  ██████╔╝██╔████╔██║",
            "██╔═██╗ ██║   ██║██║   ██║██║╚██╗██║██║   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║",
            "██║  ██╗╚██████╔╝╚██████╔╝██║ ╚████║██║   ██║   ███████╗██║  ██║██║ ╚═╝ ██║",
            "╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝",
        ]
        # Usar color hex directamente — Textual/Rich acepta [#rrggbb]texto[/#rrggbb]
        return "\n".join(f"[{c}]{line}[/{c}]" for line in lines)


    def compose(self) -> ComposeResult:
        from textual.widgets import Static
        from textual.containers import Vertical
        
        # ── Base layer: chat interface ──────────────────────
        with Vertical(id="chat_container"):
            self.chat_log = ChatLogWidget(id="chat_log")
            yield self.chat_log
            
            self.live_display = Static(id="live_display")
            yield self.live_display
        
        self.approval_container = Vertical(id="approval_container")
        yield self.approval_container
        
        self.command_popup = ListView(id="command_popup")
        yield self.command_popup
        
        with Vertical(id="bottom_container"):
            self.progress_bar = ProgressBar(show_eta=False, show_percentage=True, id="indexing_progress")
            yield self.progress_bar
            with Horizontal(id="input_container"):
                yield ChatInput()
            yield StatusFooter(model_name=self.llm_service.model_name)

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
                    "[dim]%models[/dim] modelo  [dim]%provider[/dim] proveedor  [dim]%theme[/dim] tema  [dim]esc[/dim] interrumpir",
                    id="splash_shortcuts",
                    markup=True,
                )

    def on_mount(self):
        import asyncio
        self.loop = asyncio.get_running_loop()
        
        from kogniterm.terminal.config_manager import ConfigManager
        config_manager = ConfigManager()
        saved_theme = config_manager.get_config("theme") or "default"
        self.apply_theme(saved_theme)
        # Actualizar info del modelo en el splash y enfocar el input del splash
        self.call_after_refresh(self._setup_splash)
        
        # El ratón se maneja en el mount para asegurar que las secuencias se envíen.
        # force_on/off evita spam de mensajes en el inicio.
        self.call_after_refresh(lambda: self.action_toggle_mouse(force_on=self.mouse_support, force_off=not self.mouse_support))

    def action_toggle_mouse(self, force_off: bool = False, force_on: bool = False):
        """Alterna el soporte de ratón en tiempo de ejecución o lo fuerza."""
        if force_off:
            self.mouse_support = False
        elif force_on:
            self.mouse_support = True
        else:
            self.mouse_support = not self.mouse_support
            
        try:
            # Secuencias XTerm exhaustivas para desactivar/activar tracking (Button, Drag, Motion, SGR, URXVT)
            if self.mouse_support:
                # Activar tracking (1000: button, 1002: button drag, 1003: all motion, 1006: SGR mode, 1015: URXVT)
                seq = "\x1b[?1000h\x1b[?1002h\x1b[?1003h\x1b[?1006h\x1b[?1015h"
                if hasattr(self, "_driver"):
                    self._driver.write(seq)
                if not force_on:
                    self.tui_ui.print_message("🖱️ Ratón ACTIVADO (Interacciones TUI habilitadas. Selección nativa requiere Shift o Ctrl+M para apagar)", style="cyan")
            else:
                # Desactivar tracking totalmente (las mismas secuencias pero con 'l')
                seq = "\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?1015l"
                if hasattr(self, "_driver"):
                    self._driver.write(seq)
                # Solo imprimir mensaje si es una acción explícita (no force_off silencioso)
                if not force_off:
                    self.tui_ui.print_message("🖱️ Ratón DESACTIVADO (Selección nativa de terminal habilitada. Ctrl+M para reactivar clicks)", style="cyan")
        except Exception:
            if not force_off:
                status = "ACTIVADO" if self.mouse_support else "DESACTIVADO"
                self.tui_ui.print_message(f"🖱️ Ratón {status} (Error al comunicar con driver)", style="cyan")

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
            splash_input = self.query_one("#splash_chat_input", Input)
            splash_input.focus()
        except Exception:
            pass

    async def _check_and_prompt_indexing(self):
        """Verifica el estado de indexación del workspace y actúa en consecuencia."""
        workspace = self.workspace_directory or os.getcwd()

        from kogniterm.core.context.codebase_indexer import CodebaseIndexer
        from kogniterm.core.context.vector_db_manager import VectorDBManager

        # Verificar si ya hay datos indexados (ChromaDB puede ser lento, usar thread)
        try:
            def _check_indexed():
                vector_db = VectorDBManager(workspace)
                result = vector_db.is_indexed()
                vector_db.close()
                return result
            already_indexed = await asyncio.to_thread(_check_indexed)
        except Exception:
            already_indexed = False

        if not already_indexed:
            # ── Primera vez: preguntar si desea indexar ────────────────
            from kogniterm.terminal.config_manager import ConfigManager
            config_manager = ConfigManager()
            if config_manager.get_config("index_prompt_declined"):
                return

            try:
                indexer = CodebaseIndexer(workspace)
                code_files = await asyncio.to_thread(indexer.list_code_files, workspace)
                if not code_files:
                    return
            except Exception:
                return

            from kogniterm.terminal.tui.components.settings_modals import TextualConfirmModal
            total_files = len(code_files)
            result = await self.push_screen_wait(
                TextualConfirmModal(
                    title="Indexar Directorio",
                    text=(
                        f"Este directorio no ha sido indexado.\n\n"
                        f"Se encontraron [bold]{total_files}[/bold] archivos de código.\n\n"
                        f"¿Deseas indexar y vectorizar el contenido\n"
                        f"para mejorar la búsqueda de contexto?"
                    ),
                    confirm_label="Indexar",
                    cancel_label="Ahora no"
                )
            )

            if result:
                await self._run_indexing(workspace)
            else:
                config_manager.set_global_config("index_prompt_declined", True)
        else:
            # ── Ya indexado: verificar cambios incrementales ──────────
            try:
                def _get_changes():
                    indexer = CodebaseIndexer(workspace)
                    return indexer.get_changed_files()
                changes = await asyncio.to_thread(_get_changes)
                n_changed = len(changes["changed"])
                n_new = len(changes["new"])
                n_deleted = len(changes["deleted"])
                total_diff = n_changed + n_new + n_deleted

                if total_diff == 0:
                    return

                # Construir resumen de cambios
                parts = []
                if n_new:
                    parts.append(f"[bold]{n_new}[/bold] nuevos")
                if n_changed:
                    parts.append(f"[bold]{n_changed}[/bold] modificados")
                if n_deleted:
                    parts.append(f"[bold]{n_deleted}[/bold] eliminados")
                summary = ", ".join(parts)

                from kogniterm.terminal.tui.components.settings_modals import TextualConfirmModal
                result = await self.push_screen_wait(
                    TextualConfirmModal(
                        title="Actualizar Índice",
                        text=(
                            f"Se detectaron cambios en el directorio:\n\n"
                            f"Archivos {summary}\n\n"
                            f"¿Deseas actualizar el índice?"
                        ),
                        confirm_label="Actualizar",
                        cancel_label="Ignorar"
                    )
                )

                if result:
                    await self._run_incremental_indexing(workspace, changes)
            except Exception as e:
                logger.error(f"Error verificando cambios en índice: {e}")

    async def _run_indexing(self, workspace: str):
        """Ejecuta la indexación completa del workspace."""
        from kogniterm.core.context.codebase_indexer import CodebaseIndexer
        from kogniterm.core.context.vector_db_manager import VectorDBManager

        self.tui_ui.print_message("🔍 Iniciando indexación del directorio...", style="cyan")
        self.is_processing = True
        self._start_spinner()

        try:
            indexer = CodebaseIndexer(workspace)
            vector_db = VectorDBManager(workspace)

            code_files = await asyncio.to_thread(indexer.list_code_files, workspace)
            total_files = len(code_files)
            self.progress_bar.display = True
            self.progress_bar.total = total_files
            self.progress_bar.progress = 0

            all_chunks = []
            for i, file_path in enumerate(code_files):
                file_chunks = await asyncio.to_thread(indexer.chunk_file, file_path)
                texts = [c['content'] for c in file_chunks]
                embeddings = []
                for text in texts:
                    try:
                        emb = await asyncio.to_thread(indexer.embeddings_service.generate_embeddings, [text])
                        embeddings.extend(emb)
                    except Exception as e:
                        logger.error(f"Embedding error in {file_path}: {e}")
                        embeddings.append(None)
                for j, chunk in enumerate(file_chunks):
                    if j < len(embeddings) and embeddings[j]:
                        chunk['embedding'] = embeddings[j]
                        all_chunks.append(chunk)
                self.progress_bar.progress = i + 1

            if all_chunks:
                vector_db.clear_collection()
                vector_db.add_chunks(all_chunks)
                file_state = await asyncio.to_thread(indexer.build_current_file_state)
                indexer._save_file_state(file_state)
                self.tui_ui.print_message(
                    f"✅ Indexación completada: {len(all_chunks)} bloques de código almacenados.",
                    style="green"
                )
            else:
                self.tui_ui.print_message("⚠️ No se generaron bloques de código.", style="yellow")

            vector_db.close()
        except Exception as e:
            logger.error(f"Error durante la indexación: {e}")
            self.tui_ui.print_message(f"❌ Error durante la indexación: {e}", style="red")
        finally:
            self.is_processing = False
            self._stop_spinner()
            self.progress_bar.display = False

    async def _run_incremental_indexing(self, workspace: str, changes: Dict[str, List[str]]):
        """Ejecuta indexación incremental solo para archivos con cambios."""
        from kogniterm.core.context.codebase_indexer import CodebaseIndexer
        from kogniterm.core.context.vector_db_manager import VectorDBManager

        n_new = len(changes["new"])
        n_changed = len(changes["changed"])
        n_deleted = len(changes["deleted"])
        total_steps = n_deleted + n_changed + n_new + 1

        self.tui_ui.print_message(f"🔄 Actualizando índice ({total_steps} pasos)...", style="cyan")
        self.is_processing = True
        self._start_spinner()

        try:
            indexer = CodebaseIndexer(workspace)
            vector_db = VectorDBManager(workspace)

            self.progress_bar.display = True
            self.progress_bar.total = total_steps
            self.progress_bar.progress = 0

            step = 0

            for file_path in changes["changed"] + changes["deleted"]:
                vector_db.delete_by_file_path(file_path)
                step += 1
                self.progress_bar.progress = step

            files_to_index = changes["changed"] + changes["new"]
            all_chunks = []
            for file_path in files_to_index:
                file_chunks = await asyncio.to_thread(indexer.chunk_file, file_path)
                texts = [c['content'] for c in file_chunks]
                embeddings = []
                for text in texts:
                    try:
                        emb = await asyncio.to_thread(indexer.embeddings_service.generate_embeddings, [text])
                        embeddings.extend(emb)
                    except Exception as e:
                        logger.error(f"Error generando embedding: {e}")
                        embeddings.append(None)
                for j, chunk in enumerate(file_chunks):
                    if j < len(embeddings) and embeddings[j]:
                        chunk['embedding'] = embeddings[j]
                        all_chunks.append(chunk)
                step += 1
                self.progress_bar.progress = step

            if all_chunks:
                vector_db.add_chunks(all_chunks)

            file_state = await asyncio.to_thread(indexer.build_current_file_state)
            indexer._save_file_state(file_state)
            step += 1
            self.progress_bar.progress = step

            parts = []
            if n_new: parts.append(f"{n_new} nuevos")
            if n_changed: parts.append(f"{n_changed} actualizados")
            if n_deleted: parts.append(f"{n_deleted} eliminados")

            self.tui_ui.print_message(
                f"✅ Índice actualizado: {', '.join(parts)}.",
                style="green"
            )
            vector_db.close()
        except Exception as e:
            logger.error(f"Error durante actualización incremental: {e}")
            self.tui_ui.print_message(f"❌ Error actualizando índice: {e}", style="red")
        finally:
            self.is_processing = False
            self._stop_spinner()
            self.progress_bar.display = False

    async def on_input_changed(self, event: Input.Changed):
        value = event.value
        if not value:
            self.command_popup.display = False
            return

        # Obtener el suggester para acceder a las listas cacheadas
        suggester = getattr(event.input, "suggester", None)
        
        # Determinar qué estamos buscando basándonos en el último carácter o palabra
        words = value.split()
        if not words:
            self.command_popup.display = False
            return
            
        current_word = words[-1]
        trigger = None
        search_term = ""
        
        if value.lstrip().startswith("%"):
            trigger = "%"
            search_term = value.lstrip()
        elif "@" in current_word:
            trigger = "@"
            search_term = current_word.split("@")[-1]
        elif ":" in current_word:
            trigger = ":"
            search_term = current_word.split(":")[-1]
            
        if trigger:
            self.command_popup.display = True
            await self.command_popup.clear()
            
            matches = []
            if trigger == "%":
                commands = ["%help", "%models", "%provider", "%reset", "%undo", "%compress", "%theme", "%init", "%keys", "%session", "%salir", "%mouse", "%embeddings", "%tema"]
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
                    matches = [c for c in containers if search_term.lower() in c.lower()]

            for match in matches:
                item = ListItem(Label(match))
                item.command_text = match
                self.command_popup.append(item)
                
            if not matches:
                self.command_popup.display = False
        else:
            self.command_popup.display = False

    def on_key(self, event: events.Key):
        if event.key == "escape":
            if self.is_processing:
                self.tui_ui.get_interrupt_queue().put(True)
                self.tui_ui.print_message("⏳ Solicitando interrupción...", style="yellow")
                event.prevent_default()
                return
            elif self.command_popup.display:
                self.command_popup.display = False
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
        
        # Si un comando está corriendo en el PTY y está en modo interactivo, redirigir el input
        if self.interactive_executor and self.interactive_executor.process:
            self.interactive_executor.write_input(user_input + "\n")
            event.input.value = ""
            return
        
        # Fallback para agentes que están procesando
        if self.is_processing and self.command_executor.process:
            self.command_executor.write_input(user_input + "\n")
            event.input.value = ""
            return

        event.input.value = ""
        
        # Bloquear nuevo input si ya hay una petición en curso
        # para evitar que múltiples workers corran en paralelo
        if self.is_processing:
            return
        
        self.run_worker(self._handle_input_async(user_input))

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
            
        self.process_agent_request(user_input)

    def apply_theme(self, theme_name: str):
        """Aplica un tema visual a la aplicación Textual."""
        from kogniterm.terminal.themes import ColorPalette, set_kogniterm_theme
        
        # 1. Aplicar tema a nivel de lógica (paleta global)
        set_kogniterm_theme(theme_name)
        p = ColorPalette
        
        # 2. Textual native dark mode (afecta a los widgets nativos)
        self.dark = (theme_name != "light")
        
        # 3. Aplicar colores a contenedores principales
        # Si es claro, usamos colores más claros pero manteniendo legibilidad
        bg_color = p.GRAY_900 if self.dark else p.PRIMARY_LIGHTEST
        
        self.screen.styles.background = bg_color
        self.styles.background = bg_color
        
        chat_container = self.query_one("#chat_container")
        chat_container.styles.background = bg_color
        
        # 4. Estilizar el LOG y sus SCROLLBARS
        log = self.chat_log
        log.styles.background = "transparent"
        log.styles.color = p.TEXT_PRIMARY
        # Estilo de barra de scroll adaptativo
        log.styles.scrollbar_color = p.GRAY_600
        log.styles.scrollbar_color_hover = p.PRIMARY
        log.styles.scrollbar_color_active = p.PRIMARY_LIGHT
        
        # 5. Estilizar contenedores secundarios
        self.approval_container.styles.background = bg_color
        self.live_display.styles.background = bg_color
        self.live_display.styles.color = p.TEXT_PRIMARY
        
        bottom_container = self.query_one("#bottom_container")
        bottom_container.styles.background = bg_color
        
        # Color dinámico para barras de entrada (más oscuro en light mode)
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
            
        # 8. Estilizar STATUS FOOTER
        for sf in self.query(StatusFooter):
            sf.styles.background = "transparent" # El usuario pidió la barra, y el modelo debajo
            sf.styles.border = None
            # Quitar el pipe izquierdo del modelo, solo la barra lo tiene
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

        # 10. Guardar configuración si existe
        if hasattr(self, "config_manager"):
            self.config_manager.set("theme", theme_name)
        
        # 11. Forzar refresh
        self.refresh()

    def write_stream_to_chat(self, content: str):
        """Método para escribir streaming desde hilos externos."""
        self.chat_log.write_stream(content)


    # Frames del spinner braille animado
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def _start_spinner(self):
        """Inicia la animación del spinner en live_display (ejecutar desde main thread)."""
        from rich.text import Text
        from kogniterm.terminal.themes import ColorPalette
        self._spinner_frame = 0
        # self.live_display.styles.border_left = ("tall", ColorPalette.PRIMARY) # ELIMINADO para no tener barra vertical
        self.live_display.display = True # Asegurar que sea visible
        self.live_display.update(
            Text(f" {self.SPINNER_FRAMES[0]} Procesando...", style=f"bold {ColorPalette.PRIMARY}")
        )
        if self._spinner_timer:
            self._spinner_timer.stop()
        self._spinner_timer = self.set_interval(0.12, self._tick_spinner)
        # Scroll del chat_log a su propio fondo para que el contenido existente
        # quede anclado abajo (justo encima del live_display)
        self.chat_log.scroll_end(animate=False)

    def _tick_spinner(self):
        """Avanza un frame del spinner (ejecutado por el timer del main thread)."""
        # Solo animar si no hay contenido real (si hay contenido el timer ya fue parado)
        if not self.is_processing:
            self._stop_spinner()
            return
        self._spinner_frame = (self._spinner_frame + 1) % len(self.SPINNER_FRAMES)
        from rich.text import Text
        from kogniterm.terminal.themes import ColorPalette
        frame = self.SPINNER_FRAMES[self._spinner_frame]
        self.live_display.update(
            Text(f"{frame} Procesando...", style=f"bold {ColorPalette.PRIMARY}")
        )

    def _stop_spinner(self):
        """Detiene el spinner (ejecutar desde main thread)."""
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None

    def set_terminal_cursor(self, active: bool, executor=None):
        """Activa o desactiva el simulador de cursor en el chat log."""
        self.interactive_executor = executor if active else None
        self._cursor_active = active
        
        # Cambiar placeholder del input para indicar modo
        try:
            chat_input = self.query_one(ChatInput)
            if active:
                chat_input.placeholder = "Terminal Interactiva (Escribe y pulsa Enter)..."
                chat_input.styles.color = "#00ff00" # Verde terminal
            else:
                chat_input.placeholder = "Escribe un mensaje..."
                chat_input.styles.color = "white"
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
                    self.tui_ui.print_message(f"[bold yellow]Confirmación requerida para comando:[/bold yellow] {command}")
                    
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

                    self.tui_ui.print_message(f"[bold yellow]Confirmación requerida para herramienta '{tool_name}':[/bold yellow] {message}")
                    
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

    async def push_screen_wait(self, screen) -> Any:
        """Helper asíncrono para pushear una pantalla y esperar su resultado."""
        future = asyncio.get_event_loop().create_future()
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

        if threading.current_thread() is threading.main_thread():
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
            
        if threading.current_thread() is threading.main_thread():
            push_screen_callback()
        else:
            self.call_from_thread(push_screen_callback)
        return future.result()

    def update_live_display(self, renderable):
        """Actualiza el widget de streaming en tiempo real."""
        # Detener spinner cuando llega contenido real
        if self._spinner_timer:
            self._stop_spinner()
        
        # Solo quitar el borde si aún lo tiene (evita repaints innecesarios de estilos)
        if hasattr(self.live_display, 'styles') and self.live_display.styles.border_left is not None:
             self.live_display.styles.border_left = None
        
        self._last_live_renderable = renderable
        
        # Solo activar display si no lo estaba
        if not self.live_display.display:
            self.live_display.display = True
            
        self.live_display.update(renderable)
        
        # CRÍTICO: Para que parezca que el texto nuevo empuja el historial hacia arriba
        self.call_after_refresh(self.chat_log.scroll_end, animate=False)

    def update_terminal_output(self, tool_name: str, output: str, show_cursor: bool = None):
        """
        Actualiza el panel de terminal con soporte para cursor parpadeante.
        """
        # Guardar para el timer de parpadeo
        self._last_terminal_tool_name = tool_name
        self._last_terminal_output = output
        
        if show_cursor is None:
            # Pestañeo: visible en frame 0, invisible en frame 1
            show_cursor = self._cursor_active and (self._cursor_frame == 0)
            
        from kogniterm.terminal.visual_components import create_terminal_output_panel
        panel = create_terminal_output_panel(tool_name, output, show_cursor=show_cursor)
        self.update_live_display(panel)

    def hide_live_display(self):
        """Oculta el widget de streaming y mueve el contenido al log permanente."""
        self._stop_spinner()
        if self.live_display.display:
            # Al terminar, pasamos el contenido final al log de Rich para el historial
            renderable = getattr(self, "_last_live_renderable", "")
            if renderable:  # Solo persistir si había contenido real (no el spinner)
                self.chat_log.write_message(renderable)
            self.live_display.display = False
            self.live_display.update("")
            self._last_live_renderable = None
            # Scroll al final una vez que el contenido fue consolidado al log
            self.chat_log.scroll_end(animate=False)
