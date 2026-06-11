import pytest
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from kogniterm.core.llm_service import LLMService

def test_cot_stream_parser_split_tokens():
    # Instanciamos el servicio
    service = LLMService()
    
    # Mockear response_generator con fragmentos de stream que dividen las etiquetas XML
    chunks = [
        MagicMock(choices=[MagicMock(delta=MagicMock(content="Texto normal y de pronto <"))]),
        MagicMock(choices=[MagicMock(delta=MagicMock(content="thought>"))]),
        MagicMock(choices=[MagicMock(delta=MagicMock(content="Esto es un pensamiento en stream"))]),
        MagicMock(choices=[MagicMock(delta=MagicMock(content=" de prueba </"))]),
        MagicMock(choices=[MagicMock(delta=MagicMock(content="thought> y texto final"))])
    ]
    
    # Mockear el invoke interno de LiteLLM / ProviderManager
    service.provider_manager = MagicMock()
    service.provider_manager.execute_with_fallback = MagicMock(return_value=chunks)
    service.use_multi_provider = True
    
    # Invocar
    generator = service.invoke(history=[HumanMessage(content="hola")], save_history=False)
    
    parts = []
    for p in generator:
        if isinstance(p, AIMessage):
            continue
        parts.append(p)
    
    print("Partes obtenidas:")
    for p in parts:
        print(f"  - {repr(p)}")
        
    # Validar
    assert any("Texto normal y de pronto " in str(p) for p in parts)
    assert any("__THINKING__:Esto es un pensamiento en stream" in str(p) for p in parts)
    assert any("__THINKING__: de prueba " in str(p) for p in parts)
    assert any(" y texto final" in str(p) for p in parts)
    
    # Verificar que el tag XML no se haya fugado al texto de respuesta
    for p in parts:
        if not str(p).startswith("__THINKING__:"):
            assert "<thought>" not in str(p)
            assert "</thought>" not in str(p)

if __name__ == "__main__":
    test_cot_stream_parser_split_tokens()
    print("✅ Todo correcto!")
