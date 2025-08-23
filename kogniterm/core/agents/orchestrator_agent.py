from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Any
from ..interpreter import Interpreter
from ..tools import get_callable_tools # Importar las herramientas
import json # Necesario para parsear el JSON de la decisión del LLM
import re # ¡Importar el módulo re!
import sys # Importar el módulo sys

# Initialize the interpreter globally for now
interpreter = Interpreter()

@dataclass
class OrchestratorState:
    user_query: str = ""
    # Cada elemento del plan será un diccionario con 'description' y 'action'
    plan: List[dict] = field(default_factory=list)
    plan_presentation: str = ""
    
    # Fields for execution:
    current_task_index: int = 0
    user_approval: str = "" # 's' or 'n' from terminal
    command_to_execute: str = "" # Command to be executed by terminal
    command_output: str = "" # Output from terminal
    final_response: str = ""
    status: str = "planning" # planning, awaiting_approval, executing_task, awaiting_output, finished, cancelled
    action_needed: str = "" # "present_plan", "execute_command", "respond_final", "await_user_approval", "execute_tool"
    reinvoke_for_approval: bool = False # New field
    tool_calls: List[dict] = field(default_factory=list) # New field for tool calls
    tool_output: str = "" # New field for tool output

def create_plan_node(state: OrchestratorState):
    """Calls the LLM to generate a plan based on the user's query."""
    prompt = f"""Basado en la siguiente solicitud del usuario, crea un plan detallado paso a paso para lograrla. Tu respuesta DEBE ser solo el JSON. No incluyas ningún texto conversacional, introducciones o explicaciones fuera del JSON.

Para cada paso, proporciona dos cosas:
1.  Una `description` (descripción) clara y concisa del paso para el usuario.
2.  Una `action` (acción) ejecutable, que *debe* ser un comando bash o una llamada a una herramienta (usa las herramientas disponibles siempre que sea relevante).

Formato de salida (JSON):
```json
[
    {{
        "description": "Descripción del paso 1.",
        "action": {{
            "type": "bash",
            "command": "comando_bash_aqui --opcion valor"
        }}
    }},
    {{
        "description": "Descripción del paso 2 que usa una herramienta.",
        "action": {{
            "type": "tool",
            "tool_name": "nombre_herramienta",
            "args": {{"arg1": "valor1", "arg2": "valor2"}}
        }}
    }}
]
```

IMPORTANTE:
-   Siempre devuelve un array JSON.
-   Asegúrate de que `tool_name` sea uno de los nombres de herramienta disponibles: {', '.join([tool.name for tool in get_callable_tools()])}.
-   Si una acción requiere argumentos específicos que no están explícitamente en la tarea, o si la tarea es ambigua para una herramienta, la `action` debe ser un comando bash genérico o un comando bash que ayude a obtener la información necesaria (por ejemplo, 'docker ps -a' para listar contenedores si se pide inspeccionar uno sin especificar cuál). No asumas valores.
-   Si la solicitud del usuario implica obtener información de un repositorio de GitHub (por ejemplo, "obtener información del repositorio X"), DEBES usar la herramienta `get_github_repo_info` con el `repo_name` adecuado. Ten en cuenta que algunas herramientas pueden obtener credenciales de variables de entorno (como `GITHUB_TOKEN` para la herramienta `get_github_repo_info`).

La solicitud es: '{state.user_query}'"""
    
    plan_raw_response, _ = interpreter.chat(prompt, add_to_history=False)
    
    # Extraer el bloque JSON si está envuelto en markdown
    json_match = re.search(r"```json\n(.*?)```", plan_raw_response, re.DOTALL)
    if json_match:
        plan_json_str = json_match.group(1)
    else:
        plan_json_str = plan_raw_response # Si no hay markdown, asumimos que es el JSON directo

    try:
        plan_list = json.loads(plan_json_str)
        # Validar que cada elemento del plan tenga 'description' y 'action'
        for item in plan_list:
            if "description" not in item or "action" not in item:
                raise ValueError("Cada paso del plan debe contener 'description' y 'action'.")
            
            # Validar que si el tipo de acción es 'tool', tool_name no esté vacío
            action = item.get("action", {})
            if action.get("type") == "tool":
                tool_name = action.get("tool_name")
                if not tool_name:
                    raise ValueError("Para acciones de tipo 'tool', 'tool_name' no puede estar vacío.")
        
        return {"plan": plan_list, "status": "awaiting_approval", "action_needed": "present_plan"}
    except json.JSONDecodeError as e:
        error_message = f"Error al parsear el plan JSON del LLM: {e}. Respuesta del LLM: {plan_json_str}"
        print(error_message) # Para depuración
        return {"status": "cancelled", "final_response": f"Error interno: {error_message}", "action_needed": "respond_final"}
    except ValueError as e:
        error_message = f"Error en la estructura del plan del LLM: {e}. Respuesta del LLM: {plan_json_str}"
        print(error_message) # Para depuración
        return {"status": "cancelled", "final_response": f"Error interno: {error_message}", "action_needed": "respond_final"}

