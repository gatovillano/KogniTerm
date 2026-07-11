import pytest
from kogniterm.core.agent_interaction import BaseAgentInteractionManager, AgentInteractionRegistry

def test_registry_raises_unregistered():
    with pytest.raises(RuntimeError, match="La factory de AgentInteractionManager no ha sido registrada"):
        AgentInteractionRegistry.create()

def test_registry_instantiates_registered():
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
