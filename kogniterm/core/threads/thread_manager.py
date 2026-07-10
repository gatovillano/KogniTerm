import os
import json
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class ThreadManager:
    """
    Gestiona la creación, recuperación y metadatos de los hilos de conversación.
    Sustituye la lógica de autoguardado simple por un sistema de hilos organizados.
    """
    
    THREADS_DIR_NAME = "chat_threads"

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.threads_base_dir = os.path.join(workspace_dir, self.THREADS_DIR_NAME)
        self._ensure_directories()
        
        # Hilo actual cargado
        self.current_thread_id: Optional[str] = None

    def _ensure_directories(self) -> None:
        os.makedirs(self.threads_base_dir, exist_ok=True)

    def create_thread(self, title: str = "Nueva Conversación") -> str:
        """Crea un nuevo hilo con su estructura de carpetas y metadatos."""
        thread_id = str(uuid.uuid4())
        thread_dir = os.path.join(self.threads_base_dir, thread_id)
        os.makedirs(thread_dir, exist_ok=True)
        
        self.update_thread_metadata(thread_id, title=title)
        self.current_thread_id = thread_id
        return thread_id

    def update_thread_metadata(self, thread_id: str, title: Optional[str] = None, preview: Optional[str] = None, message_count: Optional[int] = None):
        """Actualiza el archivo metadata.json de un hilo específico."""
        thread_dir = os.path.join(self.threads_base_dir, thread_id)
        meta_path = os.path.join(thread_dir, "metadata.json")
        
        now = datetime.now().isoformat()
        
        # Cargar existente o crear nuevo
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        else:
            meta = {
                "thread_id": thread_id,
                "title": "Conversación sin título",
                "created_at": now,
            }

        if title is not None: meta["title"] = title
        if preview is not None: meta["preview"] = preview
        if message_count is not None: meta["message_count"] = message_count
        meta["updated_at"] = now

        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    def list_threads(self, sort_by_recent: bool = True) -> List[Dict[str, Any]]:
        """Lista todos los hilos disponibles leyendo sus metadatos."""
        threads = []
        if not os.path.exists(self.threads_base_dir):
            return threads

        for thread_id in os.listdir(self.threads_base_dir):
            meta_path = os.path.join(self.threads_base_dir, thread_id, "metadata.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                        threads.append(meta)
                except Exception as e:
                    logger.warning(f"Error leyendo metadatos del hilo {thread_id}: {e}")

        if sort_by_recent:
            threads.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            
        return threads

    def get_thread_history_path(self, thread_id: str) -> str:
        """Devuelve la ruta al archivo de historial del hilo."""
        return os.path.join(self.threads_base_dir, thread_id, "history.json")

    def delete_thread(self, thread_id: str) -> bool:
        """Elimina un hilo completo y sus archivos."""
        import shutil
        thread_dir = os.path.join(self.threads_base_dir, thread_id)
        try:
            if os.path.exists(thread_dir):
                shutil.rmtree(thread_dir)
                return True
        except Exception as e:
            logger.error(f"Error eliminando hilo {thread_id}: {e}")
        return False
