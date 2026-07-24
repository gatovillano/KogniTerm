"""
QuestionSelectorModal - Modal de selección gráfica de opciones para ask_question.
Diseño minimalista estilo Command Palette.
"""

from typing import Optional, List
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, ListView, ListItem, Static, Input
from textual import events
from rich.text import Text

from kogniterm.terminal.themes import ColorPalette


class QuestionSelectorModal(ModalScreen[str]):
    """
    Modal interactivo minimalista para la herramienta ask_question en KogniTerm TUI.

    Permite al usuario seleccionar una opción mediante:
    - Teclas numéricas (1-9) para selección instantánea
    - Navegación por lista (flechas Arriba/Abajo + Enter)
    - Clic de ratón en una opción
    - Entrada de texto libre (si allow_freeform es True)
    """

    CSS = """
    QuestionSelectorModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }

    #modal-shell {
        width: 80%;
        max-width: 86;
        height: auto;
        max-height: 85%;
        background: #141416;
        border: solid #27272a;
        padding: 0;
    }

    #modal-header {
        width: 100%;
        height: auto;
        background: transparent;
        padding: 1 3 0 3;
    }

    #modal-title {
        width: 100%;
        text-style: bold;
        color: #8b5cf6;
    }

    #modal-question {
        width: 100%;
        color: #f4f4f5;
        margin-top: 1;
    }

    #options-list {
        width: 100%;
        height: auto;
        max-height: 16;
        background: transparent;
        border: none;
        padding: 1 2;
    }

    ListItem {
        padding: 0 2;
        height: auto;
        min-height: 2;
        margin: 0 0 1 0;
        background: transparent;
        border: none;
        content-align: left middle;
    }

    ListItem Label, ListItem Static {
        color: #d4d4d8;
        width: 100%;
    }

    ListItem:hover {
        background: #27272a;
    }

    ListItem:hover Label, ListItem:hover Static {
        color: #ffffff;
    }

    ListItem.--highlight {
        background: #27272a;
        border-left: solid #8b5cf6;
    }

    ListItem.--highlight Label, ListItem.--highlight Static {
        color: #ffffff;
        text-style: bold;
    }

    #freeform-container {
        width: 100%;
        height: auto;
        padding: 1 3;
        background: transparent;
        border-top: solid #27272a;
    }

    #freeform-label {
        color: #71717a;
        margin-bottom: 1;
    }

    #freeform-input {
        width: 100%;
        background: #09090b;
        color: #f4f4f5;
        border: solid #27272a;
    }

    #freeform-input:focus {
        border: solid #8b5cf6;
    }

    #modal-footer {
        width: 100%;
        height: 2;
        background: transparent;
        padding: 0 3 1 3;
        align: left middle;
        layout: horizontal;
    }

    #footer-hint {
        width: 1fr;
        color: #52525b;
        content-align: left middle;
    }
    """

    def __init__(
        self,
        question: str,
        options: List[str],
        title: str = "Consulta del Agente",
        allow_freeform: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.question = question
        self.options = options
        self.title_text = title
        self.allow_freeform = allow_freeform
        self._item_map = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-shell"):
            with Vertical(id="modal-header"):
                yield Label(f"❓ {self.title_text}", id="modal-title")
                yield Label(self.question, id="modal-question")

            items = []
            for i, opt in enumerate(self.options, start=1):
                item_id = f"opt_{i}"
                label = Label(f"[bold #8b5cf6]{i}.[/bold #8b5cf6] {opt}", markup=True)
                li = ListItem(label, id=item_id)
                self._item_map[item_id] = opt
                items.append(li)

            self.list_view = ListView(*items, id="options-list")
            yield self.list_view

            if self.allow_freeform:
                with Vertical(id="freeform-container"):
                    yield Label("O escribe una respuesta personalizada:", id="freeform-label")
                    self.freeform_input = Input(
                        placeholder="Respuesta personalizada...",
                        id="freeform-input",
                    )
                    yield self.freeform_input

            with Horizontal(id="modal-footer"):
                hint = "1-9  selección   ↑↓  navegar   enter  confirmar   esc  cancelar"
                yield Label(hint, id="footer-hint")

    def on_mount(self) -> None:
        if hasattr(self, "list_view") and self.list_view.children:
            self.list_view.focus()

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss("Cancelado por el usuario.")
            event.prevent_default()
            return

        # Selección directa por número (solo si el foco NO está en el Input libre)
        if (
            event.character
            and event.character.isdigit()
            and self.focused != getattr(self, "freeform_input", None)
        ):
            idx = int(event.character)
            if 1 <= idx <= len(self.options):
                self.dismiss(self.options[idx - 1])
                event.prevent_default()
                return

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id
        if item_id in self._item_map:
            self.dismiss(self._item_map[item_id])

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        if val:
            self.dismiss(val)
        event.stop()
        event.prevent_default()
