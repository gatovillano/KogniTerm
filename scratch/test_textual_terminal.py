from textual.app import App, ComposeResult
from textual_terminal import Terminal

class TerminalApp(App):
    def compose(self) -> ComposeResult:
        yield Terminal()

if __name__ == "__main__":
    app = TerminalApp()
    # we don't run it right now because it's interactive, just want to check if it imports and works
    print("Imported successfully")
