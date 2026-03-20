"""
Execute Command Skill - Ejecuta comandos en la terminal del sistema.

Esta es una skill migrada desde execute_command_tool.py.
Provee funcionalidad para ejecutar comandos bash y obtener su salida.
"""

import os
import shlex
import subprocess
import selectors
import time
from typing import Optional, Generator, Any


# Metadata de la herramienta
name = "execute_command"
description = "Ejecuta un comando bash y devuelve su salida en tiempo real."


def execute_command(
    command: str,
    timeout: int = 30,
    shell: bool = True
) -> Generator[str, None, None]:
    """
    Ejecuta un comando en la terminal y produce su salida en tiempo real.

    Args:
        command: El comando a ejecutar
        timeout: Timeout en segundos (default: 30, max: 300)
        shell: Usar shell=True (default: True)

    Yields:
        str: Fragmentos de la salida del comando (stdout o stderr)
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
            yield f"⚠️  Comando potencialmente peligroso detectado: {pattern}\nEste comando requiere aprobación manual del usuario.\n"
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

    # Ejecutar comando con Popen para permitir streaming y potencial interactividad
    try:
        process = subprocess.Popen(
            command if shell else shlex.split(command),
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )

        sel = selectors.DefaultSelector()
        sel.register(process.stdout, selectors.EVENT_READ)
        sel.register(process.stderr, selectors.EVENT_READ)

        start_time = time.time()
        
        while sel.get_map():
            # Verificar timeout total
            if time.time() - start_time > timeout:
                process.kill()
                yield f"\nError: Timeout después de {timeout} segundos\n"
                break

            events = sel.select(timeout=1)
            for key, mask in events:
                line = key.fileobj.readline()
                if not line:
                    sel.unregister(key.fileobj)
                    continue
                
                if key.fileobj is process.stdout:
                    # Permitir interactividad: si el caller usa .send(data),
                    # data se escribe en stdin del proceso.
                    input_data = yield line
                    if input_data and process.stdin:
                        process.stdin.write(input_data + ("\n" if not input_data.endswith("\n") else ""))
                        process.stdin.flush()
                else:
                    yield f"[stderr] {line}"
            
            # Si el proceso terminó y no hay más eventos, salir
            if process.poll() is not None and not events:
                # Una última comprobación de si quedan datos en los pipes que no leyó el selector
                # (aunque con readline y line buffering el selector debería haberlos captado)
                break

        # Limpieza final
        process.stdout.close()
        process.stderr.close()
        process.stdin.close()
        
    except Exception as e:
        yield f"Error al ejecutar comando: {str(e)}\n"


# Función que retorna el string completo consumiendo el generador
def execute_command_sync(command: str, timeout: int = 30) -> str:
    """
    Versión síncrona de execute_command que consume el generador.
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
