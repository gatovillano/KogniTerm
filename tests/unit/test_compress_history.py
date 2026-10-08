import asyncio
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from kogniterm.core.llm_service import LLMService
from kogniterm.server.session_pool import AgentSession


def test_llm_service_has_compress_history():
    """Verifica que LLMService posea el método compress_history y delegue en summarize_conversation_history."""
    service = LLMService(use_multi_provider=False)
    with patch.object(service, "summarize_conversation_history", return_value="Resumen de prueba") as mock_summarize:
        test_messages = [
            HumanMessage(content="¿Cómo configuro el servidor?"),
            AIMessage(content="Debes ejecutar python main.py"),
        ]
        res = service.compress_history(test_messages, force_truncate=True)
        assert res == "Resumen de prueba"
        mock_summarize.assert_called_once_with(
            messages_to_summarize=test_messages,
            force_truncate=True
        )


@pytest.mark.anyio
async def test_agent_session_process_message_compact_success():
    """Verifica que AgentSession procese /compact exitosamente usando compress_history."""
    llm_service_mock = MagicMock()
    llm_service_mock.compress_history.return_value = "Resumen condensado de la conversación"
    llm_service_mock.max_history_messages = 50
    llm_service_mock.max_history_chars = 100000
    llm_service_mock.auto_save_interval = 10

    loop = asyncio.get_running_loop()
    executor = MagicMock()
    # Ejecutar síncronamente cuando run_in_executor sea awaited
    async def fake_run_in_executor(executor, func, *args):
        return func(*args)

    with patch("kogniterm.core.history_manager.HistoryManager"), \
         patch("kogniterm.core.context.workspace_context.WorkspaceContext"), \
         patch("kogniterm.core.agent_interaction.AgentInteractionRegistry.create"), \
         patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):

        session = AgentSession("test_compact_session", llm_service_mock, loop)
        session.thread_manager = MagicMock()

        # Añadir 3 mensajes para superar el umbral de > 2
        session.agent_state.messages = [
            HumanMessage(content="Hola"),
            AIMessage(content="Hola, ¿en qué te ayudo?"),
            HumanMessage(content="Quiero listar los archivos"),
        ]

        await session.send("/compact", executor=executor)

        # Verificar que se llamó a compress_history
        llm_service_mock.compress_history.assert_called_once()

        # Verificar que el estado del agente se actualizó con el resumen
        assert len(session.agent_state.messages) == 1
        assert isinstance(session.agent_state.messages[0], SystemMessage)
        assert "Resumen condensado de la conversación" in session.agent_state.messages[0].content

        # Verificar que se sincronizó con el thread_manager
        session.thread_manager.save_thread_messages.assert_called_once()


@pytest.mark.anyio
async def test_agent_session_process_message_compact_fallback_summarize():
    """Verifica que AgentSession soporte fallback a summarize_conversation_history si compress_history falta en el objeto."""
    llm_service_mock = MagicMock(spec=["summarize_conversation_history", "max_history_messages", "max_history_chars", "auto_save_interval"])
    llm_service_mock.summarize_conversation_history.return_value = "Resumen vía fallback"
    llm_service_mock.max_history_messages = 50
    llm_service_mock.max_history_chars = 100000
    llm_service_mock.auto_save_interval = 10

    loop = asyncio.get_running_loop()
    async def fake_run_in_executor(executor, func, *args):
        return func(*args)

    with patch("kogniterm.core.history_manager.HistoryManager"), \
         patch("kogniterm.core.context.workspace_context.WorkspaceContext"), \
         patch("kogniterm.core.agent_interaction.AgentInteractionRegistry.create"), \
         patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):

        session = AgentSession("test_compact_fallback_session", llm_service_mock, loop)
        session.thread_manager = MagicMock()

        session.agent_state.messages = [
            HumanMessage(content="Msg 1"),
            AIMessage(content="Msg 2"),
            HumanMessage(content="Msg 3"),
        ]

        await session.send("/compress", executor=MagicMock())

        llm_service_mock.summarize_conversation_history.assert_called_once()
        assert len(session.agent_state.messages) == 1
        assert "Resumen vía fallback" in session.agent_state.messages[0].content


@pytest.mark.anyio
async def test_agent_session_compact_short_history_warns_and_does_not_modify():
    """Verifica que un historial corto (<=2 mensajes) no sea modificado y avise al usuario."""
    llm_service_mock = MagicMock()
    llm_service_mock.max_history_messages = 50
    llm_service_mock.max_history_chars = 100000
    llm_service_mock.auto_save_interval = 10

    loop = asyncio.get_running_loop()

    with patch("kogniterm.core.history_manager.HistoryManager"), \
         patch("kogniterm.core.context.workspace_context.WorkspaceContext"), \
         patch("kogniterm.core.agent_interaction.AgentInteractionRegistry.create"):

        session = AgentSession("test_compact_short", llm_service_mock, loop)
        session.agent_state.messages = [
            HumanMessage(content="Msg 1"),
            AIMessage(content="Msg 2"),
        ]

        await session.send("/compact", executor=MagicMock())

        assert len(session.agent_state.messages) == 2
        assert not llm_service_mock.compress_history.called


@pytest.mark.anyio
async def test_agent_session_compact_error_does_not_wipe_history():
    """Verifica que si la compresión falla o devuelve error, el historial original no sea destruido."""
    llm_service_mock = MagicMock()
    llm_service_mock.compress_history.return_value = "Error: Timeout calling LLM"
    llm_service_mock.max_history_messages = 50
    llm_service_mock.max_history_chars = 100000
    llm_service_mock.auto_save_interval = 10

    loop = asyncio.get_running_loop()
    async def fake_run_in_executor(executor, func, *args):
        return func(*args)

    with patch("kogniterm.core.history_manager.HistoryManager"), \
         patch("kogniterm.core.context.workspace_context.WorkspaceContext"), \
         patch("kogniterm.core.agent_interaction.AgentInteractionRegistry.create"), \
         patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):

        session = AgentSession("test_compact_error", llm_service_mock, loop)
        orig_msgs = [
            HumanMessage(content="Msg 1"),
            AIMessage(content="Msg 2"),
            HumanMessage(content="Msg 3"),
        ]
        session.agent_state.messages = list(orig_msgs)

        await session.send("/compact", executor=MagicMock())

        # El historial debe preservarse y no reemplazarse con el mensaje de error
        assert len(session.agent_state.messages) == 3
        assert session.agent_state.messages[0].content == "Msg 1"

