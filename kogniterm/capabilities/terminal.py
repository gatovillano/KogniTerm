"""Capacidad nativa de ejecución de comandos de terminal interactiva para KogniTerm."""

import asyncio
import os
import pty
import re
import select
import shlex
import subprocess
import termios
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from kogniterm.capabilities.registry import tool
from kogniterm.core.command_executor import _transform_python3_dash_c


class ExecuteCommandParams(BaseModel):
    command: str = Field(description="Comando de terminal bash a ejecutar")
    timeout: int = Field(default=30, description="Tiempo máximo de espera en segundos (máximo 300)")
    is_background: bool = Field(default=False, description="Si es True, ejecuta el comando en segundo plano")
    working_dir: Optional[str] = Field(default=None, description="Directorio de trabajo para el comando")


def _strip_ansi(text: str) -> str:
    """Remueve secuencias de escape ANSI de la salida."""
    ansi_regex = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_regex.sub("", text)


def _execute_pty_raw(
    command: str,
    timeout: int = 30,
    working_dir: Optional[str] = None,
    is_background: bool = False,
) -> Dict[str, Any]:
    """
    Ejecuta un comando en un proceso PTY nativo de baja latencia.
    Cumple estrictamente con las reglas de KogniTerm:
    - Entornos sin eco (ECHO off)
    - Diferenciación estricta entre el eco de comando y el marcador ##KOGNITERM_DONE_MARKER##
    """
    if is_background:
        from kogniterm.core.background_task_manager import get_default_background_task_manager
        target_dir = working_dir or os.getcwd()
        bg_manager = get_default_background_task_manager()
        task = bg_manager.start_task(command, cwd=target_dir)
        return {
            "exit_code": 0,
            "stdout": f"🚀 [KogniTerm] Comando enviado a segundo plano con ID: {task.task_id} (PID: {task.pid or 'iniciando'}).",
            "stderr": "",
            "is_background": True,
            "task_id": task.task_id,
        }

    # Interceptar cd
    cmd_clean = command.strip()
    cmd_lower = cmd_clean.lower()
    if cmd_lower.startswith("cd ") or cmd_lower == "cd":
        target_dir = cmd_clean[3:].strip() if len(cmd_clean) > 3 else ""
        target_dir = os.path.expanduser(target_dir) if target_dir else os.path.expanduser("~")
        try:
            os.chdir(target_dir)
            return {
                "exit_code": 0,
                "stdout": f"Directorio de trabajo cambiado a: {os.getcwd()}",
                "stderr": "",
            }
        except Exception as e:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Error al cambiar de directorio: {e}",
            }

    # Transformar python3 -c si corresponde para evitar problemas de comillas en PTY
    command_transformed, was_transformed, temp_path = _transform_python3_dash_c(command)

    target_cwd = working_dir or os.getcwd()
    target_cwd = str(Path(target_cwd).resolve())

    start_time = time.time()
    done_marker = "##KOGNITERM_DONE_MARKER##"

    try:
        master_fd, slave_fd = pty.openpty()

        # Configurar flags de terminal (respetando ONLCR)
        try:
            attrs = termios.tcgetattr(slave_fd)
            attrs[1] = attrs[1] | termios.OPOST | termios.ONLCR
            termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)
        except Exception:
            pass

        # Comando con marcador de finalización limpio
        # Usamos dos partes en el echo para que la cadena del marcador no aparezca
        # de forma literal idéntica dentro del comando enviado (lo que previene falsos positivos de eco)
        half_len = len(done_marker) // 2
        part1 = done_marker[:half_len]
        part2 = done_marker[half_len:]
        marker_cmd = f"echo '{part1}''{part2}'"

        if command_transformed.endswith(";") or command_transformed.endswith("&"):
            full_script = f"{command_transformed} {marker_cmd}\n"
        else:
            full_script = f"{command_transformed} ; {marker_cmd}\n"

        process = subprocess.Popen(
            ["/bin/bash", "-c", full_script],
            cwd=target_cwd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            text=False,
            preexec_fn=os.setsid,
        )
        os.close(slave_fd)

        output_chunks = []
        timed_out = False
        saw_done_marker = False

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                timed_out = True
                try:
                    os.killpg(os.getpgid(process.pid), 15)
                except Exception:
                    process.kill()
                break

            # Select de baja latencia (5ms)
            r, _, _ = select.select([master_fd], [], [], 0.005)
            if master_fd in r:
                try:
                    chunk = os.read(master_fd, 8192)
                    if not chunk:
                        break
                    output_chunks.append(chunk)

                    # Verificar presencia del marcador limpio en la salida decodificada
                    current_text = b"".join(output_chunks).decode("utf-8", errors="replace")
                    if done_marker in current_text:
                        saw_done_marker = True
                        break
                except OSError:
                    break

            if process.poll() is not None:
                # Drenar cualquier byte remanente
                while True:
                    r, _, _ = select.select([master_fd], [], [], 0.002)
                    if master_fd in r:
                        try:
                            chunk = os.read(master_fd, 8192)
                            if chunk:
                                output_chunks.append(chunk)
                            else:
                                break
                        except OSError:
                            break
                    else:
                        break
                break

        try:
            os.close(master_fd)
        except Exception:
            pass

        if was_transformed and temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass

        raw_output = b"".join(output_chunks).decode("utf-8", errors="replace")
        clean_text = _strip_ansi(raw_output)

        # Regla estricta de filtrado de eco de KogniTerm:
        # 1. No asumir que la terminal siempre emite eco (compatible con ECHO off)
        # 2. El marcador limpio no debe confundirse con la línea de eco
        # 3. Eliminar el marcador limpio de la salida final
        lines = clean_text.splitlines(keepends=True)
        filtered_lines = []

        for line in lines:
            stripped = line.strip()
            # Si la línea es exactamente el marcador limpio, se descarta (es el centinela)
            if stripped == done_marker:
                continue
            # Si contiene el comando de invocación del marcador (eco de comando con comillas partidas), descartar
            if marker_cmd in stripped:
                continue
            filtered_lines.append(line)

        final_stdout = "".join(filtered_lines).strip()
        exit_code = process.poll() if process.poll() is not None else (0 if saw_done_marker else -1)
        if timed_out:
            exit_code = -1

        stderr_msg = "Timeout excedido al ejecutar el comando." if timed_out else ""

        return {
            "exit_code": exit_code,
            "stdout": final_stdout,
            "stderr": stderr_msg,
            "duration": round(time.time() - start_time, 3),
        }

    except Exception as exc:
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Error al ejecutar comando con PTY: {exc}",
            "duration": round(time.time() - start_time, 3),
        }


@tool(
    name="execute_command",
    description="Ejecuta un comando bash en terminal de alta velocidad y devuelve su salida.",
    params_schema=ExecuteCommandParams,
    category="system",
)
async def execute_command(
    command: str,
    timeout: int = 30,
    is_background: bool = False,
    working_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Ejecuta un comando bash asíncronamente en PTY."""
    return await asyncio.to_thread(
        _execute_pty_raw,
        command=command,
        timeout=timeout,
        working_dir=working_dir,
        is_background=is_background,
    )


@tool(
    name="run_shell",
    description="Alias de alta compatibilidad para execute_command. Ejecuta comandos en terminal interactiva.",
    params_schema=ExecuteCommandParams,
    category="system",
)
async def run_shell(
    command: str,
    timeout: int = 30,
    is_background: bool = False,
    working_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Alias para execute_command."""
    return await execute_command(
        command=command,
        timeout=timeout,
        is_background=is_background,
        working_dir=working_dir,
    )
