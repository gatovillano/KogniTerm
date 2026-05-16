"""
Widget para mostrar el output en streaming de un agente especializado.
Altura fija de 30 líneas con auto-scroll mientras llega el contenido.
"""
from textual.widgets import Static
from textual.containers import Vertical
from rich.text import Text
from rich.markdown import Markdown
from rich.panel import Panel
from rich.console import Group
from rich.rule import Rule
from kogniterm.terminal.themes import ColorPalette


class AgentStreamWidget(Vertical):
    """
    Panel de streaming para agentes especializados (call_agent).
    - Altura fija de 30 líneas
    - Auto-scroll al final con cada nuevo chunk
    - Usa múltiples widgets internos para cada 'paso' o 'bloque'
    """

    DEFAULT_CSS = """
    AgentStreamWidget {
        height: 30;
        border: round $accent;
        margin: 1 0;
        padding: 0 1;
        background: $surface;
        overflow-y: scroll;
        scrollbar-size: 1 1;
    }

    AgentStreamWidget.complete {
        border: round $success;
    }

    AgentStreamWidget.error {
        border: round $error;
    }

    AgentStreamWidget > Static {
        width: 100%;
        height: auto;
    }
    """

    def __init__(self, agent_name: str, **kwargs):
        super().__init__(**kwargs)
        self.agent_name = agent_name
        self._active_widget = None
        self._active_text = ""
        self._is_complete = False
        self.can_focus = True

    def on_mount(self) -> None:
        self.set_renderable(Text.from_markup(
            f"[dim]⏳ Iniciando [bold]{self.agent_name}[/bold]...[/dim]"
        ))
        self.commit()
        # Iniciar timer para animaciones (spinner)
        self.set_interval(0.1, self._refresh_active)

    def _refresh_active(self) -> None:
        """Refresca el widget activo para permitir animaciones de Rich (spinners)."""
        if self._active_widget:
            self._active_widget.refresh()

    def _get_or_create_active(self) -> Static:
        if self._active_widget is None:
            self._active_widget = Static()
            self.mount(self._active_widget)
        return self._active_widget

    def append_text(self, text: str) -> None:
        """Acumula texto en el widget activo y hace scroll."""
        if not text:
            return
        self._active_text += text
        widget = self._get_or_create_active()
        try:
            widget.update(Text.from_ansi(self._active_text))
        except Exception:
            widget.update(Text(self._active_text))
        
        # Usar call_after_refresh para asegurar que el scroll ocurra tras el layout
        self.call_after_refresh(self.scroll_end, animate=False)

    def set_renderable(self, renderable) -> None:
        """Establece un renderable en el widget activo y hace scroll."""
        widget = self._get_or_create_active()
        if isinstance(renderable, str):
            self._active_text = renderable
            try:
                widget.update(Text.from_ansi(renderable))
            except Exception:
                widget.update(Text(renderable))
        else:
            widget.update(renderable)
            
        self.call_after_refresh(self.scroll_end, animate=False)

    def commit(self) -> None:
        """Finaliza el widget activo actual. El siguiente creará uno nuevo."""
        self._active_widget = None
        self._active_text = ""
        self.call_after_refresh(self.scroll_end, animate=False)

    def set_complete(self, final_renderable=None) -> None:
        """Marca el panel como completado (cambia el borde a verde)."""
        self._is_complete = True
        if final_renderable is not None:
            self.set_renderable(final_renderable)
        self.commit()
        self.add_class("complete")
        self.remove_class("error")

    def set_error(self, error_msg: str = "") -> None:
        """Marca el panel como error."""
        if error_msg:
            self.append_text(f"\n\n[ERROR] {error_msg}")
        self.commit()
        self.add_class("error")
        self.remove_class("complete")
