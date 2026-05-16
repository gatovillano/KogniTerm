import asyncio
from textual.app import App, ComposeResult
from textual.widgets import TextArea
from textual.containers import Horizontal

class FixedTextArea(TextArea):
    def update_height(self):
        # Forzar altura mínima de 3 y máxima de 15
        lc = self.document.line_count
        target_height = max(3, min(15, lc))
        self.styles.height = target_height
        if self.parent:
             self.parent.styles.height = target_height + 2

class TestApp(App):
    CSS = """
    #input_container {
        height: auto;
        min-height: 5;
        background: #2a2a2a;
    }
    """
    def compose(self) -> ComposeResult:
        with Horizontal(id="input_container"):
            self.ta = FixedTextArea("line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8")
            yield self.ta

    async def on_mount(self):
        await asyncio.sleep(0.2)
        # Estado inicial (debería ser 8 + padding)
        print("Antes de clear - Size:", self.ta.size)
        
        # Simular envío de mensaje
        self.ta.clear()
        self.ta.update_height()
        
        await asyncio.sleep(0.2)
        print("Después de clear - Size:", self.ta.size)
        container = self.query_one("#input_container")
        print("Después de clear - Container Size:", container.size)
        self.exit()

if __name__ == "__main__":
    app = TestApp()
    app.run(headless=True)
