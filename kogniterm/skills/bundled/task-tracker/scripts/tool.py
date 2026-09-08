"""
Skill: task_tracker
Permite a los agentes gestionar una lista de tareas compartida con panel visual.

Las tareas son exclusivamente en memoria para la sesión activa.
Al inicio de cada sesión el estado siempre empieza limpio (sin huérfanos).
"""
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Almacenamiento en memoria para esta sesión (por agente).
# Se reinicia completamente al cargar el módulo (= inicio de sesión).
_agent_plans: Dict[str, List[Dict[str, Any]]] = {}
_llm_service: Any = None  # Será inyectado por el SkillLoader

STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in-progress"
STATUS_DONE = "done"

VALID_STATUSES = {STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_DONE}


def _clear_persisted_state():
    """Borra el archivo de estado en disco si existe, para no cargar huérfanos."""
    try:
        get_state = globals().get('get_skill_state')
        save_state = globals().get('save_skill_state')
        if save_state:
            # Sobreescribir con dict vacío para limpiar el archivo en disco
            save_state({})
    except Exception as e:
        logger.debug(f"Error limpiando estado en disco: {e}")


def _update_ui():
    """Actualiza el panel lateral de tareas en la UI (TUI o ServerUI)."""
    global _agent_plans, _llm_service
    try:
        import sys
        tui = globals().get('_terminal_ui')
        llm_svc = _llm_service or globals().get('_llm_service')

        if not tui:
            mod = sys.modules.get("_task_tracker_bundled_tool")
            if mod:
                tui = getattr(mod, "_terminal_ui", None)
                if not llm_svc:
                    llm_svc = getattr(mod, "_llm_service", None)

        if not tui and llm_svc:
            if hasattr(llm_svc, 'terminal_ui') and llm_svc.terminal_ui:
                tui = llm_svc.terminal_ui
            elif hasattr(llm_svc, 'skill_manager') and llm_svc.skill_manager and getattr(llm_svc.skill_manager, 'terminal_ui', None):
                tui = llm_svc.skill_manager.terminal_ui

        if tui and hasattr(tui, 'update_task_tracker'):
            tui.update_task_tracker(_agent_plans)
    except Exception as e:
        logger.debug(f"Error actualizando UI de tareas: {e}")


def _normalize_agent_name(agent_name: str) -> str:
    """Normaliza el nombre del agente para evitar inconsistencias."""
    return agent_name.strip().lower().replace(" ", "_")


def _normalize_plan(plan: Any) -> List[str]:
    """Normaliza el plan garantizando que sea una lista de tareas limpias y no un JSON serializado."""
    if not plan:
        return []
    if isinstance(plan, str):
        plan_str = plan.strip()
        if plan_str.startswith("[") and plan_str.endswith("]"):
            try:
                import json
                parsed = json.loads(plan_str)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass
        if "\n" in plan_str:
            return [line.strip().lstrip("-*0123456789. ") for line in plan_str.split("\n") if line.strip()]
        return [plan_str]
    elif isinstance(plan, (list, tuple)):
        return [str(item).strip() for item in plan if str(item).strip()]
    return [str(plan)]


def _init_tasks(agent_name: str, plan: Any) -> str:
    """Inicializa la lista de tareas para un agente."""
    global _agent_plans
    normalized_name = _normalize_agent_name(agent_name)
    clean_plan = _normalize_plan(plan)
    if not clean_plan:
        return "❌ Error: 'plan' debe contener al menos una tarea válida."
    _agent_plans[normalized_name] = [{"task": t, "status": STATUS_PENDING} for t in clean_plan]
    _update_ui()
    return f"✅ Plan de {len(_agent_plans[normalized_name])} tareas inicializado para '{normalized_name}'."


