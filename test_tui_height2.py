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
        
        # Workaround 1: Update styles.height
        self.ta.styles.height = None
        self.ta.styles.height = "auto"
        
        # Workaround 2: Update document height manually? 
        # Textual caches `virtual_size` or uses something internally.
        self.ta.refresh(layout=True)
        
        await asyncio.sleep(0.5)
        container = self.query_one("#input_container")
        print("TextArea height with workaround 1:", self.ta.size.height)
        print("Container height with workaround 1:", container.size.height)
        self.exit()

if __name__ == "__main__":
    app = TestApp()
    app.run(headless=True)
