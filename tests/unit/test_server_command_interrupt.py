import asyncio
import queue
import pytest
from unittest.mock import MagicMock, patch

from kogniterm.server.session_pool import AgentSession, ServerUI
from kogniterm.terminal.command_approval_handler import CommandApprovalHandler
from kogniterm.core.command_executor import CommandExecutor


@pytest.mark.anyio
async def test_server_ui_interrupt_queue_and_cancel_pending():
    """Verifica que ServerUI mantenga interrupt_queue y que cancel_pending despierte los eventos."""
    loop = asyncio.get_running_loop()
    q = queue.Queue()
    ui = ServerUI(loop=loop, session_id="test_sess", interrupt_queue=q)

    assert ui.get_interrupt_queue() is q
    assert ui.interrupt_queue is q

    # Registrar una aprobación síncrona pendiente simulada
    import threading
    ev_sync = threading.Event()
    with ui._pending_lock:
        ui._pending_approvals["req_1"] = (ev_sync, False)

    # Cancelar pendientes
    ui.cancel_pending()
    assert ev_sync.is_set()
    with ui._pending_lock:
        _, approved = ui._pending_approvals["req_1"]
        assert approved is False


@pytest.mark.anyio
async def test_agent_session_wires_interrupt_queue_to_handlers():
    """Verifica que AgentSession configure interrupt_queue en ServerUI y CommandApprovalHandler."""
    llm_service_mock = MagicMock()
    loop = asyncio.get_running_loop()

    with patch("kogniterm.core.history_manager.HistoryManager"), \
         patch("kogniterm.core.context.workspace_context.WorkspaceContext"), \
         patch("kogniterm.core.agent_interaction.AgentInteractionRegistry.create"):
        session = AgentSession("test_session_interrupt", llm_service_mock, loop)

    assert session.interrupt_queue is not None
    assert session.ui.get_interrupt_queue() is session.interrupt_queue
    assert session.ui.interrupt_queue is session.interrupt_queue
    assert session.command_approval_handler.interrupt_queue is session.interrupt_queue
    assert session.llm_service.interrupt_queue is session.interrupt_queue


@pytest.mark.anyio
async def test_agent_session_interrupt_terminates_executor_and_cancels_ui():
    """Verifica que session.interrupt() envíe señal a interrupt_queue, termine el executor y cancele UI."""
    llm_service_mock = MagicMock()
    loop = asyncio.get_running_loop()

    with patch("kogniterm.core.history_manager.HistoryManager"), \
         patch("kogniterm.core.context.workspace_context.WorkspaceContext"), \
         patch("kogniterm.core.agent_interaction.AgentInteractionRegistry.create"):
        session = AgentSession("test_session_interrupt_2", llm_service_mock, loop)

    executor_mock = MagicMock()
    session.command_executor = executor_mock
    ui_mock = MagicMock()
    session.ui = ui_mock

    session.interrupt()

    assert not session.interrupt_queue.empty()
    assert session.interrupt_queue.get_nowait() is True
    assert session.llm_service.stop_generation_flag is True
    executor_mock.terminate.assert_called_once()
    ui_mock.cancel_pending.assert_called_once()


def test_command_approval_handler_passes_interrupt_queue_to_execute():
    """Verifica que CommandApprovalHandler pase interrupt_queue a command_executor.execute."""
    q = queue.Queue()
    terminal_ui_mock = MagicMock()
    terminal_ui_mock.get_interrupt_queue.return_value = q

    executor_mock = MagicMock()
    executor_mock.execute.return_value = ["⚠️  Comando interrumpido por el usuario.\n"]

    state_mock = MagicMock()
    state_mock.messages = []
    state_mock.tool_call_id_to_confirm = "call_test_123"

    handler = CommandApprovalHandler(
        llm_service=MagicMock(),
        command_executor=executor_mock,
        prompt_session=None,
        terminal_ui=terminal_ui_mock,
        agent_state=state_mock,
    )
    handler.auto_approve = True

    result = handler.handle_command_approval("sleep 10")

    executor_mock.execute.assert_called_once()
    _, kwargs = executor_mock.execute.call_args
    assert kwargs.get("interrupt_queue") is q
    assert "Comando interrumpido por el usuario" in result.get("tool_message_content", "")


def test_command_executor_interruption_via_queue():
    """Verifica que CommandExecutor.execute se detenga limpiamente cuando interrupt_queue recibe señal."""
    executor = CommandExecutor()
    q = queue.Queue()

    # Ponemos la señal de interrupción para que se detenga de inmediato
    q.put(True)

    chunks = list(executor.execute("sleep 5", interrupt_queue=q))
    output = "".join(chunks)

    assert "⚠️  Comando interrumpido por el usuario." in output


def test_command_approval_handler_drains_stale_interrupt_before_execution():
    """Verifica que señales residuales previas en interrupt_queue se drenen al aprobar un comando."""
    q = queue.Queue()
    # Insertar una señal residual previa
    q.put(True)

    terminal_ui_mock = MagicMock()
    terminal_ui_mock.get_interrupt_queue.return_value = q

    executor_mock = MagicMock()
    captured_queue_state = []

    def mock_execute(cmd, **kwargs):
        iq = kwargs.get("interrupt_queue")
        captured_queue_state.append(iq.empty() if iq else None)
        return ["output normal\n"]

    executor_mock.execute.side_effect = mock_execute

    state_mock = MagicMock()
    state_mock.messages = []
    state_mock.tool_call_id_to_confirm = "call_test_456"

    handler = CommandApprovalHandler(
        llm_service=MagicMock(),
        command_executor=executor_mock,
        prompt_session=None,
        terminal_ui=terminal_ui_mock,
        agent_state=state_mock,
    )
    handler.auto_approve = True

    result = handler.handle_command_approval("echo test")

    executor_mock.execute.assert_called_once()
    assert captured_queue_state == [True], "La cola de interrupción no fue vaciada antes de la ejecución"
    assert q.empty() is True
    assert "output normal" in result.get("tool_message_content", "")


def test_command_executor_drains_all_interrupt_items_on_interrupt():
    """Verifica que CommandExecutor limpie todos los ítems residuales de la cola al ser interrumpido."""
    executor = CommandExecutor()
    q = queue.Queue()

    # Poner múltiples señales
    q.put(True)
    q.put(True)
    q.put(True)

    chunks = list(executor.execute("sleep 5", interrupt_queue=q))
    output = "".join(chunks)

    assert "⚠️  Comando interrumpido por el usuario." in output
    assert q.empty() is True, "La cola de interrupción debió quedar completamente vacía"