def present_plan_node(state: OrchestratorState):
    """Formats the generated plan for presentation to the user."""
    presentation = "He creado el siguiente plan para ti:\n\n"
    for i, item in enumerate(state.plan):
        description = item.get("description", "Sin descripción")
        action = item.get("action", {})
        
        presentation += f"{i+1}. {description}\n"
        
        action_type = action.get("type")
        if action_type == "bash":
            command = action.get("command", "")
            presentation += f"```bash\n{command}\n```\n"
        elif action_type == "tool":
            tool_name = action.get("tool_name", "")
            tool_args = action.get("args", {})
            presentation += f"Usar herramienta '{tool_name}' con args: {tool_args}\n"
        presentation += "\n" # Espacio entre pasos
            
    presentation += "\n¿Te gustaría que lo ejecute? (s/n)"

    # Return a dictionary to update the state
    return {"plan_presentation": presentation, "final_response": presentation, "status": "awaiting_approval", "action_needed": "await_user_approval", "reinvoke_for_approval": True}

def handle_approval_node(state: OrchestratorState):
    """Handles user's approval for the plan."""
    if state.user_approval.lower() == 's':
        # Obtener la primera tarea del plan
        first_task_item = state.plan[0]
        action = first_task_item.get("action", {})
        action_type = action.get("type")
        
        updates = {"status": "executing_task", "current_task_index": 0}

        if action_type == "bash":
            updates["command_to_execute"] = action.get("command", "")
            updates["action_needed"] = "execute_command"
        elif action_type == "tool":
            updates["tool_calls"] = [{"name": action.get("tool_name"), "args": action.get("args", {})}]
            updates["action_needed"] = "execute_tool"
        else:
            # Fallback en caso de un tipo de acción inesperado
            updates["status"] = "cancelled"
            updates["final_response"] = f"Error interno: Tipo de acción no reconocido para la primera tarea: {first_task_item.get('description', '')}"
            updates["action_needed"] = "respond_final"

        return updates
    else:
        return {"status": "cancelled", "final_response": "Plan cancelado por el usuario.", "action_needed": "respond_final"}

def execute_task_node(state: OrchestratorState):
    """Extracts the current task and sets command_to_execute for terminal or tool_calls for tools."""
    if state.current_task_index >= len(state.plan):
        return {"status": "finished", "final_response": "Plan completado.", "action_needed": "respond_final"}

    current_task_item = state.plan[state.current_task_index]
    action = current_task_item.get("action", {})
    
    action_type = action.get("type")
    
    if action_type == "bash":
        command = action.get("command", "")
        return {"command_to_execute": command.strip(), "status": "executing_task", "action_needed": "execute_command"}
    elif action_type == "tool":
        tool_name = action.get("tool_name")
        tool_args = action.get("args", {})
        
        # Ejecutar la herramienta directamente a través del interpreter
        found_tool = next((tool for tool in interpreter.tools if tool.name == tool_name), None)
        if found_tool:
            try:
                tool_output = found_tool._run(**tool_args)
                return {"tool_output": tool_output, "status": "awaiting_output", "action_needed": "handle_output"}
            except Exception as e:
                error_message = f"Error al ejecutar la herramienta {tool_name}: {e}"
                return {"tool_output": error_message, "status": "awaiting_output", "action_needed": "handle_output"}
        else:
            error_message = f"Herramienta no reconocida: {tool_name}"
            return {"tool_output": error_message, "status": "awaiting_output", "action_needed": "handle_output"}
    else:
        # Esto no debería ocurrir si el plan es generado correctamente
        return {"status": "cancelled", "final_response": f"Error interno: Tipo de acción no reconocido para la tarea: {current_task_item.get('description', '')}", "action_needed": "respond_final"}

