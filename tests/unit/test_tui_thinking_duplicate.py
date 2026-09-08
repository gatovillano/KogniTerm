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


def test_thinking_is_sequential_across_streams():
    chat_log = ChatLogWidget()

    # Simular primer stream de thinking (ej. turno 1)
    r1 = build_native_renderable("Pensamiento del turno 1", "")
    chat_log.write_stream(r1)
    first_widget = chat_log._active_thinking_widget
    assert first_widget is not None

    # Simular fin del stream del turno 1
    chat_log.stop_stream()
    assert chat_log._active_thinking_widget is None

    # Simular inicio de nuevo stream de thinking (ej. turno 2 tras ejecutar herramienta)
    r2 = build_native_renderable("Pensamiento del turno 2", "")
    chat_log.write_stream(r2)
    second_widget = chat_log._active_thinking_widget
    assert second_widget is not None

    # El nuevo pensamiento debe ser un widget nuevo e independiente (secuencial, no reemplaza al primero)
    assert second_widget is not first_widget
