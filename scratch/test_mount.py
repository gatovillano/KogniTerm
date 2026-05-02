import os
import sys

# Add project to path
sys.path.insert(0, os.path.abspath("."))

from kogniterm.terminal.themes import ColorPalette
from rich.text import Text
from rich.console import Console, Group
from textual.app import App, ComposeResult
from textual.widgets import Static
from textual.containers import Horizontal, VerticalScroll

class TestApp(App):
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="chat_log"):
            pass
            
    def on_mount(self):
        text = "Hello world!"
        text_color = ColorPalette.TEXT_PRIMARY
        pipe_color = ColorPalette.PRIMARY

        available_width = 80
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

            wrapped_sublines = list(t.wrap(console, available_width - 6)) # 6 = 2 margin + 2 pipe + 2 padding
            if not wrapped_sublines:
                wrapped_text_lines.append(Text(""))
            else:
                for subline in wrapped_sublines:
                    wrapped_text_lines.append(subline)

        try:
            row = Horizontal(classes="user-message-row")
            row.styles.height = "auto"
            row.styles.margin = (0, 0, 1, 2)

            pipes_text = Text("\n".join(["┃"] * len(wrapped_text_lines)), style=pipe_color)
            left = Static(pipes_text)
            left.styles.width = 2
            left.styles.height = "auto"
            left.styles.background = "transparent"

            right = Static(Group(*wrapped_text_lines))
            right.styles.flex = 1
            right.styles.height = "auto"
            right.styles.background = ColorPalette.GRAY_800
            right.styles.padding = (1, 2)

            row.mount(left)
            row.mount(right)
            
            chat_log = self.query_one("#chat_log")
            chat_log.mount(row)
            print("Mounted successfully")
        except Exception as e:
            print(f"Error mounting: {e}")
            self.exit(code=1)
            
        self.exit()

if __name__ == "__main__":
    app = TestApp()
    app.run()
