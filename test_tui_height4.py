import asyncio
from textual.app import App, ComposeResult
from textual.widgets import TextArea
from textual.containers import Horizontal

class TestApp(App):
    CSS = """
    #input_container {
        height: auto;
        min-height: 5;
        max-height: 20;
        background: #2a2a2a;
    }
    TextArea {
        height: auto;
        min-height: 3;
    }
    """
    def compose(self) -> ComposeResult:
        with Horizontal(id="input_container"):
            self.ta = TextArea("line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8")
            yield self.ta

    async def on_mount(self):
        await asyncio.sleep(0.5)
        self.ta.clear()
        print("virtual_size:", self.ta.virtual_size)
        self.ta.styles.height = "auto"
        # Let's force update layout
        self.ta._refresh_size()
        await asyncio.sleep(0.5)
        print("virtual_size after _refresh_size:", self.ta.virtual_size)
        print("size after:", self.ta.size)
        self.exit()

if __name__ == "__main__":
    app = TestApp()
    app.run(headless=True)
