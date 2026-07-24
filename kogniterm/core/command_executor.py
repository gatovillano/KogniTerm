import os
import re
import tempfile
import pty
import select
import subprocess
import sys
import termios
import time
import tty
import queue
import shlex
import logging
from typing import Optional, Generator, Any
from .config import settings

logger = logging.getLogger(__name__)


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


class CommandExecutor:
    def __init__(self) -> None:
        """Initializes the CommandExecutor with process and PTY pipe setup."""
        self.process: Optional[subprocess.Popen] = None
        self.terminal_ui: Any = None # To be linked later
        self.workspace_directory: Optional[str] = None
        # Pipe para inyectar entrada al PTY desde la TUI
        self._input_pipe_read, self._input_pipe_write = os.pipe()
        
        # Atributos para sesión persistente
        self._persistent_master_fd: Optional[int] = None
        self._persistent_slave_fd: Optional[int] = None
        self._persistent_shell_process: Optional[subprocess.Popen] = None
        self._last_command_done_marker = "##KOGNITERM_DONE_MARKER##"

    def execute(self, command: str, cwd: Optional[str] = None, 
                interrupt_queue: Optional[queue.Queue] = None, 
                cols: int = 80, rows: int = 24) -> Generator[str, None, None]:
        """
        Ejecuta un comando en un pseudo-terminal (PTY) y cede la salida en tiempo real.
        Utiliza una sesión persistente para mantener el estado (como sudo o variables de entorno).

        Args:
            command: El comando de shell a ejecutar.
            cwd: El directorio de trabajo para el comando.
            interrupt_queue: Una cola para recibir señales de interrupción (Ctrl+C).
            cols: Número de columnas de la terminal virtual.
            rows: Número de filas de la terminal virtual.

        Yields:
            Cada fragmento de texto de la salida estándar/error del comando.
        """
        is_tui = getattr(getattr(self, 'terminal_ui', None), 'is_tui', False)
        
        # Inicializar sesión persistente si no existe
        if self._persistent_shell_process is None or self._persistent_shell_process.poll() is not None:
            self._start_persistent_session(cwd)
            
        master_fd = self._persistent_master_fd
        self.process = self._persistent_shell_process

        # Ajustar dimensiones del PTY para que coincidan con la TUI
        try:
            import fcntl
            import struct
            buf = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, buf)
        except:
            pass

        # 0. Limpiar buffer de entrada/salida previo para evitar desincronización
        # Esto evita que residuos de comandos anteriores (o el prompt oculto) 
        # se mezclen con el output del comando actual.
        try:
            while True:
                r, _, _ = select.select([master_fd], [], [], 0.0)
                if r:
                    os.read(master_fd, 8192)
                else:
                    break
        except:
            pass

        # Transformar comandos python -c "..." (multilínea o no, de cualquier venv/ruta)
        # a ejecución desde archivo temporal para evitar problemas de eco, PS2 (>) y PTY
        command, was_transformed, temp_path = _transform_python3_dash_c(command)
        
        # Eliminar saltos de línea y espacios al final para evitar errores sintácticos
        command = command.rstrip()
        
        original_command = command
        stripped_command = command.strip()
        is_multiline = "\n" in stripped_command
        
        if not was_transformed and is_multiline:
            fd, temp_path = tempfile.mkstemp(suffix='.sh', prefix='kogniterm_run_')
            os.close(fd)
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(command)
            command = f"source {temp_path}"
            was_transformed = True
            yield f"[KogniTerm] Ejecutando comando multilínea desde archivo temporal: {temp_path}\n"
        elif was_transformed:
            yield f"[KogniTerm] Transformando comando python -c a archivo temporal: {temp_path}\n"


        # Enviar el comando al shell persistente.
        # El tamaño ya se ajusta con ioctl(TIOCSWINSZ), por lo que no inyectamos
        # un comando stty en línea para evitar que aparezca en el output renderizado.
        half_len = len(self._last_command_done_marker) // 2
        part1 = self._last_command_done_marker[:half_len]
        part2 = self._last_command_done_marker[half_len:]
        marker = f"echo '{part1}''{part2}'"
        
        # Construcción segura del comando y el marcador para evitar errores sintácticos de bash
        if not stripped_command:
            full_cmd = f"{marker}\n"
        elif stripped_command.endswith(';') or stripped_command.endswith('&'):
            full_cmd = f"{command} {marker}\n"
        else:
            full_cmd = f"{command} ; {marker}\n"
        
        # Filtro de echo: definiremos la cadena exacta a borrar que producirá bash readline
        self._expected_echo = full_cmd.replace('\n', '\r\n')
        self._echo_filtered = False
        
        os.write(master_fd, full_cmd.encode())

        try:
            search_buffer = ""
            # Definir marcadores y prefijos que queremos ocultar (eco del comando de finalización)
            marker_to_hide = self._last_command_done_marker
            echo_cmd_to_hide = f"echo '{marker_to_hide}'"
            
            # Longitud de seguridad para no retener buffer innecesariamente
            max_prefix_len = max(len(marker_to_hide), len(echo_cmd_to_hide)) + 2
            
            while True:
                # Verificar interrupción
                if interrupt_queue and not interrupt_queue.empty():
                    interrupt_queue.get()
                    os.write(master_fd, b"\x03") # Ctrl+C al shell
                    yield "\n\n⚠️  Comando interrumpido por el usuario.\n"
                    break
 
                readable_fds, _, _ = select.select([master_fd, self._input_pipe_read], [], [], 0.02)
 
                if master_fd in readable_fds:
                    try:
                        # Leer fragmento del PTY
                        data = os.read(master_fd, 4096).decode(errors='replace')
                        if not data:
                            break
                        
                        search_buffer += data
 
 
                        # Filtrar el eco del comando completo provocado por bash readline
                        if not getattr(self, '_echo_filtered', True):
                            # Limpiar secuencias de escape ANSI del buffer para la comparación de prefijos
                            clean_buf = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', search_buffer).lstrip()
                            cmd_stripped = original_command.strip()
                            prefix_len = min(len(cmd_stripped), 16)
                            
                            # Si el buffer no empieza con el prefijo esperado del comando,
                            # asumimos que ECHO está desactivado y lo que recibimos ya es salida del comando.
                            # Para evitar desactivar el filtro prematuramente con buffers muy cortos que aún 
                            # están recibiendo el eco, primero verificamos si clean_buf es prefijo del comando esperado.
                            if prefix_len == 0:
                                self._echo_filtered = True
                            elif len(clean_buf) < prefix_len:
                                if not cmd_stripped.startswith(clean_buf):
                                    self._echo_filtered = True
                            elif not clean_buf.startswith(cmd_stripped[:prefix_len]):
                                self._echo_filtered = True
                            
                            # Si detectamos la firma de nuestro marcador en el eco, sabemos que terminó el eco
                            # La firma en el comando de eco es: ##KOGNITERM_''DONE_MARKER##
                            elif "##KOGNITERM_''DONE_MARKER##" in search_buffer:
                                parts = search_buffer.split("##KOGNITERM_''DONE_MARKER##", 1)
                                rest = parts[1]
                                if rest.startswith("'"):
                                    rest = rest[1:]
                                if rest.startswith("\r"):
                                    rest = rest[1:]
                                if rest.startswith("\n"):
                                    rest = rest[1:]
                                search_buffer = rest
                                self._echo_filtered = True
                                
                            # Si el buffer limpio supera en longitud de forma excesiva al comando,
                            # desactivamos el filtro por seguridad para no retener salida real
                            elif len(clean_buf) > len(cmd_stripped) + 150:
                                # Si el marcador de eco completo está presente en alguna parte, intentamos descartarlo
                                if "##KOGNITERM_''DONE_MARKER##" in search_buffer:
                                    parts = search_buffer.split("##KOGNITERM_''DONE_MARKER##", 1)
                                    rest = parts[1]
                                    if rest.startswith("'"):
                                        rest = rest[1:]
                                    if rest.startswith("\r"):
                                        rest = rest[1:]
                                    if rest.startswith("\n"):
                                        rest = rest[1:]
                                    search_buffer = rest
                                self._echo_filtered = True
                            else:
                                # Aún estamos recibiendo la línea de eco, no hacemos yield todavía
                                continue


                        # Si el marcador de fin aparece completo, hemos terminado
                        if marker_to_hide in search_buffer:
                            parts = search_buffer.split(marker_to_hide)
                            final_output = parts[0]
                            # Limpiar restos de \r y yield final
                            if final_output:
                                clean_output = final_output.replace('\r\n', '\n')
                                if clean_output: yield clean_output
                            break
                        
                        # Yield preventivo: Soltar todo lo que no sea un posible inicio del marcador.
                        # Buscamos el sufijo más largo del buffer que sea prefijo del marcador.
                        marker_prefix_len = 0
                        for i in range(min(len(search_buffer), len(marker_to_hide)), 0, -1):
                            if marker_to_hide.startswith(search_buffer[-i:]):
                                marker_prefix_len = i
                                break
                        
                        if marker_prefix_len < len(search_buffer):
                            to_yield = search_buffer[:-marker_prefix_len] if marker_prefix_len > 0 else search_buffer
                            search_buffer = search_buffer[-marker_prefix_len:] if marker_prefix_len > 0 else ""
                            
                            clean_to_yield = to_yield.replace('\r\n', '\n') # Solo normalizar saltos de línea, preservar \r
                            if clean_to_yield:
                                yield clean_to_yield
                            
                    except OSError:
                        break
                
                # Yield lo que queda en el buffer si no hay datos nuevos y no parece inicio de marcador
                if search_buffer and master_fd not in readable_fds:
                    if getattr(self, '_echo_filtered', True) and not marker_to_hide.startswith(search_buffer):
                        clean_remaining = search_buffer.replace('\r\n', '\n')
                        if clean_remaining:
                            yield clean_remaining
                        search_buffer = ""

                if self._input_pipe_read in readable_fds:
                    try:
                        injected_input = os.read(self._input_pipe_read, 1024)
                        if injected_input:
                            os.write(master_fd, injected_input)
                    except Exception as e:
                        logger.error(f"Error inyectando entrada al PTY: {e}")

        finally:
            self.process = None
            # Limpiar archivo temporal si fue creado
            if was_transformed and temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass

    def _start_persistent_session(self, cwd=None):
        """Inicia un shell persistente en un PTY."""
        self._persistent_master_fd, self._persistent_slave_fd = pty.openpty()
        
        # Dejar ECHO activado por defecto para permitir que el usuario vea lo que escribe 
        # en sesiones interactivas. El PTY se encargará de ocultar entradas (como passwords)
        # si el programa ejecutado así lo solicita.
        try:
            attrs = termios.tcgetattr(self._persistent_slave_fd)
            attrs[1] = attrs[1] | termios.OPOST | termios.ONLCR # Asegurar procesamiento de salida y mapeo de NL a CR-NL
            attrs[3] = attrs[3] | termios.ECHO # Asegurar ECHO activado
            termios.tcsetattr(self._persistent_slave_fd, termios.TCSANOW, attrs)
        except Exception:
            pass

        # Usar 'bash' como shell persistente
        self._persistent_shell_process = subprocess.Popen(
            ["bash", "--login"],
            stdin=self._persistent_slave_fd,
            stdout=self._persistent_slave_fd,
            stderr=self._persistent_slave_fd,
            close_fds=True,
            preexec_fn=os.setsid,
            cwd=cwd or getattr(self, "workspace_directory", None) or os.getcwd(),
            env=os.environ.copy()
        )
        # Consumir el banner inicial del shell
        time.sleep(0.2)
        try:
            # Desactivar el PROMPT para que no se filtre en la TUI
            # El prompt vacío (PS1="") es vital para una salida limpia en paneles
            os.write(self._persistent_master_fd, b"export PS1=''\n")

            
            time.sleep(0.1)
            # Leer todo el buffer inicial para dejar la terminal limpia (banners, mensajes de login, etc)
            while True:
                r, _, _ = select.select([self._persistent_master_fd], [], [], 0.1)
                if r:
                    os.read(self._persistent_master_fd, 8192)
                else:
                    break
        except:
            pass

    def terminate(self):
        """Interrumpe el comando actual enviando SIGINT al grupo de procesos."""
        if self._persistent_shell_process:
            import signal
            try:
                os.killpg(os.getpgid(self._persistent_shell_process.pid), signal.SIGINT)
            except:
                pass

    def write_input(self, data: str):
        """Envía texto al proceso actual a través del pipe de entrada."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        try:
            os.write(self._input_pipe_write, data)
        except Exception:
            pass
