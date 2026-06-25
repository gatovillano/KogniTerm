"""Tests del flujo batch de la skill task_tracker."""
import importlib.util
import os
import sys
from pathlib import Path


SKILL_PATH = Path(__file__).resolve().parents[2] / "kogniterm/skills/bundled/task-tracker/scripts/tool.py"


def _load_skill_module():
    """Carga limpia del módulo del skill (resetea estado entre tests)."""
    spec = importlib.util.spec_from_file_location("task_tracker_skill", SKILL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Estado fresco por test
    module._agent_plans.clear()
    module._llm_service = None
    return module


# --- init + batch update ----------------------------------------------------

def test_batch_update_aplica_cambios_y_reporta_exitos():
    skill = _load_skill_module()

    skill.task_tracker(action="init", agent_name="AgentX", plan=["A", "B", "C"])

    out = skill.task_tracker(
        action="update",
        agent_name="AgentX",
        updates=[
            {"task_index": 0, "status": "done"},
            {"task_index": 1, "status": "in-progress"},
        ],
    )

    assert "2 actualizaciones aplicadas" in out
    assert "Tarea #0" in out and "Tarea #1" in out

    # Estado final debe reflejar los cambios en lote.
    plan = skill._agent_plans["agentx"]
    assert [t["status"] for t in plan] == ["done", "in-progress", "pending"]


def test_batch_update_parcial_solo_aplica_validos():
    skill = _load_skill_module()

    skill.task_tracker(action="init", agent_name="AgentY", plan=["A", "B"])
    out = skill.task_tracker(
        action="update",
        agent_name="AgentY",
        updates=[
            {"task_index": 0, "status": "done"},
            {"task_index": 99, "status": "done"},        # fuera de rango
            {"task_index": 1, "status": "bogus"},         # estado inválido
            {"task_index": 1, "status": "in-progress"},   # válido
            "no es un dict",
            {"task_index": -1, "status": "done"},         # negativo
        ],
    )

    assert "2 actualizaciones aplicadas" in out
    assert "4 actualizaciones con error" in out

    plan = skill._agent_plans["agenty"]
    assert [t["status"] for t in plan] == ["done", "in-progress"]


def test_batch_update_sin_updates_con_param_no_es_none():
    """Cuando no se pasa updates, el modo unitario sigue activo."""
    skill = _load_skill_module()

    skill.task_tracker(action="init", agent_name="AgentZ", plan=["A", "B"])
    out = skill.task_tracker(
        action="update", agent_name="AgentZ", task_index=0, status="done"
    )

    assert "Tarea 0 de 'agentz' actualizada" in out
    assert skill._agent_plans["agentz"][0]["status"] == "done"


def test_batch_update_sin_updates_ni_unitario_da_error_explicito():
    skill = _load_skill_module()
    skill.task_tracker(action="init", agent_name="AgentW", plan=["A"])

    out = skill.task_tracker(action="update", agent_name="AgentW")

    assert "'task_index' es requerido" in out
    assert "updates" in out  # sugiere el modo batch


def test_batch_update_sin_init_reporta_error_legible():
    skill = _load_skill_module()

    out = skill.task_tracker(
        action="update",
        agent_name="NoIniciado",
        updates=[{"task_index": 0, "status": "done"}],
    )

    assert "no encontrado" in out.lower()
    assert "init" in out


def test_batch_update_actualiza_ui_una_sola_vez_si_hay_exitos():
    skill = _load_skill_module()
    skill.task_tracker(action="init", agent_name="AgentUI", plan=["A", "B", "C"])

    calls = []

    def fake_update():
        calls.append("update")

    skill._update_ui = fake_update

    skill.task_tracker(
        action="update",
        agent_name="AgentUI",
        updates=[
            {"task_index": 0, "status": "done"},
            {"task_index": 1, "status": "in-progress"},
        ],
    )

    assert len(calls) == 1


def test_batch_update_no_llama_ui_si_todos_los_items_fallan():
    skill = _load_skill_module()
    skill.task_tracker(action="init", agent_name="AgentUI2", plan=["A"])

    calls = []

    skill._update_ui = lambda: calls.append("update")

    skill.task_tracker(
        action="update",
        agent_name="AgentUI2",
        updates=[
            {"task_index": 99, "status": "done"},
            {"task_index": 0, "status": "bogus"},
        ],
    )

    assert calls == []


def test_batch_update_con_lista_vacia_devuelve_mensaje_amigable():
    skill = _load_skill_module()
    skill.task_tracker(action="init", agent_name="AgentEmpty", plan=["A"])

    out = skill.task_tracker(
        action="update", agent_name="AgentEmpty", updates=[]
    )

    assert "No se proporcionaron" in out


def test_batch_update_schema_declara_updates():
    """El schema expuesto al LLM debe declarar la propiedad 'updates'."""
    skill = _load_skill_module()
    props = skill.tool_schema["parameters"]["properties"]

    assert "updates" in props
    assert props["updates"]["type"] == "array"
    assert props["updates"]["items"]["required"] == ["task_index", "status"]


def test_init_no_se_rompe_con_updates_basura():
    """Pasar 'updates' en init no debe afectar la inicialización."""
    skill = _load_skill_module()

    out = skill.task_tracker(
        action="init",
        agent_name="AgentIgnore",
        plan=["A"],
        updates=[{"task_index": 0, "status": "done"}],
    )

    assert "inicializado" in out
    assert skill._agent_plans["agentignore"][0]["status"] == "pending"
