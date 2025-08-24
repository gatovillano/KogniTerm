from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import google.generativeai as genai

from ..llm_service import LLMService

# Inicializar el servicio LLM de forma global
llm_service = LLMService()

# --- Mensaje de Sistema para el Orquestador ---
SYSTEM_MESSAGE = SystemMessage(content="""Eres un agente orquestador experto.
Tu objetivo es desglosar problemas complejos en una secuencia de pasos ejecutables y llevarlos a cabo usando tus herramientas.

1.  **Analiza la Petición**: Comprende la solicitud completa del usuario.
2.  **Piensa Paso a Paso**: Decide cuál es la primera acción que debes tomar. No intentes resolver todo de una vez.
3.  **Ejecuta una Acción**: Usa una de tus herramientas para realizar el primer paso. La herramienta más común que usarás es `execute_command` para correr comandos de terminal.
4.  **Observa el Resultado**: Después de cada ejecución de herramienta, recibirás el resultado. Analízalo.
5.  **Decide el Siguiente Paso**: Basado en el resultado, decide si la tarea está completa o cuál es la siguiente acción a tomar.
6.  **Repite**: Continúa este ciclo de acción y observación hasta que la solicitud del usuario esté completamente resuelta.
7.  **Responde al Usuario**: Solo cuando la tarea esté 100% completada, proporciona una respuesta final y amigable al usuario.

Cuando recibas la salida de una herramienta, analízala, resúmela y preséntala al usuario de forma clara y amigable, utilizando formato Markdown si es apropiado.
""")

# --- Definición del Estado del Agente ---

# Usaremos el mismo AgentState que el bash_agent para mantener la consistencia
# ya que la estructura fundamental del flujo (mensajes) es la misma.
from .bash_agent import AgentState # Reutilizamos el estado

# --- Nodos del Grafo (Reutilizamos los del bash_agent) ---
# La lógica de llamar al modelo y ejecutar herramientas es idéntica.
from .bash_agent import call_model_node, execute_tool_node, should_continue

# --- Construcción del Grafo del Orquestador ---

# Creamos una nueva instancia del grafo, pero con el mismo estado
orchestrator_graph = StateGraph(AgentState)

# Añadimos los mismos nodos que el bash_agent
orchestrator_graph.add_node("call_model", call_model_node)
orchestrator_graph.add_node("execute_tool", execute_tool_node)

# El punto de entrada es el mismo
orchestrator_graph.set_entry_point("call_model")

# Las transiciones son las mismas
orchestrator_graph.add_conditional_edges(
    "call_model",
    should_continue,
    {
        "execute_tool": "execute_tool",
        END: END
    }
)
orchestrator_graph.add_edge("execute_tool", "call_model")

# Compilamos el grafo para el orquestador
orchestrator_app = orchestrator_graph.compile()
