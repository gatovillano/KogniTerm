"""
Execute Command Skill - Ejecuta comandos en la terminal del sistema.

Esta es una skill migrada desde execute_command_tool.py.
Provee funcionalidad para ejecutar comandos bash y obtener su salida.
"""

import os
import shlex
import subprocess
from typing import Optional, Generator, Any


# Metadata de la herramienta
name = "execute_command"
description = "Ejecuta un comando bash y devuelve su salida."


def execute_command(
    command: str,
    timeout: int = 30,
    shell: bool = True
) -> Generator[str, None, None]:
    """
    Ejecuta un comando en la terminal y devuelve su salida.

    Args:
        command: El comando a ejecutar
        timeout: Timeout en segundos (default: 30, max: 300)
        shell: Usar shell=True (default: True)

    Yields:
        str: Salida del comando (stdout o stderr)

    Raises:
        subprocess.TimeoutExpired: Si el comando excede el timeout
        Exception: Otros errores de ejecución
    """
    # Validación de comandos peligrosos
    dangerous_patterns = [
        'rm -rf', 'rm -r /', 'rm -f /',
        'dd if=', 'mkfs',
        'chmod 777', 'chmod -R 777',
        '> /dev/sd',  # Escritura directa a disco
    ]

    command_lower = command.lower().strip()
    for pattern in dangerous_patterns:
        if pattern in command_lower:
            yield f"⚠️  Comando potencialmente peligroso detectado: {pattern}\n"
            yield "Este comando requiere aprobación manual del usuario.\n"
            # No ejecutar, devolver warning
            return

    # Interceptar comandos 'cd' para cambiar directorio de trabajo
    if command_lower.startswith("cd ") or command_lower == "cd":
        target_dir = command[3:].strip() if len(command) > 3 else ""
        if not target_dir:
            target_dir = os.path.expanduser("~")
        else:
            target_dir = os.path.expanduser(target_dir)

        try:
            os.chdir(target_dir)
            new_cwd = os.getcwd()
            yield f"Directorio de trabajo cambiado a: {new_cwd}\n"
            return
        except Exception as e:
            yield f"Error al cambiar de directorio: {e}\n"
            return

    # Ejecutar comando normal
    try:
        # Usar shell=True por defecto para permitir pipes, redirects, etc.
        # Pero validar contra comandos peligrosos
        result = subprocess.run(
            command if shell else shlex.split(command),
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.stdout:
            yield result.stdout
        if result.stderr:
            yield f"[stderr] {result.stderr}"

    except subprocess.TimeoutExpired:
        yield f"Error: Timeout después de {timeout} segundos\n"
    except Exception as e:
        yield f"Error al ejecutar comando: {str(e)}\n"


# Función alternativa para ejecución síncrona (retorna string completo)
def execute_command_sync(command: str, timeout: int = 30) -> str:
    """
    Versión síncrona de execute_command.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in execute_command(command, timeout):
        output.append(chunk)
    return "".join(output)


def get_action_description(command: str, **kwargs) -> str:
    """Devuelve una descripción legible de la acción que realiza la herramienta."""
    cmd_preview = command.strip()
    if len(cmd_preview) > 50:
        cmd_preview = cmd_preview[:47] + "..."
    return f"Ejecutando comando: '{cmd_preview}'"


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "El comando bash a ejecutar"
        },
        "timeout": {
            "type": "integer",
            "description": "Timeout en segundos (default: 30, max: 300)",
            "default": 30
        },
        "shell": {
            "type": "boolean",
            "description": "Usar shell=True (default: true)",
            "default": True
        }
    },
    "required": ["command"]
}
