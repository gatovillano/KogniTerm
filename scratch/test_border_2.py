from textual.app import App, ComposeResult
from textual.widgets import Static
from textual.containers import VerticalScroll

class TestApp(App):
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            msg = Static("Este es un mensaje de prueba.\nDebería tener una línea a la izquierda y el fondo desde esa línea hacia la derecha.", classes="msg")
            msg.styles.border_left = ("solid", "cyan")
            msg.styles.background = "#2a2a2a"
            msg.styles.margin = (0, 0, 0, 2)
            msg.styles.padding = (0, 1)
            msg.styles.width = "100%"
            yield msg

if __name__ == "__main__":
    app = TestApp()
    app.run()
