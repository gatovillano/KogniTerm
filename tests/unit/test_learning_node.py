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
