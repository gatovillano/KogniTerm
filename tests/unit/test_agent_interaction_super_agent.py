import os
import pytest
from unittest.mock import MagicMock, patch
from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager
from kogniterm.core.agent_state import AgentState
from kogniterm.core.agents.super_agent import SuperAgentRunner
from kogniterm.core.agents.bash_agent import BashAgentRunner

def test_agent_interaction_manager_defaults_to_super_agent():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    terminal_ui = MagicMock()
    interrupt_queue = MagicMock()
    state = AgentState()

    with patch.dict(os.environ, {"KOGNITERM_MAIN_AGENT": "super_agent"}):
        aim = AgentInteractionManager(llm_service, state, terminal_ui, interrupt_queue)
        assert isinstance(aim.active_agent_app, SuperAgentRunner)
        # Verificar que bash_agent_app sigue existiendo como fallback
        assert hasattr(aim, "bash_agent_app")
        assert isinstance(aim.bash_agent_app, BashAgentRunner)

def test_agent_interaction_manager_fallback_to_bash_agent():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    terminal_ui = MagicMock()
    interrupt_queue = MagicMock()
    state = AgentState()

    with patch.dict(os.environ, {"KOGNITERM_MAIN_AGENT": "bash_agent"}):
        aim = AgentInteractionManager(llm_service, state, terminal_ui, interrupt_queue)
        assert isinstance(aim.active_agent_app, BashAgentRunner)
