"""
Skill: task_tracker
Permite a los agentes gestionar una lista de tareas compartida con panel visual por sesión.

Las tareas son exclusivamente en memoria para cada sesión activa.
Cada sesión mantiene su propio almacenamiento de tareas aislado.
"""
from typing import List, Dict, Any, Optional
import logging
import sys

logger = logging.getLogger(__name__)

# Almacenamiento en memoria indexado por session_id y por agente.
# Estructura: _session_plans[session_id][agent_name] = [{"task": ..., "status": ...}, ...]
_session_plans: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
_llm_service: Any = None  # Será inyectado por el SkillLoader


class _AgentPlansProxy(dict):
    """Proxy de compatibilidad para código legacy/tests que accedían directamente a _agent_plans."""

    def __getitem__(self, key):
        return _get_session_plans()[key]

    def __setitem__(self, key, value):
        _get_session_plans()[key] = value

    def __delitem__(self, key):
        del _get_session_plans()[key]

    def __contains__(self, key):
        return key in _get_session_plans()

    def get(self, key, default=None):
        return _get_session_plans().get(key, default)

    def clear(self):
        _get_session_plans().clear()

    def items(self):
        return _get_session_plans().items()

    def keys(self):
        return _get_session_plans().keys()

    def values(self):
        return _get_session_plans().values()

    def __bool__(self):
        return bool(_get_session_plans())

    def __len__(self):
        return len(_get_session_plans())


_agent_plans = _AgentPlansProxy()

STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in-progress"
STATUS_DONE = "done"

VALID_STATUSES = {STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_DONE}


def _get_current_session_id() -> str:
    """Obtiene el session_id actual desde contextvars, _terminal_ui, _llm_service o default."""
    try:
        from kogniterm.server.session_pool import session_id_var
        sid = session_id_var.get()
        if sid:
            return sid
    except Exception:
        pass

    llm_svc = _llm_service or globals().get('_llm_service')
    if llm_svc and getattr(llm_svc, 'session_id', None):
        return llm_svc.session_id

    tui = globals().get('_terminal_ui')
    if tui and getattr(tui, 'session_id', None):
        return tui.session_id

    return "default"


