"""
Race Condition Detection & Re-Read Validation System

Este módulo proporciona herramientas para detectar y prevenir race conditions
en operaciones de edición de archivos, asegurando que los archivos no hayan
sido modificados externamente entre una lectura y una escritura.

Uso:
    from kogniterm.core.race_condition_guard import RaceConditionGuard

    # Registrar un archivo leído
    RaceConditionGuard.register_read(state, file_path, content)

    # Validar antes de escribir
    is_safe, message = RaceConditionGuard.validate_write(state, file_path)
    if not is_safe:
        raise RaceConditionDetected(message)

    # Después de escribir, actualizar el cache
    RaceConditionGuard.register_write(state, file_path, new_content)
"""

import hashlib
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class FileState:
    """Estado de un archivo para detección de race conditions."""
    hash: str
    timestamp: float
    content: str
    size: int


class RaceConditionGuard:
    """
    Guardia contra race conditions en operaciones de archivos.

    Mantiene un cache de hashes de archivos que han sido leídos durante
    la sesión del agente, y valida que no hayan cambiado antes de
    permitir operaciones de escritura o eliminación.
    """

    # Cache por sesión (AgentState.file_hash_cache)
    CACHE_KEY = "file_hash_cache"

    @staticmethod
    def _compute_hash(content: str) -> str:
        """Calcula el hash SHA-256 del contenido."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    @staticmethod
    def _compute_file_state(path: str, content: str) -> FileState:
        """Crea un FileState a partir de una ruta y contenido."""
        import time
        return FileState(
            hash=RaceConditionGuard._compute_hash(content),
            timestamp=time.time(),
            content=content,
            size=len(content.encode('utf-8'))
        )

    @staticmethod
    def register_read(state: Any, file_path: str, content: str) -> None:
        """
        Registra que un archivo ha sido leído, almacenando su hash.

        Args:
            state: AgentState instance
            file_path: Ruta absoluta del archivo
            content: Contenido leído
        """
        if not hasattr(state, 'file_hash_cache'):
            state.file_hash_cache = {}

        file_state = RaceConditionGuard._compute_file_state(file_path, content)
        state.file_hash_cache[file_path] = file_state

    @staticmethod
    def validate_write(state: Any, file_path: str, original_content: Optional[str] = None) -> Tuple[bool, str]:
        """
        Valida que el archivo no haya cambiado desde la última lectura.

        Args:
            state: AgentState instance
            file_path: Ruta absoluta del archivo
            original_content: Contenido actual del archivo (opcional, si no se provee se lee del disco)

        Returns:
            (is_safe, message): Tupla con el resultado de la validación
        """
        import os

        if not hasattr(state, 'file_hash_cache'):
            # Si no hay cache, asumimos que es seguro (primera vez)
            return True, "No hay registro previo de este archivo."

        cached_state = state.file_hash_cache.get(file_path)

        if not cached_state:
            # No se ha leído previamente, no podemos validar
            return True, "Archivo no encontrado en cache (no fue leído previamente)."

        # Leer el contenido actual del archivo si no se proporcionó
        if original_content is None:
            if not os.path.exists(file_path):
                return True, "Archivo no existe (operación de creación)."
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
            except Exception as e:
                return True, f"No se pudo leer el archivo para validación: {e}"

        current_hash = RaceConditionGuard._compute_hash(original_content)

        if current_hash != cached_state.hash:
            # Race condition detectada!
            return False, (
                f"⚠️ RACE CONDITION DETECTADA: El archivo '{file_path}' fue modificado "
                f"desde la última lectura (hash cached: {cached_state.hash[:8]}..., "
                f"hash actual: {current_hash[:8]}...). "
                f"Por seguridad, se aborta la operación. "
                f"Por favor, relee el archivo y reapplica los cambios."
            )

        return True, "Validación exitosa: archivo no modificado."

    @staticmethod
    def validate_delete(state: Any, file_path: str) -> Tuple[bool, str]:
        """
        Valida que el archivo a eliminar no haya cambiado desde la última lectura.

        Args:
            state: AgentState instance
            file_path: Ruta absoluta del archivo

        Returns:
            (is_safe, message): Tupla con el resultado de la validación
        """
        import os

        if not hasattr(state, 'file_hash_cache'):
            return True, "No hay registro previo de este archivo."

        cached_state = state.file_hash_cache.get(file_path)

        if not cached_state:
            return True, "Archivo no encontrado en cache."

        # Para eliminar, verificamos que el archivo exista y su hash coincida
        if not os.path.exists(file_path):
            return True, "Archivo ya no existe (ya fue eliminado)."

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
        except Exception:
            # Si no podemos leerlo (permisos, etc), permitimos la eliminación
            return True, "No se pudo leer el archivo, pero se permite eliminación."

        current_hash = RaceConditionGuard._compute_hash(current_content)

        if current_hash != cached_state.hash:
            return False, (
                f"⚠️ RACE CONDITION DETECTADA: El archivo '{file_path}' fue modificado "
                f"desde la última lectura. Se recomienda revisar el contenido antes de eliminar."
            )

        return True, "Validación exitosa: archivo no modificado."

    @staticmethod
    def register_write(state: Any, file_path: str, content: str) -> None:
        """
        Actualiza el cache después de una escritura exitosa.

        Args:
            state: AgentState instance
            file_path: Ruta absoluta del archivo
            content: Nuevo contenido escrito
        """
        if not hasattr(state, 'file_hash_cache'):
            state.file_hash_cache = {}

        file_state = RaceConditionGuard._compute_file_state(file_path, content)
        state.file_hash_cache[file_path] = file_state

    @staticmethod
    def invalidate(state: Any, file_path: str) -> None:
        """
        Invalida la entrada del cache para un archivo (útil si se opera sin validación).

        Args:
            state: AgentState instance
            file_path: Ruta absoluta del archivo
        """
        if hasattr(state, 'file_hash_cache') and file_path in state.file_hash_cache:
            del state.file_hash_cache[file_path]

    @staticmethod
    def clear_cache(state: Any) -> None:
        """
        Limpia todo el cache de hashes.

        Args:
            state: AgentState instance
        """
        if hasattr(state, 'file_hash_cache'):
            state.file_hash_cache.clear()


class RaceConditionDetected(Exception):
    """Excepción lanzada cuando se detecta una race condition."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
