import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kogniterm.core.ai_cli_bridge.llm_bridge import (
    LLMBridge,
    _detect_continuation_intent,
)
from kogniterm.core.agents.super_agent import SuperAgent


def test_detect_continuation_intent_positive():
    """Verifica que frases de intención de acción sin herramientas sean detectadas."""
    positive_samples = [
        "Ahora voy a crear el archivo config.json",
        "A continuación procederé a ejecutar los tests con pytest.",
        "Procedo a instalar las dependencias necesarias.",
        "Siguiente paso: voy a modificar main.py para corregir el bug.",
        "Paso 2: revisaré los logs del sistema.",
        "Let me now inspect the directory contents.",
        "Next, I will run the migration script.",
    ]
    for sample in positive_samples:
        assert _detect_continuation_intent(sample) is True, f"Fallo al detectar: {sample}"


def test_detect_continuation_intent_negative():
    """Verifica que respuestas de conclusión real no activen el auto-nudge."""
    negative_samples = [
        "Tarea completada con éxito. Todos los archivos fueron modificados correctamente.",
        "He completado la investigación. Aquí está el resumen solicitado.",
        "El proceso ha finalizado con éxito.",
        "Todo listo, no se requieren más acciones.",
        "Task completed successfully without errors.",
        "All done! The changes are in place.",
        "Python es un lenguaje de programación de alto nivel interpretado.",
    ]
    for sample in negative_samples:
        assert _detect_continuation_intent(sample) is False, f"Falso positivo en: {sample}"


@pytest.mark.asyncio
async def test_llm_bridge_auto_nudge_on_continuation():
    """
    Verifica que si el modelo emite texto prometiendo una acción en el paso 1,
    LLMBridge no corte inmediatamente con 'done', sino que inyecte el auto-nudge
    y continúe el bucle.
    """
    bridge = LLMBridge(model="mock-model")
    bridge._resolve_model_provider = MagicMock(return_value=("openai/mock-model", {"custom_llm_provider": "openai"}))

    # Mock de acompletion:
    # 1era llamada: Texto de continuación ("Ahora voy a modificar...") sin tool_calls
    # 2da llamada: Texto final ("Tarea completada exitosamente.") sin tool_calls

    chunk_1 = MagicMock()
    delta_1 = MagicMock()
    delta_1.content = "Ahora voy a crear el archivo app.py y correr los tests."
    delta_1.tool_calls = None
    delta_1.reasoning_content = None
    delta_1.thinking = None
    delta_1.reasoning = None
    delta_1.thinking_content = None
    chunk_1.choices = [MagicMock(delta=delta_1)]

    chunk_2 = MagicMock()
    delta_2 = MagicMock()
    delta_2.content = "Tarea completada con éxito. Todos los cambios están listos."
    delta_2.tool_calls = None
    delta_2.reasoning_content = None
    delta_2.thinking = None
    delta_2.reasoning = None
    delta_2.thinking_content = None
    chunk_2.choices = [MagicMock(delta=delta_2)]

    async def mock_acompletion(*args, **kwargs):
        messages = kwargs.get("messages", [])
        has_nudge = any(
            "[SISTEMA ANTI-DETENCIÓN PREMATURA]" in str(m.get("content", ""))
            for m in messages
        )
        if has_nudge:
            async def gen_2():
                yield chunk_2
            return gen_2()
        else:
            async def gen_1():
                yield chunk_1
            return gen_1()

    messages = [{"role": "user", "content": "Crea el archivo app.py"}]

    with patch("litellm.acompletion", side_effect=mock_acompletion):
        events = []
        async for event in bridge.chat(messages=messages, max_steps=5):
            events.append(event)

        event_types = [e.get("type") for e in events]
        assert "done" in event_types
        done_event = next(e for e in events if e.get("type") == "done")
        assert "Tarea completada con éxito" in done_event.get("content", "")

        nudge_messages = [
            m for m in messages
            if "[SISTEMA ANTI-DETENCIÓN PREMATURA]" in str(m.get("content", ""))
        ]
        assert len(nudge_messages) == 1


@pytest.mark.asyncio
async def test_super_agent_done_fallback_accuracy():
    """Verifica que el evento done de SuperAgent no emita falsamente 'Tarea completada.'."""
    agent = SuperAgent(model="mock-model")

    # Caso 1: Salida vacía pero con herramientas usadas
    async def mock_stream_with_tools(*args, **kwargs):
        yield {"type": "tool_start", "name": "execute_command"}
        yield {"type": "tool_result", "name": "execute_command", "result": "ok"}
        yield {"type": "done", "content": ""}

    with patch.object(agent.llm_bridge, "chat", side_effect=mock_stream_with_tools):
        events = []
        async for ev in agent.execute_stream(task="Test task"):
            events.append(ev)

        done_event = next(e for e in events if e.get("type") == "done")
        assert "Acciones completadas (execute_command)" in done_event["output"]
        assert done_event["output"] != "Tarea completada."

    # Caso 2: Salida vacía y sin herramientas
    async def mock_stream_no_tools(*args, **kwargs):
        yield {"type": "done", "content": ""}

    with patch.object(agent.llm_bridge, "chat", side_effect=mock_stream_no_tools):
        events = []
        async for ev in agent.execute_stream(task="Test task"):
            events.append(ev)

        done_event = next(e for e in events if e.get("type") == "done")
        assert done_event["output"] == "Respuesta finalizada."
