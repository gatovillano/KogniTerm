import os
import shutil
import pytest
from pathlib import Path
from kogniterm.core.agents.config_manager import AgentConfigManager

@pytest.fixture
def temp_config_dir(tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    agents_dir = workspace_dir / ".agents"
    agents_dir.mkdir()
    
    # Write a markdown agent file
    md_content = """---
name: test_md_agent
description: "Test agent description"
role: leaf
allowed_tools:
  - file_operations
---
System prompt from markdown body.
"""
    with open(agents_dir / "test_md_agent.md", "w") as f:
        f.write(md_content)
        
    # Write a yaml agent file
    yaml_content = """
name: test_yaml_agent
description: "Test yaml agent"
role: orchestrator
allowed_tools:
  - execute_command
system_prompt: "System prompt from yaml key."
"""
    with open(agents_dir / "test_yaml_agent.yaml", "w") as f:
        f.write(yaml_content)
        
    return workspace_dir

def test_agent_config_loading(temp_config_dir):
    manager = AgentConfigManager(workspace_dir=str(temp_config_dir))
    manager.discover_configs()
    
    # Test Markdown Agent
    md_config = manager.get_agent_config("test_md_agent")
    assert md_config is not None
    assert md_config["name"] == "test_md_agent"
    assert md_config["role"] == "leaf"
    assert md_config["allowed_tools"] == ["file_operations"]
    assert "System prompt from markdown body." in md_config["system_prompt"]
    
    # Test YAML Agent
    yaml_config = manager.get_agent_config("test_yaml_agent")
    assert yaml_config is not None
    assert yaml_config["name"] == "test_yaml_agent"
    assert yaml_config["role"] == "orchestrator"
    assert yaml_config["allowed_tools"] == ["execute_command"]
    assert yaml_config["system_prompt"] == "System prompt from yaml key."


def test_call_agent_skill_loads_declarative_config(temp_config_dir):
    from unittest.mock import MagicMock, patch
    import importlib
    from kogniterm.core.delegation import DelegationManager, AgentRole

    tool_module = importlib.import_module("kogniterm.skills.bundled.call-agent.scripts.tool")
    call_agent_skill = tool_module.call_agent_skill

    # Mock llm_service
    llm_service = MagicMock()
    llm_service.current_workspace_dir = str(temp_config_dir)
    llm_service.delegation_manager = DelegationManager()
    llm_service.heartbeat_monitor = MagicMock()

    # We mock create_dynamic_agent to capture settings passed
    mock_graph = MagicMock()
    captured_sys_prompt = []

    def mock_create_dynamic_agent(svc, sys_prompt, ui, interrupt):
        captured_sys_prompt.append(sys_prompt)
        return mock_graph

    def mock_invoke(initial_state, config=None):
        child_ctx = initial_state.delegation_context
        # Verify it loaded the orchestrator role and execute_command from YAML config
        assert child_ctx.role == AgentRole.ORCHESTRATOR
        assert child_ctx.blocked_tools == frozenset()
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="Config tested")]}

    mock_graph.invoke = mock_invoke

    parent_ctx = llm_service.delegation_manager.register_agent(
        agent_id="orchestrator", parent_id=None, role=AgentRole.ORCHESTRATOR
    )

    with patch("kogniterm.core.agents.dynamic_agent.create_dynamic_agent", side_effect=mock_create_dynamic_agent), \
         patch.object(tool_module, "_request_autonomous_execution", return_value=True):

        res = call_agent_skill(
            agent_name="test_yaml_agent",
            task="Perform config test",
            llm_service=llm_service,
            delegation_context=parent_ctx
        )
        assert "Config tested" in res
        assert captured_sys_prompt[0] == "System prompt from yaml key."


def test_call_agents_parallel_loads_declarative_config(temp_config_dir):
    from unittest.mock import MagicMock, patch
    import importlib
    from kogniterm.core.delegation import DelegationManager, AgentRole

    tool_module = importlib.import_module("kogniterm.skills.bundled.call-agents-parallel.scripts.tool")
    call_agents_parallel = tool_module.call_agents_parallel

    # Mock llm_service
    llm_service = MagicMock()
    llm_service.current_workspace_dir = str(temp_config_dir)
    llm_service.delegation_manager = DelegationManager()
    llm_service.heartbeat_monitor = MagicMock()

    llm_service.delegation_manager.register_agent(
        agent_id="parallel_orchestrator", parent_id=None, role=AgentRole.ORCHESTRATOR
    )

    # We mock _build_agent_graph to capture settings passed
    mock_graph = MagicMock()
    captured_sys_prompt = []

    def mock_build_agent_graph(agent_type, system_prompt, svc, ui, interrupt):
        captured_sys_prompt.append(system_prompt)
        return mock_graph

    async def mock_ainvoke(initial_state, config=None):
        child_ctx = initial_state.delegation_context
        # Verify it loaded the leaf role and allowed_tools (file_operations) from Markdown config
        assert child_ctx.role == AgentRole.LEAF
        # Since file_operations is allowed, it should not be in blocked_tools. Let's verify.
        # Note: all_tools defaults to empty set since we don't mock it on llm_service tool_map, but let's check
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="Parallel config tested")], "completed": True, "result": "Success"}

    mock_graph.ainvoke = mock_ainvoke

    # Setup spec for parallel execution
    specs = [{"name": "test_md_agent", "type": "test_md_agent", "task": "Parallel task"}]

    with patch.object(tool_module, "_build_agent_graph", side_effect=mock_build_agent_graph), \
         patch.object(tool_module, "_request_autonomous_execution", return_value=True), \
         patch.object(tool_module, "_activate_parallel_container", return_value=None):

        res = call_agents_parallel(
            agents=specs,
            llm_service=llm_service,
            terminal_ui=None
        )
        assert "Success" in res
        assert "System prompt from markdown body." in captured_sys_prompt[0]

