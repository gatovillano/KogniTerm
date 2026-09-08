import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from kogniterm.core.agent_state import AgentState
from kogniterm.core.agents.deep_coder import create_deep_coder, DeepCoderRunner
from kogniterm.core.agents.deep_researcher import create_deep_researcher, DeepResearcherRunner
from kogniterm.core.agents.dynamic_agent import create_dynamic_agent, DynamicAgentRunner
from kogniterm.core.agents.code_agent import create_code_agent
from kogniterm.core.agents.researcher_agent import create_researcher_agent
from kogniterm.core.agents.bash_agent import create_bash_agent, BashAgentRunner
from kogniterm.core.agents.super_agent import SuperAgentRunner, is_terminal_tool
from kogniterm.core.utils.tool_utils import format_tool_action_target


def test_deep_coder_runner_creation():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    runner = create_deep_coder(llm_service)
    assert isinstance(runner, DeepCoderRunner)
    assert isinstance(runner, SuperAgentRunner)
    assert "KogniDeepCoder" in runner.custom_system_prompt
    assert hasattr(runner, "invoke")
    assert hasattr(runner, "ainvoke")


def test_deep_researcher_runner_creation():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    runner = create_deep_researcher(llm_service)
    assert isinstance(runner, DeepResearcherRunner)
    assert isinstance(runner, SuperAgentRunner)
    assert "KogniDeepResearcher" in runner.custom_system_prompt
    assert hasattr(runner, "invoke")
    assert hasattr(runner, "ainvoke")


def test_dynamic_agent_runner_creation():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    custom_prompt = "Eres un agente especializado en auditoría de seguridad."
    runner = create_dynamic_agent(llm_service, custom_prompt)
    assert isinstance(runner, DynamicAgentRunner)
    assert isinstance(runner, SuperAgentRunner)
    assert runner.custom_system_prompt == custom_prompt
    assert hasattr(runner, "invoke")
    assert hasattr(runner, "ainvoke")


def test_code_agent_delegates_to_deep_coder():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    terminal_ui = MagicMock()
    runner = create_code_agent(llm_service, terminal_ui)
    assert isinstance(runner, DeepCoderRunner)


def test_researcher_agent_delegates_to_deep_researcher():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    terminal_ui = MagicMock()
    runner = create_researcher_agent(llm_service, terminal_ui)
    assert isinstance(runner, DeepResearcherRunner)


def test_bash_agent_runner_is_super_agent_subclass():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    terminal_ui = MagicMock()
    runner = create_bash_agent(llm_service, terminal_ui)
    assert isinstance(runner, BashAgentRunner)
    assert isinstance(runner, SuperAgentRunner)


def test_deep_coder_invoke_and_autonomous_execution():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    llm_service.workspace_context_initialized = True
    llm_service._build_llm_context_message = MagicMock(return_value=None)
    terminal_ui = MagicMock()
    runner = create_deep_coder(llm_service, terminal_ui=terminal_ui)

    state = AgentState(
        messages=[HumanMessage(content="Escribe test.py")],
        autonomous_approvals=True
    )

    async def fake_stream(task=None, messages=None, system_prompt=None, max_steps=25, **kwargs):
        # Asegurar que el system_prompt proviene del DeepCoder
        assert "KogniDeepCoder" in system_prompt
        yield {
            "type": "tool_start",
            "name": "execute_command",
            "args": {"command": "python3 -c 'print(1)'"},
            "id": "call_1",
        }
        yield {
            "type": "tool_result",
            "name": "execute_command",
            "result": "1\n",
            "id": "call_1",
        }
        yield {
            "type": "done",
            "output": "Código implementado y probado con éxito.",
            "tools_used": ["execute_command"],
            "success": True,
            "error": None,
        }

    with patch.object(runner.agent, "execute_stream", side_effect=fake_stream):
        result = runner.invoke(state)

        assert "messages" in result
        last_msg = result["messages"][-1]
        assert isinstance(last_msg, AIMessage)
        assert "Código implementado" in last_msg.content
        # Al ser autónomo, no debe pausar pidiendo confirmación de comando
        assert result.get("command_to_confirm") is None


@pytest.mark.asyncio
async def test_deep_researcher_ainvoke():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    terminal_ui = MagicMock()
    runner = create_deep_researcher(llm_service, terminal_ui=terminal_ui)

    state = AgentState(
        messages=[HumanMessage(content="Investiga arquitectura de FastAPI")],
        autonomous_approvals=True
    )

    async def fake_stream(task=None, messages=None, system_prompt=None, max_steps=25, **kwargs):
        assert "KogniDeepResearcher" in system_prompt
        yield {"type": "reasoning", "text": "Analizando fuentes de FastAPI..."}
        yield {
            "type": "tool_start",
            "name": "web_search",
            "args": {"query": "FastAPI architecture"},
            "id": "call_search",
        }
        yield {
            "type": "tool_result",
            "name": "web_search",
            "result": "FastAPI se basa en Starlette y Pydantic.",
            "id": "call_search",
        }
        yield {
            "type": "done",
            "output": "Informe técnico sobre FastAPI completado.",
            "tools_used": ["web_search"],
            "success": True,
            "error": None,
        }

    with patch.object(runner.agent, "execute_stream", side_effect=fake_stream):
        result = await runner.ainvoke(state)
        assert "messages" in result
        last_msg = result["messages"][-1]
        assert "Informe técnico sobre FastAPI" in last_msg.content


def test_tool_action_formatting_and_terminal_filter():
    # Comandos
    assert format_tool_action_target("execute_command", {"command": "pytest -q"}) == "pytest -q"
    assert is_terminal_tool("execute_command") is True

    # Archivos
    assert format_tool_action_target("read_file", {"path": "kogniterm/core/agents/deep_coder.py"}) == "kogniterm/core/agents/deep_coder.py"
    assert is_terminal_tool("read_file") is False

    # Búsqueda web
    assert format_tool_action_target("web_search", {"query": "python async best practices"}) == "python async best practices"
    assert is_terminal_tool("web_search") is False
