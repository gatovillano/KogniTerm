import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from kogniterm.core.history_manager import HistoryManager
from kogniterm.core.llm_service import LLMService


def test_get_model_context_window():
    service = LLMService()
    
    # Probar modelo OpenRouter (limitado a 120000 por seguridad)
    win_gemini = service.get_model_context_window("openrouter/google/gemini-2.5-flash")
    assert win_gemini == 120000

    # Probar GPT-4o
    win_gpt4o = service.get_model_context_window("gpt-4o")
    assert win_gpt4o == 128000


def test_history_manager_token_truncation(tmp_path):
    history_file = str(tmp_path / "history.json")
    hm = HistoryManager(history_file_path=history_file)
    
    # Crear un mensaje con salida masiva de herramienta
    massive_output = "X" * 100000 # 100,000 caracteres (~28,000 tokens)
    messages = [
        HumanMessage(content="Ejecuta comando largo"),
        AIMessage(content="", tool_calls=[{"name": "execute_command", "args": {}, "id": "tc1"}]),
        ToolMessage(content=massive_output, tool_call_id="tc1"),
        HumanMessage(content="Continuar")
    ]
    
    # Solicitar truncamiento con límite de 5000 tokens
    truncated = hm._truncate_history(messages, max_messages=10, max_tokens=5000)
    
    # Verificar que el mensaje de herramienta gigante fue truncado
    tool_msgs = [m for m in truncated if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1
    assert "[Contenido truncado por límite de contexto]" in tool_msgs[0].content
    assert len(tool_msgs[0].content) < 10000
