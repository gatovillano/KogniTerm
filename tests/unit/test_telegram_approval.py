import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kogniterm.server.session_pool import ServerUI, pool
from kogniterm.server.channel_adapters import TelegramAdapter


@pytest.mark.anyio
async def test_server_ui_broadcast_queue():
    """Prueba que el patrón de Broadcast Queue en ServerUI envíe eventos
    concurrente a todos los consumidores registrados sin competencia/robo.
    """
    loop = asyncio.get_running_loop()
    ui = ServerUI(loop=loop, session_id="test_broadcast_session")
    
    # Iniciar dos consumidores concurrentes
    events_1 = []
    events_2 = []
    
    async def consume_1():
        async for event in ui.events():
            events_1.append(event)
            if event["type"] == "done":
                break
                
    async def consume_2():
        async for event in ui.events():
            events_2.append(event)
            if event["type"] == "done":
                break

    task_1 = asyncio.create_task(consume_1())
    task_2 = asyncio.create_task(consume_2())
    
    # Dar tiempo para que se registren los generadores (las colas)
    await asyncio.sleep(0.05)
    
    # Emitir algunos eventos desde un hilo
    ui._push("stream", "hello")
    ui._push("stream", " world")
    ui._push("done", {})
    
    # Esperar a que terminen ambos consumidores
    await asyncio.gather(task_1, task_2)
    
    # Verificar que AMBOS recibieron todos los eventos intactos y en el mismo orden
    assert len(events_1) == 3
    assert len(events_2) == 3
    assert [e["type"] for e in events_1] == ["stream", "stream", "done"]
    assert [e["type"] for e in events_2] == ["stream", "stream", "done"]
    assert events_1[0]["data"] == "hello"
    assert events_2[0]["data"] == "hello"
    assert events_1[1]["data"] == " world"
    assert events_2[1]["data"] == " world"


@pytest.mark.anyio
async def test_telegram_adapter_handle_callback_query_approved():
    """Prueba que _handle_callback_query de TelegramAdapter responda correctamente
    y actualice el reply_markup indicando la aprobación (Aprobado).
    """
    # Mocks para Telegram
    update = MagicMock()
    update.effective_chat.id = 12345
    
    query = AsyncMock()
    query.data = "approve:req_123"
    update.callback_query = query
    
    context = MagicMock()
    
    # Instanciar el adaptador de Telegram
    adapter = TelegramAdapter(token="fake_token", session_id="test_adapter_session")
    adapter._chat_sessions[12345] = "telegram_12345"
    
    # Crear un mock de sesión
    session_mock = MagicMock()
    session_mock.ui = MagicMock()
    
    with patch("kogniterm.server.session_pool.pool.get", return_value=session_mock):
        await adapter._handle_callback_query(update, context)
        
        # Debe despertar al thread worker indicando la aprobación
        session_mock.ui.handle_approval_response.assert_called_once_with("req_123", True)
        
        # Debe responder a la CallbackQuery con un toast/alerta de éxito
        query.answer.assert_called_once_with(text="✅ Aprobado")
        
        # Debe actualizar únicamente el reply_markup (teclado inline)
        query.edit_message_reply_markup.assert_called_once()
        args, kwargs = query.edit_message_reply_markup.call_args
        reply_markup = kwargs.get("reply_markup") or args[0]
        
        # Verificar que el reply_markup contiene un solo botón de "🟢 Aprobado"
        assert len(reply_markup.inline_keyboard) == 1
        assert len(reply_markup.inline_keyboard[0]) == 1
        button = reply_markup.inline_keyboard[0][0]
        assert button.text == "🟢 Aprobado"
        assert button.callback_data == "none"


@pytest.mark.anyio
async def test_telegram_adapter_handle_callback_query_denied():
    """Prueba que _handle_callback_query de TelegramAdapter responda correctamente
    y actualice el reply_markup indicando la denegación (Denegado).
    """
    update = MagicMock()
    update.effective_chat.id = 12345
    
    query = AsyncMock()
    query.data = "deny:req_123"
    update.callback_query = query
    
    context = MagicMock()
    
    adapter = TelegramAdapter(token="fake_token", session_id="test_adapter_session")
    adapter._chat_sessions[12345] = "telegram_12345"
    
    session_mock = MagicMock()
    session_mock.ui = MagicMock()
    
    with patch("kogniterm.server.session_pool.pool.get", return_value=session_mock):
        await adapter._handle_callback_query(update, context)
        
        # Debe despertar al thread worker indicando la denegación
        session_mock.ui.handle_approval_response.assert_called_once_with("req_123", False)
        
        # Debe responder a la CallbackQuery con un toast/alerta de denegación
        query.answer.assert_called_once_with(text="❌ Denegado")
        
        # Debe actualizar únicamente el reply_markup
        query.edit_message_reply_markup.assert_called_once()
        args, kwargs = query.edit_message_reply_markup.call_args
        reply_markup = kwargs.get("reply_markup") or args[0]
        
        button = reply_markup.inline_keyboard[0][0]
        assert button.text == "🔴 Denegado"
        assert button.callback_data == "none"


@pytest.mark.anyio
async def test_telegram_adapter_handle_callback_query_expired():
    """Prueba que si la sesión no se encuentra en el pool, se actualice el
    reply_markup a "❌ Sesión expirada" y responda con toast de advertencia.
    """
    update = MagicMock()
    update.effective_chat.id = 12345
    
    query = AsyncMock()
    query.data = "approve:req_123"
    update.callback_query = query
    
    context = MagicMock()
    
    adapter = TelegramAdapter(token="fake_token", session_id="test_adapter_session")
    adapter._chat_sessions[12345] = "telegram_12345"
    
    # Retornar None simulando que la sesión ya no existe en el pool
    with patch("kogniterm.server.session_pool.pool.get", return_value=None):
        await adapter._handle_callback_query(update, context)
        
        # Debe responder con un toast indicando que expiró
        query.answer.assert_called_once_with(text="⚠️ Sesión expirada o inactiva")
        
        # Debe actualizar el reply_markup a "❌ Sesión expirada"
        query.edit_message_reply_markup.assert_called_once()
        args, kwargs = query.edit_message_reply_markup.call_args
        reply_markup = kwargs.get("reply_markup") or args[0]
        
        button = reply_markup.inline_keyboard[0][0]
        assert button.text == "❌ Sesión expirada"
        assert button.callback_data == "none"
