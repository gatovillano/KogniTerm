import sys
import termios
import tty
import threading
import time
import queue
import logging
import select

logger = logging.getLogger(__name__)

class KeyboardHandler:
    def __init__(self, interrupt_queue: queue.Queue):
        self.interrupt_queue = interrupt_queue
        self.stop_event = threading.Event()
        self.thread = None

    def _worker(self):
        """Hilo que escucha el teclado continuamente usando select para no bloquear."""
        logger.debug("KeyboardHandler: Hilo de escucha iniciado.")
        
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not self.stop_event.is_set():
                # Usar select para ver si hay datos en stdin con un timeout corto
                dr, dw, de = select.select([sys.stdin], [], [], 0.1)
                if dr:
                    char = sys.stdin.read(1)
                    if char == '\x1b' or char == 'q' or char == '\x03': # Esc, q, o Ctrl+C (si llega como char)
                        logger.info(f"KeyboardHandler: Interrupción detectada ({repr(char)}).")
                        self.interrupt_queue.put(True)
                        # Evitar rebotes
                        time.sleep(0.5)
                time.sleep(0.05)
        except Exception as e:
            logger.error(f"Error en KeyboardHandler: {e}")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            logger.debug("KeyboardHandler: Hilo de escucha detenido y terminal restaurada.")

    def start(self):
        """Inicia el hilo de escucha."""
        if self.thread and self.thread.is_alive():
            return
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop(self):
        """Detiene el hilo de escucha."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=0.5)
        self.thread = None
