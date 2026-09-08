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
