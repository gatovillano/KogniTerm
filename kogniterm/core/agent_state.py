import os
import json
import hashlib
import threading
from dataclasses import dataclass, field
from collections import deque  # Importar deque
from typing import List, Optional, Dict, Any, Union
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
# No necesitamos importar LLMService aquí para los métodos estáticos de historial
# from kogniterm.core.llm_service import LLMService

# Importar MessageManager
from kogniterm.core.message_manager import MessageManager, create_message_manager


@dataclass
class AgentState:
    """Define la estructura del estado que fluye a través del grafo."""

    messages: List[BaseMessage] = field(default_factory=list)
    command_to_confirm: Optional[str] = (
        None  # Nuevo campo para comandos que requieren confirmación
    )
    tool_call_id_to_confirm: Optional[str] = (
        None  # Nuevo campo para el tool_call_id asociado al comando
    )
    current_agent_mode: str = "bash"  # Añadido para el modo del agente
    autonomous_approvals: bool = False  # Permite que ciertos agentes aprueben cambios/comandos tras consentimiento previo
    history_for_api: Optional[List[BaseMessage]] = field(
        default=None, repr=False, compare=False
    )  # Campo temporal para compatibilidad

    # MessageManager para manejo centralizado de mensajes
    message_manager: Optional[Any] = field(default=None, repr=False)

    # NUEVO: Referencia al HistoryManager para MessageManager
    history_manager_ref: Optional[Any] = field(default=None, repr=False)

    # Nuevos campos para manejar la confirmación de herramientas
    tool_pending_confirmation: Optional[str] = None
    tool_args_pending_confirmation: Optional[Dict[str, Any]] = None
    tool_code_to_confirm: Optional[str] = (
        None  # Nuevo campo para el código (diff) a confirmar
    )
    tool_code_tool_name: Optional[str] = (
        None  # Nuevo campo para el nombre de la herramienta que generó el código
    )
    tool_code_tool_args: Optional[Dict[str, Any]] = (
        None  # Nuevo campo para los args originales de la herramienta
    )
    file_update_diff_pending_confirmation: Optional[Union[str, Dict[str, Any]]] = (
        None  # Nuevo campo para el diff de file_update_tool
    )
    search_memory: List[Dict[str, Any]] = field(
        default_factory=list
    )  # ¡Nuevo campo para la memoria de búsqueda!
    tool_call_history: deque = field(
        default_factory=lambda: deque(maxlen=5)
    )  # Historial de llamadas a herramientas para detección de bucles
    # Lock para acceso thread-safe al historial de herramientas
    tool_call_history_lock: Any = field(default=None, repr=False, compare=False)
    critical_loop_detected: bool = False  # Bandera para indicar que se detectó un bucle crítico y se debe terminar el flujo
    stop_requested: bool = False
    delegation_context: Optional[Any] = None
    completed: bool = False
    result: Optional[str] = None

    # Añadir un campo para la ruta del archivo de historial
    history_file_path: str = field(
        default_factory=lambda: os.path.join(os.getcwd(), ".kogniterm", "history.json")
    )

    # NUEVO: Caché de hashes de archivos para detección de race conditions
    # Estructura: {file_path: {"hash": str, "timestamp": float, "content": str}}
    file_hash_cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __setattr__(self, name, value):
        if name == "messages":
            history_manager = self.__dict__.get("history_manager_ref")
            if history_manager is not None:
                history_manager.conversation_history = value or []
                value = history_manager.conversation_history
        super().__setattr__(name, value)

    def attach_history_manager(self, history_manager: Any):
        """Vincula el estado al HistoryManager para persistir cada mutación de mensajes."""
        self.history_manager_ref = history_manager
        self.messages = self.messages

    def reset_tool_confirmation(self):
        """Reinicia el estado de la confirmación de herramientas."""
        self.tool_pending_confirmation = None
        self.tool_args_pending_confirmation = None
        self.tool_code_to_confirm = None
        self.tool_code_tool_name = None
        self.tool_code_tool_args = None
        self.file_update_diff_pending_confirmation = None

    def reset(self):
        self.messages = []
        self.command_to_confirm = None
        self.tool_call_id_to_confirm = None
        self.reset_tool_confirmation()
        self.file_update_diff_pending_confirmation = None
        self.critical_loop_detected = False
        self.completed = False
        self.result = None

    def reset_temporary_state(self):
        """Reinicia los campos de estado temporal del agente, manteniendo el historial de mensajes."""
        self.command_to_confirm = None
        self.reset_tool_confirmation()

    def clear_tool_call_history(self):
        """Limpia el historial de llamadas a herramientas para detección de bucles."""
        self.tool_call_history.clear()

    def initialize_message_manager(self, llm_service: Any = None):
        """
        Inicializa el MessageManager para manejo centralizado de mensajes.

        Inspirado en el MessageManager de KiloCode (github.com/Kilo-Org/kilocode)

        Args:
            llm_service: Referencia al LLMService (opcional)
        """
        if self.message_manager is not None:
            return  # Ya inicializado

        # Obtener el history_manager del llm_service si está disponible
        history_manager = None
        if llm_service and hasattr(llm_service, "history_manager"):
            history_manager = llm_service.history_manager
        elif self.history_manager_ref:
            history_manager = self.history_manager_ref

        # Crear el MessageManager
        self.message_manager = create_message_manager(self, history_manager)

        # Sincronizar desde el estado existente
        self.message_manager.sync_from_agent_state()

        import logging

        logging.getLogger(__name__).info("[AgentState] MessageManager inicializado")

    def add_message(self, message: BaseMessage):
        """Añade un mensaje delegando al MessageManager si está disponible, o a la lista local."""
        if self.message_manager:
            self.message_manager.add_message(message)
            self.message_manager.sync_to_agent_state()
        else:
            self.messages.append(message)

    def add_messages(self, temp_messages: List[BaseMessage]):
        """Añade múltiples mensajes delegando al MessageManager."""
        if self.message_manager:
            for msg in temp_messages:
                self.message_manager.add_message(msg)
            self.message_manager.sync_to_agent_state()
        else:
            self.messages.extend(temp_messages)

    def __post_init__(self):

        # Si se pasó history_for_api pero no messages, sincronizar
        if self.history_for_api is not None and not self.messages:
            self.messages = self.history_for_api

        # Inicializar lock para acceso thread-safe al historial de herramientas
        if self.tool_call_history_lock is None:
            self.tool_call_history_lock = threading.Lock()

    def load_history(
        self, system_message: SystemMessage, llm_service: Any
    ):  # Añadir llm_service como parámetro
        """Carga el historial de conversación desde el archivo especificado y asegura el SYSTEM_MESSAGE."""
        loaded_messages = (
            llm_service.history_manager._load_history()
        )  # Usar la instancia de history_manager

        # Asegurarse de que el SYSTEM_MESSAGE esté al principio
        if not loaded_messages or not (
            isinstance(loaded_messages[0], SystemMessage)
            and loaded_messages[0].content == system_message.content
        ):
            self.messages.append(system_message)

        # Añadir los mensajes cargados después del SYSTEM_MESSAGE
        for msg in loaded_messages:
            if not (
                isinstance(msg, SystemMessage) and msg.content == system_message.content
            ):
                self.messages.append(msg)

        # Eliminar duplicados del SYSTEM_MESSAGE si se cargó desde el archivo y también se añadió manualmente
        system_message_count = sum(
            1
            for msg in self.messages
            if isinstance(msg, SystemMessage) and msg.content == system_message.content
        )
        if system_message_count > 1:
            first_system_message_index = -1
            indices_to_remove = []
            for i, msg in enumerate(self.messages):
                if (
                    isinstance(msg, SystemMessage)
                    and msg.content == system_message.content
                ):
                    if first_system_message_index == -1:
                        first_system_message_index = i
                    else:
                        indices_to_remove.append(i)

            # Eliminar los SYSTEM_MESSAGE duplicados, empezando por el final para no afectar los índices
            for i in sorted(indices_to_remove, reverse=True):
                self.messages.pop(i)

        # Eliminar ToolMessages duplicados, manteniendo solo el último para cada tool_call_id
        tool_messages_seen = {}
        indices_to_remove = []
        for i, msg in enumerate(self.messages):
            if isinstance(msg, ToolMessage) and msg.tool_call_id:
                if msg.tool_call_id in tool_messages_seen:
                    indices_to_remove.append(tool_messages_seen[msg.tool_call_id])
                tool_messages_seen[msg.tool_call_id] = i

        # Eliminar los ToolMessages duplicados anteriores, empezando por el final
        for i in sorted(indices_to_remove, reverse=True):
            self.messages.pop(i)

    def save_history(self, llm_service: Any):  # Añadir llm_service como parámetro
        """Guarda el historial de conversación actual en el archivo especificado."""
        llm_service.history_manager._save_history(
            self.messages
        )  # Usar la instancia de history_manager
