from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage

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

    def reset_temporary_state(self):
        """Reinicia los campos de estado temporal del agente, manteniendo el historial de mensajes."""
        self.command_to_confirm = None
        self.reset_tool_confirmation()

    @property
    def history_for_api(self) -> list[BaseMessage]:
        """Devuelve el historial de mensajes de LangChain directamente."""
        return self.messages
