import asyncio
import threading
from unittest.mock import MagicMock
import pytest
from kogniterm.server.session_pool import ServerUI
from kogniterm.terminal.tui.ws_client import TUIWebSocketClient
from kogniterm.terminal.tui.components.question_selector_modal import QuestionSelectorModal

@pytest.mark.asyncio
async def test_server_ui_ask_question():
    loop = asyncio.get_running_loop()
    server_ui = ServerUI(loop=loop, session_id="test_session")

    response_container = []

    def call_ask_question():
        res = server_ui.ask_question_sync(
            question="¿Cuál es tu color favorito?",
            options=["Azul", "Verde", "Rojo"],
            title="Preferencia de Color",
            allow_freeform=True,
        )
        response_container.append(res)

    worker_thread = threading.Thread(target=call_ask_question)
    worker_thread.start()

    # Wait a bit for worker thread to call ask_question_sync and push event
    await asyncio.sleep(0.05)

    with server_ui._pending_lock:
        assert len(server_ui._pending_questions) == 1
        req_id = list(server_ui._pending_questions.keys())[0]

    # Respond to question
    server_ui.handle_question_response(req_id, "Verde")

    worker_thread.join(timeout=1.0)
    assert not worker_thread.is_alive()
    assert response_container == ["Verde"]


@pytest.mark.asyncio
async def test_ws_client_routes_question_required_to_modal_and_sends_response():
    app_mock = MagicMock()
    app_mock.loop = asyncio.get_running_loop()
    app_mock.call_from_thread.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs)

    pushed = []

    def fake_push_screen(modal, callback=None):
        pushed.append((modal, callback))

    app_mock.push_screen.side_effect = fake_push_screen

    client = TUIWebSocketClient(
        app=app_mock,
        server_url="ws://127.0.0.1:8755",
        session_id="test_session",
    )

    event = {
        "type": "question_required",
        "data": {
            "id": "q-123",
            "question": "¿Qué arquitectura prefieres [A/B]?",
            "options": ["Opción A [rápida]", "Opción B"],
            "title": "Decisión de Arquitectura",
            "allow_freeform": False,
        },
    }

    client._route_event(event)
    # Duplicado con el mismo ID mientras está abierto no debe abrir otro modal
    client._route_event(event)

    assert len(pushed) == 1
    modal, callback = pushed[0]
    assert isinstance(modal, QuestionSelectorModal)
    assert modal.question == "¿Qué arquitectura prefieres [A/B]?"
    assert modal.options == ["Opción A [rápida]", "Opción B"]
    assert modal.title_text == "Decisión de Arquitectura"
    assert modal.allow_freeform is False

    # Simular que el usuario selecciona una opción
    callback("Opción A [rápida]")
    await asyncio.sleep(0.05)

    sent = await asyncio.wait_for(client._send_queue.get(), timeout=1.0)
    assert sent == {
        "type": "question_response",
        "id": "q-123",
        "selected": "Opción A [rápida]",
    }
    assert "q-123" not in client._active_question_ids


@pytest.mark.asyncio
async def test_ws_client_question_required_cancel_sends_default_message():
    app_mock = MagicMock()
    app_mock.loop = asyncio.get_running_loop()
    app_mock.call_from_thread.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs)

    pushed = []
    app_mock.push_screen.side_effect = lambda modal, callback=None: pushed.append((modal, callback))

    client = TUIWebSocketClient(
        app=app_mock,
        server_url="ws://127.0.0.1:8755",
        session_id="test_session",
    )

    client._route_event({
        "type": "question_required",
        "data": {
            "id": "q-cancel",
            "question": "¿Continuar?",
            "options": ["Sí", "No"],
        },
    })

    assert len(pushed) == 1
    _, callback = pushed[0]
    callback(None)
    await asyncio.sleep(0.05)

    sent = await asyncio.wait_for(client._send_queue.get(), timeout=1.0)
    assert sent == {
        "type": "question_response",
        "id": "q-cancel",
        "selected": "Cancelado por el usuario.",
    }

