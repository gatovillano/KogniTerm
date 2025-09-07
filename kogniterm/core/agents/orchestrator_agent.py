from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import google.generativeai as genai
import functools
from langchain_core.runnables import RunnableConfig # Nueva importación

from ..llm_service import LLMService




# --- Mensaje de Sistema para el Orquestador ---
SYSTEM_MESSAGE = SystemMessage(content="""Eres un agente orquestador experto.
Tu objetivo es desglosar problemas complejos en una secuencia de pasos ejecutables y llevarlos a cabo usando tus herramientas.
Antes de cualquier acción, crea un plan detallado paso a paso para abordar la solicitud del usuario.

1.  **Analiza la Petición**: Comprende la solicitud completa del usuario.
2.  **Crea un Plan**: Genera un plan de acción detallado y paso a paso para resolver la solicitud.
3.  **Piensa Paso a Paso**: Decide cuál es la primera acción que debes tomar basándote en el plan. No intentes resolver todo de una vez.
4.  **Ejecuta una Acción**: Usa una de tus herramientas para realizar el primer paso. Tienes un conjunto de herramientas, incluyendo `execute_command` para comandos de terminal, `file_operations` para interactuar con archivos y directorios, y `python_executor` para ejecutar código Python.
5.  **Observa el Resultado**: Después de cada ejecución de herramienta, recibirás el resultado. Analízalo.
6.  **Decide el Siguiente Paso**: Basado en el resultado y el plan, decide si la tarea está completa o cuál es la siguiente acción a tomar.
7.  **Repite**: Continúa este ciclo de acción y observación hasta que la solicitud del usuario esté completamente resuelta.
8.  **Responde al Usuario**: Solo cuando la tarea esté 100% completada, proporciona una respuesta final y amigable al usuario.

Cuando recibas la salida de una herramienta, analízala, resúmela y preséntala al usuario de forma clara y amigable, utilizando formato Markdown si es apropiado.
""")

# Nuevo nodo para crear el plan

# --- Definición del Estado del Agente ---

# Usaremos el mismo AgentState que el bash_agent para mantener la consistencia
# ya que la estructura fundamental del flujo (mensajes) es la misma.
from .bash_agent import AgentState # Reutilizamos el estado

# --- Nodos del Grafo (Reutilizamos los del bash_agent) ---
# La lógica de llamar al modelo y ejecutar herramientas es idéntica.
from .bash_agent import call_model_node, execute_tool_node, should_continue

# Nuevo nodo para crear el plan
async def create_plan_node(state: AgentState, llm_service: LLMService):
    """Genera un plan de acción utilizando el LLM y cede actualizaciones de estado para streaming."""
    history = state.history_for_api
    
    # Inicializar un AIMessage para acumular la respuesta del LLM
    current_ai_message = AIMessage(content="")
    state.messages.append(current_ai_message) # Añadir el mensaje vacío al estado

    try:
        response_stream = llm_service.invoke(history) # Esto ahora devuelve un iterador
        
        full_text_content = ""
        accumulated_tool_calls = []

        for chunk in response_stream: # Usar for normal para iterar sobre el stream síncrono
            # Cada chunk es un GenerateContentResponse
            if chunk.candidates:
                for part in chunk.candidates[0].content.parts:
                    if part.text:
                        full_text_content += part.text
                        # Actualizar el contenido del mensaje del AI en el estado
                        current_ai_message.content = full_text_content
                        yield state.copy() # Ceder una copia del estado actualizado
                    
                    if part.function_call:
                        tool_name = part.function_call.name
                        tool_args = {key: value for key, value in part.function_call.args.items()}
                        accumulated_tool_calls.append({"name": tool_name, "args": tool_args, "id": tool_name})
                        # No cedemos aquí para tool_calls, se añadirán al final del mensaje del AI
                        # o se manejarán en el siguiente nodo si es una herramienta de ejecución

        # Al final del stream, actualizar el mensaje del AI con el contenido completo y tool_calls
        current_ai_message.content = full_text_content
        if accumulated_tool_calls:
            current_ai_message.tool_calls = accumulated_tool_calls
        
        yield state.copy() # Ceder el estado final después de procesar todo el stream

    except Exception as e:
        error_message = f"Ocurrió un error durante la llamada al modelo: {e}"
        current_ai_message.content = error_message
        yield state.copy() # Ceder el estado con el mensaje de error

# --- Construcción del Grafo del Orquestador ---

def create_orchestrator_agent(llm_service: LLMService):
    # Creamos una nueva instancia del grafo, pero con el mismo estado
    orchestrator_graph = StateGraph(AgentState)

    # Añadimos los mismos nodos que el bash_agent
    orchestrator_graph.add_node("create_plan", functools.partial(create_plan_node, llm_service=llm_service)) # Nuevo nodo para crear el plan
    orchestrator_graph.add_node("call_model", functools.partial(call_model_node, llm_service=llm_service))
    orchestrator_graph.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service))
    orchestrator_graph.add_node("confirm_command", lambda state: state) # Nuevo nodo, solo pasa el estado

    # El punto de entrada será el nodo de creación del plan
    orchestrator_graph.set_entry_point("create_plan")

    # Las transiciones son las mismas
    orchestrator_graph.add_conditional_edges(
        "call_model",
        should_continue,
        {
            "execute_tool": "execute_tool",
            "confirm_command": "confirm_command",
            END: END
        }
    )
    orchestrator_graph.add_edge("create_plan", "call_model") # Después de crear el plan, se pasa al nodo call_model
    orchestrator_graph.add_edge("execute_tool", "call_model")
    orchestrator_graph.add_edge("confirm_command", END) # El agente termina aquí, la terminal toma el control

    return orchestrator_graph.compile()