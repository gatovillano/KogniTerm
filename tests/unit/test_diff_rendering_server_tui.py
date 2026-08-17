import pytest
from rich.panel import Panel
from rich.console import Group
from rich.text import Text
from rich.padding import Padding
from rich.markdown import Markdown

from kogniterm.server.session_pool import extract_thinking_and_response
from kogniterm.terminal.tui.ws_client import build_native_renderable
from kogniterm.utils.diff_renderer import DiffRenderer


def test_extract_thinking_and_response_preserves_diff_panel_ansi():
    renderer = DiffRenderer()
    sample_diff = (
        "--- a/test.py\n"
        "+++ b/test.py\n"
        "@@ -1,3 +1,4 @@\n"
        " line1\n"
        "-old_line\n"
        "+new_line\n"
        "+another_line\n"
    )
    diff_table = renderer.render_diff_from_string(sample_diff, "test.py")

    subtitle = Text("Operación: advanced_file_editor")
    title_text = "✅ Diff aplicado: test.py"
    diff_panel = Panel(
        Group(subtitle, Text(""), diff_table),
        title=title_text,
        border_style="green",
        expand=True,
    )

    thinking, response = extract_thinking_and_response(diff_panel)

    assert thinking == ""
    assert "Operación: advanced_file_editor" in response
    assert "\x1b[" in response  # Preserva secuencas ANSI de color/formato


def test_build_native_renderable_handles_ansi_response():
    ansi_response = "\x1b[32m✅ Diff aplicado: test.py\x1b[0m\n\x1b[31m-old_line\x1b[0m"

    renderable = build_native_renderable("", ansi_response)

    assert isinstance(renderable, Padding)
    assert isinstance(renderable.renderable, Text)


def test_build_native_renderable_handles_plain_markdown_response():
    markdown_response = "### Mensaje sin ANSI\nEsto es **markdown** normal."

    renderable = build_native_renderable("", markdown_response)

    assert isinstance(renderable, Padding)
    assert isinstance(renderable.renderable, Markdown)
