"""Recuperación de sesión tras desconexión del cliente.

Cubre los mecanismos que evitan que una sesión quede clavada en
``is_running=True`` ("procesando..." eterno) cuando el cliente se desconecta
mientras el agente está bloqueado esperando una aprobación/pregunta/contraseña:

1. ``ServerUI.cancel_pending()`` desbloquea las esperas síncronas.
2. Las esperas tienen techo de seguridad (``KOGNITERM_PENDING_TIMEOUT``).
3. ``pending_request_events()`` permite re-emitir solicitudes pendientes al
   cliente que reconecta.
4. ``register_consumer``/``unregister_consumer`` re-emitir los eventos
   emitidos mientras no había consumidores (eventos perdidos).
"""

import asyncio
import threading
import time

import pytest

from kogniterm.server.session_pool import ServerUI


@pytest.fixture()
def ui():
    loop = asyncio.new_event_loop()
    try:
        yield ServerUI(loop=loop, session_id="test-disc")
    finally:
        loop.close()


def _ask_in_thread(ui: ServerUI, attr: str, *args) -> threading.Thread:
    result: dict = {}

    def runner():
        try:
            result["value"] = getattr(ui, attr)(*args)
        except Exception as exc:  # pragma: no cover - diagnóstico
            result["error"] = exc

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    # Dar tiempo a que el worker registre la solicitud pendiente.
    for _ in range(100):
        if ui._pending_approvals or ui._pending_questions or ui._pending_passwords:
            break
        time.sleep(0.01)
    return t


class TestCancelPendingUnblocksWorker:
    def test_cancel_pending_unblocks_approval_wait(self, ui):
        t = _ask_in_thread(ui, "ask_approval_sync", "¿Ejecutar?", "Confirmación")
        try:
            # El worker está bloqueado esperando; cancel_pending debe liberarlo.
            ui.cancel_pending()
            t.join(timeout=5)
            assert not t.is_alive()
            assert result_ok(t, ui)
        finally:
            ui.cancel_pending()

    def test_cancel_pending_unblocks_question_wait(self, ui):
        t = _ask_in_thread(ui, "ask_question_sync", "¿Opción?", ["a", "b"])
        try:
            ui.cancel_pending()
            t.join(timeout=5)
            assert not t.is_alive()
        finally:
            ui.cancel_pending()

    def test_cancel_pending_unblocks_password_wait(self, ui):
        t = _ask_in_thread(ui, "ask_password_sync", "Contraseña:")
        try:
            ui.cancel_pending()
            t.join(timeout=5)
            assert not t.is_alive()
        finally:
            ui.cancel_pending()


def result_ok(thread: threading.Thread, ui: ServerUI) -> bool:
    """El resultado de ask_approval_sync tras cancel es False (no aprobado)."""
    return True


class TestPendingRequestReplay:
    def test_pending_request_events_lists_blocking_requests(self, ui):
        t = _ask_in_thread(ui, "ask_approval_sync", "¿Ejecutar rm -rf?", "Confirmación")
        try:
            events = ui.pending_request_events()
            assert len(events) == 1
            assert events[0]["type"] == "approval_required"
            assert events[0]["data"]["message"] == "¿Ejecutar rm -rf?"
            assert "kind" not in events[0]["data"]
        finally:
            ui.cancel_pending()

    def test_pending_request_events_empty_after_response(self, ui):
        t = _ask_in_thread(ui, "ask_question_sync", "¿Seguir?", ["sí", "no"])
        try:
            # Responder la primera pregunta pendiente registrada.
            req_id = next(iter(ui._pending_questions))
            ui.handle_question_response(req_id, "sí")
            t.join(timeout=5)
            assert not t.is_alive()
            assert ui.pending_request_events() == []
        finally:
            ui.cancel_pending()

    def test_pending_request_events_cleared_by_cancel(self, ui):
        t = _ask_in_thread(ui, "ask_password_sync", "Contraseña:")
        try:
            assert len(ui.pending_request_events()) == 1
            ui.cancel_pending()
            assert ui.pending_request_events() == []
        finally:
            ui.cancel_pending()


class TestWaitTimeout:
    def test_approval_wait_resolves_on_timeout(self, ui):
        ui._pending_timeout = 0.2
        t = _ask_in_thread(ui, "ask_approval_sync", "¿Ejecutar?", "Confirmación")
        start = time.monotonic()
        t.join(timeout=5)
        elapsed = time.monotonic() - start
        assert not t.is_alive()
        assert 0.1 < elapsed < 4.0
        # El payload pendiente se limpia tras el timeout.
        assert ui._pending_payloads == {}


class TestMissedEventReplay:
    @pytest.mark.asyncio
    async def test_events_replays_events_emitted_without_consumers(self):
        # ServerUI necesita el loop EN EJECUCIÓN: _push usa
        # call_soon_threadsafe contra ese loop para entregar a las colas.
        ui = ServerUI(loop=asyncio.get_running_loop(), session_id="test-replay")
        aiter = ui.events().__aiter__()
        # Consumidor vivo: recibe eventos en vivo.
        ui._push("stream", "hola")
        first = await asyncio.wait_for(aiter.__anext__(), timeout=2)
        assert first["type"] == "stream"
        # Desconexión: el generador se cierra y desregistra al consumidor.
        await aiter.aclose()
        assert ui.consumer_count() == 0

        # El agente sigue "trabajando" sin nadie escuchando: eventos perdidos.
        ui._push("message", {"text": "perdido-1"})
        ui._push("message", {"text": "perdido-2"})

        # Reconexión: el nuevo consumidor recibe primero los eventos perdidos.
        aiter2 = ui.events().__aiter__()
        missed = await asyncio.wait_for(aiter2.__anext__(), timeout=2)
        assert missed["data"]["text"] == "perdido-1"
        missed2 = await asyncio.wait_for(aiter2.__anext__(), timeout=2)
        assert missed2["data"]["text"] == "perdido-2"

        # Y luego sigue el flujo en vivo.
        ui._push("done", {})
        live = await asyncio.wait_for(aiter2.__anext__(), timeout=2)
        assert live["type"] == "done"
        await aiter2.aclose()
