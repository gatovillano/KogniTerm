import pytest
from kogniterm.core.agent_interaction import BaseAgentInteractionManager, AgentInteractionRegistry

def test_registry_raises_unregistered(monkeypatch):
    import sys
    AgentInteractionRegistry._factory = None
    monkeypatch.setitem(sys.modules, "kogniterm.terminal.agent_interaction_manager", None)
    with pytest.raises(RuntimeError, match="La factory de AgentInteractionManager no ha sido registrada"):
        AgentInteractionRegistry.create()

def test_registry_instantiates_registered():
    AgentInteractionRegistry._factory = None
    class DummyManager(BaseAgentInteractionManager):
        def __init__(self, x):
            self.x = x
        def invoke_agent(self, user_input):
            return {"status": "ok", "x": self.x}

    AgentInteractionRegistry.register_factory(DummyManager)
    manager = AgentInteractionRegistry.create(x=10)
    assert isinstance(manager, BaseAgentInteractionManager)
    assert manager.invoke_agent("test") == {"status": "ok", "x": 10}
    # Cleanup registry
    AgentInteractionRegistry._factory = None
