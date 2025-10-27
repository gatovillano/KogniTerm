from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from langchain_core.messages import BaseMessage

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
    tool_code_to_confirm: Optional[str] = None # Nuevo campo para el código (diff) a confirmar
    tool_code_tool_name: Optional[str] = None # Nuevo campo para el nombre de la herramienta que generó el código
    tool_code_tool_args: Optional[Dict[str, Any]] = None # Nuevo campo para los args originales de la herramienta
    search_memory: List[Dict[str, Any]] = field(default_factory=list) # ¡Nuevo campo para la memoria de búsqueda!

    def reset_tool_confirmation(self):
        """Reinicia el estado de la confirmación de herramientas."""
        self.tool_pending_confirmation = None
        self.tool_args_pending_confirmation = None
        self.tool_code_to_confirm = None
        self.tool_code_tool_name = None
        self.tool_code_tool_args = None

    def reset(self):
        """Reinicia completamente el estado del agente."""
        self.messages = []
        self.command_to_confirm = None
        self.tool_call_id_to_confirm = None
        self.reset_tool_confirmation()

    def reset_temporary_state(self):
        """Reinicia los campos de estado temporal del agente, manteniendo el historial de mensajes."""
        self.command_to_confirm = None
        self.reset_tool_confirmation()

    @property
    def history_for_api(self) -> list[BaseMessage]:
        """Devuelve el historial de mensajes de LangChain directamente."""
        return self.messages