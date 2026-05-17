from textual.widgets import Static
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown
from kogniterm.terminal.themes import ColorPalette, Icons
from typing import Optional
import pyte
from rich import box

class ToolOutputWidget(Static):
    """
    Widget to display tool output with:
    - Max height of 30 lines.
    - Internal scrolling.
    - Smart formatting (Markdown vs Code).
    """
    
    DEFAULT_CSS = """
    ToolOutputWidget {
        width: 85%;
        max-width: 180;
        min-width: 60;
        height: auto;
        min-height: 5;
        max-height: 30;
        border: solid #4b5563;
        margin: 0 4 1 4;
        padding: 0;
        background: #000000;
        scrollbar-gutter: stable;
        overflow-y: scroll;
        overflow-x: hidden;
    }

    #chat_log ToolOutputWidget {
        width: 100%;
        max-width: 100%;
        margin: 0 0 1 0;
    }
    
    ToolOutputWidget:focus {
        border: solid #10b981; /* emerald green */
    }
    """
    
    def __init__(self, content: str, tool_name: str, language: str = None, command: str = "", **kwargs):
        super().__init__("", **kwargs)
        self.tool_content = content
        self.tool_name = tool_name
        self.language = language
        self.command = command
        self.can_focus = True
        
        # Virtual terminal state
        self.ncol = 80
        self.nrow = 1000  # Aumentado para mantener historial extenso
        self._screen = pyte.Screen(self.ncol, self.nrow)
        self._stream = pyte.Stream(self._screen)

    def _update_title(self, command: str = None):
        """Actualiza el título del borde del widget."""
        if command is not None:
            self.command = command
            
        if self.command:
            # Truncar el comando si es muy largo para que quepa en el título
            cmd_display = self.command if len(self.command) <= 60 else self.command[:57] + "..."
            self.border_title = f"{Icons.TERMINAL} Terminal — $ {cmd_display}"
        else:
            self.border_title = f"{Icons.TERMINAL} Terminal: {self.tool_name}"

    def on_mount(self):
        self._update_title()
        # Usar dimensiones estables para evitar bucles de layout iniciales
        self._screen.resize(self.nrow, self.ncol)
        if self.tool_content:
            self.update_content(self.tool_content)
        # Iniciar parpadeo de cursor real de terminal
        self.cursor_visible = True
        self._cursor_timer = self.set_interval(0.5, self._toggle_cursor)

    def on_focus(self) -> None:
        self.cursor_visible = True
        self.update(self._render_tool_output())

    def on_blur(self) -> None:
        self.cursor_visible = False
        self.update(self._render_tool_output())

    def _toggle_cursor(self):
        if self.has_focus:
            self.cursor_visible = not self.cursor_visible
            self.update(self._render_tool_output())

    def on_resize(self, event) -> None:
        """Ajusta el ancho del emulador PTY al tamaño real del widget."""
        # Se descuenta solo el espacio del borde (2 columnas)
        new_cols = max(40, event.size.width - 2)
        if new_cols != self.ncol:
            self.ncol = new_cols
            self._screen.resize(self.nrow, self.ncol)
            if self.tool_content and isinstance(self.tool_content, str):
                try:
                    self._screen.reset()
                    self._stream.feed(self.tool_content)
                    renderable = self._render_tool_output()
                    self.update(renderable)
                except Exception:
                    pass

    def update_content(self, data, command: str = None):
        """Actualiza el contenido alimentando el emulador PTY."""
        if command:
            self._update_title(command)
            
        if not data:
            return
        
        # Si recibimos un objeto Rich (renderable), lo convertimos a string ANSI
        if not isinstance(data, str):
            from rich.console import Console
            console = Console(width=self.ncol, force_terminal=True, color_system="truecolor")
            with console.capture() as capture:
                console.print(data)
            data = capture.get()

        # Normalizar saltos de línea para asegurar retorno de carro en el emulador
        if isinstance(data, str):
            data = data.replace('\r\n', '\n').replace('\n', '\r\n')

        self.tool_content = data
        
        try:
            # Reseteamos para manejar el contenido acumulado completo que envía KogniTerm
            self._screen.reset()
            self._stream.feed(data)
        except Exception:
            pass
            
        renderable = self._render_tool_output()
        self.update(renderable)
        self.scroll_end(animate=False)

    def _render_tool_output(self):
        from rich.style import Style
        from rich.text import Text
        
        lines = []
        for y in range(self._screen.lines):
            line_text = Text()
            line = self._screen.buffer[y]
            
            current_style = None
            current_run = ""
            for x in range(self._screen.columns):
                char = line[x]
                style = self._get_rich_style(char)
                
                # Renderizar cursor si el cursor está en esta celda y no está oculto por el software
                is_cursor = (self._screen.cursor.x == x and self._screen.cursor.y == y and not self._screen.cursor.hidden)
                if is_cursor:
                    if self.has_focus:
                        if self.cursor_visible:
                            # Combinar estilo existente con reversión
                            style = style + Style(reverse=True)
                    else:
                        # Cursor no enfocado: mostrar un sutil subrayado atenuado
                        style = style + Style(underline=True, dim=True)
                
                if current_style is None:
                    current_style = style
                    current_run = char.data
                elif style == current_style:
                    current_run += char.data
                else:
                    line_text.append(current_run, style=current_style)
                    current_style = style
                    current_run = char.data
            
            if current_run:
                line_text.append(current_run, style=current_style)
            
            lines.append(line_text)
            
        # Eliminar líneas vacías al final, pero NUNCA por encima de la posición actual del cursor
        min_lines = self._screen.cursor.y + 1
        while len(lines) > min_lines and not str(lines[-1]).strip():
            lines.pop()
            
        if not lines:
            lines = [Text("")]
        
        display_content = Text("\n").join(lines)
        
        return display_content

    def _get_rich_style(self, char):
        from rich.style import Style
        fg = char.fg if char.fg != 'default' else None
        bg = char.bg if char.bg != 'default' else None
        if fg == 'brown': fg = 'yellow'
        if bg == 'brown': bg = 'yellow'
        
        # Atributos extendidos de pyte / ANSI para una emulación 100% fiel
        bold = getattr(char, 'bold', False)
        italic = getattr(char, 'italics', False)
        underline = getattr(char, 'underscore', False)
        reverse = getattr(char, 'reverse', False)
        blink = getattr(char, 'blink', False)
        dim = getattr(char, 'dim', False)
        
        # Intercambiar foreground y background si reverse está activo
        if reverse:
            fg, bg = bg, fg
            if fg is None: fg = 'black'
            if bg is None: bg = 'white'
            
        return Style(
            color=fg, 
            bgcolor=bg, 
            bold=bold, 
            italic=italic, 
            underline=underline,
            blink=blink,
            dim=dim
        )

    def _is_markdown(self, content: str) -> bool:
        if not content: return False
        # Heuristic: headers, lists, code blocks, links
        markers = [r"^# ", r"^## ", r"^### ", r"^\* ", r"^- ", r"^\d\. ", r"\[.*\]\(.*\)", r"```"]
        import re
        for m in markers:
            if re.search(m, content, re.MULTILINE):
                return True
        return False

    def _detect_language(self, content: str) -> str:
        if not content: return None
        # Basic heuristics
        if "import " in content and ("def " in content or "class " in content):
            return "python"
        if "<?php" in content:
            return "php"
        if "<html>" in content.lower() or "<!doctype" in content.lower():
            return "html"
        if "package " in content and "import " in content and "func " in content:
            return "go"
        if "using " in content and "namespace " in content:
            return "csharp"
        if "#include " in content:
            return "cpp"
        # Check for JSON
        if content.startswith("{") and content.endswith("}"):
            try:
                import json
                json.loads(content)
                return "json"
            except:
                pass
        return None
