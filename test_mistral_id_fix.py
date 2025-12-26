import os
import json
from typing import Optional, Dict
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from kogniterm.core.llm_service import LLMService

def test_mistral_id_normalization():
    # Mock de configuración para simular Mistral
    os.environ["LITELLM_MODEL"] = "openrouter/mistralai/mistral-7b-instruct"
    
    service = LLMService()
    
    # Simular un historial con IDs largos (estilo Gemini/OpenAI)
    long_id = "call_abc123longidthatisnotcompliant"
    messages = [
        HumanMessage(content="Hola"),
        AIMessage(content="Voy a usar una herramienta", tool_calls=[{
            "id": long_id,
            "name": "test_tool",
            "args": {}
        }]),
        ToolMessage(content="Resultado", tool_call_id=long_id)
    ]
    
    id_map = {}
    
    # Probar conversión de AIMessage
    litellm_ai = service._to_litellm_message(messages[1], id_map=id_map)
    new_id = litellm_ai["tool_calls"][0]["id"]
    
    print(f"Original ID: {long_id}")
    print(f"Normalized ID: {new_id}")
    
    assert len(new_id) == 9, f"Expected length 9, got {len(new_id)}"
    assert new_id.isalnum(), "Expected alphanumeric ID"
    assert long_id in id_map, "Expected original ID in map"
    assert id_map[long_id] == new_id, "Map mismatch"
    
    # Probar conversión de ToolMessage (debe usar el mismo ID mapeado)
    litellm_tool = service._to_litellm_message(messages[2], id_map=id_map)
    assert litellm_tool["tool_call_id"] == new_id, f"ToolMessage ID mismatch: {litellm_tool['tool_call_id']} != {new_id}"
    
    print("✅ Prueba de normalización de IDs para Mistral exitosa!")

if __name__ == "__main__":
    test_mistral_id_normalization()