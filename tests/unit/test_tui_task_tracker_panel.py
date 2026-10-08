import pytest
from rich.console import Group
from rich.text import Text
from kogniterm.terminal.tui.components.task_tracker_panel import TaskTrackerPanelWidget

def test_task_tracker_panel_visibility():
    widget = TaskTrackerPanelWidget()

    # 1. Sin tareas
    widget.update_tasks({})
    assert widget.display is False

    # 2. Con una tarea pendiente (replegado por defecto, pero visible)
    widget.update_tasks({"agent": [{"task": "tarea 1", "status": "pending"}]})
    assert widget.display is True
    assert widget.expanded is False

    # 3. Con todas las tareas completadas ("done")
    widget.update_tasks({"agent": [{"task": "tarea 1", "status": "done"}]})
    assert widget.display is False

    # 4. Con múltiples agentes y al menos una tarea no completada
    widget.update_tasks({
        "agent1": [{"task": "tarea 1", "status": "done"}],
        "agent2": [{"task": "tarea 2", "status": "in-progress"}]
    })
    assert widget.display is True

    # 5. Con múltiples agentes y todas las tareas completadas
    widget.update_tasks({
        "agent1": [{"task": "tarea 1", "status": "done"}],
        "agent2": [{"task": "tarea 2", "status": "done"}]
    })
    assert widget.display is False


def test_task_tracker_panel_completed_agent_disappears():
    widget = TaskTrackerPanelWidget()

    captured = []
    def fake_update(renderable):
        captured.append(renderable)
    widget.update = fake_update

    # agent1 has all tasks done (completed), agent2 has one in-progress task.
    widget.update_tasks({
        "agent1": [{"task": "tarea 1", "status": "done"}],
        "agent2": [{"task": "tarea 2", "status": "in-progress"}]
    })
    widget.expand()
    # Re-disparar el render en modo desplegado para capturar el Group
    widget.update_display()

    assert len(captured) >= 1
    group = captured[-1]
    assert isinstance(group, Group)
    # renderables[0] = línea indicadora, renderables[1] = único agente visible (agent2)
    assert len(group.renderables) == 2


def test_task_tracker_panel_collapsed_by_default_and_toggle():
    widget = TaskTrackerPanelWidget()
    widget.update_tasks({"agent": [{"task": "tarea 1", "status": "pending"}]})

    # Replegado por defecto: tira indicadora de una línea con el progreso
    assert widget.expanded is False
    assert widget.display is True
    summary = widget.get_summary()
    assert summary == {"total": 1, "done": 0, "pending": 1, "current": "tarea 1"}

    # Al presionarlo se despliega; al presionarlo de nuevo se repliega
    widget.toggle()
    assert widget.expanded is True
    assert widget.display is True
    widget.toggle()
    assert widget.expanded is False

    # Sin tareas visibles el toggle no hace nada
    widget.update_tasks({})
    assert widget.display is False
    widget.toggle()
    assert widget.expanded is False


def test_task_tracker_panel_summary_counts():
    widget = TaskTrackerPanelWidget()
    widget.update_tasks({
        "a1": [
            {"task": "t1", "status": "done"},
            {"task": "t2", "status": "in-progress"},
        ],
        "a2": [{"task": "t3", "status": "pending"}],
    })
    assert widget.get_summary()["total"] == 3
    assert widget.get_summary()["done"] == 1
    assert widget.get_summary()["pending"] == 2
    assert widget.get_summary()["current"] == "t2"
