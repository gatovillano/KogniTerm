import asyncio
import pytest
from unittest.mock import MagicMock, patch
from kogniterm.server.session_pool import AgentSession


@pytest.mark.anyio
async def test_session_pending_message_queue_fifo():
    """Verifica que _pop_pending_message procese la cola en orden FIFO y no pierda mensajes."""
    llm_service_mock = MagicMock()
    loop = asyncio.get_running_loop()

    with patch("kogniterm.core.history_manager.HistoryManager"), \
         patch("kogniterm.core.context.workspace_context.WorkspaceContext"), \
         patch("kogniterm.core.agent_interaction.AgentInteractionRegistry.create"):
        session = AgentSession("test_queue_session", llm_service_mock, loop)

    # Inicialmente la cola está vacía
    assert session._pop_pending_message() is None

    # Agregar múltiples mensajes pendientes
    session._pending_messages.append("mensaje 1")
    session._pending_messages.append("mensaje 2")
    session._pending_messages.append("mensaje 3")

    # Extraer uno por uno
    assert session._pop_pending_message() == "mensaje 1"
    assert session._pop_pending_message() == "mensaje 2"
    assert session._pop_pending_message() == "mensaje 3"
    assert session._pop_pending_message() is None

    # Agregar más y probar _drain_pending_messages
    session._pending_messages.extend(["msg A", "msg B"])
    drained = session._drain_pending_messages()
    assert drained == ["msg A", "msg B"]
    assert len(session._pending_messages) == 0
