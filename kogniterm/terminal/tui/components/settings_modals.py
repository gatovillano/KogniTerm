from textual.screen import ModalScreen
from textual.widgets import Label, ListView, ListItem, Static, Input
from textual.containers import Vertical, Horizontal
from textual.app import ComposeResult
from textual import events
from kogniterm.terminal.themes import ColorPalette


def _palette_css():
    """Genera CSS dinámico con los colores del tema activo."""
    p = ColorPalette
    return """
    .palette-bg        { background: %s; }
    .palette-border    { border: solid %s; }
    .palette-title     { color: %s; }
    .palette-hint      { color: %s; }
    .palette-text      { color: %s; }
    .palette-input     { background: %s; color: %s; border: none; border-bottom: solid %s; }
    .palette-item      { color: %s; background: %s; }
    .palette-item:hover { background: %s; color: %s; }
    ListItem.--highlight { background: %s; color: %s; }
    """ % (p.GRAY_800, p.GRAY_700, p.TEXT_PRIMARY, p.TEXT_MUTED, p.TEXT_SECONDARY, 
           p.GRAY_800, p.TEXT_PRIMARY, p.GRAY_600, p.TEXT_SECONDARY, p.GRAY_800, 
           p.GRAY_700, p.TEXT_PRIMARY, p.PRIMARY, p.GRAY_900)


# ─────────────────────────────────────────────────────────────────────────────
# MODAL BASE  –  command palette style
# ─────────────────────────────────────────────────────────────────────────────

class BaseModal(ModalScreen):
    """Modal base con estética command-palette minimalista."""

    CSS = """
    BaseModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #palette-shell {
        width: 80;
        height: auto;
        max-height: 40;
        padding: 0;
    }
    #palette-header {
        width: 100%;
        height: 3;
        padding: 0 4;
        background: transparent;
        content-align: center middle;
    }
    #palette-title-label {
        width: 1fr;
        text-style: bold;
        content-align: left middle;
    }
    #palette-hint-label {
        width: auto;
        content-align: right middle;
        opacity: 0.6;
    }
    #palette-body {
        width: 100%;
        height: auto;
        padding: 1 4;
    }
    """

    def _build_css(self) -> str:
        """Construye CSS dinámico con colores del tema actual."""
        p = ColorPalette
        return """
        BaseModal {
            align: center middle;
        }
        #palette-shell {
            background: %s;
            border: none;
            padding: 1 0;
        }
        #palette-header {
            background: %s;
            border-bottom: none;
        }
        #palette-title-label { color: %s; }
        #palette-body {
            background: %s;
        }
        """ % (p.GRAY_800, p.GRAY_800, p.TEXT_PRIMARY, p.GRAY_800)

    def on_mount(self):
        # Inyectar CSS dinámico de colores una vez montado
        self.app.stylesheet.add_source(self._build_css())
        self.focus()


# ─────────────────────────────────────────────────────────────────────────────
# MODAL DE LISTA  (selección de modelos, proveedores, temas, etc.)
# ─────────────────────────────────────────────────────────────────────────────

class TextualRadioListModal(BaseModal):
    """Command palette para selección de una opción de lista."""

    DEFAULT_CSS = BaseModal.CSS + """
    #palette-search {
        width: 100%;
        height: 3;
        padding: 0 4;
        border: none;
    }
    #palette-list {
        width: 100%;
        height: auto;
        max-height: 24;
        border: none;
        padding: 1 2;
        margin: 0;
    }
    ListItem {
        padding: 0 2;
        height: 1;
        margin: 0 2;
    }
    """

    def _build_css(self) -> str:
        p = ColorPalette
        return super()._build_css() + """
        #palette-search {
            background: %s;
            color: %s;
            border: none;
        }
        #palette-search:focus {
            border: none;
        }
        #palette-list {
            background: %s;
        }
        ListItem {
            background: %s;
            color: %s;
            padding: 0 2;
        }
        ListItem:hover {
            background: %s;
            color: %s;
        }
        ListItem.--highlight {
            background: %s;
            color: %s;
        }
        """ % (p.GRAY_800, p.TEXT_PRIMARY, p.GRAY_800, p.GRAY_800, p.TEXT_SECONDARY, 
               p.GRAY_700, p.TEXT_PRIMARY, p.GRAY_700, p.TEXT_PRIMARY)

    def __init__(self, title, text, values, default=None):
        super().__init__()
        self.dialog_title = title
        self.dialog_text = text          # used as subtitle / hint
        self.values = values             # list of (value, label) tuples
        self.default = default
        self._item_map = {}              # mapping to store value per item id

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-shell"):
            with Horizontal(id="palette-header"):
                yield Label(self.dialog_title, id="palette-title-label")
            self._search = Input(id="palette-search")
            yield self._search
            
            items = []
            for i, (val, label) in enumerate(self.values):
                if hasattr(label, "value"):
                    label = label.value
                label_str = str(label)
                item_id = f"item_{i}"
                li = ListItem(Static(label_str, markup=True), id=item_id)
                li._label_text = label_str # Texto sin procesar para filtrado
                self._item_map[item_id] = val
                items.append(li)
            
            self.list_view = ListView(*items, id="palette-list")
            yield self.list_view

    def on_mount(self):
        super().on_mount()
        self._search.focus()

    def on_key(self, event: events.Key):
        if event.key == "escape":
            self.dismiss(None)
            event.prevent_default()
        elif event.key in ("down", "up"):
            self.list_view.focus()
        elif event.key == "enter":
            if self.list_view.highlighted_child:
                item_id = self.list_view.highlighted_child.id
                self.dismiss(self._item_map.get(item_id))
            event.prevent_default()

    async def on_input_changed(self, event: Input.Changed):
        """Filtra la lista en tiempo real según el texto de búsqueda."""
        query = event.value.lower().strip()
        
        # Ocultar o mostrar items en lugar de recrear la lista
        # (Esto es más robusto en Textual para evitar problemas de ID)
        for child in self.list_view.query(ListItem):
            if not query or query in child._label_text.lower():
                child.display = True
            else:
                child.display = False
        
        # Auto-seleccionar el primero visible
        visible_items = [c for c in self.list_view.query(ListItem) if c.display]
        if visible_items:
            self.list_view.index = self.list_view.children.index(visible_items[0])

    def on_list_view_selected(self, event: ListView.Selected):
        item_id = event.item.id
        self.dismiss(self._item_map.get(item_id))


