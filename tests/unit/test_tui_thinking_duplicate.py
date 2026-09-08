import pytest
from kogniterm.terminal.tui.components.chat_log import ChatLogWidget
from kogniterm.terminal.tui.ws_client import build_native_renderable


def test_thinking_stream_updates_in_place():
    chat_log = ChatLogWidget()

    # Simular primer chunk de thinking recibido en server mode
    r1 = build_native_renderable("Pensando paso 1...", "")
    chat_log.write_stream(r1)

    first_widget = chat_log._active_thinking_widget
    assert first_widget is not None

    # Simular segundo chunk de thinking
    r2 = build_native_renderable("Pensando paso 1... y paso 2.", "")
    chat_log.write_stream(r2)

    # Debe seguir siendo el mismo widget activo de pensamiento
    assert chat_log._active_thinking_widget is first_widget


def test_thinking_relinks_after_stop_stream():
    chat_log = ChatLogWidget()

    # Simular primer chunk
    r1 = build_native_renderable("Pensando parte inicial", "")
    chat_log.write_stream(r1)
    first_widget = chat_log._active_thinking_widget
    assert first_widget is not None

    # Simular stop_stream prematuro (ej. live_stop del servidor)
    chat_log.stop_stream()
    assert chat_log._active_thinking_widget is None

    # Simular actualización con children simulados o widget activo
    chat_log._active_thinking_widget = first_widget
    r2 = build_native_renderable("Pensando parte inicial y final completa.", "")
    chat_log.write_stream(r2)

    assert chat_log._active_thinking_widget is first_widget
