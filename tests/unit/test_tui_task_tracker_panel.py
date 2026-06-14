import pytest
from kogniterm.terminal.tui.components.task_tracker_panel import TaskTrackerPanelWidget

def test_task_tracker_panel_visibility():
    widget = TaskTrackerPanelWidget()
    
    # 1. Sin tareas
    widget.update_tasks({})
    assert widget.display is False

    # 2. Con una tarea pendiente
    widget.update_tasks({"agent": [{"task": "tarea 1", "status": "pending"}]})
    assert widget.display is True

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
