from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Any
from ..interpreter import Interpreter # Assuming Interpreter is in parent directory

# Initialize the interpreter globally for now
interpreter = Interpreter()

@dataclass
class OrchestratorState:
    user_query: str = ""
    plan: List[str] = field(default_factory=list) # List of tasks/steps
    plan_presentation: str = ""
    
    # Fields for execution:
    current_task_index: int = 0
    user_approval: str = "" # 's' or 'n' from terminal
    command_to_execute: str = "" # Command to be executed by terminal
    command_output: str = "" # Output from terminal
    final_response: str = ""
    status: str = "planning" # planning, awaiting_approval, executing_task, awaiting_output, finished, cancelled
    action_needed: str = "" # "present_plan", "execute_command", "respond_final"

def create_plan_node(state: OrchestratorState):
    """Calls the LLM to generate a plan based on the user's query."""
    prompt = f"Eres un asistente experto en planificación. Basado en la siguiente solicitud del usuario, crea un plan detallado paso a paso para lograrla. Cada paso debe ser una acción clara y concisa. Lista los pasos como una lista numerada. La solicitud es: '{state.user_query}'"
    
    plan_text, _ = interpreter.chat(prompt, add_to_history=False)
    
    plan_list = [step.strip() for step in plan_text.split('\n') if step.strip()]
    
    # Return a dictionary to update the state
    return {"plan": plan_list, "status": "awaiting_approval", "action_needed": "present_plan"}

def present_plan_node(state: OrchestratorState):
    """Formats the generated plan for presentation to the user."""
    presentation = "He creado el siguiente plan para ti:\n\n"
    for i, step in enumerate(state.plan):
        presentation += f"{i+1}. {step}\n"
    presentation += "\n¿Te gustaría que lo ejecute? (s/n)"
    
    # Return a dictionary to update the state
    return {"plan_presentation": presentation}

def handle_approval_node(state: OrchestratorState):
    """Handles user's approval for the plan."""
    if state.user_approval.lower() == 's':
        return {"status": "executing_task", "action_needed": "execute_command", "current_task_index": 0}
    else:
        return {"status": "cancelled", "final_response": "Plan cancelado por el usuario.", "action_needed": "respond_final"}

def execute_task_node(state: OrchestratorState):
    """Extracts the current task and sets command_to_execute for terminal."""
    if state.current_task_index >= len(state.plan):
        return {"status": "finished", "final_response": "Plan completado.", "action_needed": "respond_final"}

    current_task = state.plan[state.current_task_index]
    
    prompt = f"Genera el comando bash para la siguiente tarea: '{current_task}'. Solo el comando, sin explicaciones."
    command, _ = interpreter.chat(prompt, add_to_history=False) # Get command from LLM
    
    return {"command_to_execute": command.strip(), "status": "awaiting_output", "action_needed": "execute_command"}

def handle_command_output_node(state: OrchestratorState):
    """Evaluates command output and decides next step."""
    prompt = f"El comando '{state.command_to_execute}' ha sido ejecutado con la siguiente salida:\n```\n{state.command_output}\n```\nLa tarea actual en el plan es: '{state.plan[state.current_task_index]}'. Evalúa si la tarea se completó con éxito. Si es así, indica 'next_task'. Si no, indica 'retry_task' o 'error_task' y explica el problema. Si el plan ha terminado, indica 'plan_completed'."
    
    evaluation, _ = interpreter.chat(prompt, add_to_history=False)
    evaluation = evaluation.strip().lower()

    if "next_task" in evaluation:
        return {"current_task_index": state.current_task_index + 1, "status": "executing_task", "action_needed": "execute_command"}
    elif "plan_completed" in evaluation:
        return {"status": "finished", "final_response": "Plan completado con éxito.", "action_needed": "respond_final"}
    elif "retry_task" in evaluation:
        return {"status": "executing_task", "action_needed": "execute_command", "final_response": f"Reintentando la tarea: {state.plan[state.current_task_index]}. Problema detectado: {evaluation}"}
    elif "error_task" in evaluation:
        return {"status": "cancelled", "final_response": f"Error al ejecutar la tarea: {state.plan[state.current_task_index]}. Problema: {evaluation}", "action_needed": "respond_final"}
    else:
        return {"status": "cancelled", "final_response": f"No se pudo evaluar la salida del comando para la tarea: {state.plan[state.current_task_index]}. Evaluación del LLM: {evaluation}", "action_needed": "respond_final"}

# Build the graph
orchestrator_graph = StateGraph(OrchestratorState)

# Add nodes
orchestrator_graph.add_node("create_plan", create_plan_node)
orchestrator_graph.add_node("present_plan", present_plan_node)
orchestrator_graph.add_node("handle_approval", handle_approval_node)
orchestrator_graph.add_node("execute_task", execute_task_node)
orchestrator_graph.add_node("handle_command_output", handle_command_output_node)

# Set entry point
orchestrator_graph.set_entry_point("create_plan")

# Add edges
orchestrator_graph.add_edge("create_plan", "present_plan")

# Conditional edges from present_plan
orchestrator_graph.add_edge("present_plan", "handle_approval")

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
orchestrator_graph.add_edge("execute_task", "handle_command_output") # Always goes to handle output

# Conditional edges from handle_command_output
orchestrator_graph.add_conditional_edges(
    "handle_command_output",
    lambda state: state.status, # Condition based on status set by evaluation
    {
        "executing_task": "execute_task", # Next task or retry
        "finished": END,
        "cancelled": END
    }
)

# Compile the graph
orchestrator_app = orchestrator_graph.compile()