import time
import threading
import logging
from typing import Dict, Callable, Optional, Set

logger = logging.getLogger(__name__)

class HeartbeatMonitor:
    """
    Monitor en segundo plano que vigila el progreso de los subagentes.
    Si un subagente no actualiza su latido en un tiempo superior a su umbral,
    se considera estancado y se notifican los callbacks registrados.
    """
    def __init__(self, check_interval: float = 5.0):
        self.last_heartbeat: Dict[str, float] = {}
        self.stalled_thresholds: Dict[str, float] = {}
        self.stall_callbacks: Set[Callable[[str, float], None]] = set()
        self._lock = threading.Lock()
        self._check_interval = check_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def update_heartbeat(self, agent_id: str, threshold: float = 60.0):
        """
        Registra o actualiza el latido de un agente con un umbral de inactividad dado en segundos.
        """
        with self._lock:
            self.last_heartbeat[agent_id] = time.time()
            self.stalled_thresholds[agent_id] = threshold

    def remove_agent(self, agent_id: str):
        """
        Elimina el registro de latido de un agente.
        """
        with self._lock:
            self.last_heartbeat.pop(agent_id, None)
            self.stalled_thresholds.pop(agent_id, None)

    def register_stall_callback(self, callback: Callable[[str, float], None]):
        """
        Registra una función a invocar cuando se detecte un estancamiento.
        La función debe aceptar (agent_id: str, elapsed_time: float).
        """
        with self._lock:
            self.stall_callbacks.add(callback)

    def unregister_stall_callback(self, callback: Callable[[str, float], None]):
        """
        Elimina un callback registrado.
        """
        with self._lock:
            self.stall_callbacks.discard(callback)

    def start(self):
        """
        Inicia el bucle de monitoreo en un hilo secundario de tipo daemon.
        """
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            logger.info("HeartbeatMonitor iniciado.")

    def stop(self):
        """
        Detiene el bucle de monitoreo.
        """
        self._stop_event.set()
        if self._thread:
            self._thread.join()
            self._thread = None
            logger.info("HeartbeatMonitor detenido.")

    def _run(self):
        while not self._stop_event.is_set():
            time.sleep(self._check_interval)
            now = time.time()
            stalled_agents = []
            
            with self._lock:
                for agent_id, last_t in list(self.last_heartbeat.items()):
                    threshold = self.stalled_thresholds.get(agent_id, 60.0)
                    elapsed = now - last_t
                    if elapsed > threshold:
                        stalled_agents.append((agent_id, elapsed))
                        # Quitar para evitar múltiples notificaciones por el mismo estancamiento
                        self.last_heartbeat.pop(agent_id, None)
                        self.stalled_thresholds.pop(agent_id, None)

            # Invocar callbacks fuera del lock para evitar deadlocks
            for agent_id, elapsed in stalled_agents:
                logger.warning(
                    f"⚠️ Agente {agent_id} estancado detectado. Sin latido por {elapsed:.1f} segundos."
                )
                with self._lock:
                    callbacks = list(self.stall_callbacks)
                for cb in callbacks:
                    try:
                        cb(agent_id, elapsed)
                    except Exception as e:
                        logger.exception(f"Error al ejecutar callback de estancamiento para {agent_id}: {e}")
