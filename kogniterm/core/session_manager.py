import os
import json
import logging
from typing import List, Optional, Dict
from datetime import datetime
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.sessions_dir = os.path.join(workspace_dir, ".kogniterm", "sessions")
        self.current_session_name: Optional[str] = None
        
        # Asegurar que el directorio de sesiones existe
        if not os.path.exists(self.sessions_dir):
            os.makedirs(self.sessions_dir)

    def list_sessions(self) -> List[Dict[str, str]]:
        """Lista todas las sesiones disponibles con sus metadatos básicos."""
        sessions = []
        if not os.path.exists(self.sessions_dir):
            return sessions

        for filename in os.listdir(self.sessions_dir):
            if filename.endswith(".json"):
                name = filename[:-5] # Quitar extensión .json
                file_path = os.path.join(self.sessions_dir, filename)
                try:
                    stats = os.stat(file_path)
                    modified_time = datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Leer brevemente para ver cuántos mensajes hay (opcional, pero útil)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        msg_count = len(data) if isinstance(data, list) else 0
                        
                    sessions.append({
                        "name": name,
                        "modified": modified_time,
                        "messages": msg_count,
                        "path": file_path
                    })
                except Exception as e:
                    logger.warning(f"Error al leer sesión {filename}: {e}")
        
        # Ordenar por fecha de modificación descendente
        sessions.sort(key=lambda x: x["modified"], reverse=True)
        return sessions

    def save_session(self, name: str, history: List[BaseMessage]) -> bool:
        """Guarda el historial actual como una sesión con nombre."""
        try:
            file_path = os.path.join(self.sessions_dir, f"{name}.json")
            
            # Convertir mensajes a dict para serialización
            history_dicts = messages_to_dict(history)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(history_dicts, f, indent=2, ensure_ascii=False)
            
            self.current_session_name = name
            return True
        except Exception as e:
            logger.error(f"Error al guardar sesión '{name}': {e}")
            return False

    def load_session(self, name: str) -> Optional[List[BaseMessage]]:
        """Carga una sesión por nombre y devuelve el historial de mensajes."""
        file_path = os.path.join(self.sessions_dir, f"{name}.json")
        
        if not os.path.exists(file_path):
            logger.warning(f"Sesión '{name}' no encontrada.")
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                messages = messages_from_dict(data)
                self.current_session_name = name
                return messages
            else:
                logger.error(f"Formato de sesión inválido en '{name}'.")
                return None
        except Exception as e:
            logger.error(f"Error al cargar sesión '{name}': {e}")
            return None

    def delete_session(self, name: str) -> bool:
        """Elimina una sesión guardada."""
        file_path = os.path.join(self.sessions_dir, f"{name}.json")
        
        if not os.path.exists(file_path):
            return False
            
        try:
            os.remove(file_path)
            if self.current_session_name == name:
                self.current_session_name = None
            return True
        except Exception as e:
            logger.error(f"Error al eliminar sesión '{name}': {e}")
            return False

    def get_current_session_name(self) -> Optional[str]:
        return self.current_session_name
