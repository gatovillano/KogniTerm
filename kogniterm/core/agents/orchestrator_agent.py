from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import google.generativeai as genai

from ..llm_service import LLMService
from .bash_agent import llm_service # Importar la instancia global de llm_service



# --- Mensaje de Sistema para el Orquestador ---
SYSTEM_MESSAGE = SystemMessage(content="""Eres un agente orquestador experto.
Tu objetivo es desglosar problemas complejos en una secuencia de pasos ejecutables y llevarlos a cabo usando tus herramientas.
Antes de cualquier acción, crea un plan detallado paso a paso para abordar la solicitud del usuario.

1.  **Analiza la Petición**: Comprende la solicitud completa del usuario.
2.  **Crea un Plan**: Genera un plan de acción detallado y paso a paso para resolver la solicitud.
3.  **Piensa Paso a Paso**: Decide cuál es la primera acción que debes tomar basándote en el plan. No intentes resolver todo de una vez.
4.  **Ejecuta una Acción**: Usa una de tus herramientas para realizar el primer paso. La herramienta más común que usarás es `execute_command` para correr comandos de terminal.
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
async def create_plan_node(state: AgentState):
    """
    Genera un plan de acción utilizando el LLM.
    """
    response = llm_service.invoke(history=state.history_for_api)

    ai_message_content = ""
    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.text:
                ai_message_content += part.text
            elif part.function_call:
                ai_message_content += f"Tool Call: {part.function_call.name}({part.function_call.args})"

    state.messages.append(AIMessage(content=ai_message_content))
    return state

# --- Construcción del Grafo del Orquestador ---

# Creamos una nueva instancia del grafo, pero con el mismo estado
orchestrator_graph = StateGraph(AgentState)

# Añadimos los mismos nodos que el bash_agent
orchestrator_graph.add_node("create_plan", create_plan_node) # Nuevo nodo para crear el plan
orchestrator_graph.add_node("call_model", call_model_node)
orchestrator_graph.add_node("execute_tool", execute_tool_node)
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

# Compilamos el grafo para el orquestador
orchestrator_app = orchestrator_graph.compile()