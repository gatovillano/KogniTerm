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

            # Informar al usuario cómo interrumpir
            yield "💡 Tip: Presiona ESC, Ctrl+C o Ctrl+D para interrumpir el comando.\n\n"

            # Bucle principal de E/S
            while self.process.poll() is None:
                # Verificar si hay una señal de interrupción en la cola
                if interrupt_queue and not interrupt_queue.empty():
                    interrupt_queue.get() # Consumir la señal de interrupción
                    self.terminate()
                    yield "\n\n⚠️  Comando interrumpido por el usuario (ESC).\n"
                    break

                try:
                    # Usar select para esperar E/S en el PTY o en stdin
                    readable_fds, _, _ = select.select([master_fd, sys.stdin.fileno()], [], [])

                    # Manejar la salida del comando
                    if master_fd in readable_fds:
                        try:
                            output = os.read(master_fd, 1024).decode(errors='replace')
                            if output:
                                # Sin límite de longitud - mostrar toda la salida
                                output_buffer += output
                                sys.stdout.write(output) # Imprimir para interactividad en tiempo real
                                sys.stdout.flush() # Asegurar que se imprime inmediatamente
                                yield output # Ceder la salida para acumular en full_command_output
                            else:
                                # Si no hay salida, y el proceso sigue vivo, esperamos un poco
                                time.sleep(0.01) # Pequeño retardo para evitar bucle busy-wait
                        except OSError:
                            # Error al leer, probablemente el proceso terminó abruptamente
                            break
                    else:
                        # Si no hay nada que leer de master_fd, esperamos un poco
                        time.sleep(0.01)

                    # Manejar la entrada del usuario
                    if sys.stdin.fileno() in readable_fds:
                        user_input = os.read(sys.stdin.fileno(), 1024)
                        if user_input:
                            # Detectar Ctrl+C (\x03), Ctrl+D (\x04) o ESC (\x1b) para interrumpir
                            # Para ESC, verificamos que sea exactamente un byte para no romper secuencias de escape (flechas, etc.)
                            if b'\x03' in user_input or b'\x04' in user_input or user_input == b'\x1b':
                                key_name = "Ctrl+C" if b'\x03' in user_input else ("Ctrl+D" if b'\x04' in user_input else "ESC")
                                self.terminate()
                                # Propagar la interrupción a la cola global si existe
                                if interrupt_queue:
                                    interrupt_queue.put(True)
                                yield f"\n\n⚠️  Comando interrumpido por el usuario ({key_name}).\n"
                                break
                            # Reenviar la entrada al comando
                            os.write(master_fd, user_input)

                except select.error as e:
                    # EINTR es una interrupción de llamada al sistema, a menudo por un redimensionamiento de ventana
                    if e.args[0] == 4: # EINTR
                        continue
                    raise # Relanzar otras excepciones de select

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
