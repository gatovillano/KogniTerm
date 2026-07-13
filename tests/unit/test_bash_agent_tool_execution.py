import pytest
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage, ToolMessage
from kogniterm.core.agent_state import AgentState
from kogniterm.core.agents.bash_agent import execute_tool_node

@pytest.mark.anyio
async def test_execute_tool_node_success():
    # Arrange
    llm_service = MagicMock()
    # Mock get_tool to return a dummy tool object
    dummy_tool = MagicMock()
    llm_service.get_tool.return_value = dummy_tool
    
    # Mock _invoke_tool_with_interrupt to return a list of strings
    llm_service._invoke_tool_with_interrupt.return_value = ["tool successfully executed"]
    
    terminal_ui = MagicMock()
    terminal_ui.is_tui = True
    
    tc = {"name": "test_tool", "args": {"param": "value"}, "id": "call_1"}
    state = AgentState(messages=[
        AIMessage(content="", tool_calls=[tc])
    ])
    
    # Act
    res = await execute_tool_node(state, llm_service, terminal_ui)
    
    # Assert
    # We should have the ToolMessage appended to state.messages
    messages = res["messages"]
    assert len(messages) == 2
    assert isinstance(messages[-1], ToolMessage)
    assert messages[-1].content == "tool successfully executed"
    assert messages[-1].tool_call_id == "call_1"
