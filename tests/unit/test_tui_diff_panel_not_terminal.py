import pytest
from unittest.mock import MagicMock
from kogniterm.terminal.tui.components.chat_log import ChatLogWidget, MessageWidget
from kogniterm.terminal.tui.components.tool_output import ToolOutputWidget
from kogniterm.terminal.tui.tui_app import KogniTermTUI
from rich.panel import Panel
from rich.text import Text
from rich.console import Group


@pytest.mark.anyio
async def test_diff_panel_not_wrapped_in_terminal_output_widget():
    """
    Verifica que al enviar un Panel de diff (ej. ✅ Diff aplicado: .../tool_executor.py)
    a chat_log.write_stream, este se monte como MessageWidget y NUNCA como ToolOutputWidget.
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        chat_log = app.chat_log

        # Panel simulación del diff aplicado producido por command_approval_handler
        diff_panel = Panel(
            Group(Text("Operación: advanced_file_editor"), Text("--- a/kogniterm/terminal/command_approval_handler.py")),
            title="✅ Diff aplicado: /home/gato/Proyectos/Gemini-Interpreter/kogniterm/terminal/command_approval_handler.py",
            border_style="green",
        )

        chat_log.write_stream(diff_panel)
        await pilot.pause()

        mounted_widgets = list(chat_log.children)
        assert len(mounted_widgets) > 0

        last_widget = mounted_widgets[-1]
        assert isinstance(last_widget, MessageWidget), f"El widget debe ser MessageWidget y no {type(last_widget)}"
        assert not isinstance(last_widget, ToolOutputWidget), "El panel de diff NO debe ser un ToolOutputWidget"
