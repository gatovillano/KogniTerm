from textual.widgets import Static
from textual.containers import VerticalScroll
from kogniterm.terminal.themes import ColorPalette

from rich.panel import Panel
from rich.text import Text
from rich.padding import Padding
from rich.align import Align
from rich.markdown import Markdown
from rich.console import Group
from rich import box

class MessageWidget(Static):
    """Widget para representar un mensaje individual en el chat."""
    def __init__(self, renderable, **kwargs):
        super().__init__(renderable, **kwargs)
        self.can_focus = False

class ChatLogWidget(VerticalScroll):
    """
    Widget para mostrar el historial del chat usando un contenedor vertical
    que permite modificar mensajes en tiempo real (streaming).
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_message_widget = None
        self.can_focus = True

    def _get_available_width(self):
        """Calcula el ancho disponible real dentro del widget."""
        try:
            w = self.size.width
            if w > 0:
                return max(w - 4, 40) # Margen para scrollbar y bordes
            
            # Fallback a dimensiones de la aplicación
            if hasattr(self, "app") and self.app.size.width > 0:
                # El chat log suele ocupar el 85% del ancho de la app
                return max(int(self.app.size.width * 0.85) - 4, 40)
                
            return 78
        except:
            return 78

    def write(self, renderable):
        """Redirige a write_message para compatibilidad con RichLog."""
        return self.write_message(renderable)

    def write_message(self, renderable, style=None):
        """Escribe un elemento Rich al log."""
        if style and isinstance(renderable, str):
            renderable = Text(renderable, style=style)
        
        # Si es un simple string, lo envolvemos para padding
        if isinstance(renderable, str):
             renderable = Text(renderable)
             
        widget = MessageWidget(Padding(renderable, (1, 0)))
        self.mount(widget)
        self.scroll_end(animate=False)
        return widget

    def write_user_message(self, text: str):
        """Escribe un mensaje de usuario con línea vertical izquierda."""
        from rich.text import Text
        from rich.console import Console, Group
        
        text_color = ColorPalette.TEXT_PRIMARY
        pipe_color = ColorPalette.PRIMARY

        # No hacemos wrapping manual aquí si usamos Static, ya que Static maneja el wrapping.
        # Pero queremos el pipe izquierdo en cada línea. 
        # RichLog lo hacía manual. Aquí podemos usar un Panel con borde izquierdo solamente.
        
        content = Text(text, style=text_color)
        
        # Usamos un Panel con estilo de borde personalizado para simular el pipe
        panel = Panel(
            content,
            border_style=pipe_color,
            box=box.ASCII,
            padding=(0, 1)
        )
        # Nota: Rich no tiene un box.LEFT_ONLY. Usamos el Group con pipes o Panel simple.
        # El diseño original era muy específico, vamos a recrearlo con un renderable custom.
        
        # Recreación del diseño con pipes:
        available_width = self._get_available_width() - 4
        console = Console(width=available_width)
        
        input_lines = text.split('\n')
        rendered_lines = []
        for input_line in input_lines:
            if not input_line.strip() and not input_line:
                rendered_lines.append(Text.assemble(("┃", pipe_color)))
                continue
            
            try:
                if "[" in input_line and "]" in input_line:
                    t = Text.from_markup(input_line, style=text_color)
                else:
                    t = Text(input_line, style=text_color)
            except Exception:
                t = Text(input_line, style=text_color)

            wrapped_sublines = list(t.wrap(console, available_width))
            if not wrapped_sublines:
                rendered_lines.append(Text.assemble(("┃", pipe_color)))
            else:
                for subline in wrapped_sublines:
                    rendered_lines.append(Text.assemble(("┃ ", pipe_color), subline))

        widget = MessageWidget(Padding(Group("", *rendered_lines, ""), (1, 0)))
        self.mount(widget)
        
        # Cerrar cualquier streaming activo al enviar mensaje nuevo
        self._active_message_widget = None
        
        self.scroll_end(animate=False)

    def write_agent_message(self, text: str):
        """Escribe un mensaje de agente."""
        if text is None: text = ""
        
        if not isinstance(text, str):
            import json
            try: text = json.dumps(text, indent=2)
            except: text = str(text)
        
        markdown_content = Markdown(text)
        widget = MessageWidget(Padding(markdown_content, (1, 0, 1, 4)))
        self.mount(widget)
        self.scroll_end(animate=False)

    def write_stream(self, content):
        """
        Escribe contenido de streaming al log. 
        Si hay un mensaje activo, lo actualiza. Si no, crea uno nuevo.
        """
        if not content:
            return
            
        renderable = content
        if isinstance(content, str):
            renderable = Padding(content, (1, 0, 1, 4))
            
        if self._active_message_widget is None:
            # Crear nuevo widget para el stream. El renderable de bash_agent 
            # ya incluye su propio padding (0, 4).
            self._active_message_widget = MessageWidget(renderable)
            self.mount(self._active_message_widget)
        else:
            self._active_message_widget.update(renderable)
        
        # Asegurar visibilidad
        self.scroll_end(animate=False)

    def stop_stream(self):
        """Finaliza el streaming actual."""
        self._active_message_widget = None

    def write_tool_notification(self, tool_name: str, action_desc: str = ""):
        """Escribe notificación de herramienta."""
        from rich.text import Text
        from kogniterm.terminal.themes import ColorPalette, Icons
        
        line1 = Text()
        line1.append(f"{Icons.TOOL} Ejecutando herramienta: ", style=f"bold {ColorPalette.SECONDARY}")
        line1.append(tool_name, style=f"bold {ColorPalette.SECONDARY_LIGHT}")
        
        lines = [line1]
        if action_desc:
            line2 = Text()
            line2.append("   ↳ ", style=f"dim {ColorPalette.GRAY_600}")
            line2.append(action_desc, style=f"italic {ColorPalette.TEXT_SECONDARY}")
            lines.append(line2)
        
        widget = MessageWidget(Padding(Group(*lines), (1, 0)))
        self.mount(widget)
        self.scroll_end(animate=False)

    def clear(self):
        """Limpia el chat log."""
        # En VerticalScroll, para limpiar eliminamos los hijos
        for child in list(self.children):
            child.remove()
        self._active_message_widget = None
