import asyncio
import threading
import pytest
from kogniterm.server.session_pool import ServerUI

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
