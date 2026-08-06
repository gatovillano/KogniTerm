import pytest
import json
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage, ToolMessage
from kogniterm.core.agent_state import AgentState
from kogniterm.core.exceptions import UserConfirmationRequired
from kogniterm.core.agents.tool_executor import ToolExecutor, should_continue

def test_parallel_file_editor_confirmations_queue(tmp_path):
    file1 = tmp_path / "file1.py"
    file2 = tmp_path / "file2.py"
    file1.write_text("a = 1\n", encoding="utf-8")
    file2.write_text("b = 2\n", encoding="utf-8")

    tool_call_1 = {
        "id": "call_1",
        "name": "advanced_file_editor",
        "args": {"path": str(file1), "action": "full_replacement", "content": "a = 10\n"}
    }
    tool_call_2 = {
        "id": "call_2",
        "name": "advanced_file_editor",
        "args": {"path": str(file2), "action": "full_replacement", "content": "b = 20\n"}
    }

    state = AgentState(
        messages=[AIMessage(content="editando", tool_calls=[tool_call_1, tool_call_2])],
        autonomous_approvals=False
    )

    mock_llm_service = MagicMock()
    mock_tool = MagicMock()

    def mock_invoke_tool_with_interrupt(tool, tool_args, delegation_context=None):
        if not tool_args.get("confirm", False):
            path = tool_args.get("path")
            raise UserConfirmationRequired(
                message=f"editar {path}",
                tool_name="advanced_file_editor",
                tool_args=tool_args,
                raw_tool_output={
                    "status": "requires_confirmation",
                    "path": path,
                    "action_description": f"editar {path}",
                    "operation": "advanced_file_editor",
                    "args": tool_args
                }
            )
        yield json.dumps({"status": "success", "path": tool_args.get("path")})

    mock_llm_service.get_tool.return_value = mock_tool
    mock_llm_service._invoke_tool_with_interrupt = mock_invoke_tool_with_interrupt

    def mock_submit(fn, *args, **kwargs):
        future = MagicMock()
        try:
            res = fn(*args, **kwargs)
            future.result.return_value = res
        except Exception as e:
            future.result.return_value = (args[0]["id"], str(e), e)
        return future

    mock_llm_service.tool_executor = MagicMock()
    mock_llm_service.tool_executor.submit = mock_submit

    # 1. Ejecutar execute_tool_node con llamadas paralelas
    new_state = ToolExecutor.execute_tool_node(
        state=state,
        llm_service=mock_llm_service,
        terminal_ui=None
    )

    # 2. Verificar que se encolaron AMBAS confirmaciones
    assert len(new_state.pending_confirmations) == 2
    assert new_state.has_pending_confirmations() is True
    assert should_continue(new_state) == "END"  # Debe pausar para confirmación

    # 3. Primera confirmación activa
    active_1 = new_state.tool_args_pending_confirmation
    assert active_1["path"] == str(file1) or active_1["path"] == str(file2)
    first_path = active_1["path"]

    # 4. Desencolar la primera confirmación
    next_confirm = new_state.pop_pending_confirmation()
    assert next_confirm is not None
    assert new_state.has_pending_confirmations() is True
    second_path = new_state.tool_args_pending_confirmation["path"]
    assert second_path != first_path

    # 5. Desencolar la segunda confirmación
    final_confirm = new_state.pop_pending_confirmation()
    assert final_confirm is None
    assert new_state.has_pending_confirmations() is False
