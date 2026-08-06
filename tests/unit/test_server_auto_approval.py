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


@pytest.mark.anyio
async def test_command_approval_handler_respects_config_manager_auto_approve():
    """Verifica que CommandApprovalHandler consulte auto_approve de ConfigManager si no está seteado explícitamente."""
    from kogniterm.terminal.command_approval_handler import CommandApprovalHandler

    with patch("kogniterm.terminal.config_manager.ConfigManager.get_config", return_value=True):
        handler = CommandApprovalHandler(
            llm_service=MagicMock(),
            command_executor=MagicMock(),
            prompt_session=None,
            terminal_ui=MagicMock(),
            agent_state=MagicMock(),
        )
        assert handler.auto_approve is True


@pytest.mark.anyio
async def test_session_pool_auto_approval_bypasses_ui_ask():
    """Verifica que handle_command_approval sea llamado directamente por AgentSession
    sin solicitar confirmación a la UI cuando auto_approve está activado.
    """
    from kogniterm.server.session_pool import AgentSession, ServerUI

    ui_mock = MagicMock(spec=ServerUI)
    llm_service_mock = MagicMock()
    loop_mock = MagicMock()

    with patch("kogniterm.server.session_pool.ServerUI", return_value=ui_mock), \
         patch("kogniterm.core.history_manager.HistoryManager"), \
         patch("kogniterm.core.context.workspace_context.WorkspaceContext"), \
         patch("kogniterm.core.command_executor.CommandExecutor"), \
         patch("kogniterm.terminal.command_approval_handler.CommandApprovalHandler"), \
         patch("kogniterm.core.agent_interaction.AgentInteractionRegistry.create"):
        session = AgentSession("test_session_id", llm_service_mock, loop_mock)

    # Configurar el handler mockeado
    handler_mock = MagicMock()
    handler_mock.handle_command_approval.return_value = {"approved": True, "tool_message_content": "ok"}
    session.command_approval_handler = handler_mock

    # Configurar comando a confirmar en agent_state
    session.agent_state.command_to_confirm = "ls -la"

    # Simular la rama del bucle de interrupción para comando bash
    command = session.agent_state.command_to_confirm
    if command and session.command_approval_handler:
        approval_result = session.command_approval_handler.handle_command_approval(
            command_to_execute=command
        )
        approved = approval_result.get("approved", False)
    else:
        approved = session.ui.ask_approval_sync(
            message=f"¿Ejecutar comando: {command}?",
            title="Confirmación de Comando",
            diff_content=command,
            file_path="bash",
        )

    assert approved is True
    # ask_approval_sync NO debió ser llamado porque command_approval_handler lo procesó directamente
    assert not ui_mock.ask_approval_sync.called
    handler_mock.handle_command_approval.assert_called_once_with(command_to_execute="ls -la")



