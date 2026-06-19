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
