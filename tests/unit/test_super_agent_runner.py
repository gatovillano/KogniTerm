import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from kogniterm.core.agent_state import AgentState
from kogniterm.core.ai_cli_bridge.super_agent_runner import SuperAgentRunner, create_super_agent

def test_super_agent_runner_invoke_converts_messages_and_returns_dict():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    runner = create_super_agent(llm_service=llm_service)

    state = AgentState(messages=[HumanMessage(content="Hola")])

    async def fake_stream(task=None, messages=None, system_prompt=None, max_steps=25):
        yield {"type": "content", "text": "¡Hola! ¿Cómo estás?"}
        yield {
            "type": "done",
            "output": "¡Hola! ¿Cómo estás?",
            "tools_used": [],
            "success": True,
            "error": None,
        }

    with patch.object(runner.agent, "execute_stream", side_effect=fake_stream):
        result = runner.invoke(state)
        assert "messages" in result
        assert len(result["messages"]) == 2
        assert isinstance(result["messages"][-1], AIMessage)
        assert result["messages"][-1].content == "¡Hola! ¿Cómo estás?"

def test_super_agent_runner_pause_for_command_confirmation():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    runner = create_super_agent(llm_service=llm_service)

    state = AgentState(messages=[HumanMessage(content="ejecuta ls")])

    async def fake_stream(task=None, messages=None, system_prompt=None, max_steps=25):
        yield {
            "type": "tool_start",
            "name": "execute_command",
            "args": {"command": "ls -la"}
        }

    with patch.object(runner.agent, "execute_stream", side_effect=fake_stream):
        result = runner.invoke(state)
        assert result.get("command_to_confirm") == "ls -la"
        assert state.command_to_confirm == "ls -la"


def test_super_agent_runner_streams_to_terminal_ui():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    terminal_ui = MagicMock()
    runner = create_super_agent(llm_service=llm_service, terminal_ui=terminal_ui)

    state = AgentState(messages=[HumanMessage(content="Hola")])

    async def fake_stream(task=None, messages=None, system_prompt=None, max_steps=25):
        yield {"type": "reasoning", "text": "pensando..."}
        yield {"type": "chunk", "text": "Hola "}
        yield {"type": "chunk", "text": "mundo"}
        yield {"type": "done", "output": "Hola mundo", "tools_used": [], "success": True, "error": None}

    with patch.object(runner.agent, "execute_stream", side_effect=fake_stream):
        runner.invoke(state)

    terminal_ui.update_live.assert_called()
    terminal_ui.stop_live.assert_called()
    assert terminal_ui.print_stream.call_count >= 2
    calls = [c.args[0] for c in terminal_ui.print_stream.call_args_list]
    assert "Hola " in calls
    assert "mundo" in calls


def test_super_agent_runner_handles_interruption():
    import queue
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    llm_service.stop_generation_flag = False
    terminal_ui = MagicMock()
    interrupt_queue = queue.Queue()
    runner = create_super_agent(
        llm_service=llm_service,
        terminal_ui=terminal_ui,
        interrupt_queue=interrupt_queue
    )

    state = AgentState(messages=[HumanMessage(content="tarea larga")])

    # Simulamos que durante la ejecución el usuario presiona interrupción
    interrupt_queue.put_nowait(True)

    async def fake_stream(task=None, messages=None, system_prompt=None, max_steps=25, **kwargs):
        yield {"type": "chunk", "text": "Iniciando..."}
        yield {"type": "chunk", "text": "procesando..."}

    with patch.object(runner.agent, "execute_stream", side_effect=fake_stream):
        result = runner.invoke(state)

    assert state.stop_requested is True
    assert interrupt_queue.empty() is True
    terminal_ui.stop_live.assert_called()


def test_super_agent_runner_only_updates_display_for_terminal_tools():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    terminal_ui = MagicMock()
    runner = create_super_agent(llm_service=llm_service, terminal_ui=terminal_ui)

    state = AgentState(messages=[HumanMessage(content="lee y ejecuta")])

    async def fake_stream(**kwargs):
        # Herramienta que NO es de terminal (solo debe mostrar notificación inicial)
        yield {"type": "tool_start", "name": "read_file", "args": {"path": "test.txt"}, "id": "call_1"}
        yield {"type": "tool_result", "name": "read_file", "result": "contenido secreto", "id": "call_1"}
        # Herramienta de terminal (SÍ debe actualizar el display)
        yield {"type": "tool_start", "name": "python_executor", "args": {"code": "print('hi')"}, "id": "call_2"}
        yield {"type": "tool_result", "name": "python_executor", "result": "hi\n", "id": "call_2"}
        yield {"type": "done", "output": "Listo", "tools_used": ["read_file", "python_executor"], "success": True}

    with patch.object(runner.agent, "execute_stream", side_effect=fake_stream):
        runner.invoke(state)

    # Verificar que update_tool_display solo fue llamado para python_executor y NO para read_file
    displayed_tools = [call.args[0] for call in terminal_ui.update_tool_display.call_args_list]
    assert "read_file" not in displayed_tools
    assert "python_executor" in displayed_tools


