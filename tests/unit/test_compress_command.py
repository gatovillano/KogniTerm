import pytest
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from kogniterm.terminal.meta_command_processor import MetaCommandProcessor
from kogniterm.core.agent_state import AgentState

@pytest.fixture
def mock_llm_service():
    service = MagicMock()
    service.conversation_history = [
        HumanMessage(content="Hello"),
        AIMessage(content="Hi, how can I help you?"),
    ]
    service.summarize_conversation_history.return_value = "This is a summary of the conversation."
    service._save_history = MagicMock()
    return service

@pytest.fixture
def mock_agent_state():
    state = AgentState()
    return state

@pytest.fixture
def mock_terminal_ui():
    ui = MagicMock()
    ui.print_message = MagicMock()
    ui.console = MagicMock()
    return ui

@pytest.fixture
def mock_app():
    app = MagicMock()
    return app

@pytest.mark.anyio
async def test_compress_command_renders_panel_without_unbound_error(mock_llm_service, mock_agent_state, mock_terminal_ui, mock_app):
    processor = MetaCommandProcessor(mock_llm_service, mock_agent_state, mock_terminal_ui, mock_app)
    
    # Process /compress command
    result = await processor.process_meta_command("/compress")
    
    assert result is True
    # Verify summary was requested
    mock_llm_service.summarize_conversation_history.assert_called_once_with(force_truncate=False)
    # Verify console.print was called with Panel object (not crashing on Panel)
    assert mock_terminal_ui.console.print.called
    printed_args = [call.args[0] for call in mock_terminal_ui.console.print.call_args_list]
    panel_types = [type(arg).__name__ for arg in printed_args]
    assert "Panel" in panel_types
