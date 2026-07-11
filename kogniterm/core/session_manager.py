"""
SessionManager: adaptador retrocompatible sobre ThreadManager.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .thread_manager import ThreadManager

logger = logging.getLogger(__name__)


class SessionManager:
    """Adaptador retrocompatible para la API antigua de sesiones."""

    ACTIVE_AUTOSAVE_NAME = "autosave_actual"

    def __init__(self, workspace_dir: str, thread_manager: Optional[ThreadManager] = None):
        self.workspace_dir = workspace_dir
        self.sessions_dir = os.path.join(workspace_dir, ".kogniterm", "sessions")
        self.history_file_path = os.path.join(workspace_dir, ".kogniterm", "history.json")
        self.current_session_name: Optional[str] = None

        self._thread_manager = thread_manager

        os.makedirs(self.sessions_dir, exist_ok=True)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Lista hilos como si fueran sesiones (formato antiguo)."""
        if not self._thread_manager:
            return []

        sessions: List[Dict[str, Any]] = []
        for thread in self._thread_manager.list_threads():
            sessions.append(
                {
                    "name": thread["id"],
                    "display_name": thread["title"],
                    "modified": thread["updated_at"],
                    "modified_ts": thread["updated_at"],
                    "messages": thread.get("message_count", 0),
                    "path": os.path.join(
                        self._thread_manager.threads_dir, thread["id"], "messages.json"
                    ),
                    "source": "thread",
                }
            )
        return sessions

    def save_session(self, name: str, history: List[BaseMessage]) -> bool:
        """Guarda un hilo con el nombre indicado."""
        if not self._thread_manager:
            return False

        thread = self._thread_manager.create_thread(thread_id=name, messages=history)
        self.current_session_name = name
        return bool(thread)

    def load_session(self, name: str) -> Optional[List[BaseMessage]]:
        """Carga un hilo por ID."""
        if not self._thread_manager:
            return None

        thread = self._thread_manager.get_thread(name)
        if not thread:
            return None

        self.current_session_name = name
        return list(thread.messages)

    def delete_session(self, name: str) -> bool:
        """Elimina un hilo."""
        if not self._thread_manager:
            return False

        if name == self.ACTIVE_AUTOSAVE_NAME:
            logger.warning("No se puede eliminar el autoguardado activo desde el gestor de sesiones.")
            return False

        return self._thread_manager.delete_thread(name)

    def _build_session_entry(self, name: str, file_path: str, source: str, display_name: Optional[str] = None) -> Dict[str, Any]:
        """Método legacy mantenido para compatibilidad."""
        import os as _os
        from datetime import datetime as _datetime

        stats = _os.stat(file_path)
        modified_dt = _datetime.fromtimestamp(stats.st_mtime)
        return {
            "name": name,
            "display_name": display_name or name,
            "modified": modified_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "modified_ts": stats.st_mtime,
            "messages": 0,
            "path": file_path,
            "source": source,
        }

    def _extract_message_list(self, data: Any) -> Optional[List[dict]]:
        """Método legacy mantenido para compatibilidad."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("messages")
        return None

    def _count_messages(self, file_path: str) -> int:
        """Método legacy mantenido para compatibilidad."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = __import__("json").load(f)
        message_list = self._extract_message_list(data)
        return len(message_list) if message_list is not None else 0

    def _deserialize_messages(self, message_list: List[dict]) -> List[BaseMessage]:
        """Método legacy mantenido para compatibilidad."""
        from langchain_core.messages import messages_from_dict
        return messages_from_dict(message_list)

    def _find_autosave_file(self, name: str) -> Optional[str]:
        """Método legacy mantenido para compatibilidad."""
        kogniterm_autosave_dir = os.path.join(self.workspace_dir, ".kogniterm", "autosave")
        if not os.path.exists(kogniterm_autosave_dir):
            return None

        for root, _, files in os.walk(kogniterm_autosave_dir):
            for filename in files:
                if filename == f"{name}.json" or filename == name:
                    return os.path.join(root, filename)
        return None
