import os
import json
import logging
from typing import List, Optional, Dict
from datetime import datetime
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage, messages_from_dict, messages_to_dict

logger = logging.getLogger(__name__)

class SessionManager:
    ACTIVE_AUTOSAVE_NAME = "autosave_actual"

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.sessions_dir = os.path.join(workspace_dir, ".kogniterm", "sessions")
        self.history_file_path = os.path.join(workspace_dir, ".kogniterm", "history.json")
        self.current_session_name: Optional[str] = None
        
        # Asegurar que el directorio de sesiones existe
        if not os.path.exists(self.sessions_dir):
            os.makedirs(self.sessions_dir)

    def list_sessions(self) -> List[Dict[str, str]]:
        """Lista todas las sesiones disponibles con sus metadatos básicos."""
        sessions = []
        if os.path.exists(self.sessions_dir):
            for filename in os.listdir(self.sessions_dir):
                if filename.endswith(".json"):
                    name = filename[:-5] # Quitar extensión .json
                    file_path = os.path.join(self.sessions_dir, filename)
                    try:
                        sessions.append(self._build_session_entry(name=name, file_path=file_path, source="session"))
                    except Exception as e:
                        logger.warning(f"Error al leer sesión {filename}: {e}")

        # Buscar autoguardados versionados en el directorio de autosave
        autosave_dir = os.path.join(self.workspace_dir, "autosave") if "autosave" not in self.workspace_dir else self.workspace_dir
        # Nota: El AutosaveManager usa self.workspace_dir / "autosave"
        # Para ser consistentes con la estructura de .kogniterm:
        kogniterm_autosave_dir = os.path.join(self.workspace_dir, ".kogniterm", "autosave")
        
        if os.path.exists(kogniterm_autosave_dir):
            for root, dirs, files in os.walk(kogniterm_autosave_dir):
                for filename in files:
                    if filename.endswith(".json") and filename.startswith("autosave_"):
                        file_path = os.path.join(root, filename)
                        name = filename[:-5]
                        try:
                            sessions.append(self._build_session_entry(
                                name=name, 
                                file_path=file_path, 
                                source="autosave", 
                                display_name=f"Autoguardado: {name}"
                            ))
                        except Exception as e:
                            logger.warning(f"Error al leer autoguardado versionado {filename}: {e}")

        if os.path.exists(self.history_file_path):
            try:
                autosave_entry = self._build_session_entry(
                    name=self.ACTIVE_AUTOSAVE_NAME,
                    file_path=self.history_file_path,
                    source="history",
                    display_name="Autoguardado actual"
                )
                if autosave_entry["messages"] > 0:
                    sessions.append(autosave_entry)
            except Exception as e:
                logger.warning(f"Error al leer autoguardado activo: {e}")
        
        # Ordenar por fecha de modificación descendente
        sessions.sort(key=lambda x: x["modified_ts"], reverse=True)
        return sessions

    def _build_session_entry(self, name: str, file_path: str, source: str, display_name: Optional[str] = None) -> Dict[str, str]:
        stats = os.stat(file_path)
        modified_dt = datetime.fromtimestamp(stats.st_mtime)
        return {
            "name": name,
            "display_name": display_name or name,
            "modified": modified_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "modified_ts": stats.st_mtime,
            "messages": self._count_messages(file_path),
            "path": file_path,
            "source": source,
        }

    def _extract_message_list(self, data) -> Optional[List[dict]]:
        """Extrae la lista de mensajes de un archivo, manejando formato con metadatos o lista directa."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("messages")
        return None

    def _count_messages(self, file_path: str) -> int:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        message_list = self._extract_message_list(data)
        return len(message_list) if message_list is not None else 0

    def _deserialize_messages(self, message_list: List[dict]) -> List[BaseMessage]:
        if not message_list:
            return []

        first_item = message_list[0]
        if isinstance(first_item, dict) and "data" in first_item:
            return messages_from_dict(message_list)

        messages: List[BaseMessage] = []
        for item in message_list:
            item_type = item.get('type')
            if item_type == 'human':
                messages.append(HumanMessage(content=item.get('content', '')))
            elif item_type == 'ai':
                thought_sigs = item.get('thought_signatures')
                additional_kwargs = {}
                if thought_sigs:
                    additional_kwargs["thought_signatures"] = thought_sigs
                messages.append(AIMessage(
                    content=item.get('content', ''),
                    tool_calls=item.get('tool_calls', []),
                    additional_kwargs=additional_kwargs
                ))
            elif item_type == 'tool':
                messages.append(ToolMessage(content=item.get('content', ''), tool_call_id=item.get('tool_call_id', '')))
            elif item_type == 'system':
                messages.append(SystemMessage(content=item.get('content', '')))
        return messages

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

    def _find_autosave_file(self, name: str) -> Optional[str]:
        """Busca recursivamente un archivo de autoguardado por nombre."""
        kogniterm_autosave_dir = os.path.join(self.workspace_dir, ".kogniterm", "autosave")
        if not os.path.exists(kogniterm_autosave_dir):
            return None
        
        for root, dirs, files in os.walk(kogniterm_autosave_dir):
            for filename in files:
                if filename == f"{name}.json" or filename == name:
                    return os.path.join(root, filename)
        return None

    def load_session(self, name: str) -> Optional[List[BaseMessage]]:
        """Carga una sesión por nombre y devuelve el historial de mensajes."""
        if name == self.ACTIVE_AUTOSAVE_NAME:
            file_path = self.history_file_path
        elif name.startswith("autosave_"):
            file_path = self._find_autosave_file(name)
        else:
            file_path = os.path.join(self.sessions_dir, f"{name}.json")
        
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"Sesión '{name}' no encontrada.")
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            message_list = self._extract_message_list(data)
            if message_list is not None:
                messages = self._deserialize_messages(message_list)
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
        if name == self.ACTIVE_AUTOSAVE_NAME:
            logger.warning("No se puede eliminar el autoguardado activo desde el gestor de sesiones.")
            return False

        if name.startswith("autosave_"):
            file_path = self._find_autosave_file(name)
        else:
            file_path = os.path.join(self.sessions_dir, f"{name}.json")
        
        if not file_path or not os.path.exists(file_path):
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

    def generate_autosave_name(self, history: List[BaseMessage]) -> str:
        """Genera un nombre descriptivo para una sesión guardada automáticamente."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Intentar obtener el contenido del primer mensaje humano
        first_human_msg = ""
        for msg in history:
            if isinstance(msg, HumanMessage):
                content = str(msg.content).strip()
                # Limpiar texto (quitar etiquetas @archivo, etc)
                content = content.split('\n')[0] # Solo primera línea
                content = "".join(c for c in content if c.isalnum() or c.isspace())[:30].strip()
                first_human_msg = content.replace(" ", "_")
                break
        
        if first_human_msg:
            return f"autosave_{timestamp}_{first_human_msg}"
        return f"autosave_{timestamp}"
