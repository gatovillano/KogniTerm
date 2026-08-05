import pytest
from unittest.mock import MagicMock, patch
from kogniterm.terminal.meta_command_processor import MetaCommandProcessor
from kogniterm.ui.terminal_ui import TerminalUI

@pytest.mark.asyncio
async def test_meta_command_processor_reset_variants():
    mock_app = MagicMock()
    mock_app._server_mode = False
    mock_agent_state = MagicMock()
    mock_llm_service = MagicMock()
    mock_llm_service.conversation_history = []
    mock_terminal_ui = MagicMock()

    processor = MetaCommandProcessor(
        kogniterm_app=mock_app,
        agent_state=mock_agent_state,
        llm_service=mock_llm_service,
        terminal_ui=mock_terminal_ui,
    )

    for cmd in ["/reset", "%reset", "reset"]:
        mock_terminal_ui.reset_mock()
        mock_agent_state.reset_mock()
        
        result = await processor.process_meta_command(cmd)
        
        assert result is True
        mock_agent_state.reset.assert_called_once()
        mock_terminal_ui.clear_chat.assert_called_once()

def test_terminal_ui_clear_chat():
    ui = TerminalUI()
    ui.console = MagicMock()
    ui.print_welcome_banner = MagicMock()
    ui.refresh_theme = MagicMock()

    ui.clear_chat()

    ui.console.clear.assert_called_once()
    ui.print_welcome_banner.assert_called_once()
