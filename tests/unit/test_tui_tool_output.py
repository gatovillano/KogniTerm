import pytest
from unittest.mock import MagicMock
from rich.style import Style
from kogniterm.terminal.tui.components.tool_output import ToolOutputWidget


class MockChar:
    def __init__(
        self,
        fg='default',
        bg='default',
        bold=False,
        italics=False,
        underscore=False,
        reverse=False,
        blink=False
    ):
        self.fg = fg
        self.bg = bg
        self.bold = bold
        self.italics = italics
        self.underscore = underscore
        self.reverse = reverse
        self.blink = blink


def test_tool_output_widget_detect_color():
    """Verifica que _detect_color normaliza los colores de pyte correctamente."""
    widget = ToolOutputWidget("content", "test_tool")

    # Colores por defecto y vacíos
    assert widget._detect_color("default") is None
    assert widget._detect_color("") is None
    assert widget._detect_color(None) is None

    # Mapeo histórico de brown a yellow
    assert widget._detect_color("brown") == "yellow"

    # Brightblack mapea a gris
    assert widget._detect_color("brightblack") == "#808080"

    # Colores hexadecimales sin prefijo '#' se normalizan
    assert widget._detect_color("00838f") == "#00838f"
    assert widget._detect_color("fff") == "#fff"
    assert widget._detect_color("ABCDEF") == "#ABCDEF"

    # Colores válidos estándar se mantienen
    assert widget._detect_color("red") == "red"
    assert widget._detect_color("#123456") == "#123456"


def test_tool_output_widget_get_rich_style_standard():
    """Verifica la generación de Rich Style para condiciones estándar."""
    widget = ToolOutputWidget("content", "test_tool")

    # Caracter por defecto
    char = MockChar()
    style = widget._get_rich_style(char)
    assert isinstance(style, Style)
    assert style.color is None
    assert style.bgcolor is None
    assert style.bold is False

    # Caracter con colores y estilos básicos
    char_styled = MockChar(fg="red", bg="blue", bold=True, italics=True)
    style_styled = widget._get_rich_style(char_styled)
    assert style_styled.color.name == "red"
    assert style_styled.bgcolor.name == "blue"
    assert style_styled.bold is True
    assert style_styled.italic is True


def test_tool_output_widget_get_rich_style_hex_no_hash():
    """Verifica que códigos hex sin hash no hacen fallar la creación de Style."""
    widget = ToolOutputWidget("content", "test_tool")

    # Hex sin hash (el caso que fallaba)
    char = MockChar(fg="00838f", bg="ffffff")
    style = widget._get_rich_style(char)
    assert isinstance(style, Style)
    assert style.color.name == "#00838f"
    assert style.bgcolor.name == "#ffffff"


def test_tool_output_widget_get_rich_style_fallback():
    """Verifica que en caso de error en parseo de color, retorna fallback seguro sin crashear."""
    widget = ToolOutputWidget("content", "test_tool")

    # Pasar un valor de color que sea un tipo totalmente inválido para forzar error
    char = MockChar(fg=12345, bg=True, bold=True, italics=True)
    style = widget._get_rich_style(char)
    assert isinstance(style, Style)
    # Debe mantener las propiedades básicas pero sin colores
    assert style.bold is True
    assert style.italic is True
    assert style.color is None
    assert style.bgcolor is None
