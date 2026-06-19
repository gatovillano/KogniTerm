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
