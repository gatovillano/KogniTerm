import json
from rich.console import Console

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from kogniterm.core.agent_state import AgentState
from kogniterm.core.agents.base_agent import BaseAgentNode
from kogniterm.core.history_manager import HistoryManager
from kogniterm.core.llm_service import LLMService
from kogniterm.terminal.command_approval_handler import CommandApprovalHandler, _load_file_ops_module
advanced_file_editor = _load_file_ops_module("file_editor").advanced_file_editor


@pytest.fixture
def compact_history_manager(tmp_path):
    return HistoryManager(
        history_file_path=str(tmp_path / "history.json"),
        max_history_messages=6,
        max_history_chars=400,
    )


def test_processed_history_can_be_built_without_overwriting_full_history(
    compact_history_manager,
):
    for i in range(8):
        compact_history_manager.add_message(
            HumanMessage(content=f"Mensaje usuario {i} " + ("x" * 40))
        )
        compact_history_manager.add_message(
            AIMessage(content=f"Respuesta asistente {i} " + ("y" * 40))
        )

    original_history = compact_history_manager.get_history()

    processed_history = compact_history_manager.get_processed_history_for_llm(
        llm_service_summarize_method=lambda messages: f"Resumen de {len(messages)} mensajes",
        max_history_messages=compact_history_manager.max_history_messages,
        max_history_chars=compact_history_manager.max_history_chars,
        console=None,
        save_history=False,
        history=list(original_history),
    )

    assert len(processed_history) < len(original_history)
    assert compact_history_manager.get_history() == original_history





def test_base_agent_persists_full_history_after_response():
    state = AgentState(messages=[HumanMessage(content="hola")])

    class DummyLLMService:
        def __init__(self):
            self.saved_history = None

        def _save_history(self, messages):
            self.saved_history = list(messages)

    llm_service = DummyLLMService()
    stream_state = {
        "final_ai_message": AIMessage(content="respuesta"),
        "full_response": "",
    }

    result = BaseAgentNode._build_node_output(state, stream_state, llm_service)

    assert [msg.content for msg in result["messages"]] == ["hola", "respuesta"]
    assert [msg.content for msg in llm_service.saved_history] == ["hola", "respuesta"]


def test_explicit_command_denial_does_not_execute_safe_command():
    executed_commands = []

    class DummyTerminalUI:
        def __init__(self):
            self.messages = []
            self.console = Console()

        def get_interrupt_queue(self):
            return None

        def print_confirmation_panel(self, *args, **kwargs):
            pass

        def ask_approval_sync(self, *args, **kwargs):
            return False

        def print_message(self, message, style=None):
            self.messages.append((message, style))

        def update_terminal_output(self, *args, **kwargs):
            raise AssertionError("No debería mostrar salida de ejecución")

        def set_terminal_cursor(self, *args, **kwargs):
            pass

        def stop_live(self, **kwargs):
            pass

        def update_live(self, renderable, **kwargs):
            pass

    class DummyCommandExecutor:
        def execute(self, command, **kwargs):
            executed_commands.append(command)
            yield "unexpected"

    class DummyLLMService:
        def __init__(self):
            self.saved_history = None

        def _save_history(self, messages):
            self.saved_history = list(messages)

    handler = CommandApprovalHandler(
        llm_service=DummyLLMService(),
        command_executor=DummyCommandExecutor(),
        prompt_session=None,
        terminal_ui=DummyTerminalUI(),
        agent_state=AgentState(messages=[AIMessage(content="voy a ejecutar rm -rf /")]),
    )

    result = handler.handle_command_approval(
        command_to_execute="rm -rf /",
        auto_approve=False,
    )

    assert result["approved"] is False
    assert executed_commands == []
    assert isinstance(handler.agent_state.messages[-1], AIMessage)
    assert "no ejecutado" in handler.agent_state.messages[-1].content.lower()


def test_advanced_editor_confirmation_reuses_original_args_and_replaces_pending_tool_message(tmp_path):
    file_path = tmp_path / "demo.py"
    file_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    original_args = {
        "path": str(file_path),
        "action": "replace_block",
        "target_content": "beta",
        "replacement_content": "BETA",
    }
    pending_payload = {
        "status": "requires_confirmation",
        "operation": "advanced_file_editor",
        "path": str(file_path),
        "args": original_args,
        "diff": "--- fake diff ---",
    }

    class DummyTerminalUI:
        def __init__(self):
            self.messages = []
            self.live_updates = []

        def get_interrupt_queue(self):
            return None

        def print_confirmation_panel(self, *args, **kwargs):
            raise AssertionError("No debería pedir una segunda confirmación")

        def ask_approval_sync(self, *args, **kwargs):
            raise AssertionError("No debería volver a preguntar")

        def print_message(self, message, style=None):
            self.messages.append((message, style))

        def update_live(self, renderable, **kwargs):
            self.live_updates.append(renderable)

        def stop_live(self, **kwargs):
            pass

        def update_terminal_output(self, *args, **kwargs):
            pass

        def set_terminal_cursor(self, *args, **kwargs):
            pass

    class DummyLLMService:
        def __init__(self):
            self.saved_history = None

        def _save_history(self, messages):
            self.saved_history = list(messages)

        def _invoke_tool_with_interrupt(self, tool, tool_args):
            yield tool(**tool_args)

    agent_state = AgentState(
        messages=[
            AIMessage(
                content="",
                tool_calls=[{"name": "advanced_file_editor", "args": original_args, "id": "tool-1"}],
            ),
            ToolMessage(
                content=json.dumps(pending_payload),
                tool_call_id="tool-1",
            ),
        ]
    )

    handler = CommandApprovalHandler(
        llm_service=DummyLLMService(),
        command_executor=None,
        prompt_session=None,
        terminal_ui=DummyTerminalUI(),
        agent_state=agent_state,
        advanced_file_editor_tool=advanced_file_editor,
    )

    result = handler.handle_command_approval(
        command_to_execute="",
        auto_approve=True,
        tool_name="advanced_file_editor",
        raw_tool_output=pending_payload,
        original_tool_args=original_args,
    )

    tool_messages = [
        message for message in handler.agent_state.messages
        if getattr(message, "tool_call_id", None) == "tool-1"
    ]
    assert len(tool_messages) == 1
    assert "requires_confirmation" not in tool_messages[0].content
    assert json.loads(tool_messages[0].content)["status"] == "success"
    assert result["approved"] is True
    assert "BETA" in file_path.read_text(encoding="utf-8")
