import pytest

def test_websocket_connected_payload_structure():
    payload = {
        "type": "connected",
        "data": {
            "session_id": "test-123",
            "is_running": True,
            "live_state": {
                "thinking": "Analizando...",
                "response": "Hola",
                "terminal_entries": []
            }
        }
    }
    assert payload["data"]["is_running"] is True
    assert payload["data"]["live_state"]["thinking"] == "Analizando..."
