import pytest
from textual.app import App
from textual.widgets import TextArea
from kogniterm.terminal.tui.components.status_footer import ChatInput


class DummyExpandApp(App):
    CSS = """
    ChatInput {
        width: 30;
        height: auto;
    }
    """

    def compose(self):
        yield ChatInput(id="chat_input")


@pytest.mark.asyncio
async def test_chat_input_expands_with_newlines():
    """ChatInput must increase its height when multiple lines are added."""
    app = DummyExpandApp()
    async with app.run_test(size=(60, 25)) as pilot:
        inp = app.query_one(ChatInput)
        # Initial height should be minimum 2
        assert inp.styles.height.value == 2

        # 4 explicit lines -> height should be 4
        inp.value = "line 1\nline 2\nline 3\nline 4"
        await pilot.pause()
        assert inp.styles.height.value == 4

        # 7 explicit lines -> height should be 7
        inp.value = "\n".join(f"line {i}" for i in range(7))
        await pilot.pause()
        assert inp.styles.height.value == 7

        # Clear text -> height should shrink back to 2
        inp.clear()
        await pilot.pause()
        assert inp.styles.height.value == 2


@pytest.mark.asyncio
async def test_chat_input_expands_with_wrapped_text():
    """ChatInput must increase its height when long continuous text soft-wraps across lines."""
    app = DummyExpandApp()
    async with app.run_test(size=(35, 25)) as pilot:
        inp = app.query_one(ChatInput)
        assert inp.styles.height.value == 2

        # Type long continuous text that exceeds 35 columns and wraps across multiple lines
        inp.value = "Este es un texto largo que definitivamente ocupa mas de treinta caracteres y por ende debe envolverse en multiples lineas de visualizacion."
        await pilot.pause()
        visual_lines = inp._get_visual_lines()
        assert visual_lines > 2
        assert inp.styles.height.value == visual_lines

        # Deleting/clearing restores minimum height 2
        inp.value = ""
        await pilot.pause()
        assert inp.styles.height.value == 2