def test_super_agent_runner_preserves_tool_messages_in_state():
    from langchain_core.messages import ToolMessage
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    runner = create_super_agent(llm_service=llm_service)

    state = AgentState(messages=[HumanMessage(content="lee archivo")])

    async def fake_stream(**kwargs):
        yield {
            "type": "tool_calls_start",
            "content": "Voy a leer el archivo.",
            "tool_calls": [{
                "id": "call_abc",
                "type": "function",
                "function": {"name": "read_file", "arguments": '{"path": "foo.py"}'}
            }]
        }
        yield {"type": "tool_start", "name": "read_file", "args": {"path": "foo.py"}, "id": "call_abc"}
        yield {"type": "tool_result", "name": "read_file", "result": "print('hello')", "id": "call_abc"}
        yield {"type": "done", "output": "El archivo imprime hello", "tools_used": ["read_file"], "success": True}

    with patch.object(runner.agent, "execute_stream", side_effect=fake_stream):
        runner.invoke(state)

    # El historial debe tener: HumanMessage -> AIMessage (tool_call) -> ToolMessage (resultado) -> AIMessage (final)
    assert len(state.messages) == 4
    assert isinstance(state.messages[0], HumanMessage)
    assert isinstance(state.messages[1], AIMessage)
    assert state.messages[1].tool_calls[0]["id"] == "call_abc"
    assert isinstance(state.messages[2], ToolMessage)
    assert state.messages[2].tool_call_id == "call_abc"
    assert state.messages[2].content == "print('hello')"
    assert isinstance(state.messages[3], AIMessage)
    assert state.messages[3].content == "El archivo imprime hello"


def test_langchain_to_dict_messages_handles_orphan_tool_message():
    from langchain_core.messages import ToolMessage
    from kogniterm.core.agents.super_agent import _langchain_to_dict_messages

    messages = [
        HumanMessage(content="comando ejecutado"),
        ToolMessage(content="salida del comando", tool_call_id="call_orphan", name="execute_command"),
    ]

    dict_msgs = _langchain_to_dict_messages(messages)
    # Debe haber insertado un mensaje asistente sintético para evitar error de API
    assert len(dict_msgs) == 3
    assert dict_msgs[0]["role"] == "user"
    assert dict_msgs[1]["role"] == "assistant"
    assert any(tc["id"] == "call_orphan" for tc in dict_msgs[1]["tool_calls"])
    assert dict_msgs[2]["role"] == "tool"
    assert dict_msgs[2]["tool_call_id"] == "call_orphan"


def test_super_agent_runner_formats_tool_notification_cleanly():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    terminal_ui = MagicMock()
    runner = create_super_agent(llm_service=llm_service, terminal_ui=terminal_ui)

    state = AgentState(messages=[HumanMessage(content="haz cosas")])

    async def fake_stream(**kwargs):
        # 1. Herramienta de lectura de archivo con argumentos complejos
        yield {
            "type": "tool_start",
            "name": "read_file",
            "args": {"path": "kogniterm/main.py", "offset": 10, "limit": 50},
            "id": "c1",
        }
        # 2. Herramienta de listado de directorio
        yield {
            "type": "tool_start",
            "name": "list_dir",
            "args": {"DirectoryPath": "/home/user/workspace"},
            "id": "c2",
        }
        # 3. Herramienta de comando
        yield {
            "type": "tool_start",
            "name": "run_command",
            "args": {"CommandLine": "git status -s", "Cwd": "/home/user"},
            "id": "c3",
        }
        yield {"type": "done", "output": "ok"}

    with patch.object(runner.agent, "execute_stream", side_effect=fake_stream):
        runner.invoke(state)

    notify_calls = terminal_ui.print_tool_notification.call_args_list
    assert len(notify_calls) >= 3

    # Para read_file: solo la ruta del archivo, no el dict completo
    assert notify_calls[0].args == ("read_file", "kogniterm/main.py")
    # Para list_dir: solo la ruta del directorio
    assert notify_calls[1].args == ("list_dir", "/home/user/workspace")
    # Para run_command: solo el comando
    assert notify_calls[2].args == ("run_command", "git status -s")



