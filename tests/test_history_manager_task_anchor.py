import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from kogniterm.core.history_manager import HistoryManager

def test_initial_goal_preservation_during_truncation(tmp_path):
    history_file = str(tmp_path / "history.json")
    hm = HistoryManager(history_file_path=history_file)
    
    initial_goal = HumanMessage(content="OBJETIVO PRINCIPAL: Construir un sistema de pagos seguro")
    
    messages = [initial_goal]
    for i in range(15):
        messages.append(AIMessage(content=f"Pensando paso {i}", tool_calls=[{"name": "exec", "args": {}, "id": f"tc_{i}"}]))
        messages.append(ToolMessage(content=f"Resultado paso {i}", tool_call_id=f"tc_{i}"))
        messages.append(HumanMessage(content=f"Mensaje intermedio {i}"))

    # Truncar a máximo 6 mensajes conversacionales
    truncated = hm._truncate_history(messages, max_messages=6, max_tokens=100000)
    
    # Verificar que el mensaje inicial del objetivo se mantiene al inicio
    assert len(truncated) > 0
    assert truncated[0].content == initial_goal.content
    assert isinstance(truncated[0], HumanMessage)


def test_summarize_and_compress_preserves_initial_goal(tmp_path):
    history_file = str(tmp_path / "history.json")
    hm = HistoryManager(history_file_path=history_file)
    hm.max_history_messages = 10
    
    initial_goal = HumanMessage(content="OBJETIVO PRINCIPAL: Refactorizar modulo auth")
    
    messages = [initial_goal]
    for i in range(12):
        messages.append(AIMessage(content=f"Respuesta {i}"))
        messages.append(HumanMessage(content=f"Pregunta {i}"))

    def mock_summarize(msgs):
        return "Resumen simulado de acciones anteriores"

    compressed = hm._summarize_and_compress(messages, mock_summarize, console=None)
    
    # El primer mensaje debe ser el objetivo inicial del usuario
    assert isinstance(compressed[0], HumanMessage)
    assert compressed[0].content == initial_goal.content
    
    # El segundo mensaje debe ser el SystemMessage con el resumen
    assert isinstance(compressed[1], SystemMessage)
    assert "🎯 RESUMEN DE LA CONVERSACIÓN" in compressed[1].content
