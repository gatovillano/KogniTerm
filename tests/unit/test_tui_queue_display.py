from rich.text import Text

from kogniterm.terminal.tui.tui_app import QueueDisplay


def test_queue_display_does_not_treat_user_input_as_markup():
    widget = QueueDisplay()
    captured = []

    def fake_update(renderable):
        captured.append(renderable)

    widget.update = fake_update

    widget.update_queue(
        [
            "Expression expected\n\n./src/app/(dashboard)/rag/page.tsx\n\n"
            "Error:   x Expression expected\n  [/app/src/app/(dashboard)/rag/page.tsx:45:1]"
        ]
    )

    assert len(captured) == 1
    renderable = captured[0]
    assert isinstance(renderable, Text)
    assert "⏳ En cola:" in renderable.plain
    assert "[/app/src/app/(dashboard)/rag/page.tsx:45:1]" in renderable.plain
