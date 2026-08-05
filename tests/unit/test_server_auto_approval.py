import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from kogniterm.terminal.tui.ws_client import TUIWebSocketClient
from kogniterm.terminal.tui.components.command_approval_modal import CommandApprovalModal


@pytest.mark.anyio
async def test_ws_client_auto_approves_when_auto_approve_all_is_true():
    """Prueba que TUIWebSocketClient auto-apruebe inmediatamente las solicitudes
    del servidor si self._app._auto_approve_all es True, sin montar widgets.
    """
    app_mock = MagicMock()
    app_mock._auto_approve_all = True
    app_mock.loop = asyncio.get_running_loop()

    client = TUIWebSocketClient(app=app_mock, server_url="ws://localhost:8000", session_id="test_session")
    client.send_approval = AsyncMock()

    # Invocar _handle_approval_request
    client._handle_approval_request(
        request_id="req_999",
        message="¿Ejecutar ls?",
        title="Confirmación",
        diff_content="ls",
        file_path="bash",
    )

    # Esperar tareas asíncronas
    await asyncio.sleep(0.05)

    # Verificar que NO se montó ningún widget en la app
    assert not app_mock.mount.called
    assert not app_mock.approval_container.mount.called

    # Verificar que se envió la aprobación directamente al servidor
    client.send_approval.assert_called_once_with("req_999", True)


def test_command_approval_modal_accept_all():
    """Prueba que CommandApprovalModal apoye la opción 'accept_all' al presionar botón o tecla 'a'."""
    modal = CommandApprovalModal(message="Test message", title="Test Title")
    modal.dismiss = MagicMock()

    # Simular botón "btn-always"
    event_btn = MagicMock()
    event_btn.button.id = "btn-always"
    modal.on_button_pressed(event_btn)
    modal.dismiss.assert_called_with("accept_all")

    # Simular tecla "a"
    event_key = MagicMock()
    event_key.key = "a"
    modal.on_key(event_key)
    modal.dismiss.assert_called_with("accept_all")
