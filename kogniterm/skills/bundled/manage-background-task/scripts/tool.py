"""
Skill: manage_background_task
Permite listar, consultar logs y cancelar tareas en segundo plano.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

name = "manage_background_task"
description = "Consulta, monitorea o cancela tareas ejecutadas en segundo plano."


def _get_background_manager():
    global_service = globals().get('_llm_service')
    bg_manager = None
    if global_service and hasattr(global_service, 'command_executor') and global_service.command_executor:
        bg_manager = getattr(global_service.command_executor, 'background_task_manager', None)
    if not bg_manager:
        from kogniterm.core.background_task_manager import get_default_background_task_manager
        bg_manager = get_default_background_task_manager()
    return bg_manager


def manage_background_task(
    action: str,
    task_id: Optional[str] = None,
    tail_lines: int = 50
) -> str:
    """
    Gestiona tareas en segundo plano.

    Args:
        action: Acción a realizar: 'list' (listar tareas), 'status' (consultar estado y logs), 'kill' (cancelar tarea).
        task_id: ID de la tarea (requerido para 'status' y 'kill').
        tail_lines: Número de últimas líneas a obtener en 'status' (default: 50).

    Returns:
        str: Resultado de la operación en texto plano o JSON.
    """
    bg_manager = _get_background_manager()
    action = action.lower().strip()

    if action == "list":
        tasks = bg_manager.list_tasks()
        if not tasks:
            return "No hay tareas registradas en segundo plano."
        lines = ["📋 Tareas en segundo plano:"]
        for t in tasks:
            lines.append(f" - [{t['task_id']}] ({t['status']}) PID: {t['pid'] or 'N/A'} | Comando: '{t['command']}' (Duración: {t['duration_seconds']}s)")
        return "\n".join(lines)

    elif action == "status":
        if not task_id:
            return "❌ Error: 'task_id' es requerido para consultar el estado."
        info = bg_manager.get_task_status(task_id)
        if not info:
            return f"❌ Error: Tarea '{task_id}' no encontrada."
        
        output_snippet = info.get("output", "").rstrip()
        if not output_snippet:
            output_snippet = "(Sin salida registrada aún)"
            
        res = [
            f"🔍 Estado de la tarea {info['task_id']}:",
            f" - Estado: {info['status'].upper()}",
            f" - Comando: {info['command']}",
            f" - PID: {info['pid'] or 'N/A'}",
            f" - Código de salida: {info['exit_code'] if info['exit_code'] is not None else 'N/A'}",
            f" - Duración: {info['duration_seconds']}s",
            "\n--- Última salida ---",
            output_snippet
        ]
        return "\n".join(res)

    elif action == "kill":
        if not task_id:
            return "❌ Error: 'task_id' es requerido para cancelar una tarea."
        success = bg_manager.kill_task(task_id)
        if success:
            return f"🛑 Tarea '{task_id}' cancelada exitosamente."
        return f"⚠️ No se pudo cancelar la tarea '{task_id}' (quizás ya finalizó o no existe)."

    else:
        return f"❌ Error: Acción '{action}' no válida. Usa 'list', 'status', o 'kill'."


def get_action_description(action: str, task_id: Optional[str] = None, **kwargs) -> str:
    if action == "list":
        return "Listando tareas en segundo plano"
    elif action == "status":
        return f"Consultando estado de tarea en segundo plano '{task_id}'"
    elif action == "kill":
        return f"Deteniendo tarea en segundo plano '{task_id}'"
    return f"Gestionando tarea en segundo plano: action='{action}'"


parameters_schema = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": "Acción a realizar: 'list' (listar tareas), 'status' (consultar estado y logs), 'kill' (cancelar tarea).",
            "enum": ["list", "status", "kill"]
        },
        "task_id": {
            "type": "string",
            "description": "ID de la tarea en segundo plano (ej: 'task-1'). Requerido para 'status' y 'kill'."
        },
        "tail_lines": {
            "type": "integer",
            "description": "Número de últimas líneas a mostrar al consultar el estado (default: 50).",
            "default": 50
        }
    },
    "required": ["action"]
}
