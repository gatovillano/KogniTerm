"""
Gestor de autoguardados versionados por sesión.

Mantiene múltiples versiones de autoguardos con identificadores únicos
por sesión, evitando que se sobrescriban versiones anteriores.

Características:
- Versionado automático con timestamps
- Identificador único de sesión (UUID)
- Gestión thread-safe de múltiples versiones
- Rotación automática de autoguardos antiguos
- Recuperación de versiones previas
"""

import os
import json
import uuid
import threading
import logging
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from langchain_core.messages import BaseMessage, messages_to_dict, messages_from_dict

logger = logging.getLogger(__name__)


class AutosaveManager:
    """Gestor de autoguardados versionados con soporte multi-sesión."""
    
    # Configuración
    AUTOSAVE_DIR_NAME = "autosave"
    MAX_VERSIONS_PER_SESSION = 10  # Máximo de versiones a mantener por sesión
    MAX_TOTAL_AUTOSAVES = 50  # Máximo total de autoguardos
    CLEANUP_INTERVAL = 300  # Limpiar cada 5 minutos
    VERSION_RETENTION_DAYS = 7  # Mantener autoguardos por 7 días
    
    def __init__(self, workspace_dir: str):
        """
        Inicializa el gestor de autoguardados.
        
        Args:
            workspace_dir: Directorio raíz del workspace (.kogniterm)
        """
        self.workspace_dir = workspace_dir
        self.autosave_base_dir = os.path.join(workspace_dir, self.AUTOSAVE_DIR_NAME)
        self.session_id = str(uuid.uuid4())
        self.session_dir = os.path.join(self.autosave_base_dir, f"session_{self.session_id}")
        
        # Lock para thread-safety
        self._lock = threading.RLock()
        
        # Historial de versiones guardadas en esta sesión
        self._session_versions: List[Dict] = []
        
        # Crear directorios necesarios
        self._ensure_directories()
        
        # Iniciar thread de limpieza
        self._cleanup_thread = None
        self._stop_cleanup = threading.Event()
        self._start_cleanup_thread()
        
        logger.info(f"AutosaveManager inicializado con session_id: {self.session_id}")
    
    def _ensure_directories(self) -> None:
        """Asegura que existan los directorios necesarios."""
        os.makedirs(self.session_dir, exist_ok=True)
    
    def save_version(self, messages: List[BaseMessage], description: str = "") -> Tuple[bool, str]:
        """
        Guarda una versión del historial con timestamp y UUID de sesión.
        
        Args:
            messages: Lista de mensajes a guardar
            description: Descripción opcional de la versión
            
        Returns:
            (éxito, ruta_del_archivo)
        """
        with self._lock:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # ms de precisión
                filename = f"autosave_{timestamp}.json"
                file_path = os.path.join(self.session_dir, filename)
                
                # Serializar mensajes
                messages_dict = messages_to_dict(messages)
                
                # Agregar metadatos
                autosave_data = {
                    "session_id": self.session_id,
                    "timestamp": datetime.now().isoformat(),
                    "description": description,
                    "message_count": len(messages),
                    "messages": messages_dict
                }
                
                # Guardar con thread-safety
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(autosave_data, f, indent=2, ensure_ascii=False)
                
                # Registrar la versión
                version_info = {
                    "filename": filename,
                    "path": file_path,
                    "timestamp": datetime.now().isoformat(),
                    "message_count": len(messages),
                    "description": description
                }
                self._session_versions.append(version_info)
                
                logger.debug(f"Autoguardado guardado: {file_path}")
                return True, file_path
                
            except Exception as e:
                logger.error(f"Error al guardar versión de autoguardado: {e}")
                return False, ""
    
    def get_session_versions(self) -> List[Dict]:
        """
        Obtiene todas las versiones de autoguardos de la sesión actual.
        
        Returns:
            Lista de diccionarios con información de versiones
        """
        with self._lock:
            return list(self._session_versions)
    
    def get_all_versions(self) -> List[Dict]:
        """
        Obtiene TODAS las versiones de autoguardos de todas las sesiones.
        Útil para recuperar autoguardados de sesiones anteriores.
        
        Returns:
            Lista de diccionarios con información de versiones
        """
        all_versions = []
        
        with self._lock:
            if not os.path.exists(self.autosave_base_dir):
                return all_versions
            
            # Iterar sobre todos los directorios de sesión
            for session_dir_name in os.listdir(self.autosave_base_dir):
                session_path = os.path.join(self.autosave_base_dir, session_dir_name)
                
                if not os.path.isdir(session_path):
                    continue
                
                # Leer versiones de esta sesión
                for filename in sorted(os.listdir(session_path), reverse=True):
                    if filename.endswith(".json"):
                        file_path = os.path.join(session_path, filename)
                        try:
                            stats = os.stat(file_path)
                            all_versions.append({
                                "filename": filename,
                                "path": file_path,
                                "session_dir": session_dir_name,
                                "modified": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                                "size_bytes": stats.st_size
                            })
                        except Exception as e:
                            logger.warning(f"Error al leer versión {filename}: {e}")
        
        return all_versions
    
    def load_version(self, file_path: str) -> Optional[List[BaseMessage]]:
        """
        Carga una versión específica de autoguardado.
        
        Args:
            file_path: Ruta al archivo de autoguardado
            
        Returns:
            Lista de mensajes o None si hay error
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                autosave_data = json.load(f)
            
            messages_dict = autosave_data.get("messages", [])
            messages = messages_from_dict(messages_dict)
            
            logger.info(f"Versión de autoguardado cargada: {file_path}")
            return messages
            
        except Exception as e:
            logger.error(f"Error al cargar versión de autoguardado: {e}")
            return None
    
    def _start_cleanup_thread(self) -> None:
        """Inicia thread de limpieza de versiones antiguas."""
        self._stop_cleanup.clear()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def _cleanup_loop(self) -> None:
        """Loop de limpieza periódica."""
        while not self._stop_cleanup.is_set():
            try:
                self._stop_cleanup.wait(self.CLEANUP_INTERVAL)
                if not self._stop_cleanup.is_set():
                    self._cleanup_old_versions()
            except Exception as e:
                logger.error(f"Error en thread de limpieza: {e}")
    
    def _cleanup_old_versions(self) -> None:
        """
        Limpia versiones antiguas según políticas de retención.
        
        Políticas:
        - Mantener máximo MAX_VERSIONS_PER_SESSION por sesión
        - Mantener máximo MAX_TOTAL_AUTOSAVES totales
        - Eliminar autoguardos más antiguos que VERSION_RETENTION_DAYS
        """
        with self._lock:
            try:
                now = datetime.now()
                cutoff_date = now - timedelta(days=self.VERSION_RETENTION_DAYS)
                
                if not os.path.exists(self.autosave_base_dir):
                    return
                
                # Recolectar todos los autoguardos
                all_autosaves = []
                for session_dir_name in os.listdir(self.autosave_base_dir):
                    session_path = os.path.join(self.autosave_base_dir, session_dir_name)
                    
                    if not os.path.isdir(session_path):
                        continue
                    
                    for filename in os.listdir(session_path):
                        if filename.endswith(".json"):
                            file_path = os.path.join(session_path, filename)
                            try:
                                stats = os.stat(file_path)
                                mod_time = datetime.fromtimestamp(stats.st_mtime)
                                all_autosaves.append({
                                    "path": file_path,
                                    "session": session_dir_name,
                                    "mod_time": mod_time,
                                    "age_days": (now - mod_time).days
                                })
                            except Exception:
                                continue
                
                # Limpiar por edad
                for autosave in all_autosaves:
                    if autosave["mod_time"] < cutoff_date:
                        try:
                            os.remove(autosave["path"])
                            logger.debug(f"Autoguardado antiguo eliminado: {autosave['path']}")
                        except Exception as e:
                            logger.warning(f"Error al eliminar autoguardado: {e}")
                
                # Limpiar por límite de versiones por sesión
                sessions_versions = {}
                for autosave in all_autosaves:
                    session = autosave["session"]
                    if session not in sessions_versions:
                        sessions_versions[session] = []
                    sessions_versions[session].append(autosave)
                
                for session, versions in sessions_versions.items():
                    if len(versions) > self.MAX_VERSIONS_PER_SESSION:
                        # Ordenar por antigüedad y eliminar los más viejos
                        versions.sort(key=lambda x: x["mod_time"])
                        to_delete = versions[:-self.MAX_VERSIONS_PER_SESSION]
                        for autosave in to_delete:
                            try:
                                os.remove(autosave["path"])
                                logger.debug(f"Autoguardado excedente eliminado: {autosave['path']}")
                            except Exception as e:
                                logger.warning(f"Error al eliminar autoguardado: {e}")
                
                # Limpiar por límite total
                if len(all_autosaves) > self.MAX_TOTAL_AUTOSAVES:
                    all_autosaves.sort(key=lambda x: x["mod_time"])
                    to_delete = all_autosaves[:-self.MAX_TOTAL_AUTOSAVES]
                    for autosave in to_delete:
                        try:
                            os.remove(autosave["path"])
                            logger.debug(f"Autoguardado global excedente eliminado: {autosave['path']}")
                        except Exception as e:
                            logger.warning(f"Error al eliminar autoguardado: {e}")
                
            except Exception as e:
                logger.error(f"Error en limpieza de versiones: {e}")
    
    def stop(self) -> None:
        """Detiene el thread de limpieza."""
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
    
    def get_statistics(self) -> Dict:
        """Obtiene estadísticas del sistema de autoguardados."""
        with self._lock:
            all_versions = self.get_all_versions()
            session_versions = self.get_session_versions()
            
            # Agrupar por sesión
            by_session = {}
            for version in all_versions:
                session = version.get("session_dir", "unknown")
                if session not in by_session:
                    by_session[session] = 0
                by_session[session] += 1
            
            return {
                "current_session_id": self.session_id,
                "current_session_versions": len(session_versions),
                "total_versions": len(all_versions),
                "sessions_count": len(by_session),
                "by_session": by_session
            }
