import asyncio
from textual.app import App, ComposeResult
from textual.widgets import TextArea
from textual.containers import Horizontal
from textual.events import Key

class AutoShrinkTextArea(TextArea):
    def on_key(self, event: Key):
        super().on_key(event)
        self.update_height()
        
    def update_height(self):
        lc = self.document.line_count
        self.styles.height = lc

class TestApp(App):
    CSS = """
    #input_container {
        height: auto;
        min-height: 5;
        max-height: 20;
        background: #2a2a2a;
    }
    AutoShrinkTextArea {
        min-height: 3;
    }
    """
    def compose(self) -> ComposeResult:
        with Horizontal(id="input_container"):
            self.ta = AutoShrinkTextArea("line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8")
            yield self.ta

    async def on_mount(self):
        await asyncio.sleep(0.5)
        self.ta.clear()
        self.ta.update_height()
        await asyncio.sleep(0.5)
        print("size after backspaces:", self.ta.size)
        print("container:", self.query_one("#input_container").size)
        self.exit()

if __name__ == "__main__":
    app = TestApp()
    app.run(headless=True)
