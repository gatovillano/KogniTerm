import os
import pty
import select
import subprocess
import sys
import termios
import tty

class CommandExecutor:
    def execute(self, command):
        """
        Ejecuta un comando en un pseudo-terminal (PTY), permitiendo la comunicación interactiva.
        Captura la salida del comando y la cede (yields) en tiempo real.
        También captura la entrada del usuario desde stdin y la reenvía al comando.
        """
        # Guardar la configuración original de la terminal
        try:
            old_settings = termios.tcgetattr(sys.stdin.fileno())
        except termios.error:
            # Si no se ejecuta en una terminal real, no se puede continuar con el modo interactivo.
            # Se podría implementar un fallback a un modo no interactivo aquí si fuera necesario.
            yield "Error: No se pudo obtener la configuración de la terminal. Ejecución no interactiva no implementada."
            return

        master_fd, slave_fd = pty.openpty()

        try:
            # Poner la terminal del usuario en modo "raw"
            # Esto pasa todas las teclas directamente al proceso sin procesarlas
            tty.setraw(sys.stdin.fileno())

            # Iniciar el proceso del comando en el PTY
            process = subprocess.Popen(
                command,
                shell=True,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
            )

            # Bucle principal de E/S
            while process.poll() is None:
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
            process.wait()

        finally:
            # CRÍTICO: Restaurar siempre la configuración original de la terminal
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
            
            # Cerrar los descriptores de archivo
            os.close(master_fd)
            os.close(slave_fd)

    def terminate(self):
        # Con el nuevo diseño, la cancelación (Ctrl+C) es manejada por la terminal
        # y el bloque `finally` en `execute` se encarga de la limpieza.
        # Esta función se mantiene por si se necesita una terminación explícita desde otra parte.
        pass
