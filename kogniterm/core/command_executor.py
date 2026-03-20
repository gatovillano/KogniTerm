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
from typing import Optional, Generator, Any
from .config import settings

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

        # Enviar el comando al shell persistente
        # Usamos un marcador muy robusto para saber cuándo termina el comando
        marker = f"echo '{self._last_command_done_marker}'"
        full_cmd = f"{command} ; {marker}\n"
        os.write(master_fd, full_cmd.encode())

        try:
            search_buffer = ""
            while True:
                # Verificar interrupción
                if interrupt_queue and not interrupt_queue.empty():
                    interrupt_queue.get()
                    os.write(master_fd, b"\x03") # Ctrl+C al shell
                    yield "\n\n⚠️  Comando interrumpido por el usuario.\n"
                    break

                readable_fds, _, _ = select.select([master_fd, self._input_pipe_read], [], [], 0.1)

                if master_fd in readable_fds:
                    try:
                        output = os.read(master_fd, 4096).decode(errors='replace')
                        if output:
                            search_buffer += output
                            
                            # Caso 1: El marcador completo está en el buffer
                            if self._last_command_done_marker in search_buffer:
                                parts = search_buffer.split(self._last_command_done_marker, 1)
                                chunk = parts[0]
                                
                                # Limpiar ruidos terminales y el eco del comando echo
                                marker_echo = f"echo '{self._last_command_done_marker}'"
                                chunk = chunk.replace(marker_echo, "")
                                chunk = chunk.replace('\r\n', '\n').replace('\r', '')
                                
                                if chunk: yield chunk
                                break
                            
                            # Caso 2: El buffer no contiene el inicio de un posible marcador
                            # (ni '##' ni parte de 'echo '...). Podemos soltarlo todo.
                            marker_start_1 = "##"
                            marker_start_2 = "echo '"
                            
                            idx1 = search_buffer.find(marker_start_1)
                            idx2 = search_buffer.find(marker_start_2)
                            
                            # split_idx será el primer punto donde podría empezar un marcador
                            split_idx = -1
                            if idx1 != -1 and idx2 != -1:
                                split_idx = min(idx1, idx2)
                            elif idx1 != -1:
                                split_idx = idx1
                            elif idx2 != -1:
                                split_idx = idx2
                                
                            if split_idx == -1:
                                # No hay rastro de marcadores, soltar todo el buffer
                                yield search_buffer.replace('\r\n', '\n').replace('\r', '')
                                search_buffer = ""
                            elif split_idx > 0:
                                # Hay rastro de marcador más adelante, soltar lo que hay antes
                                to_yield = search_buffer[:split_idx]
                                search_buffer = search_buffer[split_idx:]
                                yield to_yield.replace('\r\n', '\n').replace('\r', '')
                            
                            # Si search_buffer empieza con un posible marcador (split_idx == 0),
                            # solo soltamos si el buffer crece demasiado (margen de seguridad)
                            # para no bloquear la salida si alguien escribe '##' sin ser el marcador.
                            marker_len = len(self._last_command_done_marker)
                            marker_echo_len = len(f"echo '{self._last_command_done_marker}'")
                            safe_margin = max(marker_len, marker_echo_len) + 10
                            
                            if len(search_buffer) > safe_margin:
                                # No es el marcador (demasiado largo), soltar un trozo
                                to_yield = search_buffer[:-safe_margin]
                                search_buffer = search_buffer[-safe_margin:]
                                yield to_yield.replace('\r\n', '\n').replace('\r', '')
                    except OSError:
                        if search_buffer:
                            # Limpiar eco residual
                            search_buffer = search_buffer.replace(f"echo '{self._last_command_done_marker}'", "")
                            search_buffer = search_buffer.replace('\r\n', '\n').replace('\r', '')
                            if search_buffer: yield search_buffer
                        break
                if self._input_pipe_read in readable_fds:
                    injected_input = os.read(self._input_pipe_read, 1024)
                    if injected_input:
                        os.write(master_fd, injected_input)

        finally:
            self.process = None

    def _start_persistent_session(self, cwd=None):
        """Inicia un shell persistente en un PTY."""
        self._persistent_master_fd, self._persistent_slave_fd = pty.openpty()
        
        # Configurar terminal slave para NO tener eco (modo robusto)
        try:
            attrs = termios.tcgetattr(self._persistent_slave_fd)
            attrs[3] = attrs[3] & ~termios.ECHO # Desactivar ECHO
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
            # Desactivar eco y silenciar el PROMPT para que no se filtre en la TUI
            # El prompt vacío (PS1="") es vital para una salida limpia en paneles
            os.write(self._persistent_master_fd, b"stty -echo\n")
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
