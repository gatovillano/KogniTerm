import asyncio
from textual.app import App, ComposeResult
from textual.widgets import TextArea
from textual.containers import Horizontal

class TestApp(App):
    CSS = """
    #input_container {
        height: 5;
        background: #2a2a2a;
    }
    TextArea {
        height: 3;
    }
    """
    def compose(self) -> ComposeResult:
        with Horizontal(id="input_container"):
            self.ta = TextArea("line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8")
            yield self.ta

    async def on_mount(self):
        await asyncio.sleep(0.1)
        print("Size con CSS fijo:", self.ta.size)
        self.exit()

if __name__ == "__main__":
    app = TestApp()
    app.run(headless=True)
