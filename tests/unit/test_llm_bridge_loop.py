import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from kogniterm.core.ai_cli_bridge.llm_bridge import LLMBridge

@pytest.mark.asyncio
async def test_llm_bridge_executes_tools_and_loops_for_final_answer():
    bridge = LLMBridge(model="test-model")

    # Simular turno 1: modelo pide herramienta "read_file"
    chunk_t1_tc = MagicMock()
    tc1 = MagicMock()
    tc1.index = 0
    tc1.id = "call_123"
    tc1.function.name = "read_file"
    tc1.function.arguments = '{"path": "test.txt"}'
    chunk_t1_tc.choices = [MagicMock(delta=MagicMock(content=None, reasoning_content=None, thinking=None, reasoning=None, thinking_content=None, tool_calls=[tc1]))]

    # Simular turno 2: modelo genera la respuesta final basada en el resultado
    chunk_t2_text = MagicMock()
    chunk_t2_text.choices = [MagicMock(delta=MagicMock(content="El archivo contiene datos.", reasoning_content=None, thinking=None, reasoning=None, thinking_content=None, tool_calls=None))]

    async def mock_stream_turn1():
        yield chunk_t1_tc

    async def mock_stream_turn2():
        yield chunk_t2_text

    mock_acompletion = AsyncMock(side_effect=[mock_stream_turn1(), mock_stream_turn2()])

    with patch("litellm.acompletion", mock_acompletion), \
         patch.object(bridge, "execute_tool_call", AsyncMock(return_value="contenido de prueba")):
        
        messages = [{"role": "user", "content": "lee test.txt"}]
        events = []
        async for ev in bridge.chat(messages=messages, max_steps=5):
            events.append(ev)

        event_types = [e["type"] for e in events]
        assert "tool_start" in event_types
        assert "tool_result" in event_types
        assert "content" in event_types
        assert "done" in event_types

        # Verificar que acompletion fue llamado dos veces (bucle agéntico)
        assert mock_acompletion.call_count == 2
        # Verificar que el mensaje de tool fue agregado al historial
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["content"] == "contenido de prueba"


def test_parse_text_tool_calls():
    from kogniterm.core.ai_cli_bridge.llm_bridge import _parse_text_tool_calls

    xml_text = (
        "Voy a listar los archivos.\n"
        "<function_calls>\n"
        '<invoke name="execute_command">\n'
        "<parameter name=\"command\">ls -la</parameter>\n"
        "</invoke>\n"
        "</function_calls>"
    )
    calls, clean = _parse_text_tool_calls(xml_text)
    assert len(calls) == 1
    assert calls[0]["name"] == "execute_command"
    assert calls[0]["arguments"] == {"command": "ls -la"}
    assert "Voy a listar los archivos." in clean
    assert "<invoke" not in clean


@pytest.mark.asyncio
async def test_llm_bridge_handles_inline_think_tags():
    bridge = LLMBridge(model="test-model")

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock(delta=MagicMock(content="<think>Pensando en la solución...</think>Respuesta lista", reasoning_content=None, thinking=None, reasoning=None, thinking_content=None, tool_calls=None))]

    async def mock_stream():
        yield chunk1

    with patch("litellm.acompletion", AsyncMock(return_value=mock_stream())):
        messages = [{"role": "user", "content": "hola"}]
        events = []
        async for ev in bridge.chat(messages=messages):
            events.append(ev)

        reasoning_events = [e for e in events if e["type"] == "reasoning"]
        content_events = [e for e in events if e["type"] == "content"]

        assert len(reasoning_events) >= 1
        assert "Pensando en la solución..." in reasoning_events[0]["text"]
        assert len(content_events) >= 1
        assert "Respuesta lista" in content_events[0]["text"]
