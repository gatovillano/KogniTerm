import os
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

class CommandExecutor:
    def __init__(self) -> None:
        """Initializes the CommandExecutor with process and PTY pipe setup."""
        self.process: Optional[subprocess.Popen] = None
        self.terminal_ui: Any = None # To be linked later
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
            # También enviar via shell por si acaso
            os.write(master_fd, f"stty rows {rows} cols {cols}\n".encode())
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

        # --- Gestión de ECHO temporal ---
        # Desactivamos ECHO mientras enviamos el comando y el marcador para que no 
        # se 'escuchen' a sí mismos. Lo reactivaremos justo después.
        try:
            attrs = termios.tcgetattr(self._persistent_slave_fd)
            attrs[3] &= ~termios.ECHO
            termios.tcsetattr(self._persistent_slave_fd, termios.TCSANOW, attrs)
        except: pass

        # Enviar el comando al shell persistente
        # Usamos un marcador muy robusto para saber cuándo termina el comando
        marker = f"echo '{self._last_command_done_marker}'"
        full_cmd = f"{command} ; {marker}\n"
        os.write(master_fd, full_cmd.encode())

        # Reactivar ECHO para que el usuario pueda interactuar con el comando
        try:
            attrs[3] |= termios.ECHO
            termios.tcsetattr(self._persistent_slave_fd, termios.TCSANOW, attrs)
        except: pass

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

                readable_fds, _, _ = select.select([master_fd, self._input_pipe_read], [], [], 0.05)

                if master_fd in readable_fds:
                    try:
                        # Leer fragmento del PTY
                        data = os.read(master_fd, 4096).decode(errors='replace')
                        if not data:
                            break
                        
                        search_buffer += data
                        
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
                    if not marker_to_hide.startswith(search_buffer):
                        yield search_buffer
                        search_buffer = ""

                if self._input_pipe_read in readable_fds:
                    injected_input = os.read(self._input_pipe_read, 1024)
                    if injected_input:
                        os.write(master_fd, injected_input)

        finally:
            self.process = None

    def _start_persistent_session(self, cwd=None):
        """Inicia un shell persistente en un PTY."""
        self._persistent_master_fd, self._persistent_slave_fd = pty.openpty()
        
        # Dejar ECHO activado por defecto para permitir que el usuario vea lo que escribe 
        # en sesiones interactivas. El PTY se encargará de ocultar entradas (como passwords)
        # si el programa ejecutado así lo solicita.
        try:
            attrs = termios.tcgetattr(self._persistent_slave_fd)
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
            cwd=cwd or os.getcwd(),
            env=os.environ.copy()
        )
        # Consumir el banner inicial del shell
        time.sleep(0.5)
        try:
            # Desactivar el PROMPT para que no se filtre en la TUI
            # El prompt vacío (PS1="") es vital para una salida limpia en paneles
            os.write(self._persistent_master_fd, b"export PS1=''\n")

            
            time.sleep(0.3)
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
