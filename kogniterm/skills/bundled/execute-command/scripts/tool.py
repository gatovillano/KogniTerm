"""
Execute Command Skill - Ejecuta comandos en la terminal del sistema.

Esta es una skill migrada desde execute_command_tool.py.
Provee funcionalidad para ejecutar comandos bash y obtener su salida.
"""

import os
import re
import shlex
import subprocess
import selectors
import tempfile
import time
from typing import Optional, Generator, Any


# Metadata de la herramienta
name = "execute_command"
description = "Ejecuta un comando bash y devuelve su salida en tiempo real."


def _transform_python3_dash_c(command: str) -> tuple[str, bool, Optional[str]]:
    """
    Transforma comandos python -c "..." o python -c '...' (con cualquier ruta de python)
    a ejecución desde un archivo temporal.
    
    Returns:
        (comando_transformado, fue_transformado, ruta_temp)
    """
    cmd_stripped = command.strip()
    
    # 1. Intentar con comillas dobles
    pattern_double = r'^([^\s&|;]*python[0-9.]*(?:\s+[^&|;]*?)*)\s+-c\s+"((?:[^"\\]|\\.)*)"(.*)$'
    match = re.match(pattern_double, cmd_stripped, re.DOTALL)
    
    # 2. Si no coincide, intentar con comillas simples
    if not match:
        pattern_single = r"^([^\s&|;]*python[0-9.]*(?:\s+[^&|;]*?)*)\s+-c\s+'((?:[^'\\]|\\.)*)'(.*)$"
        match = re.match(pattern_single, cmd_stripped, re.DOTALL)
        
    if not match:
        return command, False, None
        
    prefix = match.group(1)  # python ... (hasta -c)
    code = match.group(2)    # código entre comillas
    suffix = match.group(3)  # resto del comando (si hay)
    
    # Des-escapar las comillas correspondientes del código capturado para guardarlo en un archivo .py real
    is_double_quotes = cmd_stripped[match.start(2) - 1] == '"'
    if is_double_quotes:
        code = code.replace('\\"', '"').replace('\\\\', '\\')
    else:
        code = code.replace("\\'", "'").replace('\\\\', '\\')
    
    # Crear archivo temporal
    fd, temp_path = tempfile.mkstemp(suffix='.py', prefix='kogniterm_py_')
    os.close(fd)
    
    # Escribir código al archivo
    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write(code)
    
    # Construir comando transformado: python ... /tmp/...py [suffix]
    transformed = f"{prefix} {temp_path}{suffix}"
    
    return transformed, True, temp_path


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

    # Transformar python3 -c "..." a archivo temporal para evitar problemas con comillas en PTY
    original_command = command
    command, was_transformed, temp_path = _transform_python3_dash_c(command)
    
    if was_transformed:
        yield f"[KogniTerm] Transformando comando python -c a archivo temporal: {temp_path}\n"

    # Ejecutar comando con PTY para permitir streaming, colores e interactividad real
    import pty
    import select
    
    try:
        master_fd, slave_fd = pty.openpty()
        
        # Asegurar mapeo de saltos de línea (ONLCR) en la PTY
        try:
            import termios
            attrs = termios.tcgetattr(slave_fd)
            attrs[1] = attrs[1] | termios.OPOST | termios.ONLCR
            termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)
        except Exception:
            pass
        
        # Iniciar proceso con el slave_fd como stdout/stderr/stdin
        process = subprocess.Popen(
            command if shell else shlex.split(command),
            shell=shell,
            stdout=slave_fd,
            stderr=slave_fd,
            stdin=slave_fd,
            text=True,
            bufsize=1,
            universal_newlines=True,
            preexec_fn=os.setsid  # Crear un nuevo grupo de procesos
        )
        
        # Cerrar el slave_fd en el proceso padre ya que lo usará el hijo
        os.close(slave_fd)
        
        start_time = time.time()
        
        while True:
            # Verificar timeout total
            elapsed = time.time() - start_time
            if elapsed > timeout:
                try:
                    os.killpg(os.getpgid(process.pid), 15) # SIGTERM
                except:
                    process.kill()
                yield f"\nError: Timeout después de {timeout} segundos\n"
                break

            # Usar select para esperar datos del PTY sin bloquear demasiado
            # para poder chequear el timeout y señales de interrupción.
            r, _, _ = select.select([master_fd], [], [], 0.1)
            
            if master_fd in r:
                try:
                    data = os.read(master_fd, 8192).decode(errors='replace')
                    if not data:
                        break
                    
                    # Yield data y permitir recibir input vía .send()
                    input_data = yield data
                    
                    if input_data:
                        # Si recibimos input, lo enviamos al PTY
                        if isinstance(input_data, str):
                            os.write(master_fd, input_data.encode())
                        else:
                            os.write(master_fd, input_data)
                except OSError:
                    # El PTY se cerró o hay error
                    break
            
            # Si el proceso terminó y no hay más datos, salir
            if process.poll() is not None:
                # Hacer una última lectura para capturar el remanente
                r, _, _ = select.select([master_fd], [], [], 0.05)
                if not r:
                    break

        # Limpieza final
        try:
            os.close(master_fd)
        except:
            pass
        
        # Limpiar archivo temporal si fue creado
        if was_transformed and temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
        
    except Exception as e:
        yield f"Error al ejecutar comando con PTY: {str(e)}\n"


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
