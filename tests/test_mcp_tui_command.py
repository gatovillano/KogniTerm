import pytest
from unittest.mock import AsyncMock, MagicMock
from kogniterm.terminal.tui.command_processor import TUICommandProcessor
from kogniterm.terminal.meta_command_processor import MetaCommandProcessor
from kogniterm.terminal.config_manager import ConfigManager
from kogniterm.core.mcp.mcp_manager import MCPManager

@pytest.mark.asyncio
async def test_tui_command_processor_mcp():
    mock_app = MagicMock()
    mock_ui = MagicMock()
    mock_ui.print_message = MagicMock()
    mock_ui.ask_radiolist_async = AsyncMock(return_value=None)
    mock_app.tui_ui = mock_ui
    mock_app.llm_service = MagicMock()

    proc = TUICommandProcessor(mock_app)

    # Test /mcp list
    handled = await proc.process_command("/mcp list")
    assert handled is True
    assert mock_ui.print_message.called

    # Test /mcp add
    mock_ui.print_message.reset_mock()
    handled = await proc.process_command("/mcp add test_add echo hello")
    assert handled is True
    cm = ConfigManager()
    servers = cm.get_mcp_servers()
    assert "test_add" in servers

    # Test /mcp toggle
    handled = await proc.process_command("/mcp toggle test_add")
    assert handled is True
    assert cm.get_mcp_servers()["test_add"]["disabled"] is True

    # Test /mcp reload
    handled = await proc.process_command("/mcp reload")
    assert handled is True

    # Test /mcp remove
    handled = await proc.process_command("/mcp remove test_add")
    assert handled is True
    assert "test_add" not in cm.get_mcp_servers()

@pytest.mark.asyncio
async def test_meta_command_processor_mcp():
    mock_llm = MagicMock()
    mock_state = MagicMock()
    mock_ui = MagicMock()
    mock_ui.print_message = MagicMock()
    mock_ui.console = MagicMock()
    mock_app = MagicMock()

    proc = MetaCommandProcessor(mock_llm, mock_state, mock_ui, mock_app)

    # Test /mcp list
    handled = await proc.process_meta_command("/mcp list")
    assert handled is True

    # Test /mcp add
    handled = await proc.process_meta_command("/mcp add cli_test echo hello")
    assert handled is True
    cm = ConfigManager()
    assert "cli_test" in cm.get_mcp_servers()

    # Test /mcp toggle
    handled = await proc.process_meta_command("/mcp toggle cli_test")
    assert handled is True
    assert cm.get_mcp_servers()["cli_test"]["disabled"] is True

    # Test /mcp remove
    handled = await proc.process_meta_command("/mcp remove cli_test")
    assert handled is True
    assert "cli_test" not in cm.get_mcp_servers()
