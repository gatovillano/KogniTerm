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


from kogniterm.core.exceptions import UserConfirmationRequired

@pytest.mark.anyio
async def test_execute_tool_node_advanced_file_editor(tmp_path):
    # Arrange
    llm_service = MagicMock()
    dummy_tool = MagicMock()
    llm_service.get_tool.return_value = dummy_tool
    del llm_service.skill_manager.approval_handler
    
    # Create temp file
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("original content")
    
    # Mock _invoke_tool_with_interrupt to raise UserConfirmationRequired
    exc = UserConfirmationRequired(
        message="Confirmation needed",
        tool_name="advanced_file_editor",
        tool_args={
            "path": str(test_file),
            "action": "full_replacement",
            "content": "new content"
        },
        raw_tool_output={}
    )
    
    def side_effect(*args, **kwargs):
        raise exc
        
    llm_service._invoke_tool_with_interrupt.side_effect = side_effect
    
    terminal_ui = MagicMock()
    terminal_ui.is_tui = False
    
    tc = {
        "name": "advanced_file_editor",
        "args": {
            "path": str(test_file),
            "action": "full_replacement",
            "content": "new content"
        },
        "id": "call_1"
    }
    state = AgentState(messages=[
        AIMessage(content="", tool_calls=[tc])
    ])
    
    # Act
    res = await execute_tool_node(state, llm_service, terminal_ui)
    
    # Assert
    # File content should be updated to "new content"
    assert test_file.read_text().strip() == "new content"
    
    # Message should be appended with the result
    messages = res["messages"]
    assert len(messages) == 2
    assert isinstance(messages[-1], ToolMessage)
    content_lower = messages[-1].content.lower()
    assert any(word in content_lower for word in ["success", "ok", "cambio", "exitosa", "actualizado"])


@pytest.mark.anyio
async def test_execute_tool_node_file_update(tmp_path):
    # Arrange
    llm_service = MagicMock()
    dummy_tool = MagicMock()
    llm_service.get_tool.return_value = dummy_tool
    del llm_service.skill_manager.approval_handler
    
    test_file = tmp_path / "test_file_update.txt"
    test_file.write_text("original content")
    
    # Mock _invoke_tool_with_interrupt to raise UserConfirmationRequired
    exc = UserConfirmationRequired(
        message="Confirmation needed",
        tool_name="file_update",
        tool_args={
            "path": str(test_file),
            "content": "new file_update content"
        },
        raw_tool_output={}
    )
    
    def side_effect(*args, **kwargs):
        raise exc
        
    llm_service._invoke_tool_with_interrupt.side_effect = side_effect
    
    terminal_ui = MagicMock()
    terminal_ui.is_tui = False
    
    tc = {
        "name": "file_update",
        "args": {
            "path": str(test_file),
            "content": "new file_update content"
        },
        "id": "call_2"
    }
    state = AgentState(messages=[
        AIMessage(content="", tool_calls=[tc])
    ])
    
    # Act
    res = await execute_tool_node(state, llm_service, terminal_ui)
    
    # Assert
    assert test_file.read_text().strip() == "new file_update content"
    messages = res["messages"]
    assert len(messages) == 2
    assert isinstance(messages[-1], ToolMessage)
    content_lower = messages[-1].content.lower()
    assert any(word in content_lower for word in ["success", "ok", "cambio", "exitosa", "actualizado"])