def _update_task(agent_name: str, task_index: Any, status: str) -> str:
    """Marca una tarea como completada o en curso para un agente."""
    global _agent_plans
    normalized_name = _normalize_agent_name(agent_name)

    if status not in VALID_STATUSES:
        return f"❌ Error: estado '{status}' no válido. Usa: {', '.join(sorted(VALID_STATUSES))}"

    if normalized_name not in _agent_plans:
        return f"❌ Error: agente '{agent_name}' no encontrado. Inicializa un plan primero con action='init'."

    tasks = _agent_plans[normalized_name]
    try:
        idx = int(task_index)
    except (ValueError, TypeError):
        return f"❌ Error: índice '{task_index}' no es un número entero válido."

    if idx < 0 or idx >= len(tasks):
        return f"❌ Error: índice {idx} fuera de rango. El plan tiene {len(tasks)} tareas (0-{len(tasks)-1})."

    old_status = tasks[idx]["status"]
    tasks[idx]["status"] = status
    _update_ui()

    if old_status == status:
        return f"ℹ️ Tarea {idx} de '{normalized_name}' ya estaba en estado '{status}'."
    return f"✅ Tarea {idx} de '{normalized_name}' actualizada: '{old_status}' → '{status}'."


def _batch_update_tasks(agent_name: str, updates: Any) -> str:
    """Aplica múltiples actualizaciones de estado en una sola llamada atómica."""
    global _agent_plans
    normalized_name = _normalize_agent_name(agent_name)

    if normalized_name not in _agent_plans:
        return f"❌ Error: agente '{agent_name}' no encontrado. Inicializa un plan primero con action='init'."

    if isinstance(updates, str):
        try:
            import json
            parsed = json.loads(updates)
            if isinstance(parsed, list):
                updates = parsed
        except Exception:
            pass

    tasks = _agent_plans[normalized_name]
    successes: List[str] = []
    errors: List[str] = []

    for i, update in enumerate(updates or []):
        if not isinstance(update, dict):
            errors.append(f"item #{i}: se esperaba un objeto {{'task_index', 'status'}}")
            continue

        raw_idx = update.get("task_index")
        status = update.get("status")

        if status not in VALID_STATUSES:
            errors.append(f"item #{i}: estado '{status}' no válido. Usa: {', '.join(sorted(VALID_STATUSES))}")
            continue

        try:
            task_index = int(raw_idx)
        except (ValueError, TypeError):
            errors.append(f"item #{i}: índice '{raw_idx}' no es un entero")
            continue

        if task_index < 0 or task_index >= len(tasks):
            errors.append(f"item #{i}: índice {task_index} fuera de rango (0-{len(tasks)-1})")
            continue

        old_status = tasks[task_index]["status"]
        tasks[task_index]["status"] = status
        successes.append(f"#{task_index}: '{old_status}' → '{status}'")

    if successes:
        _update_ui()

    lines: List[str] = []
    if successes:
        lines.append(f"✅ {len(successes)} actualizaciones aplicadas a '{normalized_name}':")
        lines.extend(f"   • Tarea {s}" for s in successes)
    if errors:
        lines.append(f"❌ {len(errors)} actualizaciones con error:")
        lines.extend(f"   • {e}" for e in errors)

    if not lines:
        return "ℹ️ No se proporcionaron actualizaciones válidas."
    return "\n".join(lines)



def _get_status(agent_name: str = None) -> str:
    """Devuelve el estado actual de todas las tareas (o de un agente)."""
    global _agent_plans
    if not _agent_plans:
        return "📋 No hay tareas inicializadas."

    if agent_name:
        normalized_name = _normalize_agent_name(agent_name)
        if normalized_name not in _agent_plans:
            return f"❌ Error: agente '{agent_name}' no encontrado."
        tasks = _agent_plans[normalized_name]
        summary = "\n".join([f"{i}. [{t['status'].upper()}] {t['task']}" for i, t in enumerate(tasks)])
        return f"📋 Estado del Plan de '{normalized_name}':\n{summary}"

    # Resumen general
    all_summary = []
    for agent, tasks in _agent_plans.items():
        summary = "\n".join([f"  {i}. [{t['status'].upper()}] {t['task']}" for i, t in enumerate(tasks)])
        all_summary.append(f"Agente: {agent}\n{summary}")

    return "📋 Estado de todos los Planes:\n" + "\n\n".join(all_summary)


