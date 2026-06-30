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
            "Short error with [/app/path:45:1]"
        ]
    )

    assert len(captured) == 1
    renderable = captured[0]
    assert isinstance(renderable, Text)
    assert "⏳ En cola:" in renderable.plain
    assert "[/app/path:45:1]" in renderable.plain


def test_queue_display_truncates_long_messages():
    widget = QueueDisplay()
    captured = []

    def fake_update(renderable):
        captured.append(renderable)

    widget.update = fake_update

    long_message = "This is a very long message that definitely exceeds sixty characters to test the truncation logic."
    widget.update_queue([long_message])

    assert len(captured) == 1
    renderable = captured[0]
    assert isinstance(renderable, Text)
    assert len(renderable.plain) < len("⏳ En cola: ") + len(long_message)
    assert renderable.plain.endswith("...")
    # Maximum length is 60. So "⏳ En cola: " (11 chars) + 60 chars of message + "..." (3 chars) = 74 chars.
    assert len(renderable.plain) == 74
