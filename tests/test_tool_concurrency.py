import time
import pytest
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from kogniterm.core.agent_state import AgentState
from kogniterm.core.agents.tool_executor import ToolExecutor
from kogniterm.core.agents.code_agent import execute_tool_node as code_agent_execute_tool_node

class DummyTool:
    def __init__(self, name: str, delay: float = 0.05, return_val: str = "ok"):
        self.name = name
        self.__name__ = name
        self.delay = delay
        self.return_val = return_val

    def __call__(self, **kwargs):
        if self.delay > 0:
            time.sleep(self.delay)
        return f"{self.return_val}: {kwargs}"

    def invoke(self, kwargs):
        if self.delay > 0:
            time.sleep(self.delay)
        return f"{self.return_val}: {kwargs}"


def test_tool_executor_parallel_speedup():
    """Verifica que múltiples herramientas de solo lectura se ejecuten concurrentemente."""
    tool_a = DummyTool(name="view_file", delay=0.06, return_val="file_a")
    tool_b = DummyTool(name="grep_search", delay=0.06, return_val="file_b")
    tool_c = DummyTool(name="list_dir", delay=0.06, return_val="file_c")

    tool_map = {
        "view_file": tool_a,
        "grep_search": tool_b,
        "list_dir": tool_c,
    }

    mock_llm = MagicMock()
    mock_llm.get_tool.side_effect = lambda name: tool_map.get(name)
    mock_llm._invoke_tool_with_interrupt.side_effect = lambda tool, args, *a, **kwargs: [tool.invoke(args)]

    tool_calls = [
        {"name": "view_file", "args": {"path": "a.py"}, "id": "call_1"},
        {"name": "grep_search", "args": {"query": "test"}, "id": "call_2"},
        {"name": "list_dir", "args": {"dir": "."}, "id": "call_3"},
    ]

    state = AgentState(
        messages=[
            HumanMessage(content="Analiza estos archivos"),
            AIMessage(content="", tool_calls=tool_calls),
        ]
    )

    start_time = time.time()
    result_state = ToolExecutor.execute_tool_node(state=state, llm_service=mock_llm)
    elapsed = time.time() - start_time

    # Si fuera secuencial tardaría >= 0.18s. Concurrente debe tardar < 0.15s
    assert elapsed < 0.15, f"La ejecución paralela fue demasiado lenta ({elapsed:.3f}s)"

    # Verificar que los mensajes resultantes conservan el orden exacto
    tool_messages = [m for m in result_state.messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 3
    assert tool_messages[0].tool_call_id == "call_1"
    assert "file_a" in tool_messages[0].content
    assert tool_messages[1].tool_call_id == "call_2"
    assert "file_b" in tool_messages[1].content
    assert tool_messages[2].tool_call_id == "call_3"
    assert "file_c" in tool_messages[2].content


def test_tool_executor_interactive_command_pause():
    """Verifica que un execute_command interactivo pause para confirmación tras procesar herramientas previas."""
    tool_a = DummyTool(name="view_file", delay=0.01, return_val="file_a")
    tool_map = {"view_file": tool_a}

    mock_llm = MagicMock()
    mock_llm.get_tool.side_effect = lambda name: tool_map.get(name)
    mock_llm._invoke_tool_with_interrupt.side_effect = lambda tool, args, *a, **kwargs: [tool.invoke(args)]

    tool_calls = [
        {"name": "view_file", "args": {"path": "a.py"}, "id": "call_1"},
        {"name": "execute_command", "args": {"command": "echo hello"}, "id": "call_2"},
    ]

    state = AgentState(
        messages=[
            HumanMessage(content="Ejecuta"),
            AIMessage(content="", tool_calls=tool_calls),
        ]
    )

    result = ToolExecutor.execute_tool_node(state=state, llm_service=mock_llm)

    assert isinstance(result, dict)
    assert result["command_to_confirm"] == "echo hello"
    # El view_file previo debe haberse completado
    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].tool_call_id == "call_1"


def test_code_agent_parallel_execution():
    """Verifica que code_agent.execute_tool_node ejecute herramientas de lectura en paralelo."""
    tool_a = DummyTool(name="read_file", delay=0.05, return_val="code_a")
    tool_b = DummyTool(name="grep_search", delay=0.05, return_val="code_b")

    tool_map = {
        "read_file": tool_a,
        "grep_search": tool_b,
    }

    mock_llm = MagicMock()
    mock_llm.get_tool.side_effect = lambda name: tool_map.get(name)
    mock_llm._invoke_tool_with_interrupt.side_effect = lambda tool, args, *a, **kwargs: [tool.invoke(args)]

    tool_calls = [
        {"name": "read_file", "args": {"file_path": "foo.py"}, "id": "tc_1"},
        {"name": "grep_search", "args": {"pattern": "bar"}, "id": "tc_2"},
    ]

    state = AgentState(
        messages=[
            HumanMessage(content="Inspecciona"),
            AIMessage(content="", tool_calls=tool_calls),
        ]
    )

    start = time.time()
    res_state = code_agent_execute_tool_node(state=state, llm_service=mock_llm)
    elapsed = time.time() - start

    assert elapsed < 0.09, f"CodeAgent ejecutó herramientas demasiado lento ({elapsed:.3f}s)"
    tool_msgs = [m for m in res_state.messages if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 2
    assert tool_msgs[0].tool_call_id == "tc_1"
    assert tool_msgs[1].tool_call_id == "tc_2"
