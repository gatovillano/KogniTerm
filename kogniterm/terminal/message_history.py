"""
Módulo para gestionar el historial de mensajes de forma persistente.
Permite navegar por mensajes anteriores usando las flechas arriba/abajo.
"""
import json
import os
from pathlib import Path
from typing import List, Optional
import threading


class MessageHistory:
    """
    Gestor de historial de mensajes persistente.
    El historial se guarda en un archivo JSON y se comparte entre sesiones.
    """
    
    # Máximo de mensajes a guardar en el historial
    MAX_HISTORY_SIZE = 100
    
    GLOBAL_CONFIG_DIR = Path.home() / ".kogniterm"
    HISTORY_FILE = GLOBAL_CONFIG_DIR / "message_history.json"
    
    # Instancia singleton para compartir historial entre todos los ChatInput
    _instance: Optional['MessageHistory'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Patrón singleton para compartir historial entre instancias."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._history: List[str] = []
        self._lock = threading.Lock()
        self._ensure_dir_exists()
        self._load_history()
        self._initialized = True
    
    def _ensure_dir_exists(self):
        """Asegura que el directorio de configuración existe."""
        if not self.GLOBAL_CONFIG_DIR.exists():
            self.GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    def _load_history(self):
        """Carga el historial desde el archivo JSON."""
        if not self.HISTORY_FILE.exists():
            return
            
        try:
            with open(self.HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._history = data.get('messages', [])
        except (json.JSONDecodeError, IOError, Exception):
            # Si hay algún error, empezar con historial vacío
            self._history = []
    
    def _save_history(self):
        """Guarda el historial en el archivo JSON."""
        try:
            with open(self.HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump({'messages': self._history}, f, indent=2)
        except IOError:
            # Silenciar errores de escritura
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
            # Si el mensaje ya está al inicio del historial, no duplicar
            if self._history and self._history[0] == message:
                return
            
            # Insertar al inicio de la lista
            self._history.insert(0, message)
            
            # Limitar el tamaño del historial
            if len(self._history) > self.MAX_HISTORY_SIZE:
                self._history = self._history[:self.MAX_HISTORY_SIZE]
            
            # Guardar de forma asíncrona para no bloquear
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


# Instancia global para importar directamente
_message_history_instance: Optional[MessageHistory] = None


def get_message_history() -> MessageHistory:
    """Retorna la instancia singleton del gestor de historial."""
    global _message_history_instance
    if _message_history_instance is None:
        _message_history_instance = MessageHistory()
    return _message_history_instance
