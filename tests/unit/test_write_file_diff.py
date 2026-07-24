import os
import pytest
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage
from kogniterm.terminal.command_approval_handler import CommandApprovalHandler
from kogniterm.core.agent_state import AgentState

class DummyLLMService:
    def __init__(self):
        self.saved_history = None

    def _save_history(self, messages):
        self.saved_history = list(messages)

class DummyCommandExecutor:
    workspace_directory = "/tmp"

class DummyTerminalUI:
    def __init__(self):
        self.printed_messages = []
        self.updated_lives = []
        self.stopped_lives = 0

    def ask_approval_sync(self, message: str, title: str = "", diff_content: str = "", file_path: str = "") -> bool:
        self.printed_messages.append({"message": message, "diff": diff_content, "file_path": file_path})
        return True

    def update_live(self, renderable):
        self.updated_lives.append(renderable)

    def stop_live(self):
        self.stopped_lives += 1

    def print_message(self, *args, **kwargs):
        pass

    def get_interrupt_queue(self):
        return None

def test_ensure_unified_diff_for_new_file(tmp_path):
    handler = CommandApprovalHandler(
        llm_service=DummyLLMService(),
        command_executor=DummyCommandExecutor(),
        prompt_session=None,
        terminal_ui=DummyTerminalUI(),
        agent_state=AgentState(messages=[])
    )

    new_file = tmp_path / "new_script.py"
    raw_content = "def hello():\n    print('Hello World')\n"

    diff = handler._ensure_unified_diff(str(new_file), raw_content)

    assert "--- /dev/null" in diff
    assert f"+++ b/{new_file}" in diff
    assert "@@" in diff
    assert "+def hello():" in diff
    assert "+    print('Hello World')" in diff

def test_ensure_unified_diff_for_existing_file(tmp_path):
    handler = CommandApprovalHandler(
        llm_service=DummyLLMService(),
        command_executor=DummyCommandExecutor(),
        prompt_session=None,
        terminal_ui=DummyTerminalUI(),
        agent_state=AgentState(messages=[])
    )

    existing_file = tmp_path / "existing.py"
    existing_file.write_text("old_line = 1\n", encoding="utf-8")

    new_content = "old_line = 1\nnew_line = 2\n"

    diff = handler._ensure_unified_diff(str(existing_file), new_content)

    assert f"a/{existing_file}" in diff
    assert f"b/{existing_file}" in diff
    assert "-old_line = 1" not in diff  # Context line
    assert "+new_line = 2" in diff

def test_handle_command_approval_write_file_renders_diff(tmp_path):
    file_path = tmp_path / "output.txt"
    file_path.write_text("line 1\n", encoding="utf-8")

    ui = DummyTerminalUI()
    handler = CommandApprovalHandler(
        llm_service=DummyLLMService(),
        command_executor=DummyCommandExecutor(),
        prompt_session=None,
        terminal_ui=ui,
        agent_state=AgentState(messages=[AIMessage(content="Escribiendo archivo")])
    )

    # Prevenir llamada real que modifique el archivo antes de aprobar
    raw_output = {
        "status": "requires_confirmation",
        "operation": "write_file",
        "path": str(file_path),
        "args": {
            "path": str(file_path),
            "content": "line 1\nline 2\n"
        }
    }

    result = handler.handle_command_approval(
        command_to_execute="",
        raw_tool_output=raw_output,
        tool_name="write_file",
        original_tool_args={"path": str(file_path), "content": "line 1\nline 2\n"}
    )

    # Verificar que el diff enviado a la UI de aprobación fue unificado
    assert len(ui.printed_messages) == 1
    assert "+++ b/" in ui.printed_messages[0]["diff"]
    assert "+line 2" in ui.printed_messages[0]["diff"]

    # Verificar que tras ejecutar se llamó a update_live (renderizado del historial)
    assert len(ui.updated_lives) > 0
    # Verificar que el archivo fue escrito exitosamente
    assert file_path.read_text(encoding="utf-8") == "line 1\nline 2\n"
