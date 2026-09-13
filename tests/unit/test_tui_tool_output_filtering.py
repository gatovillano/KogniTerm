import pytest
import json
from unittest.mock import MagicMock, patch
from rich.panel import Panel
from rich.text import Text

from kogniterm.terminal.tui.tui_app import KogniTermTUI, TextualTerminalUI
from kogniterm.terminal.tui.components.chat_log import ChatLogWidget, MessageWidget
from kogniterm.terminal.tui.components.tool_output import ToolOutputWidget
from kogniterm.core.agents.super_agent import is_terminal_tool, create_super_agent
from kogniterm.core.agent_state import AgentState
from langchain_core.messages import HumanMessage
from kogniterm.core.agents.tool_executor import ToolExecutor


@pytest.mark.anyio
async def test_non_terminal_tool_output_not_displayed_in_tui():
    """
    Verifica que la salida de herramientas que NO sean de terminal
    (ej: read_file, web_search, list_dir) no se muestren en la TUI.
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        chat_log = app.chat_log
        tui_ui = app.tui_ui

        # 1. Notificación de ejecución (indicador): SÍ debe mostrarse
        tui_ui.print_tool_notification("read_file", action_desc="Leyendo archivo secret.txt")
        await pilot.pause()

        notif_widgets = [w for w in chat_log.children if isinstance(w, MessageWidget)]
        assert len(notif_widgets) == 1, "El indicador de ejecución debe mostrarse"

        # 2. Intento de mostrar salida de herramienta no terminal
        tui_ui.update_tool_display("read_file", "contenido secreto del archivo")
        await pilot.pause()

        # No debe haberse montado ningún ToolOutputWidget
        tool_widgets = [w for w in chat_log.children if isinstance(w, ToolOutputWidget)]
        assert len(tool_widgets) == 0, "Las herramientas no-terminales NO deben mostrar su salida"

        # Directamente a chat_log.write_tool_output tampoco debe montarse
        chat_log.write_tool_output("resultado web", "web_search")
        await pilot.pause()
        tool_widgets = [w for w in chat_log.children if isinstance(w, ToolOutputWidget)]
        assert len(tool_widgets) == 0, "web_search no debe mostrar salida en TUI"


@pytest.mark.anyio
async def test_terminal_tool_output_is_displayed_in_tui():
    """
    Verifica que las herramientas de comandos de terminal
    (ej: execute_command, bash, python_executor) SÍ muestren su salida en la TUI.
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        chat_log = app.chat_log
        tui_ui = app.tui_ui

        # Indicador de ejecución
        tui_ui.print_tool_notification("execute_command", action_desc="ls -la")
        await pilot.pause()

        # Salida de comando de terminal
        tui_ui.update_tool_display("execute_command", "total 42\n-rw-r--r-- file.txt", command="ls -la")
        await pilot.pause()

        tool_widgets = [w for w in chat_log.children if isinstance(w, ToolOutputWidget)]
        assert len(tool_widgets) == 1, "Los comandos de terminal SÍ deben mostrar su salida"
        assert tool_widgets[0].command == "ls -la"


@pytest.mark.anyio
async def test_file_edit_shows_only_diff_not_raw_output():
    """
    Verifica que la edición de archivos muestre únicamente el diff aplicado
    y NO la salida cruda de la herramienta.
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        chat_log = app.chat_log
        tui_ui = app.tui_ui

        diff_content = "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old_line\n+new_line\n"

        # Mostrar diff aplicado
        tui_ui.show_applied_diff(
            tool_name="advanced_file_editor",
            file_path="test.py",
            diff_content=diff_content,
        )
        await pilot.pause()

        # El diff debe estar como MessageWidget y contener el diff aplicado
        message_widgets = [w for w in chat_log.children if isinstance(w, MessageWidget)]
        assert len(message_widgets) == 1
        rendered_visual = message_widgets[0].render()
        padding = rendered_visual._renderable
        align = padding.renderable
        panel = align.renderable
        assert isinstance(panel, Panel)
        assert "Diff aplicado: test.py" in str(panel.title)

        # Si se intentara actualizar tool display con la salida cruda, debe descartarse
        raw_output = json.dumps({"success": True, "message": "File test.py updated successfully"})
        tui_ui.update_tool_display("advanced_file_editor", raw_output)
        await pilot.pause()

        # No debe haber ToolOutputWidget
        tool_widgets = [w for w in chat_log.children if isinstance(w, ToolOutputWidget)]
        assert len(tool_widgets) == 0, "No debe mostrarse salida cruda para edición de archivos"


def test_tool_executor_does_not_call_update_tool_display_for_non_terminal():
    """
    Verifica que ToolExecutor no llame a update_tool_display para herramientas no-terminales,
    y solo llame al renderizador de diff para edición de archivos.
    """
    terminal_ui = MagicMock()
    tool_mock = MagicMock()
    tool_mock.name = "read_file"
    tool_mock.args_schema = None

    llm_service = MagicMock()
    llm_service.get_tool.return_value = tool_mock
    llm_service._invoke_tool_with_interrupt.return_value = "secret content"

    ToolExecutor.execute_single_tool(
        tc={"name": "read_file", "args": {"path": "secret.txt"}, "id": "call_123"},
        llm_service=llm_service,
        terminal_ui=terminal_ui,
    )

    # update_tool_display NO debe haber sido llamado
    assert terminal_ui.update_tool_display.call_count == 0
    assert terminal_ui.update_terminal_output.call_count == 0


def test_tool_executor_renders_diff_for_file_edit_without_raw_display():
    """
    Verifica que ToolExecutor para edición de archivo llame a _render_file_edit_diff
    pero NO a update_tool_display.
    """
    terminal_ui = MagicMock()
    tool_mock = MagicMock()
    tool_mock.name = "advanced_file_editor"
    tool_mock.args_schema = None

    diff_str = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-a\n+b\n"
    llm_service = MagicMock()
    llm_service.get_tool.return_value = tool_mock
    llm_service._invoke_tool_with_interrupt.return_value = {
        "success": True,
        "path": "foo.py",
        "applied_diff": diff_str,
    }

    ToolExecutor.execute_single_tool(
        tc={"name": "advanced_file_editor", "args": {"path": "foo.py", "action": "replace"}, "id": "call_456"},
        llm_service=llm_service,
        terminal_ui=terminal_ui,
    )

    # Debe haber llamado a show_applied_diff
    terminal_ui.show_applied_diff.assert_called_once_with(
        tool_name="advanced_file_editor",
        file_path="foo.py",
        diff_content=diff_str,
    )
    # Y NO debe haber llamado a update_tool_display ni update_terminal_output
    assert terminal_ui.update_tool_display.call_count == 0
    assert terminal_ui.update_terminal_output.call_count == 0
