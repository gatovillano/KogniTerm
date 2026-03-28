from textual.widgets import RichLog
from kogniterm.terminal.themes import ColorPalette

from rich.panel import Panel
from rich.text import Text
from rich.padding import Padding
from rich.align import Align
from rich.markdown import Markdown
from rich.console import Group
from rich import box

class ChatLogWidget(RichLog):
    """
    Widget para mostrar el historial del chat usando Rich log para mayor robustez.
    """
    def __init__(self, **kwargs):
        # markup=False es CRÍTICO para prevenir crasheos al renderizar objetos Rich complejos
        super().__init__(markup=False, wrap=True, auto_scroll=True, **kwargs)

    def _get_available_width(self):
        """Calcula el ancho disponible real dentro del widget."""
        try:
            # Si el widget ya tiene tamaño, usarlo (es lo más preciso)
            w = self.size.width
            if w > 0:
                # Ya no restamos 10 porque quitamos el padding CSS manual
                # Dejamos un margen mínimo de 2 para el scrollbar/bordes
                return max(w - 2, 20)
            
            # Fallback a dimensiones de la aplicación
            if hasattr(self, "app") and self.app.size.width > 0:
                return max(self.app.size.width - 2, 20)
                
            # Fallback final a la terminal
            import shutil
            term_w = shutil.get_terminal_size().columns
            return max(term_w - 2, 20)
        except:
            return 78


    def write_message(self, renderable, style=None):
        """Escribe un elemento Rich al log asegurando que se muestre correctamente."""
        # Añadir separación vertical
        self.write("")
        
        if style and isinstance(renderable, str):
            renderable = Text(renderable, style=style)
        
        self.write(renderable)
        
        # Añadir separación vertical después
        self.write("")
        
        # Forzar scroll al final tras el próximo refresh de layout
        self.call_after_refresh(self.scroll_end, animate=False)

    def write_user_message(self, text: str):
        """Escribe un mensaje de usuario con línea vertical izquierda en toda la altura."""
        bg_color = ColorPalette.GRAY_800
        text_color = ColorPalette.TEXT_PRIMARY
        pipe_color = ColorPalette.GRAY_600

        from rich.text import Text
        from rich.console import Group

        lines = text.split('\n')
        rendered_lines = []
        for line in lines:
            # Cada línea tiene el pipe vertical al inicio con fondo
            line_text = Text.assemble(
                ("┃ ", pipe_color),
                (line, text_color),
                style=f"on {bg_color}"
            )
            rendered_lines.append(line_text)

        group = Group(
            "",  # línea vacía arriba
            *rendered_lines,
            ""   # línea vacía abajo
        )

        self.write(group)
        self.call_after_refresh(self.scroll_end, animate=False)

    def write_agent_message(self, text: str):
        """Escribe un mensaje de agente."""
        if text is None:
            text = ""
        
        # ASEGURAR QUE EL TEXTO SEA STRING PARA EL RENDERIZADO
        if not isinstance(text, str):
            import json
            try:
                text = json.dumps(text, indent=2)
            except:
                text = str(text)
        
        # Añadir separación vertical
        self.write("")
            
        # El Markdown se ajustará al ancho disponible del widget automáticamente
        markdown_content = Markdown(text)
        
        # Escribir directamente.
        self.write(markdown_content)

        # Añadir separación vertical
        self.write("")
        
        # Mantener el scroll al fondo
        self.call_after_refresh(self.scroll_end, animate=False)

    def write_stream(self, content: str):
        """Escribe contenido de streaming al log sin separaciones verticales excesivas."""
        if not content:
            return
            
        # Para streaming, escribimos directamente. RichLog maneja el scroll si auto_scroll=True.
        # Si el contenido tiene saltos de línea, RichLog los procesará como líneas nuevas.
        self.write(content, scroll_end=True)

    def write_tool_notification(self, tool_name: str, action_desc: str = ""):
        """Escribe notificación de herramienta alineada a la izquierda con padding del chat."""
        from rich.text import Text
        from kogniterm.terminal.themes import ColorPalette, Icons
        
        # Línea 1: icono + nombre de herramienta
        line1 = Text()
        line1.append(f"{Icons.TOOL} Ejecutando herramienta: ", style=f"bold {ColorPalette.SECONDARY}")
        line1.append(tool_name, style=f"bold {ColorPalette.SECONDARY_LIGHT}")
        
        lines = [line1]
        
        # Línea 2 (opcional): descripción de la acción
        if action_desc:
            line2 = Text()
            line2.append("   ↳ ", style=f"dim {ColorPalette.GRAY_600}")
            line2.append(action_desc, style=f"italic {ColorPalette.TEXT_SECONDARY}")
            lines.append(line2)
        
        from rich.console import Group
        self.write("")
        self.write(Group(*lines))

        self.write("")
        
        # Mantener el scroll al fondo
        self.call_after_refresh(self.scroll_end, animate=False)
