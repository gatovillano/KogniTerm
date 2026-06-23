import pytest
from unittest.mock import MagicMock
from kogniterm.terminal.tui.tui_app import KogniTermTUI
from kogniterm.terminal.tui.components.chat_log import ChatLogWidget
from textual.widgets import TabbedContent, TabPane

@pytest.mark.anyio
async def test_kogniterm_tui_agent_tabs():
    # Mock llm_service
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    
    # Initialize App with mocked service
    app = KogniTermTUI(llm_service=llm_service)
    
    async with app.run_test() as pilot:
        # Check initial tabs container
        tabbed_content = app.query_one("#parallel_agents_container", TabbedContent)
        assert tabbed_content is not None
        
        # Add dynamic tab
        widget = app.add_agent_tab("test_agent_1", "Dynamic Coder")
        assert widget is not None
        assert isinstance(widget, ChatLogWidget)
        assert widget.id == "live_display_test_agent_1"
        
        # Verify it was added to the tab panes
        pane = app.query_one("#pane_test_agent_1", TabPane)
        assert pane is not None
        assert getattr(pane, "_title", "Dynamic Coder") == "Dynamic Coder"
        
        # Remove dynamic tab
        app.remove_agent_tab("test_agent_1")
        
        # Wait a small moment for TUI thread to process removal
        await pilot.pause()
        
        # Verify it was removed
        with pytest.raises(Exception):
            app.query_one("#pane_test_agent_1", TabPane)


@pytest.mark.anyio
async def test_websocket_client_routes_subagent_events():
    # Mock KogniTermTUI
    app = MagicMock()
    app.chat_log = MagicMock()
    app.live_display_coder = MagicMock()
    app.call_from_thread = lambda f, *args, **kwargs: f(*args, **kwargs)
    
    from kogniterm.terminal.tui.ws_client import TUIWebSocketClient
    
    client = TUIWebSocketClient(app, "ws://localhost:8765", "test_session")
    
    # Test main agent panel retrieval
    assert client._get_chat_log(None) == app.chat_log
    
    # Test subagent panel retrieval
    assert client._get_chat_log("live_display_coder") == app.live_display_coder
    
    # Route event: tool_call for subagent
    event = {
        "type": "tool_call",
        "agent_id": "live_display_coder",
        "data": {
            "name": "python_executor",
            "description": "running script",
            "skill": "python"
        }
    }
    client._route_event(event)
    
    # Verify it routed to live_display_coder and not the main one
    app.live_display_coder.write_tool_notification.assert_called_once_with(
        "python_executor", "running script", "python"
    )


@pytest.mark.anyio
async def test_textual_terminal_ui_routes_local_subagent_events():
    # Mock KogniTermTUI
    app = MagicMock()
    app.chat_log = MagicMock()
    app.live_display_coder = MagicMock()
    app.call_from_thread = lambda f, *args, **kwargs: f(*args, **kwargs)
    
    # Assign attributes as if they were composed on the app
    app.live_display_coder.id = "live_display_coder"
    setattr(app, "live_display_coder", app.live_display_coder)
    
    from kogniterm.terminal.tui.tui_app import TextualTerminalUI
    
    terminal_ui = TextualTerminalUI(app)
    
    # Route print_message to subagent
    terminal_ui.print_message("test message", panel_id="live_display_coder")
    app.live_display_coder.write_agent_message.assert_called_once_with("test message")
    
    # Route print_tool_notification to subagent
    terminal_ui.print_tool_notification("test_tool", "test action", "test_skill", panel_id="live_display_coder")
    app.live_display_coder.write_tool_notification.assert_called_once_with(
        "test_tool", "test action", "test_skill"
    )
    
    # Route print_success_box to subagent
    terminal_ui.print_success_box("success msg", "Success Title", panel_id="live_display_coder")
    app.live_display_coder.write_message.assert_called_once_with(
        "✅ [box] **Success Title**: success msg", style="green"
    )

