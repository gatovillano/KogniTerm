import os
import pty
import select
import subprocess
import sys
import termios
import time
import tty
import queue
from typing import Optional
from .config import settings

class CommandExecutor:
    def __init__(self):
        self.process = None

    def execute(self, command, cwd=None, interrupt_queue: Optional[queue.Queue] = None):
        """
        Ejecuta un comando en un pseudo-terminal (PTY), permitiendo la comunicación interactiva.
        Captura la salida del comando y la cede (yields) en tiempo real.
        También captura la entrada del usuario desde stdin y la reenvía al comando.

        Args:
            command (str): El comando a ejecutar.
            cwd (str, optional): El directorio de trabajo para el comando. Defaults to None.
        """
        MAX_OUTPUT_LENGTH = settings.max_output_length # Usar valor de configuración
        output_buffer = "" # Buffer para acumular la salida

        # Guardar la configuración original de la terminal
        try:
            old_settings = termios.tcgetattr(sys.stdin.fileno())
        except termios.error as e:
            # Si no se ejecuta en una terminal real, no se puede continuar con el modo interactivo.
            # Se podría implementar un fallback a un modo no interactivo aquí si fuera necesario.
            yield f"Error: No se pudo obtener la configuración de la terminal ({e}). Ejecución no interactiva no implementada."
            return

        master_fd, slave_fd = pty.openpty()

        try:
            # Poner la terminal del usuario en modo "raw"
            # Esto pasa todas las teclas directamente al proceso sin procesarlas
            tty.setraw(sys.stdin.fileno())

            # Si el comando contiene 'sudo', envolverlo con 'script -qc' para manejar la solicitud de contraseña
            if command.strip().startswith("sudo "):
                command = f"script -qc '{command}' /dev/null"
                
            # Iniciar el proceso del comando en el PTY
            self.process = subprocess.Popen(
                command,
                shell=True,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                preexec_fn=os.setsid,  # Create a new process session
                cwd=cwd
            )

            # Iniciar el proceso del comando en el PTY (sin mostrar el Tip)

            # Bucle principal de E/S
            while self.process.poll() is None:
                # Verificar si hay una señal de interrupción en la cola
                if interrupt_queue and not interrupt_queue.empty():
                    interrupt_queue.get() # Consumir la señal de interrupción
                    self.terminate()
                    yield "\n\n⚠️  Comando interrumpido por el usuario (ESC).\n"
                    break

                try:
                    # Usar select para esperar E/S en el PTY o en stdin con un timeout pequeño
                    # El timeout permite que el bucle verifique poll() periódicamente incluso sin actividad
                    readable_fds, _, _ = select.select([master_fd, sys.stdin.fileno()], [], [], 0.1)

                    # Manejar la salida del comando
                    if master_fd in readable_fds:
                        try:
                            output = os.read(master_fd, 4096).decode(errors='replace')
                            if output:
                                output_buffer += output
                                sys.stdout.write(output)
                                sys.stdout.flush()
                                yield output
                        except OSError:
                            break

                    # Manejar la entrada del usuario
                    if sys.stdin.fileno() in readable_fds:
                        user_input = os.read(sys.stdin.fileno(), 1024)
                        if user_input:
                            if b'\x03' in user_input or b'\x04' in user_input or user_input == b'\x1b':
                                key_name = "Ctrl+C" if b'\x03' in user_input else ("Ctrl+D" if b'\x04' in user_input else "ESC")
                                self.terminate()
                                if interrupt_queue:
                                    interrupt_queue.put(True)
                                yield f"\n\n⚠️  Comando interrumpido por el usuario ({key_name}).\n"
                                break
                            os.write(master_fd, user_input)

                except select.error as e:
                    if e.args[0] == 4: # EINTR
                        continue
                    raise

            # --- Drenaje final del PTY ---
            # Una vez que el proceso termina, puede quedar salida pendiente en el puerto PTY.
            # Hacemos una lectura final no bloqueante para asegurar que capturamos todo.
            try:
                # Esperar un momento muy corto para que terminen de llegar los últimos bytes
                time.sleep(0.05)
                while True:
                    # Usar select con timeout 0 para verificar si hay algo más sin bloquear
                    r, _, _ = select.select([master_fd], [], [], 0)
                    if not r:
                        break
                    output = os.read(master_fd, 4096).decode(errors='replace')
                    if output:
                        sys.stdout.write(output)
                        sys.stdout.flush()
                        yield output
                    else:
                        break
            except (OSError, select.error):
                pass

            # Esperar a que el proceso termine completamente
            self.process.wait()

        finally:
            # Si aún hay contenido en el buffer y no se ha cedido (por ejemplo, si el comando terminó antes de truncar)
            # if output_buffer:
            #    yield output_buffer

            # CRÍTICO: Restaurar siempre la configuración original de la terminal
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
            
            # Cerrar los descriptores de archivo
            os.close(master_fd)
            os.close(slave_fd)
            self.process = None # Reset process

    def terminate(self):
        if self.process and self.process.poll() is None:
            import signal
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except ProcessLookupError:
                # Process might have just finished
                pass
            except Exception as e:
                # It's good to log this, but for now, we'll just ignore it
                # as the main goal is to not crash the interpreter itself.
                pass
