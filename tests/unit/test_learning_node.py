import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from kogniterm.core.agents.bash_agent import learning_node, AgentState


def test_learning_node_uses_provider_manager():
    # Arrange
    state = AgentState(messages=[
        HumanMessage(content="hola"),
        AIMessage(content="respuesta de prueba")
    ])
    
    llm_service = MagicMock()
    llm_service.model_name = "google/gemini-1.5-flash"
    llm_service.use_multi_provider = True
    
    # Mock return value of execute to yield a dummy response object
    dummy_response = MagicMock()
    dummy_response.choices = [
        MagicMock(message=MagicMock(content="NADA"))
    ]
    
    def fake_execute(*args, **kwargs):
        assert kwargs.get("stream") is False
        assert kwargs.get("temperature") == 0.3
        assert kwargs.get("max_tokens") == 100
        yield dummy_response
        
    llm_service.provider_manager.execute.side_effect = fake_execute

    # Act
    result_state = learning_node(state, llm_service)

    # Assert
    assert result_state == state
    llm_service.provider_manager.execute.assert_called_once()


def test_learning_node_falls_back_to_completion_without_provider_manager():
    # Arrange
    state = AgentState(messages=[
        HumanMessage(content="hola"),
        AIMessage(content="respuesta de prueba")
    ])
    
    llm_service = MagicMock()
    llm_service.model_name = "google/gemini-1.5-flash"
    llm_service.use_multi_provider = False
    llm_service.api_key = "fake-key"
    del llm_service.provider_manager  # Asegurarse de que no esté presente
    
    dummy_response = MagicMock()
    dummy_response.choices = [
        MagicMock(message=MagicMock(content="NADA"))
    ]
    
    with patch("litellm.completion", return_value=dummy_response) as mock_completion:
        # Act
        result_state = learning_node(state, llm_service)
        
        # Assert
        assert result_state == state
        # Se verifica que llamara a la función de finalización de litellm con los parámetros correctos
        mock_completion.assert_called_once()


def test_learning_node_handles_exceptions_gracefully():
    # Arrange
    state = AgentState(messages=[
        HumanMessage(content="hola"),
        AIMessage(content="respuesta de prueba")
    ])
    
    llm_service = MagicMock()
    llm_service.model_name = "google/gemini-1.5-flash"
    llm_service.use_multi_provider = True
    llm_service.provider_manager.execute.side_effect = Exception("API connection failure")

    # Act
    # No debería lanzar ninguna excepción
    result_state = learning_node(state, llm_service)

    # Assert
    assert result_state == state
    llm_service.provider_manager.execute.assert_called_once()


def test_learning_node_handles_none_content_gracefully():
    # Arrange
    state = AgentState(messages=[
        HumanMessage(content="hola"),
        AIMessage(content="respuesta de prueba")
    ])
    
    llm_service = MagicMock()
    llm_service.model_name = "google/gemini-1.5-flash"
    llm_service.use_multi_provider = True
    
    dummy_response = MagicMock()
    # Simulate content being None (which triggers the AttributeError in original code)
    dummy_response.choices = [
        MagicMock(message=MagicMock(content=None))
    ]
    
    def fake_execute(*args, **kwargs):
        yield dummy_response
        
    llm_service.provider_manager.execute.side_effect = fake_execute

    # Act
    # Should not raise any exception (especially AttributeError on .strip())
    result_state = learning_node(state, llm_service)

    # Assert
    assert result_state == state
    llm_service.provider_manager.execute.assert_called_once()


def test_learning_node_calls_print_learning_when_available(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = AgentState(messages=[
        HumanMessage(content="hola"),
        AIMessage(content="respuesta de prueba")
    ])
    llm_service = MagicMock()
    llm_service.model_name = "google/gemini-1.5-flash"
    llm_service.use_multi_provider = True

    dummy_response = MagicMock()
    dummy_response.choices = [
        MagicMock(message=MagicMock(content="El usuario prefiere terminal limpia."))
    ]
    llm_service.provider_manager.execute.side_effect = lambda *a, **kw: iter([dummy_response])

    terminal_ui = MagicMock()
    terminal_ui.print_learning = MagicMock()

    result_state = learning_node(state, llm_service, terminal_ui=terminal_ui)

    assert result_state == state
    terminal_ui.print_learning.assert_called_once_with("El usuario prefiere terminal limpia.")


def test_server_ui_print_learning_pushes_learning_event():
    import asyncio
    from kogniterm.server.session_pool import ServerUI

    loop = asyncio.new_event_loop()
    server_ui = ServerUI(loop=loop, session_id="test-session")

    events = []
    original_push = server_ui._push
    def mock_push(event_type, data, agent_id=None):
        events.append((event_type, data))
    server_ui._push = mock_push

    server_ui.print_learning("[dim cyan]El usuario prefiere reintentar.[/]")

    event_types = [ev[0] for ev in events]
    assert "learning" in event_types
    assert "info" in event_types
    assert "message" in event_types
    assert "chunk" not in event_types

    learning_event = next(ev for ev in events if ev[0] == "learning")
    assert learning_event[1]["text"] == "El usuario prefiere reintentar."


def test_server_ui_print_message_does_not_push_chunk_and_strips_markup():
    import asyncio
    from kogniterm.server.session_pool import ServerUI

    loop = asyncio.new_event_loop()
    server_ui = ServerUI(loop=loop, session_id="test-session")

    events = []
    server_ui._push = lambda event_type, data, agent_id=None: events.append((event_type, data))

    server_ui.print_message("[dim cyan]Operación completada.[/]", style="cyan")

    event_types = [ev[0] for ev in events]
    assert "chunk" not in event_types
    assert "info" in event_types
    assert "message" in event_types

    info_event = next(ev for ev in events if ev[0] == "info")
    assert info_event[1]["content"] == "Operación completada."


def test_server_ui_print_message_intercepts_learning():
    import asyncio
    from kogniterm.server.session_pool import ServerUI

    loop = asyncio.new_event_loop()
    server_ui = ServerUI(loop=loop, session_id="test-session")

    events = []
    server_ui._push = lambda event_type, data, agent_id=None: events.append((event_type, data))

    server_ui.print_message("🤔 [dim cyan]Aprendizaje consolidado:[/] [italic white]Lección aprendida.[/]", style="cyan")

    event_types = [ev[0] for ev in events]
    assert "learning" in event_types
    assert "chunk" not in event_types

    learning_event = next(ev for ev in events if ev[0] == "learning")
    assert learning_event[1]["text"] == "Lección aprendida."

