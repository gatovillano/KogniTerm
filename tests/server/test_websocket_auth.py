import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from kogniterm.server.app import create_app, API_TOKEN

def test_websocket_require_token_dependency():
    """Verifica que la dependencia require_token no falle con TypeError en rutas WebSocket."""
    app = create_app()
    client = TestClient(app)
    
    # Conexión WebSocket con token válido
    with client.websocket_connect(f"/ws/test-session?token={API_TOKEN}") as websocket:
        # Si la conexión se acepta o procede sin error 500, require_token funcionó correctamente
        assert websocket is not None

def test_websocket_invalid_token():
    """Verifica que un token inválido en WebSocket sea rechazado limpiamente."""
    app = create_app()
    client = TestClient(app)
    
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/test-session?token=invalid_token"):
            pass

def test_get_api_token_resolution():
    """Verifica que get_api_token() devuelva el token activo del servidor."""
    from kogniterm.terminal.tui.ws_client import get_api_token
    token = get_api_token()
    assert token == API_TOKEN