def _get_session_plans(session_id: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Obtiene el diccionario de planes de agente para una sesión específica."""
    sid = session_id or _get_current_session_id()
    if sid not in _session_plans:
        _session_plans[sid] = {}
    return _session_plans[sid]


def clear_session_tasks(session_id: str) -> None:
    """Limpia las tareas de una sesión específica cuando esta se cierra o elimina."""
    global _session_plans
    if session_id in _session_plans:
        _session_plans.pop(session_id, None)
        logger.debug(f"Tareas limpiadas para sesión '{session_id}'.")


def _clear_persisted_state():
    """Borra el archivo de estado en disco si existe, para no cargar huérfanos."""
    try:
        save_state = globals().get('save_skill_state')
        if save_state:
            save_state({})
    except Exception as e:
        logger.debug(f"Error limpiando estado en disco: {e}")


def _get_tui_for_session(session_id: Optional[str] = None):
    """Obtiene la instancia de UI (TerminalUI / ServerUI) adecuada para la sesión."""
    try:
        from kogniterm.server.session_pool import session_ui_var
        tui = session_ui_var.get()
        if tui:
            return tui
    except Exception:
        pass

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

    return tui


def _update_ui(session_id: Optional[str] = None):
    """Actualiza el panel lateral de tareas en la UI (TUI o ServerUI) de la sesión dada."""
    sid = session_id or _get_current_session_id()
    plans = _get_session_plans(sid)
    try:
        tui = _get_tui_for_session(sid)
        if tui and hasattr(tui, 'update_task_tracker'):
            tui.update_task_tracker(plans)
    except Exception as e:
        logger.debug(f"Error actualizando UI de tareas para sesión {sid}: {e}")


def _call_update_ui(session_id: Optional[str] = None):
    """Llama a _update_ui de forma segura manejando monkeypatching de 0 argumentos en tests."""
    fn = globals().get("_update_ui", _update_ui)
    try:
        fn(session_id)
    except TypeError:
        try:
            fn()
        except Exception as e:
            logger.debug(f"Error actualizando UI: {e}")
    except Exception as e:
        logger.debug(f"Error actualizando UI: {e}")


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


def _init_tasks(agent_name: str, plan: Any, session_id: Optional[str] = None) -> str:
    """Inicializa la lista de tareas para un agente dentro de una sesión."""
    sid = session_id or _get_current_session_id()
    agent_plans = _get_session_plans(sid)
    normalized_name = _normalize_agent_name(agent_name)
    clean_plan = _normalize_plan(plan)
    if not clean_plan:
        return "❌ Error: 'plan' debe contener al menos una tarea válida."
    agent_plans[normalized_name] = [{"task": t, "status": STATUS_PENDING} for t in clean_plan]
    _call_update_ui(sid)
    return f"✅ Plan de {len(agent_plans[normalized_name])} tareas inicializado para '{normalized_name}'."


def _update_task(agent_name: str, task_index: Any, status: str, session_id: Optional[str] = None) -> str:
    """Marca una tarea como completada o en curso para un agente dentro de una sesión."""
    sid = session_id or _get_current_session_id()
    agent_plans = _get_session_plans(sid)
    normalized_name = _normalize_agent_name(agent_name)

    if status not in VALID_STATUSES:
        return f"❌ Error: estado '{status}' no válido. Usa: {', '.join(sorted(VALID_STATUSES))}"

    if normalized_name not in agent_plans:
        return f"❌ Error: agente '{agent_name}' no encontrado. Inicializa un plan primero con action='init'."

    tasks = agent_plans[normalized_name]
    try:
        idx = int(task_index)
    except (ValueError, TypeError):
        return f"❌ Error: índice '{task_index}' no es un número entero válido."

    if idx < 0 or idx >= len(tasks):
        return f"❌ Error: índice {idx} fuera de rango. El plan tiene {len(tasks)} tareas (0-{len(tasks)-1})."

    old_status = tasks[idx]["status"]
    tasks[idx]["status"] = status
    _call_update_ui(sid)

    if old_status == status:
        return f"ℹ️ Tarea {idx} de '{normalized_name}' ya estaba en estado '{status}'."
    return f"✅ Tarea {idx} de '{normalized_name}' actualizada: '{old_status}' → '{status}'."


def _batch_update_tasks(agent_name: str, updates: Any, session_id: Optional[str] = None) -> str:
    """Aplica múltiples actualizaciones de estado en una sola llamada atómica para una sesión."""
    sid = session_id or _get_current_session_id()
    agent_plans = _get_session_plans(sid)
    normalized_name = _normalize_agent_name(agent_name)

    if normalized_name not in agent_plans:
        return f"❌ Error: agente '{agent_name}' no encontrado. Inicializa un plan primero con action='init'."

    if isinstance(updates, str):
        try:
            import json
            parsed = json.loads(updates)
            if isinstance(parsed, list):
                updates = parsed
        except Exception:
            pass

    tasks = agent_plans[normalized_name]
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
        _call_update_ui(sid)

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


def _get_status(agent_name: str = None, session_id: Optional[str] = None) -> str:
    """Devuelve el estado actual de todas las tareas (o de un agente) para la sesión especificada."""
    sid = session_id or _get_current_session_id()
    agent_plans = _get_session_plans(sid)
    if not agent_plans:
        return "📋 No hay tareas inicializadas."

    if agent_name:
        normalized_name = _normalize_agent_name(agent_name)
        if normalized_name in agent_plans:
            tasks = agent_plans[normalized_name]
            summary = "\n".join([f"{i}. [{t['status'].upper()}] {t['task']}" for i, t in enumerate(tasks)])
            return f"📋 Estado del Plan de '{normalized_name}':\n{summary}"
        elif agent_name != "kogni_agent":
            return f"❌ Error: agente '{agent_name}' no encontrado."

    all_summary = []
    for agent, tasks in agent_plans.items():
        summary = "\n".join([f"  {i}. [{t['status'].upper()}] {t['task']}" for i, t in enumerate(tasks)])
        all_summary.append(f"Agente: {agent}\n{summary}")

    return "📋 Estado de todos los Planes:\n" + "\n\n".join(all_summary)


def _show_task_tracker_panel(session_id: Optional[str] = None):
    """Muestra el panel de tareas en la UI de la sesión."""
    sid = session_id or _get_current_session_id()
    _call_update_ui(sid)


tool_schema = {
    "name": "task_tracker",
    "description": "Gestiona planes de trabajo especializados para cada agente con panel visual por sesión.",
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
            "session_id": {
                "type": "string",
                "description": "Identificador opcional de sesión (por defecto se detecta del contexto)."
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
    session_id: Optional[str] = None,
) -> str:
    """
    Gestiona planes de trabajo especializados para cada agente.

    Para aplicar varios cambios en una sola llamada, usa ``action="update"`` con
    ``updates=[{"task_index": 0, "status": "done"}, {"task_index": 1, "status": "in-progress"}]``.
    """
    sid = session_id or _get_current_session_id()
    if action == "init":
        if not plan:
            return "❌ Error: 'plan' es requerido para action='init'. Proporciona una lista de tareas."
        result = _init_tasks(agent_name, plan, session_id=sid)
        return result
    elif action == "update":
        if updates is not None:
            return _batch_update_tasks(agent_name, updates, session_id=sid)
        if task_index is None:
            return "❌ Error: 'task_index' es requerido para action='update' (o usa 'updates' para varias a la vez)."
        if status is None:
            return "❌ Error: 'status' es requerido para action='update'."
        result = _update_task(agent_name, task_index, status, session_id=sid)
        return result
    elif action == "get":
        return _get_status(agent_name, session_id=sid)
    elif action == "show":
        _show_task_tracker_panel(session_id=sid)
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
        session_id = kwargs.get('session_id')
        return task_tracker(
            action=action,
            agent_name=agent_name,
            plan=plan,
            task_index=task_index,
            status=status,
            updates=updates,
            session_id=session_id,
        )
