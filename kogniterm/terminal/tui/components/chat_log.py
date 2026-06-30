import logging
from textual.widgets import Static
from textual.containers import VerticalScroll, Horizontal
from kogniterm.terminal.themes import ColorPalette

logger = logging.getLogger(__name__)

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

class AnimatedSpinnerWidget(Static):
    """Widget que representa un spinner animado en el chat log."""
    def __init__(self, text: str = "Procesando", **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.frame_idx = 0
        self.can_focus = False

    def on_mount(self) -> None:
        self.set_interval(0.1, self.tick)

    def tick(self) -> None:
        self.frame_idx = (self.frame_idx + 1) % len(self.frames)
        frame = self.frames[self.frame_idx]
        from rich.text import Text
        self.update(Text(f" {frame} {self.text}", style="bold cyan"))

class ChatLogWidget(VerticalScroll):
    """
    Widget para mostrar el historial del chat usando un contenedor vertical
    que permite modificar mensajes en tiempo real (streaming).
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_message_widget = None
        self._last_tracker_widget = None
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

        # Centrar el mensaje envolviéndolo en Align.center
        renderable = Align.center(renderable)

        def _mount_msg(r):
            try:
                widget = MessageWidget(Padding(r, (1, 0)))
                self.mount(widget)
                self.scroll_end(animate=False)
                return widget
            except Exception as e:
                logger.warning("ChatLogWidget.write_message: _mount_msg falló: %s", e)
                return None

        try:
            if hasattr(self, "app") and getattr(self.app, "call_from_thread", None):
                # call_from_thread will schedule the mount on the main thread
                self.app.call_from_thread(_mount_msg, renderable)
                return None
        except Exception as e:
            logger.warning("ChatLogWidget.write_message: call_from_thread falló, intentando mount directo: %s", e)

        return _mount_msg(renderable)

    def write_user_message(self, text: str):
        """Escribe un mensaje de usuario con línea vertical izquierda."""
        self._last_tracker_widget = None
        from rich.text import Text
        from rich.console import Console, Group
        
        text_color = ColorPalette.TEXT_PRIMARY
        pipe_color = ColorPalette.PRIMARY

        available_width = self._get_available_width()
        console = Console(width=available_width)

        input_lines = text.split('\n')
        wrapped_text_lines = []
        
        for input_line in input_lines:
            if not input_line.strip() and not input_line:
                wrapped_text_lines.append(Text(""))
                continue

            try:
                if "[" in input_line and "]" in input_line:
                    t = Text.from_markup(input_line, style=text_color)
                else:
                    t = Text(input_line, style=text_color)
            except Exception:
                t = Text(input_line, style=text_color)

            wrapped_sublines = list(t.wrap(console, available_width - 5)) # 5 = 0 margin + 1 pipe + 2 padding left + 2 padding right
            if not wrapped_sublines:
                wrapped_text_lines.append(Text(""))
            else:
                for subline in wrapped_sublines:
                    wrapped_text_lines.append(subline)

        def _mount_user_message():
            try:
                # Creamos el texto de los pipes para que coincida con el número de líneas + padding (1 arriba, 1 abajo)
                pipes_text = Text("\n".join(["┃"] * (len(wrapped_text_lines) + 2)), style=pipe_color)
                left = Static(pipes_text)
                left.styles.width = 1
                left.styles.height = "auto"
                left.styles.background = ColorPalette.GRAY_800 # El pipe ahora tiene el mismo fondo que el mensaje

                # El panel derecho con el texto y su fondo
                right = Static(Group(*wrapped_text_lines))
                right.styles.flex = 1
                right.styles.height = "auto"
                right.styles.background = ColorPalette.GRAY_800
                right.styles.padding = (1, 2) # Margen interno (padding) añadido

                row = Horizontal(left, right, classes="user-message-row")
                row.styles.height = "auto"
                row.styles.margin = (0, 0, 1, 0) # Eliminado el margen izquierdo para que esté al borde
                
                self.mount(row)
                self._active_message_widget = None
                self.scroll_end(animate=False)
            except Exception as e:
                import logging
                logging.error(f"Error mounting user message: {e}")
                pass

        try:
            if hasattr(self, "app") and getattr(self.app, "call_from_thread", None):
                self.app.call_from_thread(_mount_user_message)
                return
        except Exception:
            pass

        _mount_user_message()

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
        is_terminal = False
        is_spinner = False
        tool_name = "Terminal"
        
        # Detectar si recibimos la tupla especial de spinner especial ("__SPINNER__", text)
        if isinstance(content, tuple) and len(content) == 2 and content[0] == "__SPINNER__":
            is_spinner = True
            renderable = content[1]
            terminal_command = ""
        # Detectar si recibimos la tupla especial ("__TERMINAL__", tool_name, output) o ("__TERMINAL__", tool_name, output, command)
        elif isinstance(content, tuple) and len(content) >= 3 and content[0] == "__TERMINAL__":
            is_terminal = True
            tool_name = content[1]
            renderable = content[2]
            terminal_command = content[3] if len(content) >= 4 else tool_name
        else:
            # Detectar si es un panel de terminal (vía tui_app.update_terminal_output fallback)
            # El renderable puede venir envuelto en Padding o Group desde visual_components
            def _check_is_terminal(r):
                from rich.panel import Panel
                from rich.padding import Padding
                from rich.console import Group
                
                if isinstance(r, Panel):
                    title = str(r.title) if r.title else ""
                    if "TERMINAL" in title or "execute_command" in title:
                        return True, title.replace("TERMINAL | ", "")
                
                if isinstance(r, Padding):
                    return _check_is_terminal(r.renderable)
                    
                if isinstance(r, Group):
                    for sub_r in r.renderables:
                        # En visual_components, el primer elemento suele ser el título (Text)
                        if "TERMINAL" in str(sub_r):
                            return True, "bash"
                        # O puede ser un Panel anidado
                        found, name = _check_is_terminal(sub_r)
                        if found: return True, name
                
                return False, "Terminal"

            is_terminal, tool_name = _check_is_terminal(content)
            
            if isinstance(content, str):
                if "\x1b" in content or "┃" in content or "╭" in content:
                    from rich.text import Text
                    renderable = Padding(Text.from_ansi(content), (1, 0, 1, 4))
                else:
                    from rich.markdown import Markdown
                    renderable = Padding(Markdown(content), (1, 0, 1, 4))
            else:
                renderable = content
            terminal_command = tool_name  # para el caso no-terminal, coincide con tool_name

        def _mount_or_update(r, terminal_flag, spinner_flag, t_name, t_command=""):
            try:
                if spinner_flag:
                    if self._active_message_widget is None or not isinstance(self._active_message_widget, AnimatedSpinnerWidget):
                        if self._active_message_widget:
                            self._active_message_widget.remove()
                        self._active_message_widget = AnimatedSpinnerWidget(r)
                        self.mount(self._active_message_widget)
                    else:
                        if self._active_message_widget.text != r:
                            self._active_message_widget.text = r
                # Si es terminal, forzar el uso de ToolOutputWidget para interactividad
                elif terminal_flag:
                    if self._active_message_widget is None or not isinstance(self._active_message_widget, ToolOutputWidget):
                        # Reemplazar widget si cambió de tipo
                        if self._active_message_widget:
                            self._active_message_widget.remove()
                        
                        self._active_message_widget = ToolOutputWidget("", t_name, command=t_command)
                        self.mount(self._active_message_widget)
                    
                    # ToolOutputWidget.update_content maneja la lógica de pyte
                    self._active_message_widget.update_content(r, command=t_command)
                else:
                    if self._active_message_widget is None or isinstance(self._active_message_widget, ToolOutputWidget) or isinstance(self._active_message_widget, AnimatedSpinnerWidget):
                        if self._active_message_widget:
                            self._active_message_widget.remove()
                        self._active_message_widget = MessageWidget(r)
                        self.mount(self._active_message_widget)
                    else:
                        self._active_message_widget.update(r)
                
                self.scroll_end(animate=False)
            except Exception as e:
                import logging
                logging.exception("ChatLogWidget: Error in _mount_or_update for %s: %s", self.id, e)

        try:
            if hasattr(self, "app") and getattr(self.app, "call_from_thread", None):
                self.app.call_from_thread(_mount_or_update, renderable, is_terminal, is_spinner, tool_name, terminal_command)
                return
        except Exception as e:
            import logging
            logging.exception("ChatLogWidget: Error calling call_from_thread in write_stream: %s", e)

        _mount_or_update(renderable, is_terminal, is_spinner, tool_name, terminal_command)

    def stop_stream(self):
        """Finaliza el streaming actual y elimina el spinner si estaba activo."""
        if self._active_message_widget:
            if isinstance(self._active_message_widget, AnimatedSpinnerWidget):
                try:
                    self._active_message_widget.remove()
                except Exception:
                    pass
        self._active_message_widget = None

    def write_tool_notification(self, tool_name: str, action_desc: str = "", skill_name: str = ""):
        """Escribe notificación de herramienta."""
        from rich.text import Text
        from kogniterm.terminal.themes import ColorPalette, Icons
        
        line1 = Text()
        if skill_name:
            # Formatear el nombre de la skill (ej. file_operations -> File Operations)
            skill_title = skill_name.replace('_', ' ').title()
            line1.append(f"{Icons.TOOL} Ejecutando Skill: ", style=f"bold {ColorPalette.SECONDARY}")
            line1.append(skill_title, style=f"bold {ColorPalette.SECONDARY_LIGHT}")
            line1.append(f" ({skill_name})", style=f"dim {ColorPalette.SECONDARY_LIGHT}")
        else:
            line1.append(f"{Icons.TOOL} Ejecutando herramienta: ", style=f"bold {ColorPalette.SECONDARY}")
            line1.append(tool_name, style=f"bold {ColorPalette.SECONDARY_LIGHT}")
        
        lines = [line1]
        if action_desc:
            line2 = Text()
            line2.append("   ↳ ", style=f"dim {ColorPalette.GRAY_600}")
            line2.append("Acción: ", style=f"bold italic {ColorPalette.TEXT_SECONDARY}")
            line2.append(action_desc, style=f"italic {ColorPalette.TEXT_SECONDARY}")
            lines.append(line2)
        
        def _mount_tool_notify(lines_group):
            try:
                widget = MessageWidget(Padding(lines_group, (1, 0, 1, 4)))
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

    def write_task_tracker(self, panel):
        """Escribe o actualiza el panel de seguimiento de tareas en el chat log."""
        def _mount_or_update():
            try:
                # Comprobar si ya existe un widget de tracker anterior montado y activo
                if hasattr(self, "_last_tracker_widget") and self._last_tracker_widget and self._last_tracker_widget.parent:
                    # Centrar el mensaje envolviéndolo en Align.center
                    self._last_tracker_widget.update(Padding(Align.center(panel), (1, 0)))
                else:
                    widget = MessageWidget(Padding(Align.center(panel), (1, 0)))
                    self._last_tracker_widget = widget
                    self.mount(widget)
                self.scroll_end(animate=False)
            except Exception as e:
                logger.warning("ChatLogWidget.write_task_tracker: _mount_or_update falló: %s", e)

        try:
            if hasattr(self, "app") and getattr(self.app, "call_from_thread", None):
                self.app.call_from_thread(_mount_or_update)
                return
        except Exception as e:
            logger.warning("ChatLogWidget.write_task_tracker: call_from_thread falló: %s", e)

        _mount_or_update()

    def clear(self):
        """Limpia el chat log."""
        # En VerticalScroll, para limpiar eliminamos los hijos
        for child in list(self.children):
            child.remove()
        self._active_message_widget = None
        self._last_tracker_widget = None
