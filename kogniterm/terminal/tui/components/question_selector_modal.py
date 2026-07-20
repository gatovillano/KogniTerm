"""
QuestionSelectorModal - Modal de selección gráfica de opciones para ask_question.
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
    Modal interactivo para la herramienta ask_question en KogniTerm TUI.

    Permite al usuario seleccionar una opción mediante:
    - Teclas numéricas (1-9) para selección instantánea
    - Navegación por lista (flechas Arriba/Abajo + Enter)
    - Clic de ratón en una opción
    - Entrada de texto libre (si allow_freeform es True)
    """

    CSS = """
    QuestionSelectorModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.80);
    }

    #modal-shell {
        width: 85%;
        max-width: 95;
        height: auto;
        max-height: 85%;
        background: #111827;
        border: solid #7C3AED;
        padding: 0;
    }

    #modal-header {
        width: 100%;
        height: auto;
        min-height: 3;
        background: #1f2937;
        padding: 1 2;
        border-bottom: solid #374151;
    }

    #modal-title {
        width: 100%;
        text-style: bold;
        color: #a78bfa;
    }

    #modal-question {
        width: 100%;
        color: #f3f4f6;
        margin-top: 1;
    }

    #options-list {
        width: 100%;
        height: auto;
        max-height: 16;
        background: #111827;
        border: none;
        padding: 1 1;
    }

    ListItem {
        padding: 0 2;
        height: 2;
        margin: 0 1;
        background: #1f2937;
        color: #e5e7eb;
        border: solid #374151;
        content-align: left middle;
    }

    ListItem:hover {
        background: #374151;
        color: #ffffff;
    }

    ListItem.--highlight {
        background: #7c3aed;
        color: #ffffff;
        border: solid #a78bfa;
    }

    #freeform-container {
        width: 100%;
        height: auto;
        padding: 1 2;
        background: #1f2937;
        border-top: solid #374151;
    }

    #freeform-label {
        color: #9ca3af;
        margin-bottom: 1;
    }

    #freeform-input {
        width: 100%;
        background: #111827;
        color: #f9fafb;
        border: solid #4b5563;
    }

    #modal-footer {
        width: 100%;
        height: 2;
        background: #1f2937;
        padding: 0 2;
        border-top: solid #374151;
        align: left middle;
        layout: horizontal;
    }

    #footer-hint {
        width: 1fr;
        color: #9ca3af;
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
                label_text = f"{i}. {opt}"
                li = ListItem(Static(label_text), id=item_id)
                self._item_map[item_id] = opt
                items.append(li)

            self.list_view = ListView(*items, id="options-list")
            yield self.list_view

            if self.allow_freeform:
                with Vertical(id="freeform-container"):
                    yield Label("O escribe una respuesta personalizada:", id="freeform-label")
                    self.freeform_input = Input(
                        placeholder="Escribe tu respuesta y presiona Enter...",
                        id="freeform-input",
                    )
                    yield self.freeform_input

            with Horizontal(id="modal-footer"):
                hint = "1-9  selección directa   ↑↓  navegar   enter  confirmar   esc  cancelar"
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
