import os
import sys
import json
from unittest.mock import MagicMock
from kogniterm.core.llm_service import LLMService, _to_litellm_message
from kogniterm.core.tools.memory_append_tool import MemoryAppendTool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import uuid

# Configurar variables de entorno si es necesario para LiteLLM
# Asegúrate de que LITELLM_MODEL y GOOGLE_API_KEY o OPENROUTER_API_KEY estén configurados en tu entorno
os.environ["LITELLM_MODEL"] = "gemini/gemini-2.5-flash" # O el modelo que estés usando
os.environ["GOOGLE_API_KEY"] = "YOUR_API_KEY" # Reemplazar con tu clave real o asegurar que esté en .env

def run_test():
    print("Iniciando prueba del LLMService y tool_calls...")

    # Mock del interrupt_queue para evitar dependencias de threading en la prueba simple
    mock_interrupt_queue = MagicMock()
    mock_interrupt_queue.empty.return_value = True

    # Inicializar LLMService
    llm_service = LLMService(interrupt_queue=mock_interrupt_queue)

    # Reemplazar la lista de herramientas con solo MemoryAppendTool para esta prueba
    llm_service.langchain_tools = [MemoryAppendTool(llm_service_instance=llm_service)]
    llm_service.litellm_tools = [llm_service._convert_langchain_tool_to_litellm(tool) for tool in llm_service.langchain_tools]
    
    # Simular una conversación con una llamada a herramienta
    history = [
        HumanMessage(content="Añade 'Hola mundo' a mi memoria."),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": str(uuid.uuid4()),
                    "name": "memory_append",
                    "args": {"content": "Hola mundo"}
                }
            ]
        )
    ]

    print("\nHistorial simulado con tool_call:")
    for msg in history:
        print(f"- {type(msg).__name__}: {msg.content}")
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            print(f"  Tool Calls: {msg.tool_calls}")

    # Simular la respuesta de la herramienta
    tool_call_id = history[1].tool_calls[0]["id"]
    tool_response = "Contenido 'Hola mundo' añadido a llm_context.md."
    history.append(ToolMessage(content=tool_response, tool_call_id=tool_call_id))

    print("\nHistorial con respuesta de tool_call:")
    for msg in history:
        print(f"- {type(msg).__name__}: {msg.content}")
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            print(f"  Tool Calls: {msg.tool_calls}")
        if isinstance(msg, ToolMessage):
            print(f"  Tool Call ID: {msg.tool_call_id}")


    print("\nInvocando LLMService para procesar la respuesta de la herramienta...")
    try:
        # Aquí es donde se invoca el método invoke real
        response_chunks = []
        for chunk in llm_service.invoke(history=history):
            response_chunks.append(chunk)
        
        print("\nRespuesta del LLMService:")
        final_response = "".join([chunk.content if hasattr(chunk, 'content') else str(chunk) for chunk in response_chunks])
        print(final_response)

        if "error" in final_response.lower():
            print("\n¡La prueba falló! Se detectó un error en la respuesta del LLM.")
            sys.exit(1)
        else:
            print("\n¡La prueba de tool_calls se completó exitosamente!")
            # Opcional: verificar el contenido del archivo si memory_append_tool realmente escribe
            # with open(os.path.join(os.getcwd(), ".kogniterm", "llm_context.md"), "r") as f:
            #     print(f"Contenido de llm_context.md: {f.read()}")

    except Exception as e:
        print(f"\n¡La prueba falló con una excepción inesperada: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
