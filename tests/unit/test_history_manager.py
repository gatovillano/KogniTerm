"""Tests unitarios para HistoryManager"""

import threading
import time
import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from kogniterm.core.agent_state import AgentState
from kogniterm.core.history_manager import HistoryManager


@pytest.fixture
def temp_history_file(tmp_path):
    """Crea un archivo temporal para el historial"""
    return str(tmp_path / "test_history.json")


@pytest.fixture
def history_manager(temp_history_file):
    """Instancia de HistoryManager para tests"""
    return HistoryManager(
        history_file_path=temp_history_file,
        max_history_messages=50,
        max_history_chars=75000
    )


def test_add_and_get_message(history_manager):
    """Prueba que add_message almacena y get_history recupera mensajes"""
    msg = HumanMessage(content="Hola")
    history_manager.add_message(msg)
    
    history = history_manager.get_history()
    assert len(history) == 1
    assert history[0].content == "Hola"


def test_thread_safety_concurrent_adds(history_manager):
    """Prueba que múltiples hilos pueden añadir mensajes sin race conditions"""
    num_threads = 10
    messages_per_thread = 50
    errors = []
    
    def worker(thread_id):
        try:
            for i in range(messages_per_thread):
                msg = HumanMessage(content=f"Mensaje {thread_id}-{i}")
                history_manager.add_message(msg)
        except Exception as e:
            errors.append(e)
    
    threads = []
    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    assert len(errors) == 0, f"Errores en hilos: {errors}"
    
    history = history_manager.get_history()
    expected_total = num_threads * messages_per_thread
    assert len(history) == expected_total, f"Esperados {expected_total}, obtenidos {len(history)}"


def test_clear_history(history_manager):
    """Prueba que clear_history elimina todos los mensajes"""
    history_manager.add_message(HumanMessage(content="Mensaje 1"))
    history_manager.add_message(AIMessage(content="Respuesta"))
    
    assert len(history_manager.get_history()) == 2
    
    history_manager.clear_history()
    
    assert len(history_manager.get_history()) == 0
    assert history_manager._message_length_cache == {}


def test_get_history_returns_copy(history_manager):
    """Prueba que get_history retorna una copia, no la referencia interna"""
    original_msg = HumanMessage(content="Original")
    history_manager.add_message(original_msg)
    
    retrieved = history_manager.get_history()
    retrieved.append(HumanMessage(content="Injected"))
    
    # La lista interna no debe haberse modificado
    current = history_manager.get_history()
    assert len(current) == 1
    assert current[0].content == "Original"


def test_message_length_cache_consistency(history_manager):
    """Prueba que el caché de longitud se mantiene consistente"""
    msg = HumanMessage(content="Test content")
    
    length1 = history_manager._get_message_length(msg)
    length2 = history_manager._get_message_length(msg)
    
    assert length1 == length2
    assert len(history_manager._message_length_cache) == 1


def test_truncate_history(history_manager):
    """Prueba el truncamiento automático del historial"""
    # Añadir muchos mensajes para superar el límite
    for i in range(60):
        history_manager.add_message(HumanMessage(content=f"Mensaje {i}"))
    
    history = history_manager.get_history()
    assert len(history) <= history_manager.max_history_messages + 10  # Tolerancia


def test_tool_message_pairing(history_manager):
    """Prueba que los ToolMessages se mantienen con sus AIMessage correspondientes"""
    ai_msg = AIMessage(
        content="Voy a ejecutar",
        tool_calls=[{"name": "test_tool", "args": {"x": 1}, "id": "call_123"}]
    )
    tool_msg = ToolMessage(content="Resultado", tool_call_id="call_123")
    
    history_manager.add_message(ai_msg)
    history_manager.add_message(tool_msg)
    
    history = history_manager.get_history()
    assert len(history) == 2
    assert isinstance(history[0], AIMessage)
    assert isinstance(history[1], ToolMessage)
    assert history[1].tool_call_id == "call_123"


def test_direct_history_list_mutation_persists_immediately(temp_history_file):
    history_manager = HistoryManager(history_file_path=temp_history_file)

    history_manager.conversation_history.append(HumanMessage(content="Hola inmediata"))

    reloaded = HistoryManager(history_file_path=temp_history_file)
    history = reloaded.get_history()
    assert len(history) == 1
    assert history[0].content == "Hola inmediata"


def test_agent_state_messages_stay_bound_to_history_manager(temp_history_file):
    history_manager = HistoryManager(history_file_path=temp_history_file)
    state = AgentState(messages=[HumanMessage(content="hola")])

    state.attach_history_manager(history_manager)
    state.messages.append(AIMessage(content="respuesta"))

    reloaded = HistoryManager(history_file_path=temp_history_file)
    history = reloaded.get_history()

    assert state.messages is history_manager.conversation_history
    assert [msg.content for msg in history] == ["hola", "respuesta"]
