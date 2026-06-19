import pytest
import time
from kogniterm.core.delegation import (
    AgentRole,
    DelegationLimits,
    DelegationContext,
    DelegationManager,
    HeartbeatMonitor,
)

def test_agent_role_permissions():
    from kogniterm.core.delegation.agent_roles import DEFAULT_BLOCKED_TOOLS
    assert "execute_command" in DEFAULT_BLOCKED_TOOLS[AgentRole.LEAF]
    assert "call_agent" in DEFAULT_BLOCKED_TOOLS[AgentRole.LEAF]
    assert "memory_append" in DEFAULT_BLOCKED_TOOLS[AgentRole.LEAF]
    assert len(DEFAULT_BLOCKED_TOOLS[AgentRole.ORCHESTRATOR]) == 0

def test_delegation_limits_registration():
    limits = DelegationLimits(max_depth=2, max_concurrent_children=2)
    manager = DelegationManager(limits=limits)

    # Registro de agente raíz orchestrator
    root_ctx = manager.register_agent("root", parent_id=None, role=AgentRole.ORCHESTRATOR)
    assert root_ctx.agent_id == "root"
    assert root_ctx.depth == 0
    assert root_ctx.parent_id is None

    # Registro de hijo (nivel 1)
    child1 = manager.register_agent("child1", parent_id="root", role=AgentRole.ORCHESTRATOR)
    assert child1.depth == 1
    assert child1.parent_id == "root"

    # Registro de segundo hijo (nivel 1) - Concurrencia de root = 2
    child2 = manager.register_agent("child2", parent_id="root", role=AgentRole.LEAF)
    assert child2.depth == 1

    # Intento de registrar un tercer hijo para root (Excede max_concurrent_children=2)
    with pytest.raises(ValueError, match="máximo de subagentes concurrentes"):
        manager.register_agent("child3", parent_id="root", role=AgentRole.LEAF)

    # Registro de nieto (nivel 2)
    grandchild = manager.register_agent("grandchild", parent_id="child1", role=AgentRole.LEAF)
    assert grandchild.depth == 2

    # Intento de registrar un bisnieto (Excede max_depth=2)
    with pytest.raises(ValueError, match="Excedido límite de profundidad"):
        manager.register_agent("great_grandchild", parent_id="grandchild", role=AgentRole.LEAF)

def test_delegation_manager_can_delegate():
    limits = DelegationLimits(max_depth=2, max_concurrent_children=2)
    manager = DelegationManager(limits=limits)

    manager.register_agent("root", parent_id=None, role=AgentRole.ORCHESTRATOR)
    assert manager.can_delegate("root") is True

    # Rol LEAF no puede delegar
    manager.register_agent("leaf_child", parent_id="root", role=AgentRole.LEAF)
    assert manager.can_delegate("leaf_child") is False

    # Nivel 2 no puede delegar si max_depth=2
    child1 = manager.register_agent("child1", parent_id="root", role=AgentRole.ORCHESTRATOR)
    grandchild = manager.register_agent("grandchild", parent_id="child1", role=AgentRole.ORCHESTRATOR)
    assert manager.can_delegate("grandchild") is False

def test_heartbeat_monitor():
    monitor = HeartbeatMonitor(check_interval=0.1)
    stalled_agents = []

    def stall_cb(agent_id, elapsed):
        stalled_agents.append(agent_id)

    monitor.register_stall_callback(stall_cb)
    monitor.start()

    try:
        # Añadir agente con umbral muy bajo (0.2s)
        monitor.update_heartbeat("agent_x", threshold=0.2)
        
        # Esperar a que se active el estancamiento
        time.sleep(0.4)
        assert "agent_x" in stalled_agents

        # Limpiar
        stalled_agents.clear()
        
        # Añadir de nuevo y actualizar latido a mitad de camino
        monitor.update_heartbeat("agent_y", threshold=0.3)
        time.sleep(0.1)
        monitor.update_heartbeat("agent_y", threshold=0.3)
        time.sleep(0.1)
        
        # No debería haberse estancado aún porque actualizó su latido
        assert "agent_y" not in stalled_agents
        
        # Esperar hasta 0.5s para que se estanque
        found = False
        for _ in range(10):
            time.sleep(0.05)
            if "agent_y" in stalled_agents:
                found = True
                break
        assert found, f"agent_y no se estancó a tiempo, stalled: {stalled_agents}"

    finally:
        monitor.stop()

