from textual.widgets import Static
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.style import Style
from kogniterm.terminal.themes import ColorPalette, Icons
from typing import Optional
import pyte
import re
from rich import box

# Estilo vacío (sin formato) compartido para celdas en blanco — evita crear
# miles de objetos Style por actualización.
_EMPTY_STYLE = Style.null()

class ToolOutputWidget(Static):
    """
    Widget to display tool output with:
    - Max height of 30 lines.
    - Internal scrolling.
    - Smart formatting (Markdown vs Code vs Terminal).
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
        self.nrow = 1000  # Historial extenso para comandos con mucha salida
        self._screen = pyte.Screen(self.ncol, self.nrow)
        self._stream = pyte.Stream(self._screen)
        
        # Cursor blink state
        self.cursor_visible = True

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
        """Actualiza el contenido alimentando el emulador PTY o mediante smart formatting."""
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

        self.tool_content = data

        # --- Smart Formatting ---
        # Si el texto tiene secuencias ANSI, siempre usar emulador PTY
        if self._has_ansi(data):
            renderable = self._render_pyte(data)
        elif self._is_markdown(data):
            renderable = Markdown(data)
        else:
            lang = self.language or self._detect_language(data)
            if lang:
                renderable = Syntax(
                    data, lang,
                    theme="monokai",
                    line_numbers=False,
                    word_wrap=True,
                )
            else:
                renderable = self._render_pyte(data)

        self.update(renderable)
        self.scroll_end(animate=False)

    # ─────────────────────────── Helpers ────────────────────────────────────

    def _has_ansi(self, content: str) -> bool:
        """Devuelve True si el contenido tiene secuencias de escape ANSI/terminal."""
        return "\x1b" in content or "\r" in content

    def _render_pyte(self, data: str) -> Text:
        """Alimenta el buffer PTY con *data* y devuelve el renderizable Rich."""
        # Normalizar saltos de línea para el emulador
        data = data.replace('\r\n', '\n').replace('\n', '\r\n')
        try:
            self._screen.reset()
            self._stream.feed(data)
        except Exception:
            pass
        return self._render_tool_output()

    def _render_tool_output(self) -> Text:
        """
        Convierte el buffer PTY actual a un objeto Rich Text.

        Optimización clave: en lugar de iterar las 1 000 líneas del buffer
        virtual, encontramos el índice de la última fila con contenido real
        (usando el cursor como cota inferior) y sólo procesamos hasta ahí.
        """
        cursor_y = self._screen.cursor.y
        cursor_x = self._screen.cursor.x
        cursor_hidden = self._screen.cursor.hidden
        buffer = self._screen.buffer
        columns = self._screen.columns
        
        # Calcular la última línea que debemos renderizar:
        # buscamos desde cursor_y hacia arriba la última fila no vacía.
        max_y = cursor_y
        for y in range(self._screen.lines - 1, cursor_y, -1):
            row = buffer[y]
            if any(row[x].data != ' ' for x in range(columns)):
                max_y = y
                break

        lines = []
        for y in range(max_y + 1):
            line_text = Text()
            row = buffer[y]
            
            current_style: Optional[Style] = None
            current_run = ""
            
            for x in range(columns):
                char = row[x]
                
                # Estilo rápido: celdas por defecto (la gran mayoría)
                is_default_char = (
                    char.fg == 'default' and
                    char.bg == 'default' and
                    not char.bold and
                    not char.italics and
                    not char.underscore and
                    not char.reverse and
                    not char.blink
                )
                
                if is_default_char:
                    style = _EMPTY_STYLE
                else:
                    style = self._get_rich_style(char)
                
                # Renderizar cursor
                is_cursor = (x == cursor_x and y == cursor_y and not cursor_hidden)
                if is_cursor:
                    if self.has_focus and self.cursor_visible:
                        style = style + Style(reverse=True)
                    elif not self.has_focus:
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
        
        # Eliminar líneas vacías al final, respetando la posición del cursor
        min_lines = cursor_y + 1
        while len(lines) > min_lines and not str(lines[-1]).strip():
            lines.pop()
            
        if not lines:
            lines = [Text("")]
        
        return Text("\n").join(lines)

    def _get_rich_style(self, char) -> Style:
        """Convierte los atributos de un carácter pyte a un Rich Style."""
        fg = char.fg if char.fg != 'default' else None
        bg = char.bg if char.bg != 'default' else None
        # pyte usa 'brown' por compatibilidad histórica; Rich lo llama 'yellow'
        if fg == 'brown': fg = 'yellow'
        if bg == 'brown': bg = 'yellow'
        
        bold = char.bold
        italic = char.italics
        underline = char.underscore
        reverse = char.reverse
        blink = char.blink

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
            blink=blink
        )

    def _is_markdown(self, content: str) -> bool:
        """Heurística para detectar contenido Markdown."""
        if not content:
            return False
        markers = [r"^# ", r"^## ", r"^### ", r"^\* ", r"^- ", r"^\d\. ", r"\[.*\]\(.*\)", r"```"]
        for m in markers:
            if re.search(m, content, re.MULTILINE):
                return True
        return False

    def _detect_language(self, content: str) -> Optional[str]:
        """Heurística para detectar el lenguaje de programación del contenido."""
        if not content:
            return None
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
        # JSON
        stripped = content.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or \
           (stripped.startswith("[") and stripped.endswith("]")):
            try:
                import json
                json.loads(stripped)
                return "json"
            except Exception:
                pass
        return None
