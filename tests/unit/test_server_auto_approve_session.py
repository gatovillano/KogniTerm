"""Regresión: la auto-aprobación desactivada por el cliente (desktop v3) debe respetarse.

Contexto del bug:
  - `~/.kogniterm/config.json` puede tener `auto_approve: true` (o el workspace).
  - El toggle "⚡ auto" de kogniterm-desktop-v3 solo vivía en memoria del renderer,
    así que nunca llegaba al backend.
  - `CommandApprovalHandler.handle_command_approval()` re-consultaba `ConfigManager`
    en cada llamada y auto-aprobaba siempre, emitiendo nunca `approval_required`.

Contrato verificado aquí:
  1. Sin preferencia del cliente  -> manda la config global (comportamiento previo intacto).
  2. Cliente fija False            -> la sesión NO auto-aprueba (debe preguntar).
  3. Cliente fija True             -> la sesión auto-aprueba sin emitir evento.
  4. La sesión pasa el valor resuelto al handler, así el handler no re-consulta
     ConfigManager y no pisa la preferencia del cliente.
"""

from __future__ import annotations

import asyncio
import queue
from pathlib import Path
from typing import Optional

import pytest

from kogniterm.server.session_pool import ServerUI


def _make_ui(loop: asyncio.AbstractEventLoop, session_id: str = "s1") -> ServerUI:
    """ServerUI mínimo, sin tocar disco ni red (solo la machinery de aprobaciones)."""
    ui = ServerUI(loop=loop, session_id=session_id, interrupt_queue=queue.Queue())
    return ui


def _global_auto_approve(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    """Fuerza el valor de `auto_approve` que vería ConfigManager."""
    import kogniterm.terminal.config_manager as cm_mod

    monkeypatch.setattr(
        cm_mod.ConfigManager,
        "get_config",
        lambda self, key=None: value if key == "auto_approve" else {},
    )


class TestServerUIAutoApprove:
    def test_default_follows_global_config(self, monkeypatch: pytest.MonkeyPatch):
        """Sin preferencia del cliente, manda la config global (no regresión)."""
        loop = asyncio.new_event_loop()
        try:
            ui = _make_ui(loop)
            _global_auto_approve(monkeypatch, True)
            assert ui._client_auto_approve is None
            assert ui.resolve_auto_approve() is True

            _global_auto_approve(monkeypatch, False)
            assert ui.resolve_auto_approve() is False
        finally:
            loop.close()

    def test_client_false_overrides_global_true(self, monkeypatch: pytest.MonkeyPatch):
        """El bug: config global activa + toggle del cliente OFF => preguntar."""
        loop = asyncio.new_event_loop()
        try:
            ui = _make_ui(loop)
            _global_auto_approve(monkeypatch, True)
            ui.set_client_auto_approve(False)
            assert ui.resolve_auto_approve() is False
        finally:
            loop.close()

    def test_client_true_overrides_global_false(self, monkeypatch: pytest.MonkeyPatch):
        loop = asyncio.new_event_loop()
        try:
            ui = _make_ui(loop)
            _global_auto_approve(monkeypatch, False)
            ui.set_client_auto_approve(True)
            assert ui.resolve_auto_approve() is True
        finally:
            loop.close()

    def test_client_none_restores_global(self, monkeypatch: pytest.MonkeyPatch):
        """Devolver a None devuelve el control a la config global."""
        loop = asyncio.new_event_loop()
        try:
            ui = _make_ui(loop)
            ui.set_client_auto_approve(False)
            ui.set_client_auto_approve(None)
            _global_auto_approve(monkeypatch, True)
            assert ui.resolve_auto_approve() is True
        finally:
            loop.close()

    def test_ask_approval_sync_blocks_when_client_disabled(self, monkeypatch: pytest.MonkeyPatch):
        """Con el cliente en OFF debe emitir el evento y esperar respuesta real."""
        loop = asyncio.new_event_loop()
        try:
            ui = _make_ui(loop)
            _global_auto_approve(monkeypatch, True)  # global dice "auto"
            ui.set_client_auto_approve(False)       # el usuario lo apagó en la UI

            published: list = []
            ui._push = lambda t, d: published.append((t, d))  # type: ignore[assignment]

            # Lanzamos en un hilo: ask_approval_sync bloquea esperando la respuesta.
            import threading

            result: list = []

            def worker():
                result.append(
                    ui.ask_approval_sync(message="¿Ejecutar?", title="Confirmación")
                )

            th = threading.Thread(target=worker, daemon=True)
            th.start()

            # Esperamos a que se publique el evento approval_required.
            import time

            for _ in range(50):
                if published:
                    break
                time.sleep(0.02)

            assert published, "debería emitir approval_required cuando el cliente disables auto-approve"
            assert published[0][0] == "approval_required"

            # El worker sigue bloqueado: la decisión la toma el usuario.
            th.join(timeout=0.2)
            assert th.is_alive(), "no debe aprobar solo: debe esperar al usuario"
            assert result == []
        finally:
            loop.close()

    def test_ask_approval_sync_autoresolves_when_client_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Con el cliente en ON resuelve True y NO emite evento (auto-approve)."""
        loop = asyncio.new_event_loop()
        try:
            ui = _make_ui(loop)
            _global_auto_approve(monkeypatch, False)
            ui.set_client_auto_approve(True)

            published: list = []
            ui._push = lambda t, d: published.append((t, d))  # type: ignore[assignment]

            assert ui.ask_approval_sync(message="¿Ejecutar?", title="Confirmación") is True
            assert published == [], "en auto-approve no debe emitirse approval_required"
        finally:
            loop.close()

    def test_tui_path_unaffected_by_default_none(self, monkeypatch: pytest.MonkeyPatch):
        """La TUI nunca envía set_auto_approve: queda en None y el flujo no cambia.

        Con None, ask_approval_sync NO resuelve solo (compatibilidad con la TUI,
        que decide en su propia capa de UI tras recibir el evento).
        """
        loop = asyncio.new_event_loop()
        try:
            ui = _make_ui(loop)
            _global_auto_approve(monkeypatch, True)  # config global activa
            assert ui._client_auto_approve is None

            published: list = []
            ui._push = lambda t, d: published.append((t, d))  # type: ignore[assignment]

            import threading
            import time

            result: list = []
            th = threading.Thread(
                target=lambda: result.append(
                    ui.ask_approval_sync(message="¿Ejecutar?", title="Confirmación")
                ),
                daemon=True,
            )
            th.start()
            for _ in range(50):
                if published:
                    break
                time.sleep(0.02)

            assert published and published[0][0] == "approval_required"
            th.join(timeout=0.2)
            assert th.is_alive()
        finally:
            loop.close()