def test_tool_executor_rbac_blocking():
    from kogniterm.core.agent_state import AgentState
    from kogniterm.core.agents.tool_executor import ToolExecutor
    from langchain_core.messages import AIMessage, ToolMessage
    
    # 1. Test execute_single_tool with blocked tool
    tc = {"name": "execute_command", "args": {"command": "ls"}, "id": "call_1"}
    
    # Create delegation context for LEAF agent (which has execute_command blocked)
    limits = DelegationLimits()
    manager = DelegationManager(limits=limits)
    leaf_ctx = manager.register_agent("leaf_agent", parent_id=None, role=AgentRole.LEAF)
    
    # Execute single tool: should be blocked
    tid, content, exc = ToolExecutor.execute_single_tool(tc, None, None, delegation_context=leaf_ctx)
    assert tid == "call_1"
    assert "Error: La herramienta 'execute_command' está deshabilitada" in content
    assert exc is None

    # 2. Test execute_tool_node with blocked tool in agent state
    state = AgentState(messages=[
        AIMessage(content="", tool_calls=[tc])
    ])
    state.delegation_context = leaf_ctx
    
    # We pass None for llm_service because the execution should be blocked before calling any service.
    # We pass None for terminal_ui
    res_state = ToolExecutor.execute_tool_node(state, None, None)
    
    # The output should have the ToolMessage with the error
    assert len(res_state.messages) == 2
    last_msg = res_state.messages[-1]
    assert isinstance(last_msg, ToolMessage)
    assert last_msg.tool_call_id == "call_1"
    assert "Error: La herramienta 'execute_command' está deshabilitada" in last_msg.content

def test_call_agent_skill_delegation_integration():
    import kogniterm.core.agents.deep_coder
    from unittest.mock import MagicMock, patch
    from kogniterm.skills.bundled.call_agent.scripts.tool import call_agent_skill
    from kogniterm.core.delegation import DelegationManager, HeartbeatMonitor, AgentRole

    # Mock llm_service
    llm_service = MagicMock()
    llm_service.delegation_manager = DelegationManager()
    llm_service.heartbeat_monitor = MagicMock()
    
    # Store thread-local simulation
    delegation_state = {"current": None}
    
    # Simulate current_delegation_context property on mock
    type(llm_service).current_delegation_context = property(
        fget=lambda self: delegation_state["current"],
        fset=lambda self, val: delegation_state.update({"current": val})
    )

    # Register parent context
    parent_ctx = llm_service.delegation_manager.register_agent(
        agent_id="orchestrator", parent_id=None, role=AgentRole.ORCHESTRATOR
    )

    # Mock create_deep_coder to return a mock graph
    mock_graph = MagicMock()
    
    def mock_invoke(initial_state, config=None):
        # Assert that child agent was registered
        active_agents = llm_service.delegation_manager.active_agents
        child_agents = [a for a in active_agents.values() if a.parent_id == "orchestrator"]
        assert len(child_agents) == 1
        child_ctx = child_agents[0]
        assert child_ctx.role == AgentRole.LEAF
        assert child_ctx.depth == 1
        
        # Assert that delegation context was set on initial_state
        assert initial_state.delegation_context == child_ctx
        
        # Assert that thread local context was set on llm_service
        assert llm_service.current_delegation_context == child_ctx
        
        # Return a dummy final state with a message
        from kogniterm.core.agent_state import AgentState
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="Done")]}
        
    mock_graph.invoke = mock_invoke

    with patch("kogniterm.core.agents.deep_coder.create_deep_coder", return_value=mock_graph), \
         patch("kogniterm.skills.bundled.call_agent.scripts.tool._request_autonomous_execution", return_value=True):
         
        # Execute skill
        res = call_agent_skill(
            agent_name="code_agent",
            task="Test task",
            llm_service=llm_service,
            delegation_context=parent_ctx
        )
        
        assert "Done" in res

    # After execution, child agent should be unregistered
    active_agents = llm_service.delegation_manager.active_agents
    child_agents = [a for a in active_agents.values() if a.parent_id == "orchestrator"]
    assert len(child_agents) == 0
    
    # Thread local context should be restored
    assert llm_service.current_delegation_context is None
    
    # Heartbeat monitor should have removed the agent
    llm_service.heartbeat_monitor.remove_agent.assert_called_once()
