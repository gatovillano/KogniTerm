import importlib.util
from pathlib import Path
import pytest

# Cargar dinámicamente el módulo task-tracker con guión en la ruta
tt_path = Path(__file__).resolve().parent.parent / "kogniterm" / "skills" / "bundled" / "task-tracker" / "scripts" / "tool.py"
spec = importlib.util.spec_from_file_location("_task_tracker_bundled_tool", str(tt_path))
task_tracker_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task_tracker_mod)

task_tracker = task_tracker_mod.task_tracker
_get_session_plans = task_tracker_mod._get_session_plans
clear_session_tasks = task_tracker_mod.clear_session_tasks

from kogniterm.server.session_pool import session_context


class MockUI:
    def __init__(self, session_id):
        self.session_id = session_id
        self.last_plans = None

    def update_task_tracker(self, agent_plans: dict):
        self.last_plans = agent_plans


def test_task_tracker_session_isolation():
    session_a = "session_alpha"
    session_b = "session_beta"

    ui_a = MockUI(session_a)
    ui_b = MockUI(session_b)

    # 1. En Sesión A, inicializar tareas de BashAgent
    with session_context(cwd=".", session_id=session_a, terminal_ui=ui_a):
        res_a = task_tracker(
            action="init",
            agent_name="BashAgent",
            plan=["Tarea A1", "Tarea A2"],
        )
        assert "✅" in res_a
        assert ui_a.last_plans is not None
        assert "bashagent" in ui_a.last_plans
        assert len(ui_a.last_plans["bashagent"]) == 2
        assert ui_a.last_plans["bashagent"][0]["task"] == "Tarea A1"

    # 2. En Sesión B, inicializar tareas distintas para Coder y BashAgent
    with session_context(cwd=".", session_id=session_b, terminal_ui=ui_b):
        res_b = task_tracker(
            action="init",
            agent_name="Coder",
            plan=["Tarea B1"],
        )
        assert "✅" in res_b
        assert ui_b.last_plans is not None
        assert "coder" in ui_b.last_plans
        # Sesión B NO debe tener las tareas de Sesión A
        assert "bashagent" not in ui_b.last_plans
        assert len(ui_b.last_plans["coder"]) == 1

    # 3. Verificar consulta de estado 'get' para cada sesión
    with session_context(cwd=".", session_id=session_a, terminal_ui=ui_a):
        status_a = task_tracker(action="get")
        assert "Tarea A1" in status_a
        assert "Tarea B1" not in status_a

    with session_context(cwd=".", session_id=session_b, terminal_ui=ui_b):
        status_b = task_tracker(action="get")
        assert "Tarea B1" in status_b
        assert "Tarea A1" not in status_b

    # 4. Actualizar tarea en Sesión A y verificar que Sesión B permanece inalterada
    with session_context(cwd=".", session_id=session_a, terminal_ui=ui_a):
        task_tracker(action="update", agent_name="BashAgent", task_index=0, status="done")
        assert ui_a.last_plans["bashagent"][0]["status"] == "done"

    plans_b = _get_session_plans(session_b)
    assert "coder" in plans_b
    assert plans_b["coder"][0]["status"] == "pending"

    # 5. Limpieza de sesión
    clear_session_tasks(session_a)
    plans_a_cleaned = _get_session_plans(session_a)
    assert plans_a_cleaned == {}
    # Sesión B debe seguir existiendo intacta
    assert "coder" in _get_session_plans(session_b)

    # Clean up
    clear_session_tasks(session_b)
