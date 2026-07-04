import pytest
from unittest.mock import MagicMock
from kogniterm.terminal.tui.tui_app import KogniTermTUI
from kogniterm.terminal.tui.ws_client import TUIWebSocketClient

@pytest.mark.anyio
async def test_tui_server_fallback_and_reconnect():
    # Mock llm_service
    llm_service = MagicMock()
    llm_service.model_name = "local-model"
    
    # Initialize App with mocked service
    app = KogniTermTUI(llm_service=llm_service)
    
    # Mock call_from_thread to execute synchronously for the test
    app.call_from_thread = lambda f, *args, **kwargs: f(*args, **kwargs)
    
    # Explicitly set server mode and setup status footer mock
    app._server_mode = True
    app.status_footer = MagicMock()
    app.tui_ui = MagicMock()
    
    # Verify starting conditions
    assert app._server_mode is True
    
    # Create the WS Client
    client = TUIWebSocketClient(app, "ws://localhost:8765", "test_session")
    client._connected = True
    
    # Simulate connection loss using _handle_disconnect
    client._handle_disconnect("Connection refused")
    
    # Verify state transitions:
    # 1. client._connected should be False
    assert client._connected is False
    # 2. app._server_mode should have switched to False (local mode fallback)
    assert app._server_mode is False
    # 3. app.status_footer should be updated with the local model
    app.status_footer.update_model.assert_called_with("local-model")
    # 4. A warning message should be printed
    app.tui_ui.print_message.assert_any_call(
        "🔌 Conexión al servidor perdida. Cambiando al modo local autónomo.",
        "yellow",
    )
    
    # Reset mocks to test reconnection
    app.tui_ui.print_message.reset_mock()
    
    # Simulate successful reconnection
    app.switch_to_server_mode()
    
    # Verify state transitions:
    # 1. app._server_mode should be True
    assert app._server_mode is True
    # 2. A success message should be printed
    app.tui_ui.print_message.assert_called_once_with(
        "🔗 Conectado al servidor KogniTerm (modo servidor activo).",
        "green",
    )
