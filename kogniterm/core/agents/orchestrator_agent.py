import json
import re
import sys
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    BaseMessage
)
from langgraph.graph import END, StateGraph
from langchain.memory import FileChatMessageHistory

from kogniterm.core.llm_service import llm_service
from kogniterm.core.agents.bash_agent import AgentState as BaseAgentState

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
    custom_system_message: Optional[str] = None # Nuevo campo para el mensaje del sistema personalizado
    # Nueva adición para la memoria de LangChain
    chat_history: List[BaseMessage] = field(default_factory=list)
    memory_file_path: str = "llm_context.json" # Ruta por defecto para el archivo de memoria

# --- Nodos del Grafo del Orquestador ---

# --- Constantes para la gestión de memoria ---
MEMORY_THRESHOLD = 4000  # Tokens a partir de los cuales se intenta resumir
LLM_SUMMARIZE_MODEL = "gemini-1.5-flash" # Modelo para el resumen, podría ser más pequeño/barato

async def create_plan_node(state: OrchestratorState):
    """Genera un plan de acción estructurado en formato JSON."""
    print("🤖 Orquestador: Creando un plan...", file=sys.stdout, flush=True)
    
    # Usar el mensaje del sistema personalizado si existe, de lo contrario usar el predeterminado
    system_message_content = state.custom_system_message if state.custom_system_message else SYSTEM_MESSAGE.content
    
    # Cargar el historial de chat desde el archivo para pasarlo al LLM
    # Asegurarse de que el archivo exista antes de intentar leerlo
    file_history = FileChatMessageHistory(file_path=state.memory_file_path)
    state.chat_history = file_history.messages

    # --- Lógica de Resumen de Memoria ---
    # Convertir el historial a un solo string para estimación de tokens
    # LangChain messages can have content as str or list of dicts (for tool calls).
    # We need to extract only string content for summarization.
    string_contents = []
    for msg in state.chat_history:
        if isinstance(msg.content, str):
            string_contents.append(msg.content)
        elif isinstance(msg.content, list): # Handle tool messages or multi-part content
            for part in msg.content:
                if isinstance(part, dict) and 'text' in part:
                    string_contents.append(part['text'])
                elif isinstance(part, str):
                    string_contents.append(part)

    full_content_for_token_count = "\n".join(string_contents)
    # Simple estimación de tokens (aproximada)
    current_tokens = len(full_content_for_token_count) // 4 # Ajustar esta heurística o usar tiktoken si es posible para OpenAI

    if current_tokens > MEMORY_THRESHOLD:
        print(f"🤖 Orquestador: Historial de memoria excede el umbral ({current_tokens} tokens). Intentando resumir...", file=sys.stdout, flush=True)
        summarize_tool = llm_service.get_tool("memory_summarize_tool")
        if summarize_tool:
            try:
                # Pasar la clave API del LLM principal para el resumen
                llm_api_key = os.getenv("LLM_API_KEY") if llm_service.provider == "openai" else os.getenv("GOOGLE_API_KEY")
                summary_output = await summarize_tool.ainvoke({
                    "filename": state.memory_file_path,
                    "max_tokens": MEMORY_THRESHOLD,
                    "llm_model_name": LLM_SUMMARIZE_MODEL,
                    "llm_api_key": llm_api_key
                })
                print(f"🤖 Orquestador: Resumen de memoria completado: {summary_output}", file=sys.stdout, flush=True)
                # Recargar el historial después del resumen
                file_history = FileChatMessageHistory(file_path=state.memory_file_path)
                state.chat_history = file_history.messages
            except Exception as e:
                print(f"⚠️ Orquestador: Error al intentar resumir la memoria: {e}", file=sys.stderr, flush=True)
        else:
            print("⚠️ Orquestador: Herramienta 'memory_summarize_tool' no encontrada para resumir la memoria.", file=sys.stderr, flush=True)
    # --- Fin Lógica de Resumen ---

    # Añadir el mensaje del sistema y la consulta del usuario al historial para la invocación actual
    temp_history_for_llm = [SystemMessage(content=system_message_content)] + state.chat_history + [HumanMessage(content=state.user_query)]
    
    response = await llm_service.ainvoke(history=temp_history_for_llm)
    ai_message_content = response.candidates[0].content.parts[0].text

    try:
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", ai_message_content, re.DOTALL)
        if not json_match:
            json_match = re.search(r"(\{.*?\})", ai_message_content, re.DOTALL)

        if json_match:
            plan_json = json.loads(json_match.group(1))
            state.plan = plan_json.get("plan", [])
            if not state.plan:
                 raise ValueError("El plan generado está vacío o tiene un formato incorrecto.")
            state.status = "presenting_plan"
            
            # Añadir el mensaje de IA al historial persistente
            file_history.add_ai_message(ai_message_content)
            state.messages.append(AIMessage(content="Plan generado."))
        else:
            raise ValueError("El modelo no generó un plan en formato JSON.")
    except (json.JSONDecodeError, ValueError) as e:
        error_message = f"Error al procesar el plan: {e}. Respuesta del modelo:\n{ai_message_content}"
        print(f"DEBUG: {error_message}", file=sys.stderr, flush=True) # Añadido para depuración
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
    # Add tool output to the persistent chat history
    file_history = FileChatMessageHistory(file_path=state.memory_file_path)
    file_history.add_message(ToolMessage(content=str(output), tool_call_id=tool_name))
    
    state.messages.append(ToolMessage(content=str(output), tool_call_id=tool_name))

    # Si la herramienta ejecutada fue set_llm_instructions, actualizamos el mensaje del sistema personalizado
    if tool_name == "set_llm_instructions":
        state.custom_system_message = str(output)
        print(f"🤖 Orquestador: Mensaje del sistema personalizado actualizado: {state.custom_system_message}", file=sys.stdout, flush=True)

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
    "present_plan",
    lambda state: "handle_approval" if state.action_needed == "await_user_approval" else END,
    {"handle_approval": "handle_approval"}
)

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
