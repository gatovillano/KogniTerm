import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from kogniterm.terminal.meta_command_processor import MetaCommandProcessor
from kogniterm.core.agent_state import AgentState

@pytest.fixture
def mock_llm_service():
    service = MagicMock()
    service.conversation_history = []
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
    app.thread_manager = MagicMock()
    return app

@pytest.mark.anyio
async def test_resume_command_no_threads(mock_llm_service, mock_agent_state, mock_terminal_ui, mock_app):
    mock_app.thread_manager.list_threads.return_value = []
    
    processor = MetaCommandProcessor(mock_llm_service, mock_agent_state, mock_terminal_ui, mock_app)
    
    result = await processor.process_meta_command("/resume")
    
    assert result is True
    mock_terminal_ui.print_message.assert_called_with("No saved threads to resume.", style="yellow")

@pytest.mark.anyio
async def test_resume_command_exact_id(mock_llm_service, mock_agent_state, mock_terminal_ui, mock_app):
    # Mocking single thread
    thread_mock = MagicMock()
    thread_mock.id = "thread-123"
    thread_mock.title = "Mi Hilo de Test"
    thread_mock.messages = [HumanMessage(content="hola"), AIMessage(content="mundo")]
    
    mock_app.thread_manager.list_threads.return_value = [{"id": "thread-123", "title": "Mi Hilo de Test"}]
    mock_app.thread_manager.get_thread.return_value = thread_mock
    
    processor = MetaCommandProcessor(mock_llm_service, mock_agent_state, mock_terminal_ui, mock_app)
    
    # Process exact id
    result = await processor.process_meta_command("/resume thread-123")
    
    assert result is True
    mock_app.thread_manager.set_current_thread_id.assert_called_with("thread-123")
    assert mock_llm_service.conversation_history == thread_mock.messages
    mock_terminal_ui.print_message.assert_any_call("Thread 'Mi Hilo de Test' resumed with 2 messages.", style="green")

@pytest.mark.anyio
async def test_resume_command_partial_title_match(mock_llm_service, mock_agent_state, mock_terminal_ui, mock_app):
    thread_mock = MagicMock()
    thread_mock.id = "thread-123"
    thread_mock.title = "Mi Hilo de Test"
    thread_mock.messages = [HumanMessage(content="hola"), AIMessage(content="mundo")]
    
    mock_app.thread_manager.list_threads.return_value = [{"id": "thread-123", "title": "Mi Hilo de Test"}]
    mock_app.thread_manager.get_thread.side_effect = lambda tid: thread_mock if tid == "thread-123" else None
    mock_app.thread_manager.find_threads.return_value = [{"id": "thread-123", "title": "Mi Hilo de Test"}]
    
    processor = MetaCommandProcessor(mock_llm_service, mock_agent_state, mock_terminal_ui, mock_app)
    
    # Process partial title
    result = await processor.process_meta_command("/resume Test")
    
    assert result is True
    mock_app.thread_manager.find_threads.assert_called_with("Test")
    mock_app.thread_manager.set_current_thread_id.assert_called_with("thread-123")
    mock_terminal_ui.print_message.assert_any_call("Thread 'Mi Hilo de Test' resumed with 2 messages.", style="green")