# ─────────────────────────────────────────────────────────────────────────────
# MODAL DE INPUT  (API keys, nombres, etc.)
# ─────────────────────────────────────────────────────────────────────────────

class TextualInputModal(BaseModal):
    """Command palette para entrada de texto libre."""

    DEFAULT_CSS = BaseModal.CSS + """
    #palette-input-field {
        width: 100%;
        margin: 0;
        border: none;
        padding: 0 4;
        height: auto;
    }
    #palette-input-field:focus {
        border: none;
    }
    #palette-subtitle {
        padding: 0 4;
        margin-bottom: 1;
    }
    """

    def __init__(self, title, text, password=False):
        super().__init__()
        self.dialog_title = title
        self.dialog_text = text
        self.password = password

    def _build_css(self) -> str:
        p = ColorPalette
        return super()._build_css() + """
        #palette-input-field {
            background: %s;
            color: %s;
            border: none;
        }
        #palette-subtitle {
            color: %s;
        }
        """ % (p.GRAY_800, p.TEXT_PRIMARY, p.TEXT_MUTED)

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-shell"):
            with Horizontal(id="palette-header"):
                yield Label(self.dialog_title, id="palette-title-label")
            if self.dialog_text:
                yield Label(self.dialog_text, id="palette-subtitle")
            self.input_field = Input(
                password=self.password,
                id="palette-input-field"
            )
            yield self.input_field

    def on_mount(self):
        super().on_mount()
        self.input_field.focus()

    def on_key(self, event: events.Key):
        if event.key == "escape":
            self.dismiss(None)
            event.prevent_default()

    def on_input_submitted(self, event: Input.Submitted):
        self.dismiss(self.input_field.value)


# ─────────────────────────────────────────────────────────────────────────────
# MODAL DE MENSAJE  (confirmaciones, avisos)
# ─────────────────────────────────────────────────────────────────────────────

class TextualMessageModal(BaseModal):
    """Command palette para mostrar un mensaje y confirmar."""

    DEFAULT_CSS = BaseModal.CSS + """
    #palette-msg-body {
        padding: 1 4 2 4;
    }
    #palette-msg-text {
        margin-bottom: 1;
    }
    #palette-msg-footer {
        content-align: right middle;
        padding: 0 4;
        height: 3;
        border-top: solid transparent;
    }
    """

    def __init__(self, title, text):
        super().__init__()
        self.dialog_title = title
        self.dialog_text = text

    def _build_css(self) -> str:
        p = ColorPalette
        return super()._build_css() + """
        #palette-msg-text  { color: %s; }
        #palette-msg-footer { color: %s; border-top: solid %s; }
        """ % (p.TEXT_SECONDARY, p.TEXT_MUTED, p.GRAY_600)

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-shell"):
            with Horizontal(id="palette-header"):
                yield Label(self.dialog_title, id="palette-title-label")
            with Vertical(id="palette-msg-body"):
                yield Label(self.dialog_text, id="palette-msg-text")

    def on_key(self, event: events.Key):
        if event.key in ("escape", "enter"):
            self.dismiss(None)
            event.prevent_default()
