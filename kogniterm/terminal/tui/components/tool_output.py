from textual.widgets import Static
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown
from kogniterm.terminal.themes import ColorPalette, Icons
from typing import Optional

class ToolOutputWidget(Static):
    """
    Widget to display tool output with:
    - Max height of 30 lines.
    - Internal scrolling.
    - Smart formatting (Markdown vs Code).
    """
    
    DEFAULT_CSS = """
    ToolOutputWidget {
        height: auto;
        max-height: 30;
        border: round $accent;
        margin: 1 0;
        padding: 0 1;
        background: $surface;
        scrollbar-gutter: stable;
        overflow-y: scroll;
    }
    
    ToolOutputWidget:focus {
        border: round $primary;
    }
    
    ToolOutputWidget .tool-title {
        color: $accent;
        text-style: bold;
    }
    """
    
    def __init__(self, content: str, tool_name: str, language: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.tool_content = content
        self.tool_name = tool_name
        self.language = language
        self.can_focus = True

    def on_mount(self):
        self.update_content(self.tool_content)

    def update_content(self, content: str):
        self.tool_content = content
        renderable = self._render_tool_output()
        self.update(renderable)
        # Auto-scroll al final del widget de salida si el contenido excede el alto máximo
        self.scroll_end(animate=False)

    def _render_tool_output(self):
        from rich.console import Group
        from rich.rule import Rule
        
        # Clean output
        clean_output = self.tool_content.replace('\r\n', '\n').replace('\r', '').strip()
        if not clean_output:
            clean_output = "(sin salida)"

        # Header
        title = Text.assemble(
            (f"{Icons.TOOL} ", ColorPalette.SECONDARY),
            (f"Tool Output: {self.tool_name}", ColorPalette.SECONDARY_LIGHT)
        )
        
        # content
        if self._is_markdown(clean_output):
            display_content = Markdown(clean_output)
        else:
            lang = self.language or self._detect_language(clean_output)
            if lang:
                display_content = Syntax(clean_output, lang, theme="monokai", line_numbers=True)
            else:
                display_content = Text.from_ansi(clean_output)

        return Group(
            title,
            Rule(style=ColorPalette.GRAY_700),
            Text(""), # Espacio divisor
            display_content
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
