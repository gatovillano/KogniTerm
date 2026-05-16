"""
Skill: task_tracker
Permite a los agentes gestionar una lista de tareas compartida con panel visual.
"""
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)

# Almacenamiento en memoria para esta sesión (por agente)
_agent_plans: Dict[str, List[Dict[str, Any]]] = {}
_llm_service: Any = None  # Será inyectado por el SkillLoader

def _update_ui():
    """Actualiza el panel lateral de tareas en la TUI."""
    global _agent_plans, _llm_service
    if not _llm_service:
        return
        
    try:
        # Usar el adaptador de TUI para actualizar el panel de tareas
        if hasattr(_llm_service, 'terminal_ui') and _llm_service.terminal_ui:
            tui = _llm_service.terminal_ui
            if hasattr(tui, 'update_task_tracker'):
                tui.update_task_tracker(_agent_plans)
    except Exception as e:
        logger.debug(f"Error actualizando UI de tareas: {e}")

def _init_tasks(agent_name: str, plan: List[str]) -> str:
    """Inicializa la lista de tareas para un agente."""
    global _agent_plans
    _agent_plans[agent_name] = [{"task": t, "status": "pending"} for t in plan]
    _update_ui()
    return f"Plan de {len(_agent_plans[agent_name])} tareas inicializado para {agent_name}."

def _update_task(agent_name: str, task_index: int, status: str) -> str:
    """Marca una tarea como completada o en curso para un agente."""
    global _agent_plans
    if agent_name in _agent_plans:
        tasks = _agent_plans[agent_name]
        if 0 <= task_index < len(tasks):
            tasks[task_index]["status"] = status
            _update_ui()
            return f"Tarea {task_index} de {agent_name} marcada como {status}."
    return f"Error: agente '{agent_name}' no encontrado o índice inválido."

def _get_status(agent_name: str = None) -> str:
    """Devuelve el estado actual de todas las tareas (o de un agente)."""
    global _agent_plans
    if not _agent_plans:
        return "No hay tareas inicializadas."
    
    if agent_name and agent_name in _agent_plans:
        tasks = _agent_plans[agent_name]
        summary = "\n".join([f"{i}. [{t['status'].upper()}] {t['task']}" for i, t in enumerate(tasks)])
        return f"Estado del Plan de {agent_name}:\n{summary}"
    
    # Resumen general
    all_summary = []
    for agent, tasks in _agent_plans.items():
        summary = "\n".join([f"  {i}. [{t['status'].upper()}] {t['task']}" for i, t in enumerate(tasks)])
        all_summary.append(f"Agente: {agent}\n{summary}")
    
    return "Estado de todos los Planes:\n" + "\n\n".join(all_summary)

def _show_task_tracker_panel():
    """Muestra el panel de tareas en la TUI."""
    global _agent_plans, _llm_service
    if not _llm_service:
        return
        
    try:
        tui = _llm_service.terminal_ui
        if tui and hasattr(tui, 'update_task_tracker'):
            tui.update_task_tracker(_agent_plans)
    except Exception as e:
        logger.debug(f"Error mostrando panel: {e}")

tool_schema = {
    "name": "task_tracker",
    "description": "Gestiona planes de trabajo especializados para cada agente con panel visual.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Acción: 'init', 'update', 'get', 'show'.",
                "enum": ["init", "update", "get", "show"]
            },
            "agent_name": {
                "type": "string",
                "description": "Nombre identificador del agente (ej. 'Researcher', 'Coder')."
            },
            "plan": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lista de tareas para 'init'."
            },
            "task_index": {
                "type": "integer",
                "description": "Índice de la tarea para 'update'."
            },
            "status": {
                "type": "string",
                "description": "Nuevo estado (ej. 'done', 'in-progress')."
            }
        },
        "required": ["action", "agent_name"]
    }
}

def task_tracker(action: str, agent_name: str, plan: List[str] = None, task_index: int = None, status: str = None) -> str:
    """
    Gestiona planes de trabajo especializados para cada agente.
    """
    if action == "init":
        result = _init_tasks(agent_name, plan or [])
        # Mostrar el panel después de inicializar
        _show_task_tracker_panel()
        return result
    elif action == "update":
        result = _update_task(agent_name, task_index, status)
        return result
    elif action == "get":
        return _get_status(agent_name)
    elif action == "show":
        _show_task_tracker_panel()
        return "Panel de tareas mostrado."
    return "Acción no reconocida."

# Para inyección de dependencias por parte del SkillLoader
def set_llm_service(llm_service: Any):
    """Inyecta el servicio LLM para acceso a la TUI."""
    global _llm_service
    _llm_service = llm_service