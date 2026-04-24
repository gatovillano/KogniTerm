from textual.app import App, ComposeResult
from textual.widgets import TextArea, Static
from textual.containers import Vertical

class TestApp(App):
    CSS = """
    Vertical {
        background: #2a2a2a;
        padding: 5;
    }
    TextArea {
        background: transparent !important;
        border: none;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Container background should be #2a2a2a")
            yield TextArea("This is a text area. Is it transparent?")

if __name__ == "__main__":
    app = TestApp()
    app.run()
