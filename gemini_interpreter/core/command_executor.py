import os
import pty
import select
import subprocess
import sys
import termios
import tty

class CommandExecutor:
    def __init__(self):
        self.process = None

    def execute(self, command):
        """
        Ejecuta un comando en un pseudo-terminal (PTY), permitiendo la comunicación interactiva.
        Captura la salida del comando y la cede (yields) en tiempo real.
        También captura la entrada del usuario desde stdin y la reenvía al comando.
        """
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

            # Si el comando contiene 'sudo', añadir la opción '-S' para que lea la contraseña de stdin
            if command.strip().startswith("sudo ") and "-S" not in command:
                command = command.replace("sudo", "sudo -S", 1)
                
            # Iniciar el proceso del comando en el PTY
            self.process = subprocess.Popen(
                command,
                shell=True,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                preexec_fn=os.setsid  # Create a new process session
            )

            # Bucle principal de E/S
            while self.process.poll() is None:
                try:
                    # Usar select para esperar E/S en el PTY o en stdin
                    readable_fds, _, _ = select.select([master_fd, sys.stdin.fileno()], [], [])

                    # Manejar la salida del comando
                    if master_fd in readable_fds:
                        try:
                            output = os.read(master_fd, 1024).decode(errors='ignore')
                            if output:
                                yield output
                            else:
                                # EOF (End Of File) - el proceso ha cerrado su extremo del PTY
                                break
                        except OSError:
                            # Error al leer, probablemente el proceso terminó abruptamente
                            break

                    # Manejar la entrada del usuario
                    if sys.stdin.fileno() in readable_fds:
                        user_input = os.read(sys.stdin.fileno(), 1024)
                        if user_input:
                            os.write(master_fd, user_input)

                except select.error as e:
                    # EINTR es una interrupción de llamada al sistema, a menudo por un redimensionamiento de ventana
                    if e.args[0] == 4: # EINTR
                        continue
                    raise # Relanzar otras excepciones de select

            # Esperar a que el proceso termine completamente
            self.process.wait()

        finally:
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
