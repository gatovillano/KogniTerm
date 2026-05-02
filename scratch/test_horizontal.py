from textual.app import App, ComposeResult
from textual.widgets import Static
from textual.containers import Horizontal, VerticalScroll

class TestApp(App):
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            with Horizontal(styles="height: auto;"):
                left = Static("┃\n┃\n┃\n┃", styles="width: 2; color: cyan; background: transparent;")
                right = Static("Este es un mensaje de prueba.\nDebería tener una línea a la izquierda y el fondo desde esa línea hacia la derecha.", styles="background: #2a2a2a; padding: 1 2; height: auto;")
                yield left
                yield right

if __name__ == "__main__":
    app = TestApp()
    app.run()
