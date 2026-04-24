from textual.widgets import Static
from textual.containers import VerticalScroll, Horizontal
from kogniterm.terminal.themes import ColorPalette

from rich.panel import Panel
from rich.text import Text
from rich.padding import Padding
from rich.align import Align
from rich.markdown import Markdown
from rich.console import Group
from rich import box

from .tool_output import ToolOutputWidget

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
        def _mount_msg(r):
            try:
                widget = MessageWidget(Padding(r, (1, 0)))
                self.mount(widget)
                self.scroll_end(animate=False)
                return widget
            except Exception:
                return None

        try:
            if hasattr(self, "app") and getattr(self.app, "call_from_thread", None):
                # call_from_thread will schedule the mount on the main thread
                self.app.call_from_thread(_mount_msg, renderable)
                return None
        except Exception:
            pass

        return _mount_msg(renderable)

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
        # El ChatLogWidget ya tiene scrollbar-gutter: stable, pero queremos que el texto
        # empiece en la misma columna que el input (col 4).
        # El pipe '┃ ' ocupa 2 chars. Añadimos 2 espacios iniciales para llegar a 4.
        # Ajustamos el ancho para que coincida exactamente con los mensajes del Agente.
        # El Agente usa Padding(..., (1, 0, 1, 4)), por lo que su texto tiene width - 4.
        # Aquí el pipe "  ┃ " ya ocupa 4 caracteres, por lo que el texto restante debe ser width - 4.
        # Preparar las líneas (objetos Rich) en este hilo; crear y montar
        # widgets debe ejecutarse en el hilo principal de la aplicación Textual.
        available_width = self._get_available_width()
        console = Console(width=available_width)

        input_lines = text.split('\n')
        rendered_lines = []
        for input_line in input_lines:
            if not input_line.strip() and not input_line:
                rendered_lines.append(Text.assemble(("  ┃", pipe_color)))
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
                rendered_lines.append(Text.assemble(("  ┃", pipe_color)))
            else:
                for subline in wrapped_sublines:
                    rendered_lines.append(Text.assemble(("  ┃ ", pipe_color), subline))

        def _mount_user_message(lines):
            # Crear los widgets y montarlos en el hilo principal
            try:
                row = Horizontal()
                left = Static(Text.assemble(("  ┃ ", pipe_color)))
                try:
                    left.styles.width = 4
                    left.styles.min_width = 4
                except Exception:
                    pass

                right = Static(Padding(Group(*lines), (0, 1)))
                try:
                    right.styles.flex = 1
                except Exception:
                    pass
                right.styles.background = ColorPalette.GRAY_800

                row.mount(left)
                row.mount(right)
                self.mount(row)
                self._active_message_widget = None
                self.scroll_end(animate=False)
            except Exception:
                # En caso de fallo, intentar montar de forma simple
                try:
                    widget = MessageWidget(Padding(Group(*lines), (0, 0)), classes="user-message")
                    widget.styles.background = ColorPalette.GRAY_800
                    self.mount(widget)
                    self._active_message_widget = None
                    self.scroll_end(animate=False)
                except Exception:
                    pass

        # Preferir ejecutar el montaje en el hilo principal de la app
        try:
            if hasattr(self, "app") and getattr(self.app, "call_from_thread", None):
                # call_from_thread acepta la función y argumentos
                self.app.call_from_thread(_mount_user_message, rendered_lines)
                return
        except Exception:
            pass

        # Fallback: intentar montar directamente (si ya estamos en el hilo principal)
        _mount_user_message(rendered_lines)

    def write_agent_message(self, text: str):
        """Escribe un mensaje de agente."""
        if text is None: text = ""
        
        if not isinstance(text, str):
            import json
            try: text = json.dumps(text, indent=2)
            except: text = str(text)
        
        markdown_content = Markdown(text)

        def _mount_agent(md):
            try:
                widget = MessageWidget(Padding(md, (1, 0, 1, 4)))
                self.mount(widget)
                self.scroll_end(animate=False)
            except Exception:
                try:
                    # Fallback simple
                    widget = MessageWidget(Padding(md, (1, 0)))
                    self.mount(widget)
                    self.scroll_end(animate=False)
                except Exception:
                    pass

        try:
            if hasattr(self, "app") and getattr(self.app, "call_from_thread", None):
                self.app.call_from_thread(_mount_agent, markdown_content)
                return
        except Exception:
            pass

        _mount_agent(markdown_content)
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

        def _mount_or_update(r):
            try:
                if self._active_message_widget is None:
                    self._active_message_widget = MessageWidget(r)
                    self.mount(self._active_message_widget)
                else:
                    self._active_message_widget.update(r)
                self.scroll_end(animate=False)
            except Exception:
                pass

        try:
            if hasattr(self, "app") and getattr(self.app, "call_from_thread", None):
                self.app.call_from_thread(_mount_or_update, renderable)
                return
        except Exception:
            pass

        _mount_or_update(renderable)

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
        
        def _mount_tool_notify(lines_group):
            try:
                widget = MessageWidget(Padding(lines_group, (1, 0)))
                self.mount(widget)
                self.scroll_end(animate=False)
            except Exception:
                pass

        try:
            if hasattr(self, "app") and getattr(self.app, "call_from_thread", None):
                self.app.call_from_thread(_mount_tool_notify, Group(*lines))
                return
        except Exception:
            pass

        _mount_tool_notify(Group(*lines))

    def write_tool_output(self, content: str, tool_name: str, language: str = None):
        """Escribe la salida de una herramienta usando el ToolOutputWidget."""
        def _mount_tool_output(c, tname, lang):
            try:
                widget = ToolOutputWidget(c, tname, language=lang)
                self.mount(widget)
                self.scroll_end(animate=False)
                return widget
            except Exception:
                return None

        try:
            if hasattr(self, "app") and getattr(self.app, "call_from_thread", None):
                self.app.call_from_thread(_mount_tool_output, content, tool_name, language)
                return None
        except Exception:
            pass

        return _mount_tool_output(content, tool_name, language)

    def clear(self):
        """Limpia el chat log."""
        # En VerticalScroll, para limpiar eliminamos los hijos
        for child in list(self.children):
            child.remove()
        self._active_message_widget = None
