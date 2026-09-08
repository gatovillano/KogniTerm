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
