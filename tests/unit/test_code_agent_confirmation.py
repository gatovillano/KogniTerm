import pytest
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage, ToolMessage
from kogniterm.core.agent_state import AgentState
from kogniterm.core.exceptions import UserConfirmationRequired
from kogniterm.core.agents.code_agent import execute_tool_node

def test_code_agent_requires_confirmation_in_interactive_mode(tmp_path):
    target_file = tmp_path / "sample.py"
    target_file.write_text("print('hello')\n", encoding="utf-8")

    tool_call = {
        "id": "call_123",
        "name": "advanced_file_editor",
        "args": {
            "path": str(target_file),
            "action": "full_replacement",
            "content": "print('world')\n"
        }
    }

    state = AgentState(
        messages=[AIMessage(content="", tool_calls=[tool_call])],
        autonomous_approvals=False
    )

    mock_llm_service = MagicMock()
    mock_tool = MagicMock()

    raw_output = {
        "status": "requires_confirmation",
        "operation": "advanced_file_editor",
        "action_description": "editar archivo",
        "diff": "--- a/sample.py\n+++ b/sample.py\n@@ -1 +1 @@\n-print('hello')\n+print('world')\n",
        "path": str(target_file),
        "args": tool_call["args"]
    }

    def mock_invoke_tool_with_interrupt(tool, tool_args, terminal_ui=None):
        if not tool_args.get("confirm", False):
            raise UserConfirmationRequired(
                message="editar archivo",
                tool_name="advanced_file_editor",
                tool_args=tool_args,
                raw_tool_output=raw_output
            )
        yield json.dumps({"status": "success"})

    mock_llm_service.get_tool.return_value = mock_tool
    mock_llm_service._invoke_tool_with_interrupt = mock_invoke_tool_with_interrupt

    def mock_submit(fn, *args, **kwargs):
        future = MagicMock()
        try:
            res = fn(*args, **kwargs)
            future.result.return_value = res
        except Exception as e:
            future.result.return_value = (tool_call["id"], str(e), e)
        return future

    mock_llm_service.tool_executor.submit = mock_submit
    mock_llm_service.save_history = MagicMock()

    # Simular la llamada a execute_tool_node
    new_state = execute_tool_node(
        state=state,
        llm_service=mock_llm_service,
        terminal_ui=None
    )

    # Verificar que en modo interactivo NO se auto-confirmó y se pausó para confirmación del usuario
    assert new_state.tool_pending_confirmation == "advanced_file_editor"
    assert new_state.file_update_diff_pending_confirmation is not None
    assert new_state.file_update_diff_pending_confirmation["status"] == "requires_confirmation"
