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
    
    # Create delegation context for LEAF agent (explicitly blocking execute_command)
    limits = DelegationLimits()
    manager = DelegationManager(limits=limits)
    leaf_ctx = manager.register_agent(
        "leaf_agent",
        parent_id=None,
        role=AgentRole.LEAF,
        blocked_tools=frozenset(["execute_command"])
    )
    
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
    import importlib
    tool_module = importlib.import_module("kogniterm.skills.bundled.call-agent.scripts.tool")
    call_agent_skill = tool_module.call_agent_skill
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
         patch.object(tool_module, "_request_autonomous_execution", return_value=True):
         
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


def test_call_agent_skill_dynamic_agent_allowed_tools():
    from unittest.mock import MagicMock, patch
    import importlib
    tool_module = importlib.import_module("kogniterm.skills.bundled.call-agent.scripts.tool")
    call_agent_skill = tool_module.call_agent_skill
    from kogniterm.core.delegation import DelegationManager, AgentRole
    from kogniterm.core.agents.tool_executor import ToolExecutor

    # Mock llm_service
    llm_service = MagicMock()
    llm_service.delegation_manager = DelegationManager()
    llm_service.heartbeat_monitor = MagicMock()
    
    # Mock tool_map
    llm_service.tool_map = {
        "file_operations": MagicMock(),
        "web_fetch": MagicMock(),
        "execute_command": MagicMock(),
    }
    
    def mock_get_tool(name):
        if name in llm_service.tool_map:
            return llm_service.tool_map[name]
        return None
        
    llm_service.get_tool = mock_get_tool
    
    # Mock _invoke_tool_with_interrupt to act as a generator yielding a mock string
    def mock_invoke_tool_with_interrupt(tool, args, ctx):
        yield "mock_execution_output"
        
    llm_service._invoke_tool_with_interrupt = mock_invoke_tool_with_interrupt
    
    delegation_state = {"current": None}
    type(llm_service).current_delegation_context = property(
        fget=lambda self: delegation_state["current"],
        fset=lambda self, val: delegation_state.update({"current": val})
    )

    parent_ctx = llm_service.delegation_manager.register_agent(
        agent_id="orchestrator", parent_id=None, role=AgentRole.ORCHESTRATOR
    )

    mock_graph = MagicMock()
    
    custom_prompt = "Eres un agente SQL experto que solo puede usar operaciones de archivo."
    allowed_tools = ["file_operations"]
    
    captured_sys_prompt = []
    
    def mock_create_dynamic_agent(svc, sys_prompt, ui, interrupt):
        captured_sys_prompt.append(sys_prompt)
        return mock_graph
        
    def mock_invoke(initial_state, config=None):
        child_ctx = initial_state.delegation_context
        # Verificar que se creó el rol LEAF con herramientas bloqueadas personalizadas
        assert child_ctx.role == AgentRole.LEAF
        assert "execute_command" in child_ctx.blocked_tools
        assert "web_fetch" in child_ctx.blocked_tools  # Debe estar bloqueada porque no está en allowed_tools
        assert "file_operations" not in child_ctx.blocked_tools  # Debe estar permitida
        
        # Probar bloqueo en ToolExecutor
        tc_allowed = {"name": "file_operations", "args": {"operation": "read"}, "id": "call_allow"}
        tc_blocked = {"name": "web_fetch", "args": {"url": "http://example.com"}, "id": "call_block"}
        
        # Test execute_single_tool con tool permitida
        tid_allow, content_allow, _ = ToolExecutor.execute_single_tool(tc_allowed, llm_service, None, delegation_context=child_ctx)
        assert "está deshabilitada" not in content_allow
        assert "mock_execution_output" in content_allow
        
        # Test execute_single_tool con tool bloqueada
        tid_block, content_block, _ = ToolExecutor.execute_single_tool(tc_blocked, llm_service, None, delegation_context=child_ctx)
        assert "Error: La herramienta 'web_fetch' está deshabilitada" in content_block

        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="SQL query verified")]}

    mock_graph.invoke = mock_invoke

    with patch("kogniterm.core.agents.dynamic_agent.create_dynamic_agent", side_effect=mock_create_dynamic_agent), \
         patch.object(tool_module, "_request_autonomous_execution", return_value=True):
         
        res = call_agent_skill(
            agent_name="sql_expert",
            task="Retrieve user count",
            llm_service=llm_service,
            delegation_context=parent_ctx,
            custom_system_prompt=custom_prompt,
            allowed_tools=allowed_tools
        )
        
        assert "SQL query verified" in res
        assert captured_sys_prompt[0] == custom_prompt


def test_tool_executor_execute_tools_parallel():
    from kogniterm.core.agent_state import AgentState
    from kogniterm.core.agents.tool_executor import ToolExecutor
    from langchain_core.messages import AIMessage
    from unittest.mock import MagicMock

    mock_llm_service = MagicMock()
    mock_tool = MagicMock()
    mock_llm_service.get_tool.return_value = mock_tool
    mock_llm_service._invoke_tool_with_interrupt.return_value = iter(["parallel_result"])

    state = AgentState()
    ai_message = AIMessage(
        content="Testing parallel execution",
        tool_calls=[{"name": "read_file", "args": {"path": "test.py"}, "id": "call_1"}]
    )
    state.messages.append(ai_message)

    res_state = ToolExecutor.execute_tools_parallel(
        state=state,
        llm_service=mock_llm_service,
        terminal_ui=None,
        delegation_context=None,
        interrupt_queue=None,
    )

    assert len(res_state.messages) == 2
    assert res_state.messages[-1].content == "parallel_result"
    assert res_state.messages[-1].tool_call_id == "call_1"