def _show_task_tracker_panel():
    """Muestra el panel de tareas en la TUI."""
    global _agent_plans, _llm_service
    if not _llm_service:
        return

    try:
        tui = None
        if hasattr(_llm_service, 'terminal_ui') and _llm_service.terminal_ui:
            tui = _llm_service.terminal_ui
        elif hasattr(_llm_service, 'skill_manager') and _llm_service.skill_manager and getattr(_llm_service.skill_manager, 'terminal_ui', None):
            tui = _llm_service.skill_manager.terminal_ui
        elif globals().get('_terminal_ui'):
            tui = globals().get('_terminal_ui')

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
                "description": "Nombre identificador del agente (ej. 'BashAgent', 'Researcher', 'Coder')."
            },
            "plan": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lista de tareas para 'init'."
            },
            "task_index": {
                "type": "integer",
                "description": "Índice de la tarea para 'update' (0-indexed). Usa 'updates' para cambiar varias a la vez."
            },
            "status": {
                "type": "string",
                "description": f"Nuevo estado: {', '.join(sorted(VALID_STATUSES))}."
            },
            "updates": {
                "type": "array",
                "description": (
                    "Lista de cambios a aplicar de una sola vez en 'update'. "
                    "Cada elemento debe ser un objeto {'task_index': int, 'status': str}."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "task_index": {"type": "integer", "minimum": 0},
                        "status": {
                            "type": "string",
                            "enum": sorted(VALID_STATUSES),
                        },
                    },
                    "required": ["task_index", "status"],
                },
            },
        },
        "required": ["action", "agent_name"]
    }
}


def task_tracker(
    action: str,
    agent_name: str = "kogni_agent",
    plan: List[str] = None,
    task_index: int = None,
    status: str = None,
    updates: List[Dict[str, Any]] = None,
) -> str:
    """
    Gestiona planes de trabajo especializados para cada agente.

    Para aplicar varios cambios en una sola llamada, usa ``action="update"`` con
    ``updates=[{"task_index": 0, "status": "done"}, {"task_index": 1, "status": "in-progress"}]``.
    """
    if action == "init":
        if not plan:
            return "❌ Error: 'plan' es requerido para action='init'. Proporciona una lista de tareas."
        result = _init_tasks(agent_name, plan)
        return result
    elif action == "update":
        if updates is not None:
            return _batch_update_tasks(agent_name, updates)
        if task_index is None:
            return "❌ Error: 'task_index' es requerido para action='update' (o usa 'updates' para varias a la vez)."
        if status is None:
            return "❌ Error: 'status' es requerido para action='update'."
        result = _update_task(agent_name, task_index, status)
        return result
    elif action == "get":
        return _get_status(agent_name)
    elif action == "show":
        _show_task_tracker_panel()
        return "🖥️ Panel de tareas actualizado."
    return f"❌ Error: acción '{action}' no reconocida. Usa: init, update, get, show."


# Para inyección de dependencias por parte del SkillLoader
def set_llm_service(llm_service: Any = None, *args, **kwargs):
    """Inyecta el servicio LLM para acceso a la TUI."""
    global _llm_service
    if llm_service is not None:
        _llm_service = llm_service

    # Si se llama como herramienta por error (ej. se pasa 'action'), delegar a task_tracker
    if 'action' in kwargs or (args and isinstance(args[0], str)):
        action = kwargs.get('action') or args[0]
        agent_name = kwargs.get('agent_name', 'kogni_agent')
        plan = kwargs.get('plan')
        task_index = kwargs.get('task_index')
        status = kwargs.get('status')
        updates = kwargs.get('updates')
        return task_tracker(
            action=action,
            agent_name=agent_name,
            plan=plan,
            task_index=task_index,
            status=status,
            updates=updates,
        )

