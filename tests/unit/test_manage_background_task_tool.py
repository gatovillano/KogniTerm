import importlib.util
from pathlib import Path
import time
import pytest

# Carga dinámica de las skills bundled con guiones
root_dir = Path(__file__).parent.parent.parent
exec_cmd_path = root_dir / "kogniterm" / "skills" / "bundled" / "execute-command" / "scripts" / "tool.py"
spec1 = importlib.util.spec_from_file_location("exec_cmd_tool", exec_cmd_path)
exec_cmd_mod = importlib.util.module_from_spec(spec1)
spec1.loader.exec_module(exec_cmd_mod)
execute_command = exec_cmd_mod.execute_command

manage_bg_path = root_dir / "kogniterm" / "skills" / "bundled" / "manage-background-task" / "scripts" / "tool.py"
spec2 = importlib.util.spec_from_file_location("manage_bg_tool", manage_bg_path)
manage_bg_mod = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(manage_bg_mod)
manage_background_task = manage_bg_mod.manage_background_task


def test_manage_background_task_flow():
    # 1. Ejecutar comando en segundo plano
    gen = execute_command("echo 'Background Task Skill Test'", is_background=True)
    out = "".join(list(gen))
    assert "task-" in out

    time.sleep(0.5)

    # 2. Listar tareas
    list_out = manage_background_task(action="list")
    assert "task-1" in list_out or "task-" in list_out

    # 3. Consultar estado de task-1
    status_out = manage_background_task(action="status", task_id="task-1")
    assert "Background Task Skill Test" in status_out or "Estado de la tarea" in status_out

    # 4. Probar kill de tarea inexistente o terminada
    kill_out = manage_background_task(action="kill", task_id="task-999")
    assert "No se pudo cancelar" in kill_out
