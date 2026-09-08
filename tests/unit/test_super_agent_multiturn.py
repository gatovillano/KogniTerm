import pytest
from unittest.mock import AsyncMock, patch
from kogniterm.core.ai_cli_bridge.super_agent import SuperAgent

@pytest.mark.asyncio
async def test_super_agent_preserves_multiturn_history():
    agent = SuperAgent(model="test-model")

    async def fake_chat(messages, tools=None, max_steps=25):
        yield {"type": "content", "text": "Respuesta al turno 2"}
        yield {"type": "done", "content": "Respuesta al turno 2"}

    with patch.object(agent.llm_bridge, "chat", side_effect=fake_chat):
        existing_history = [
            {"role": "system", "content": "Eres KogniTerm."},
            {"role": "user", "content": "Hola"},
            {"role": "assistant", "content": "Hola, ¿en qué ayudo?"}
        ]
        events = []
        async for ev in agent.execute_stream(task="¿Qué hora es?", messages=existing_history):
            events.append(ev)

        assert any(e.get("type") == "done" for e in events)
        # Verificar que el mensaje nuevo se añadió a la historia
        assert len(existing_history) == 4
        assert existing_history[-1]["content"] == "¿Qué hora es?"

@pytest.mark.asyncio
async def test_super_agent_injects_custom_system_prompt():
    agent = SuperAgent(model="test-model")

    captured_messages = []
    async def fake_chat(messages, tools=None, max_steps=25):
        captured_messages.extend(messages)
        yield {"type": "done", "content": "ok"}

    with patch.object(agent.llm_bridge, "chat", side_effect=fake_chat):
        events = [e async for e in agent.execute_stream(task="test", system_prompt="Instrucciones avanzadas de KogniTerm")]
        assert len(captured_messages) >= 2
        assert captured_messages[0]["role"] == "system"
        assert "Instrucciones avanzadas de KogniTerm" in captured_messages[0]["content"]
