"""
Tests unitarios para BackgroundTaskManager.
"""

import time
import pytest
from kogniterm.core.background_task_manager import (
    BackgroundTaskManager,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_KILLED,
)


def test_background_task_execution():
    manager = BackgroundTaskManager()
    task = manager.start_task("echo 'Hello Background'")
    assert task.task_id == "task-1"
    
    # Esperar a que la tarea termine
    for _ in range(50):
        if task.status != STATUS_RUNNING:
            break
        time.sleep(0.1)

    assert task.status == STATUS_COMPLETED
    assert task.exit_code == 0
    assert "Hello Background" in task.get_output()


def test_background_task_list_and_status():
    manager = BackgroundTaskManager()
    t1 = manager.start_task("echo 'Task One'")
    t2 = manager.start_task("echo 'Task Two'")

    time.sleep(0.5)

    tasks_list = manager.list_tasks()
    assert len(tasks_list) == 2
    task_ids = [t["task_id"] for t in tasks_list]
    assert "task-1" in task_ids
    assert "task-2" in task_ids

    status_t1 = manager.get_task_status("task-1")
    assert status_t1 is not None
    assert "Task One" in status_t1["output"]


def test_background_task_kill():
    manager = BackgroundTaskManager()
    task = manager.start_task("sleep 10")
    time.sleep(0.2)
    assert task.status == STATUS_RUNNING

    success = manager.kill_task(task.task_id)
    assert success is True
    assert task.status == STATUS_KILLED
