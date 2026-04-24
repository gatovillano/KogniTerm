import pytest
from langchain_core.messages import AIMessage, HumanMessage

from kogniterm.core.agent_state import AgentState
from kogniterm.core.agents.base_agent import BaseAgentNode
from kogniterm.core.history_manager import HistoryManager
from kogniterm.core.llm_service import LLMService
from kogniterm.terminal.command_approval_handler import CommandApprovalHandler


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


def test_summary_snapshot_keeps_recent_removed_context():
    service = LLMService.__new__(LLMService)
    service.SUMMARY_INPUT_CHAR_BUDGET = 240
    service.SUMMARY_MESSAGE_CHAR_LIMIT = 40
    service.SUMMARY_RECENT_MESSAGES_PRIORITY = 3

    history = [HumanMessage(content=f"mensaje-{i}-" + ("z" * 30)) for i in range(10)]
    snapshot = service._build_summary_snapshot(history)
    snapshot_text = "\n".join(snapshot)

    assert "mensaje-0-" in snapshot_text
    assert "mensaje-9-" in snapshot_text
    assert "omitidos" in snapshot_text


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

        def get_interrupt_queue(self):
            return None

        def print_confirmation_panel(self, *args, **kwargs):
            raise AssertionError("No debería volver a pedir confirmación")

        def ask_approval_sync(self, *args, **kwargs):
            raise AssertionError("No debería volver a preguntar")

        def print_message(self, message, style=None):
            self.messages.append((message, style))

        def update_terminal_output(self, *args, **kwargs):
            raise AssertionError("No debería mostrar salida de ejecución")

        def set_terminal_cursor(self, *args, **kwargs):
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
        agent_state=AgentState(messages=[AIMessage(content="voy a ejecutar ls")]),
    )

    result = handler.handle_command_approval(
        command_to_execute="ls",
        auto_approve=False,
        explicit_user_approval=False,
    )

    assert result["approved"] is False
    assert executed_commands == []
    assert isinstance(handler.agent_state.messages[-1], AIMessage)
    assert "no ejecutado" in handler.agent_state.messages[-1].content.lower()
