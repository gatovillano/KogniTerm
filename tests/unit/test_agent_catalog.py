from unittest.mock import MagicMock, patch

import pytest

from kogniterm.core.agents.agent_catalog import (
    DEFAULT_CHAT_AGENT,
    SUPPORTED_CHAT_AGENTS,
    create_agent_runner,
    describe_agents,
    normalize_agent_id,
)


def test_supported_agents_are_unique_and_documented():
    agents = describe_agents()
    assert [agent["id"] for agent in agents] == list(SUPPORTED_CHAT_AGENTS)
    assert all(agent["name"] and agent["description"] and agent["engine"] for agent in agents)
    assert DEFAULT_CHAT_AGENT == "super_agent"


def test_normalize_agent_id_accepts_canonical_names_and_aliases():
    assert normalize_agent_id("super_agent") == "super_agent"
    assert normalize_agent_id(" BashAgent ") == "bash_agent"
    assert normalize_agent_id("DeepCoder") == "code_agent"
    assert normalize_agent_id("researcher") == "researcher_agent"
    assert normalize_agent_id(None) == DEFAULT_CHAT_AGENT


def test_normalize_agent_id_rejects_unknown_names():
    with pytest.raises(ValueError, match="Agente no soportado"):
        normalize_agent_id("crewai-helper")


def test_create_agent_runner_delegates_to_real_factories():
    llm_service = MagicMock()
    with (
        patch("kogniterm.core.agents.super_agent.create_super_agent") as super_factory,
        patch("kogniterm.core.agents.bash_agent.create_bash_agent") as bash_factory,
        patch("kogniterm.core.agents.deep_coder.create_deep_coder") as code_factory,
        patch("kogniterm.core.agents.deep_researcher.create_deep_researcher") as researcher_factory,
    ):
        create_agent_runner("super_agent", llm_service=llm_service)
        create_agent_runner("bash_agent", llm_service=llm_service)
        create_agent_runner("code_agent", llm_service=llm_service)
        create_agent_runner("researcher_agent", llm_service=llm_service)

    assert super_factory.call_count == 1
    assert bash_factory.call_count == 1
    assert code_factory.call_count == 1
    assert researcher_factory.call_count == 1
