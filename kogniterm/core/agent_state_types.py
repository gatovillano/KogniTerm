import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage

logger = logging.getLogger(__name__)

@dataclass
class AgentState:
    """Define la estructura del estado que fluye a través del grafo."""
    messages: List[BaseMessage] = field(default_factory=list)
    command_to_confirm: Optional[str] = None # Nuevo campo para comandos que requieren confirmación
    tool_call_id_to_confirm: Optional[str] = None # Nuevo campo para el tool_call_id asociado al comando
    current_agent_mode: str = "bash" # Añadido para el modo del agente
    
    # Nuevos campos para manejar la confirmación de herramientas
    tool_pending_confirmation: Optional[str] = None
    tool_args_pending_confirmation: Optional[Dict[str, Any]] = None
    file_update_diff_pending_confirmation: Optional[str] = None # Nuevo campo para el diff de file_update_tool
    command_output_ready_for_processing: bool = False # Nuevo campo para indicar si la salida del comando está lista para procesar
    command_explanation: Optional[str] = None # Nuevo campo para almacenar la explicación del comando

    def reset_tool_confirmation(self):
        """Reinicia el estado de la confirmación de herramientas."""
        self.tool_pending_confirmation = None
        self.tool_args_pending_confirmation = None
        self.file_update_diff_pending_confirmation = None # Limpiar el diff también

    def reset(self):
        """Reinicia completamente el estado del agente."""
        self.messages = []
        self.command_to_confirm = None
        self.tool_call_id_to_confirm = None
        self.reset_tool_confirmation()
        self.file_update_diff_pending_confirmation = None # Limpiar el diff también
        self.command_output_ready_for_processing = False # Resetear la nueva bandera
        self.command_explanation = None # Resetear la explicación del comando
        self.save_history() # Guardar el historial vacío al reiniciar

    def reset_temporary_state(self):
        """Reinicia los campos de estado temporal del agente, manteniendo el historial de mensajes."""
        self.command_to_confirm = None
        self.reset_tool_confirmation()
        self.command_output_ready_for_processing = False # Resetear la nueva bandera
        self.command_explanation = None # Resetear la explicación del comando

    @property
    def history_for_api(self) -> list[BaseMessage]:
        """Devuelve el historial de mensajes de LangChain directamente."""
        return self.messages

    def _to_dict(self, message: BaseMessage) -> Dict[str, Any]:
        """Convierte un mensaje de LangChain a un diccionario serializable."""
        if isinstance(message, HumanMessage):
            return {"type": "human", "content": message.content}
        elif isinstance(message, AIMessage):
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append({
                        "id": tc.get("id"),
                        "name": tc.get("name"),
                        "args": tc.get("args")
                    })
            return {"type": "ai", "content": message.content, "tool_calls": tool_calls}
        elif isinstance(message, ToolMessage):
            return {"type": "tool", "content": message.content, "tool_call_id": message.tool_call_id}
        elif isinstance(message, SystemMessage):
            return {"type": "system", "content": message.content}
        else:
            logger.warning(f"Tipo de mensaje desconocido para serializar: {type(message)}")
            return {"type": "unknown", "content": str(message)}

    def _from_dict(self, message_dict: Dict[str, Any]) -> BaseMessage:
        """Convierte un diccionario serializado de vuelta a un mensaje de LangChain."""
        msg_type = message_dict.get("type")
        content = message_dict.get("content", "")
        if msg_type == "human":
            return HumanMessage(content=content)
        elif msg_type == "ai":
            tool_calls = message_dict.get("tool_calls")
            if tool_calls:
                return AIMessage(content=content, tool_calls=tool_calls)
            return AIMessage(content=content)
        elif msg_type == "tool":
            return ToolMessage(content=content, tool_call_id=message_dict.get("tool_call_id"))
        elif msg_type == "system":
            return SystemMessage(content=content)
        else:
            logger.warning(f"Tipo de mensaje desconocido para deserializar: {msg_type}")
            return HumanMessage(content=f"Mensaje desconocido: {content}")

    def load_history(self, system_message: SystemMessage):
        """Carga el historial de la sesión anterior desde un archivo, asegurando que el SYSTEM_MESSAGE esté al principio."""
        history_file_path = os.path.join(os.getcwd(), ".kogniterm", "history.json")
        self.messages = [system_message] # Asegurar que el SYSTEM_MESSAGE esté siempre al principio
        
        if os.path.exists(history_file_path):
            try:
                with open(history_file_path, 'r', encoding='utf-8') as f:
                    serialized_messages = json.load(f)
                
                loaded_messages = [self._from_dict(msg_dict) for msg_dict in serialized_messages]
                
                # Filtrar el SYSTEM_MESSAGE si ya existe en el historial cargado para evitar duplicación
                filtered_loaded_messages = [
                    msg for msg in loaded_messages
                    if not (isinstance(msg, SystemMessage) and msg.content == system_message.content)
                ]
                self.messages.extend(filtered_loaded_messages)
                logger.debug(f"Historial cargado desde {history_file_path}. {len(filtered_loaded_messages)} mensajes adicionales.")
            except (json.JSONDecodeError, FileNotFoundError, Exception) as e:
                logger.error(f"Error al cargar el historial desde {history_file_path}: {e}")
        else:
            logger.debug(f"No se encontró archivo de historial en {history_file_path}. Iniciando historial vacío.")
        
        # Eliminar SystemMessages duplicados si los hay (solo mantener el primero)
        unique_messages = []
        system_message_added = False
        for msg in self.messages:
            if isinstance(msg, SystemMessage) and msg.content == system_message.content:
                if not system_message_added:
                    unique_messages.append(msg)
                    system_message_added = True
            else:
                unique_messages.append(msg)
        self.messages = unique_messages


    def save_history(self):
        """Guarda el historial actual del agente en un archivo."""
        history_file_path = os.path.join(os.getcwd(), ".kogniterm", "history.json")
        os.makedirs(os.path.dirname(history_file_path), exist_ok=True)
        
        # Filtrar el SYSTEM_MESSAGE antes de guardar para evitar duplicación
        # Se asume que el SYSTEM_MESSAGE se insertará al cargar el historial
        messages_to_save = [self._to_dict(msg) for msg in self.messages if not isinstance(msg, SystemMessage)]
        
        try:
            with open(history_file_path, 'w', encoding='utf-8') as f:
                json.dump(messages_to_save, f, ensure_ascii=False, indent=2)
            logger.debug(f"Historial guardado en {history_file_path}.")
        except IOError as e:
            logger.error(f"Error al guardar el historial en {history_file_path}: {e}")
