"""
Módulo para gestionar el historial de mensajes de forma persistente.
Permite navegar por mensajes anteriores usando las flechas arriba/abajo.

Cada directorio de trabajo tiene su propio historial independiente.
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import threading


class MessageHistory:
    """
    Gestor de historial de mensajes persistente por directorio de trabajo.
    Cada directorio (workspace) tiene su propio historial aislado.
    """

    # Máximo de mensajes a guardar en el historial
    MAX_HISTORY_SIZE = 100

    GLOBAL_CONFIG_DIR = Path.home() / ".kogniterm"
    HISTORY_DIR = GLOBAL_CONFIG_DIR / "history"

    # Diccionario de instancias por directorio de trabajo
    _instances: Dict[str, 'MessageHistory'] = {}
    _instances_lock = threading.Lock()

    @staticmethod
    def _dir_key(cwd: str) -> str:
        """Genera una clave única para un directorio de trabajo."""
        resolved = str(Path(cwd).resolve())
        return hashlib.sha256(resolved.encode()).hexdigest()[:16]

    @classmethod
    def get_instance(cls, cwd: Optional[str] = None) -> 'MessageHistory':
        """
        Retorna la instancia de MessageHistory para el directorio dado.
        Usa un diccionario de instancias por directorio (no singleton global).
        """
        if cwd is None:
            cwd = os.getcwd()

        resolved = str(Path(cwd).resolve())

        with cls._instances_lock:
            if resolved not in cls._instances:
                instance = cls.__new__(cls)
                instance._init_for_dir(resolved)
                cls._instances[resolved] = instance
            return cls._instances[resolved]

    def _init_for_dir(self, cwd: str):
        """Inicializa la instancia para un directorio específico."""
        self._cwd = cwd
        self._dir_key = self._dir_key(cwd)
        self._history: List[str] = []
        self._lock = threading.Lock()
        self._ensure_dir_exists()
        self._load_history()

    def _ensure_dir_exists(self):
        """Asegura que el directorio de configuración existe."""
        if not self.HISTORY_DIR.exists():
            self.HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    def _get_history_file(self) -> Path:
        """Retorna la ruta del archivo de historial para este directorio."""
        return self.HISTORY_DIR / f"{self._dir_key}.json"

    def _load_history(self):
        """Carga el historial desde el archivo JSON."""
        history_file = self._get_history_file()
        if not history_file.exists():
            return

        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._history = data.get('messages', [])
        except (json.JSONDecodeError, IOError, Exception):
            self._history = []

    def _save_history(self):
        """Guarda el historial en el archivo JSON."""
        try:
            history_file = self._get_history_file()
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({'messages': self._history}, f, indent=2)
        except IOError:
            pass

    def get_history(self) -> List[str]:
        """Retorna una copia del historial."""
        with self._lock:
            return self._history.copy()

    def add_message(self, message: str):
        """
        Añade un mensaje al historial.
        Evita duplicados consecutivos y limita el tamaño del historial.
        """
        if not message or not message.strip():
            return

        message = message.strip()

        with self._lock:
            if self._history and self._history[0] == message:
                return

            self._history.insert(0, message)

            if len(self._history) > self.MAX_HISTORY_SIZE:
                self._history = self._history[:self.MAX_HISTORY_SIZE]

            threading.Thread(target=self._save_history, daemon=True).start()

    def clear_history(self):
        """Limpia todo el historial de mensajes."""
        with self._lock:
            self._history = []
            self._save_history()

    def get_message_at_index(self, index: int) -> Optional[str]:
        """Obtiene un mensaje en un índice específico."""
        with self._lock:
            if 0 <= index < len(self._history):
                return self._history[index]
        return None

    @property
    def length(self) -> int:
        """Retorna la cantidad de mensajes en el historial."""
        with self._lock:
            return len(self._history)

    @property
    def cwd(self) -> str:
        """Retorna el directorio de trabajo asociado a este historial."""
        return self._cwd


# Compatibilidad: función que acepta cwd opcional
def get_message_history(cwd: Optional[str] = None) -> MessageHistory:
    """
    Retorna la instancia del gestor de historial para el directorio dado.
    Si no se especifica, usa el directorio de trabajo actual.
    """
    return MessageHistory.get_instance(cwd)
