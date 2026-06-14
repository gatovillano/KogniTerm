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
    
    assert len(captured) >= 1
    group = captured[-1]
    # The group should only render the non-completed agent (agent2).
    # Therefore, group.renderables should only contain 1 element.
    assert len(group.renderables) == 1

