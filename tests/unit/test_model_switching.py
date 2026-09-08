import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager
from kogniterm.core.agent_state import AgentState
from kogniterm.core.agents.super_agent import SuperAgent, SuperAgentRunner
from kogniterm.core.ai_cli_bridge.llm_bridge import LLMBridge
from kogniterm.core.multi_provider_manager import MultiProviderManager, ProviderConfig

def test_llm_bridge_and_super_agent_set_model():
    bridge = LLMBridge(model="gemini/gemini-1.5-flash")
    assert bridge.model == "gemini/gemini-1.5-flash"
    bridge.set_model("openrouter/openai/gpt-4o")
    assert bridge.model == "openrouter/openai/gpt-4o"

    agent = SuperAgent(model="gemini/gemini-1.5-flash")
    assert agent.model == "gemini/gemini-1.5-flash"
    assert agent.llm_bridge.model == "gemini/gemini-1.5-flash"
    agent.set_model("anthropic/claude-3-5-sonnet")
    assert agent.model == "anthropic/claude-3-5-sonnet"
    assert agent.llm_bridge.model == "anthropic/claude-3-5-sonnet"

def test_super_agent_runner_set_model():
    llm_mock = MagicMock()
    llm_mock.model_name = "gemini/gemini-1.5-flash"
    runner = SuperAgentRunner(llm_service=llm_mock)
    assert runner.agent.model == "gemini/gemini-1.5-flash"
    assert runner.agent.llm_bridge.model == "gemini/gemini-1.5-flash"

    runner.set_model("antigravity/gemini-3-flash")
    assert runner.agent.model == "antigravity/gemini-3-flash"
    assert runner.agent.llm_bridge.model == "antigravity/gemini-3-flash"

def test_agent_interaction_manager_set_model():
    llm_mock = MagicMock()
    llm_mock.model_name = "gemini/gemini-1.5-flash"
    state = AgentState()
    aim = AgentInteractionManager(llm_mock, state, MagicMock(), MagicMock())
    assert aim.active_agent_app.agent.model == "gemini/gemini-1.5-flash"

    aim.set_model("openrouter/google/gemini-2.0-flash-exp:free")
    assert aim.active_agent_app.agent.model == "openrouter/google/gemini-2.0-flash-exp:free"
    assert aim.active_agent_app.agent.llm_bridge.model == "openrouter/google/gemini-2.0-flash-exp:free"
    assert llm_mock.set_model.called or llm_mock.model_name == "openrouter/google/gemini-2.0-flash-exp:free"

@pytest.mark.asyncio
async def test_super_agent_runner_dynamic_model_sync_in_run():
    llm_mock = MagicMock()
    llm_mock.model_name = "initial-model"
    runner = SuperAgentRunner(llm_service=llm_mock)
    assert runner.agent.model == "initial-model"

    # Simulate model change on llm_service without calling set_model on runner directly
    llm_mock.model_name = "new-updated-model"
    
    with patch.object(runner.agent, "execute_stream") as mock_stream:
        async def fake_stream(**kwargs):
            yield {"type": "done", "output": "ok", "tools_used": [], "success": True}
        mock_stream.side_effect = fake_stream

        state = AgentState()
        await runner._run_async(state)
        
        # runner should have synced its agent and bridge model before calling execute_stream
        assert runner.agent.model == "new-updated-model"
        assert runner.agent.llm_bridge.model == "new-updated-model"

def test_multi_provider_manager_prefix_routing():
    providers = [
        ProviderConfig(name="antigravity", model_prefix="antigravity", api_key_env="DUMMY_KEY"),
        ProviderConfig(name="google", model_prefix="gemini", api_key_env="DUMMY_KEY"),
        ProviderConfig(name="openrouter", model_prefix="openrouter", api_key_env="DUMMY_KEY"),
        ProviderConfig(name="kilocode", model_prefix="openai", api_key_env="DUMMY_KEY"),
        ProviderConfig(name="anthropic", model_prefix="anthropic", api_key_env="DUMMY_KEY"),
    ]
    for p in providers:
        p.get_api_key = MagicMock(return_value="dummy-key")

    pm = MultiProviderManager(providers=providers)

    # 1. openrouter prefix should NOT be routed to Google native even if the underlying model is google/gemini
    p1 = pm._determine_ideal_provider("openrouter/google/gemini-2.0-flash-exp:free")
    assert p1 is not None and p1.name == "openrouter"

    # 2. kilocode prefix should be routed to kilocode
    p2 = pm._determine_ideal_provider("kilocode/kilo/auto")
    assert p2 is not None and p2.name == "kilocode"

    # 3. antigravity prefix should be routed to antigravity
    p3 = pm._determine_ideal_provider("antigravity/gemini-3-flash")
    assert p3 is not None and p3.name == "antigravity"

    # 4. gemini prefix should be routed to google
    p4 = pm._determine_ideal_provider("gemini/gemini-2.5-flash")
    assert p4 is not None and p4.name == "google"
