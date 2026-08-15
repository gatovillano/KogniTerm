import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from kogniterm.server.session_pool import AgentSession, ServerUI
from langchain_core.messages import HumanMessage, AIMessage

@pytest.mark.asyncio
async def test_agent_session_magic_command_clear():
    loop = asyncio.get_event_loop()
    mock_llm = MagicMock()
    mock_llm.auto_save_interval = 60
    mock_thread_mgr = MagicMock()
    
    session = AgentSession("test-magic-clear", mock_llm, loop, thread_manager=mock_thread_mgr)
    session.ui._push = MagicMock()
    
    # Send /clear
    await session.send("/clear", executor=None)
    
    assert len(session.agent_state.messages) == 0
    mock_thread_mgr.save_thread_messages.assert_called_with("test-magic-clear", [])

@pytest.mark.asyncio
async def test_agent_session_magic_command_help():
    loop = asyncio.get_event_loop()
    mock_llm = MagicMock()
    mock_llm.auto_save_interval = 60
    mock_thread_mgr = MagicMock()
    
    session = AgentSession("test-magic-help", mock_llm, loop, thread_manager=mock_thread_mgr)
    session.ui._push = MagicMock()
    
    # Send /help
    await session.send("/help", executor=None)
    
    # Check that info/message was printed via ui
    pushed_events = [call.args[0] for call in session.ui._push.call_args_list]
    assert "done" in pushed_events

@pytest.mark.asyncio
async def test_agent_session_unrecognized_slash_command():
    loop = asyncio.get_event_loop()
    mock_llm = MagicMock()
    mock_thread_mgr = MagicMock()
    
    session = AgentSession("test-magic-unknown", mock_llm, loop, thread_manager=mock_thread_mgr)
    session.ui._push = MagicMock()
    
    # Send unknown slash command
    await session.send("/invalid_command_xyz", executor=None)
    
    # Check that it did NOT add a human message to agent_state
    assert len(session.agent_state.messages) == 0
