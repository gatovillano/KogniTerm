import pytest
from textual.widgets import TextArea, Input
from kogniterm.terminal.tui.components.status_footer import ChatInput
from kogniterm.terminal.tui.tui_app import TUIApp


def test_chat_input_value_setter_places_cursor_at_end():
    """ChatInput.value setter should place cursor at the end of text, not (0, 0)."""
    input_widget = ChatInput()
    input_widget.value = "hello world"
    assert input_widget.cursor_location == (0, 11)


def test_chat_input_value_setter_clears_to_zero_when_empty():
    """ChatInput.value = '' should place cursor at (0, 0)."""
    input_widget = ChatInput()
    input_widget.value = "hello"
    assert input_widget.cursor_location == (0, 5)
    input_widget.value = ""
    assert input_widget.cursor_location == (0, 0)


def test_chat_input_cursor_position_property():
    """ChatInput should support cursor_position integer property compatible with Input."""
    input_widget = ChatInput()
    input_widget.value = "line 1\nline 2"
    # End of text
    assert input_widget.cursor_position == len("line 1\nline 2")

    # Set cursor_position to line 1
    input_widget.cursor_position = 3
    assert input_widget.cursor_location == (0, 3)
    assert input_widget.cursor_position == 3

    # Set cursor_position to line 2
    input_widget.cursor_position = 8
    assert input_widget.cursor_location == (1, 1)
    assert input_widget.cursor_position == 8


def test_apply_completion_root_command():
    """Applying % or / completion must position cursor after the command and space."""
    app = TUIApp()
    input_widget = ChatInput()
    input_widget.value = "%he"

    app._apply_completion("%help", input_widget, "%he")

    assert input_widget.value == "%help "
    assert input_widget.cursor_position == len("%help ")
    assert input_widget.cursor_location == (0, len("%help "))


def test_apply_completion_file_at_end():
    """Applying @file completion at the end of text must place cursor at the end."""
    app = TUIApp()
    input_widget = ChatInput()
    input_widget.value = "check @doc"

    app._apply_completion("doc/readme.md", input_widget, "check @doc")

    assert input_widget.value == "check @doc/readme.md "
    assert input_widget.cursor_position == len("check @doc/readme.md ")
    assert input_widget.cursor_location == (0, len("check @doc/readme.md "))


def test_apply_completion_multiline():
    """Applying completion in multiline text must preserve newlines and position cursor correctly."""
    app = TUIApp()
    input_widget = ChatInput()
    input_widget.value = "first line\nsecond line @file"

    app._apply_completion("file.txt", input_widget, "first line\nsecond line @file")

    assert input_widget.value == "first line\nsecond line @file.txt "
    assert "\n" in input_widget.value
    expected_len = len("first line\nsecond line @file.txt ")
    assert input_widget.cursor_position == expected_len
    # second line, after '@file.txt '
    assert input_widget.cursor_location == (1, len("second line @file.txt "))


def test_apply_completion_middle_of_text():
    """Applying completion in the middle of text must preserve trailing text and keep cursor in place."""
    app = TUIApp()
    input_widget = ChatInput()
    input_widget.value = "revisa @doc y ejecuta"
    # Position cursor right after @doc (index 11)
    input_widget.cursor_position = 11

    app._apply_completion("doc/readme.md", input_widget, "revisa @doc y ejecuta")

    assert input_widget.value == "revisa @doc/readme.md y ejecuta"
    # Cursor should be placed right after '@doc/readme.md '
    expected_pos = len("revisa @doc/readme.md ")
    assert input_widget.cursor_position == expected_pos
    assert input_widget.cursor_location == (0, expected_pos)
