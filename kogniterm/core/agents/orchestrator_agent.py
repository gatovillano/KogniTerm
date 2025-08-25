import json
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, StateGraph

from ..llm_service import llm_service
from .bash_agent import AgentState as BaseAgentState

# --- Mensaje de Sistema Mejorado para el Orquestador ---
SYSTEM_MESSAGE = SystemMessage(content='''Eres un agente orquestador experto con acceso a un conjunto de herramientas, incluyendo acceso a internet. Tu misión es descomponer problemas complejos en una secuencia de pasos ejecutables y llevarlos a cabo usando tus herramientas.

1.  **Analiza la Petición**: Comprende la solicitud completa del usuario.
2.  **Crea un Plan ESTRUCTURADO**: Genera un plan de acción detallado. Tu respuesta DEBE ser un único objeto JSON que contenga una clave "plan". El valor de "plan" debe ser una lista de diccionarios.
    Cada diccionario representa un paso y debe tener dos claves:
    - "description": Una explicación en lenguaje natural de lo que hace el paso.
    - "action": Un objeto JSON que representa la herramienta a ejecutar, con "tool_name" y "arguments".

    Si la acción es un comando bash, usa la herramienta `execute_command`.
    Asegúrate de que el plan sea exhaustivo.

    **Ejemplo de formato de respuesta JSON OBLIGATORIO:**
    ```json
    {
        "plan": [
            {
                "description": "Buscar información sobre LangGraph en la web.",
                "action": {
                    "tool_name": "brave_search",
                    "arguments": {
                        "query": "qué es LangGraph"
                    }
                }
            },
            {
                "description": "Listar los archivos en el directorio actual para ver el contexto.",
                "action": {
                    "tool_name": "execute_command",
                    "arguments": {
                        "command": "ls -la"
                    }
                }
            }
        ]
    }
    ```
3.  **Ejecuta el Plan**: Una vez aprobado, ejecutarás cada paso en orden.
4.  **Responde al Usuario**: Solo cuando todas las tareas del plan estén 100% completadas, proporciona una respuesta final y amigable al usuario resumiendo los resultados.
''')

# --- Definición del Estado del Orquestador ---
@dataclass
class OrchestratorState(BaseAgentState):
    """Define la estructura del estado que fluye a través del grafo del orquestador."""
    user_query: str = ""
    plan: List[Dict[str, Any]] = field(default_factory=list)
    plan_presentation: str = ""
    current_task_index: int = 0
    user_approval: Optional[bool] = None
    command_to_execute: Optional[str] = None
    tool_output: Optional[str] = None
    action_needed: Optional[str] = None  # "await_user_approval", "execute_command", "final_response"
    final_response: str = ""
    status: str = "planning"  # planning, presenting_plan, executing, finished, failed

# --- Nodos del Grafo del Orquestador ---

async def create_plan_node(state: OrchestratorState):
    """Genera un plan de acción estructurado en formato JSON."""
    print("🤖 Orquestador: Creando un plan...", file=sys.stdout, flush=True)
    temp_history = [SYSTEM_MESSAGE, HumanMessage(content=state.user_query)]
    response = await llm_service.ainvoke(history=temp_history)
    ai_message_content = response.candidates[0].content.parts[0].text

    try:
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", ai_message_content, re.DOTALL)
        if not json_match:
            json_match = re.search(r"(\{.*?\})", ai_message_content, re.DOTALL)

        if json_match:
            plan_json = json.loads(json_match.group(1))
            state.plan = plan_json.get("plan", [])
            if not state.plan:
                 raise ValueError("El plan generado está vacío o tiene un formato incorrecto.")
            state.status = "presenting_plan"
            state.messages.append(AIMessage(content="Plan generado."))
        else:
            raise ValueError("El modelo no generó un plan en formato JSON.")
    except (json.JSONDecodeError, ValueError) as e:
        error_message = f"Error al procesar el plan: {e}. Respuesta del modelo:\n{ai_message_content}"
        state.final_response = error_message
        state.status = "failed"
        state.action_needed = "final_response"
        state.messages.append(AIMessage(content=error_message))

    return state

