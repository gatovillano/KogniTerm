"""Tests de regresión para la recuperación de BadRequestError en LLMBridge.

Escenario real que motivó el fix (nov 2026): el gateway "stealth"
(kilocode/stealth/*) falla con 400 genérico de forma intermitente. La escalera
anterior de reintentos destruya el historial completo en el intento 2
(`messages[:] = [last_user]`), por lo que el agente respondía SIN NINGÚN
contexto en cada turno ("pierde el historial tras cada mensaje").
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from kogniterm.core.ai_cli_bridge.llm_bridge import LLMBridge, _build_retry_window
from litellm.exceptions import BadRequestError


def _mk_history(n_pairs: int):
    """Historial realista: system + N turnos user/assistant."""
    msgs = [{"role": "system", "content": "SYSTEM PROMPT"}]
    for i in range(n_pairs):
        msgs.append({"role": "user", "content": f"pregunta {i}"})
        msgs.append({"role": "assistant", "content": f"respuesta {i}"})
    return msgs


def _bad_request():
    return BadRequestError(
        message="The stealth model could not complete the request.",
        model="stealth/glyph-cluster",
        llm_provider="openai",
    )


@pytest.mark.asyncio
async def test_badrequest_keeps_recent_context_not_only_last_user():
    """El reintento 2 debe conservar system + contexto reciente, no solo el último user."""
    bridge = LLMBridge(model="stealth/glyph-cluster")
    history = _mk_history(40)  # 81 mensajes

    async def mock_stream():
        chunk = MagicMock()
        chunk.choices = [MagicMock(delta=MagicMock(
            content="respuesta final",
            reasoning_content=None, thinking=None, reasoning=None,
            thinking_content=None, tool_calls=None,
        ))]
        yield chunk

    # Los 2 primeros intentos fallan con 400, el 3º tiene éxito
    mock_acompletion = AsyncMock(side_effect=[_bad_request(), _bad_request(), mock_stream()])

    with patch.object(bridge, "_resolve_model_provider", return_value=("stealth/glyph-cluster", {})), \
         patch("litellm.acompletion", mock_acompletion):
        events = []
        async for ev in bridge.chat(messages=history, max_steps=5):
            events.append(ev)

    assert any(e["type"] == "done" for e in events)

    # El payload del 3er intento debe conservar el system y contexto reciente
    third_call_messages = mock_acompletion.call_args_list[2].kwargs["messages"]
    assert len(third_call_messages) > 1, (
        "El reintento no debe reducir el payload a un solo mensaje"
    )
    assert third_call_messages[0]["role"] == "system"
    # Debe incluir más de un turno de conversación
    user_msgs = [m for m in third_call_messages if m.get("role") == "user"]
    assert len(user_msgs) >= 2


@pytest.mark.asyncio
async def test_badrequest_final_resort_still_limits_to_last_user():
    """Si el modelo falla 3 veces, el último recurso sigue siendo el último user."""
    bridge = LLMBridge(model="stealth/glyph-cluster")
    history = _mk_history(40)

    call_snapshots = []

    async def fake_acompletion(**kwargs):
        call_snapshots.append(list(kwargs["messages"]))
        if len(call_snapshots) <= 3:
            raise _bad_request()

        async def gen():
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(
                content="Resultado final del análisis completado",
                reasoning_content=None, thinking=None, reasoning=None,
                thinking_content=None, tool_calls=None,
            ))]
            yield chunk

        return gen()

    with patch.object(bridge, "_resolve_model_provider", return_value=("stealth/glyph-cluster", {})), \
         patch("litellm.acompletion", fake_acompletion):
        events = []
        async for ev in bridge.chat(messages=history, max_steps=5):
            events.append(ev)

    assert any(e["type"] == "done" for e in events)
    assert len(call_snapshots) == 4
    # Último recurso (4º intento): solo el último mensaje del usuario
    assert len(call_snapshots[3]) == 1
    assert call_snapshots[3][0]["role"] == "user"


def test_build_retry_window_preserves_system_and_opens_at_user_turn():
    msgs = _mk_history(40)
    window = _build_retry_window(msgs, max_keep=20)
    assert window[0]["role"] == "system"
    assert len(window) <= 21
    assert window[1]["role"] == "user"


def test_build_retry_window_never_starts_mid_tool_pair():
    """La ventana nunca abre a mitad de un par assistant(tool_calls)+tool."""
    msgs = [{"role": "system", "content": "S"}]
    for t in range(6):
        msgs.append({"role": "user", "content": f"u{t}"})
        msgs.append({
            "role": "assistant", "content": "",
            "tool_calls": [{"id": f"c{t}", "type": "function",
                            "function": {"name": "tool", "arguments": "{}"}}],
        })
        msgs.append({"role": "tool", "tool_call_id": f"c{t}", "content": "out"})
    window = _build_retry_window(msgs, max_keep=10)
    assert window[0]["role"] == "system"
    # El primer mensaje del cuerpo nunca es un tool huérfano
    assert window[1]["role"] != "tool"


def test_build_retry_window_short_history_untouched():
    msgs = _mk_history(3)
    assert _build_retry_window(msgs, max_keep=20) == msgs
