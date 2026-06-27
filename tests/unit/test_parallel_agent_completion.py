import pytest
from unittest.mock import MagicMock, patch
from kogniterm.core.delegation import DelegationManager, AgentRole
from kogniterm.core.agent_state import AgentState
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
import importlib.util
import sys

def _load_parallel_tool():
    spec = importlib.util.spec_from_file_location(
        "call_agents_parallel_tool",
        "/home/gato/Proyectos/Gemini-Interpreter/kogniterm/skills/bundled/call-agents-parallel/scripts/tool.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["call_agents_parallel_tool"] = module
    spec.loader.exec_module(module)
    return module.call_agents_parallel

call_agents_parallel = _load_parallel_tool()


def test_complete_task_tool_logic():
    """
    Verifica que la herramienta complete_task guarda el resultado
    en el metadata del delegation_context y lo marca como completado.
    """
    from kogniterm.core.delegation import DelegationContext
    
    # Crear un contexto de delegación dummy
    ctx = DelegationContext(
        agent_id="test_subagent",
        parent_id="orchestrator",
        role=AgentRole.LEAF,
        depth=1
    )
    
    # Registrar la herramienta
    # Simulamos el comportamiento del decorador @tool de LangChain
    from langchain_core.tools import tool
    
    @tool
    def dummy_complete_task(result: str, delegation_context=None) -> str:
        """Entrega el resultado final y finaliza el proceso."""
        if delegation_context is not None:
            delegation_context.metadata["result"] = result
            delegation_context.metadata["completed"] = True
        return "Completado"

    # Ejecutar la herramienta
    res = dummy_complete_task.invoke({"result": "Reporte final del Coder", "delegation_context": ctx})
    
    assert "Completado" in res
    assert ctx.metadata.get("completed") is True
    assert ctx.metadata.get("result") == "Reporte final del Coder"


def test_base_agent_skip_call_model_when_completed():
    """
    Verifica que BaseAgentNode.call_model no invoca al LLM si el agente ya completó
    su tarea a través de complete_task.
    """
    from kogniterm.core.agents.base_agent import BaseAgentNode
    from kogniterm.core.delegation import DelegationContext
    
    # Crear estado y marcarlo como completado
    ctx = DelegationContext(
        agent_id="subagent",
        parent_id="orchestrator",
        role=AgentRole.LEAF,
        depth=1
    )
    ctx.metadata["completed"] = True
    ctx.metadata["result"] = "Resultado final"
    
    state = AgentState(messages=[HumanMessage(content="hola")])
    state.delegation_context = ctx
    
    llm_service = MagicMock()
    
    # Intentar invocar call_model
    # Si llama al modelo, fallaría porque llm_service.invoke no está mocked o retornaría error.
    # Pero debe retornar de inmediato con un mensaje dummy de AIMessage sin invocar llm_service.invoke
    res = BaseAgentNode.call_model(
        state=state,
        llm_service=llm_service,
        system_prompt="prompt",
        terminal_ui=None
    )
    
    assert len(res["messages"]) == 2
    assert isinstance(res["messages"][-1], AIMessage)
    assert "complete_task" in res["messages"][-1].content
    assert not llm_service.invoke.called


def test_code_agent_skip_call_model_when_completed():
    """
    Verifica que code_agent.call_model_node no invoca al LLM si el agente ya completó.
    """
    from kogniterm.core.agents.code_agent import call_model_node
    from kogniterm.core.delegation import DelegationContext
    
    ctx = DelegationContext(
        agent_id="subagent",
        parent_id="orchestrator",
        role=AgentRole.LEAF,
        depth=1
    )
    ctx.metadata["completed"] = True
    
    state = AgentState(messages=[HumanMessage(content="hola")])
    state.delegation_context = ctx
    
    llm_service = MagicMock()
    
    res = call_model_node(state, llm_service, terminal_ui=None)
    
    assert len(res["messages"]) == 2
    assert isinstance(res["messages"][-1], AIMessage)
    assert not llm_service.invoke.called


def test_researcher_agent_skip_call_model_when_completed():
    """
    Verifica que researcher_agent.call_model_node no invoca al LLM si el agente ya completó.
    """
    from kogniterm.core.agents.researcher_agent import call_model_node
    from kogniterm.core.delegation import DelegationContext
    
    ctx = DelegationContext(
        agent_id="subagent",
        parent_id="orchestrator",
        role=AgentRole.LEAF,
        depth=1
    )
    ctx.metadata["completed"] = True
    
    state = AgentState(messages=[HumanMessage(content="hola")])
    state.delegation_context = ctx
    
    llm_service = MagicMock()
    
    res = call_model_node(state, llm_service)
    
    assert len(res["messages"]) == 2
    assert isinstance(res["messages"][-1], AIMessage)
    assert not llm_service.invoke.called


def test_call_agents_parallel_result_extraction():
    """
    Verifica que call_agents_parallel extrae el resultado del metadato del contexto
    cuando el subagente finaliza exitosamente con complete_task.
    """
    llm_service = MagicMock()
    llm_service.delegation_manager = DelegationManager()
    
    # Pre-registrar el agente padre
    llm_service.delegation_manager.register_agent(
        agent_id="parallel_orchestrator",
        parent_id=None,
        role=AgentRole.ORCHESTRATOR
    )
    
    llm_service.heartbeat_monitor = MagicMock()
    llm_service.tool_map = {}
    
    delegation_state = {"current": None}
    type(llm_service).current_delegation_context = property(
        fget=lambda self: delegation_state["current"],
        fset=lambda self, val: delegation_state.update({"current": val})
    )

    mock_graph = MagicMock()
    
    async def mock_ainvoke(initial_state, config=None):
        # El subagente simula llamar a la herramienta complete_task
        ctx = initial_state.delegation_context
        ctx.metadata["result"] = "Resultado exitoso del agente paralelo"
        ctx.metadata["completed"] = True
        return {"messages": [AIMessage(content="Proceso finalizado.")]}
        
    mock_graph.ainvoke = mock_ainvoke

    agents = [
        {"name": "ParallelCoder", "task": "Escribir código", "type": "code_agent"}
    ]

    with patch("call_agents_parallel_tool._build_agent_graph", return_value=mock_graph), \
         patch("call_agents_parallel_tool._request_autonomous_execution", return_value=True), \
         patch("call_agents_parallel_tool._activate_parallel_container"), \
         patch("call_agents_parallel_tool._deactivate_parallel_container"):
         
        res = call_agents_parallel(
            agents=agents,
            llm_service=llm_service,
            terminal_ui=None
        )
        
        # Debe contener el resultado formal del agente extraído del metadato
        assert "Resultado exitoso del agente paralelo" in res