def present_plan_node(state: OrchestratorState):
    """Formatea el plan para presentarlo al usuario y solicita aprobación."""
    if state.status == 'failed':
        return state

    print("🤖 Orquestador: Presentando plan para aprobación...", file=sys.stdout, flush=True)
    formatted_plan = "### Plan de Acción Propuesto:\n\n"
    for i, step in enumerate(state.plan):
        description = step.get('description', 'Sin descripción')
        action = step.get('action', {})
        tool_name = action.get('tool_name', 'N/A')
        args = action.get('arguments', {})
        
        args_str = ', '.join([f"{k}='{v}'" for k, v in args.items()])
        action_str = f"{tool_name}({args_str})"
        
        formatted_plan += f"**Paso {i+1}:** {description}\n"
        formatted_plan += f"   - **Acción:** `{action_str}`\n"

    formatted_plan += "\n¿Deseas aprobar y ejecutar este plan? (s/n)"
    state.plan_presentation = formatted_plan
    state.action_needed = "await_user_approval"
    state.messages.append(AIMessage(content=formatted_plan))
    return state

def handle_approval_node(state: OrchestratorState):
    """Procesa la aprobación del usuario y decide el siguiente paso."""
    if state.user_approval:
        print("🤖 Orquestador: Plan aprobado. Iniciando ejecución...", file=sys.stdout, flush=True)
        state.status = "executing"
        state.current_task_index = 0
        state.messages.append(AIMessage(content="Plan aprobado. Iniciando ejecución..."))
    else:
        state.final_response = "Plan no aprobado. Ejecución cancelada."
        state.status = "failed"
        state.action_needed = "final_response"
        state.messages.append(AIMessage(content=state.final_response))
    return state

async def execute_task_node(state: OrchestratorState):
    """Ejecuta la tarea actual del plan."""
    task = state.plan[state.current_task_index]
    action = task.get("action", {})
    tool_name = action.get("tool_name")
    tool_args = action.get("arguments", {})

    print(f"🤖 Orquestador: Ejecutando paso {state.current_task_index + 1}/{len(state.plan)}: {tool_name}...", file=sys.stdout, flush=True)

    if tool_name == "execute_command":
        state.command_to_execute = tool_args.get("command")
        state.action_needed = "execute_command"
    else:
        tool = llm_service.get_tool(tool_name)
        if tool:
            try:
                output = await tool.ainvoke(tool_args)
                state.tool_output = str(output)
            except Exception as e:
                state.tool_output = f"Error al ejecutar la herramienta '{tool_name}': {e}"
        else:
            state.tool_output = f"Error: Herramienta '{tool_name}' no encontrada."
    return state

def handle_output_node(state: OrchestratorState):
    """Evalúa la salida de la última tarea y avanza el plan."""
    output = state.tool_output
    state.tool_output = None 

    print(f"🤖 Orquestador: Evaluando resultado del paso {state.current_task_index + 1}...", file=sys.stdout, flush=True)
    
    task = state.plan[state.current_task_index]
    tool_name = task.get("action", {}).get("tool_name", "unknown_tool")
    state.messages.append(ToolMessage(content=str(output), tool_call_id=tool_name))

    state.current_task_index += 1
    return state

# --- Construcción del Grafo del Orquestador ---
orchestrator_graph = StateGraph(OrchestratorState)

orchestrator_graph.add_node("create_plan", create_plan_node)
orchestrator_graph.add_node("present_plan", present_plan_node)
orchestrator_graph.add_node("handle_approval", handle_approval_node)
orchestrator_graph.add_node("execute_task", execute_task_node)
orchestrator_graph.add_node("handle_output", handle_output_node)

orchestrator_graph.set_entry_point("create_plan")

orchestrator_graph.add_edge("create_plan", "present_plan")

orchestrator_graph.add_conditional_edges(
    "handle_approval",
    lambda state: "execute_task" if state.user_approval else END,
    {"execute_task": "execute_task", END: END}
)

orchestrator_graph.add_edge("execute_task", "handle_output")

orchestrator_graph.add_conditional_edges(
    "handle_output",
    lambda state: "execute_task" if state.current_task_index < len(state.plan) else END,
    {"execute_task": "execute_task", END: END}
)

orchestrator_app = orchestrator_graph.compile()