def handle_output_node(state: OrchestratorState):
    """Evaluates command/tool output and decides next step."""
    output_content = state.command_output if state.action_needed == "execute_command" else state.tool_output
    current_task_item = state.plan[state.current_task_index]
    current_task_description = current_task_item.get("description", "Tarea desconocida")

    prompt = f"""El paso actual del plan es: '{current_task_description}'.
    
    La salida de la ejecución fue la siguiente:
    ```
    {output_content}
    ```
    
    Evalúa si la tarea se completó con éxito basándote en la salida.
    - Si la tarea se completó con éxito y NO es la última tarea del plan, responde 'next_task'.
    - Si la tarea se completó con éxito y ES la última tarea del plan, responde 'plan_completed'.
    - Si la tarea falló y debe reintentarse (por ejemplo, un error temporal), responde 'retry_task'.
    - Si la tarea falló y no se puede recuperar (error fatal), responde 'error_task' y explica brevemente el problema.
    Sé conciso y solo proporciona una de las palabras clave.
    """
    
    evaluation, _ = interpreter.chat(prompt, add_to_history=False)
    evaluation = evaluation.strip().lower()

    if evaluation == "next_task":
        next_index = state.current_task_index + 1
        if next_index < len(state.plan):
            return {"current_task_index": next_index, "status": "executing_task", "action_needed": "execute_command"}
        else:
            # Si es la última tarea y se evalúa como next_task, significa que el plan está completo.
            return {"status": "finished", "final_response": "Plan completado con éxito.", "action_needed": "respond_final"}
    elif evaluation == "plan_completed":
        return {"status": "finished", "final_response": "Plan completado con éxito.", "action_needed": "respond_final"}
    elif evaluation == "retry_task":
        return {"status": "executing_task", "action_needed": "execute_command", "final_response": f"Reintentando la tarea: {current_task_description}. Problema detectado: {evaluation}"}
    elif evaluation == "error_task":
        return {"status": "cancelled", "final_response": f"Error al ejecutar la tarea: {current_task_description}. Problema: {evaluation}", "action_needed": "respond_final"}
    else:
        return {"status": "cancelled", "final_response": f"No se pudo evaluar la salida para la tarea: {current_task_description}. Evaluación del LLM: {evaluation}", "action_needed": "respond_final"}

# Build the graph
orchestrator_graph = StateGraph(OrchestratorState)

# Add nodes
orchestrator_graph.add_node("create_plan", create_plan_node)
orchestrator_graph.add_node("present_plan", present_plan_node)
orchestrator_graph.add_node("handle_approval", handle_approval_node)
orchestrator_graph.add_node("execute_task", execute_task_node)
orchestrator_graph.add_node("handle_output", handle_output_node)

# Set entry point
orchestrator_graph.set_conditional_entry_point(
    lambda state: "handle_approval" if state.reinvoke_for_approval else "create_plan",
    {
        "handle_approval": "handle_approval",
        "create_plan": "create_plan"
    }
)

# Add edges
orchestrator_graph.add_edge("create_plan", "present_plan")

# Conditional edges from present_plan
orchestrator_graph.add_edge("present_plan", END) # Always end after presenting plan for user approval

# Conditional edges from handle_approval
orchestrator_graph.add_conditional_edges(
    "handle_approval",
    lambda state: state.status, # Condition based on status
    {
        "executing_task": "execute_task",
        "cancelled": END
    }
)

# Conditional edges from execute_task (orchestrator pauses here, terminal re-invokes)
orchestrator_graph.add_edge("execute_task", "handle_output") # Always goes to handle output

# Conditional edges from handle_output
orchestrator_graph.add_conditional_edges(
    "handle_output",
    lambda state: state.status, # Condition based on status set by evaluation
    {
        "executing_task": "execute_task", # Next task or retry
        "finished": END,
        "cancelled": END
    }
)

# Compile the graph
orchestrator_app = orchestrator_graph.compile()