"""
BackgroundTaskManager — Gestor de tareas de terminal en segundo plano para KogniTerm.

Permite ejecutar comandos asíncronos en subprocesos independientes/PTY, capturar
su salida en búferes de log, consultar su estado (running, completed, failed, killed)
y cancelar su ejecución de forma segura.
"""

import logging
import os
import pty
import select
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from kogniterm.core.delegation.command_rules import CommandRulesResolver

logger = logging.getLogger(__name__)

STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_KILLED = "killed"

_default_bg_manager: Optional["BackgroundTaskManager"] = None


def get_default_background_task_manager() -> "BackgroundTaskManager":
    global _default_bg_manager
    if _default_bg_manager is None:
        _default_bg_manager = BackgroundTaskManager()
    return _default_bg_manager


class BackgroundTask:
    def __init__(self, task_id: str, command: str, cwd: Optional[str] = None):
        self.task_id = task_id
        self.command = command
        self.cwd = cwd or os.getcwd()
        self.status = STATUS_RUNNING
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.exit_code: Optional[int] = None
        self.pid: Optional[int] = None
        self._output_chunks: List[str] = []
        self._lock = threading.Lock()
        self.process: Optional[subprocess.Popen] = None
        self._master_fd: Optional[int] = None

    def append_output(self, text: str) -> None:
        with self._lock:
            self._output_chunks.append(text)

    def get_output(self, tail_lines: Optional[int] = None) -> str:
        with self._lock:
            full_text = "".join(self._output_chunks)
        if tail_lines and tail_lines > 0:
            lines = full_text.splitlines(keepends=True)
            return "".join(lines[-tail_lines:])
        return full_text

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            duration = (self.end_time or time.time()) - self.start_time
            output_len = sum(len(c) for c in self._output_chunks)
            return {
                "task_id": self.task_id,
                "command": self.command,
                "cwd": self.cwd,
                "status": self.status,
                "pid": self.pid,
                "exit_code": self.exit_code,
                "start_time": self.start_time,
                "duration_seconds": round(duration, 2),
                "output_bytes": output_len,
            }


class BackgroundTaskManager:
    def __init__(self) -> None:
        self._tasks: Dict[str, BackgroundTask] = {}
        self._task_counter = 0
        self._lock = threading.Lock()
        self._rules = CommandRulesResolver()
        self._rules.load_rules()

    def _generate_task_id(self) -> str:
        with self._lock:
            self._task_counter += 1
            return f"task-{self._task_counter}"

    def start_task(self, command: str, cwd: Optional[str] = None, approved: bool = False) -> BackgroundTask:
        action = self._rules.resolve(command)
        if action == "deny":
            raise PermissionError(f"Comando bloqueado por política de seguridad: {command!r}")
        if action == "ask" and not approved:
            raise PermissionError(f"El comando requiere aprobación explícita para ejecutarse en segundo plano: {command!r}")

        task_id = self._generate_task_id()
        task = BackgroundTask(task_id, command, cwd)
        with self._lock:
            self._tasks[task_id] = task

        thread = threading.Thread(
            target=self._run_task_thread,
            args=(task,),
            daemon=True,
            name=f"KogniTerm-BackgroundTask-{task_id}",
        )
        thread.start()
        return task

    def _run_task_thread(self, task: BackgroundTask) -> None:
        master_fd, slave_fd = None, None
        try:
            master_fd, slave_fd = pty.openpty()
            task._master_fd = master_fd

            # Configurar PTY (ONLCR)
            try:
                import termios
                attrs = termios.tcgetattr(slave_fd)
                attrs[1] = attrs[1] | termios.OPOST | termios.ONLCR
                termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)
            except Exception:
                pass

            process = subprocess.Popen(
                task.command,
                shell=True,
                cwd=task.cwd,
                stdout=slave_fd,
                stderr=slave_fd,
                stdin=slave_fd,
                start_new_session=True,
            )
            os.close(slave_fd)
            slave_fd = None

            task.process = process
            task.pid = process.pid

            while True:
                r, _, _ = select.select([master_fd], [], [], 0.1)
                if master_fd in r:
                    try:
                        data = os.read(master_fd, 8192).decode(errors="replace")
                        if not data:
                            break
                        task.append_output(data)
                    except OSError:
                        break

                if process.poll() is not None:
                    # Lectura final
                    try:
                        r, _, _ = select.select([master_fd], [], [], 0.05)
                        if r:
                            data = os.read(master_fd, 8192).decode(errors="replace")
                            if data:
                                task.append_output(data)
                    except OSError:
                        pass
                    break

            exit_code = process.poll()
            task.exit_code = exit_code
            if task.status != STATUS_KILLED:
                task.status = STATUS_COMPLETED if exit_code == 0 else STATUS_FAILED

        except Exception as e:
            logger.error(f"Error ejecutando tarea en segundo plano {task.task_id}: {e}")
            task.append_output(f"\n[Error de ejecución: {e}]\n")
            if task.status != STATUS_KILLED:
                task.status = STATUS_FAILED
        finally:
            task.end_time = time.time()
            if master_fd is not None:
                try:
                    os.close(master_fd)
                except OSError:
                    pass

    def list_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]

    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.get_task(task_id)
        if not task:
            return None
        info = task.to_dict()
        info["output"] = task.get_output(tail_lines=100)
        return info

    def kill_task(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if not task or task.status != STATUS_RUNNING:
            return False

        task.status = STATUS_KILLED
        if task.process:
            try:
                os.killpg(os.getpgid(task.process.pid), 15)  # SIGTERM
            except Exception:
                try:
                    task.process.kill()
                except Exception:
                    pass
        return True
