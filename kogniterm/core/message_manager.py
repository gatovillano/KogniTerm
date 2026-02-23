"""
MessageManager: Sistema centralizado de mensajes con rewind consistente

Inspirado en el MessageManager de KiloCode (github.com/Kilo-Org/kilocode)

Este módulo proporciona:
- Sistema de mensajes dual: API history vs UI messages
- Rewind centralizado con consistencia
- Tracking de costos de API borrados
- Manejo de mensajes condensados (summaries)
"""

import json
import time
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import logging

logger = logging.getLogger(__name__)


@dataclass
class ContextEvent:
    """Representa un evento de contexto (condensación o truncamiento)."""
    event_id: str  # ID único para vincular con mensajes API
    event_type: str  # "condense_context" o "sliding_window_truncation"
    timestamp: float
    summary: Optional[str] = None
    tokens_removed: int = 0


@dataclass  
class ApiMessage:
    """Representa un mensaje en la historia de API con metadatos."""
    role: str
    content: str
    ts: Optional[float] = None
    is_summary: bool = False
    condense_id: Optional[str] = None
    is_truncation_marker: bool = False
    truncation_id: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None


class MessageManager:
    """
    MessageManager proporciona manejo centralizado para todas las operaciones de rewind.
    
    Esto asegura que cuando el historial de chat se rebobina (delete, edit, checkpoint restore, etc.),
    la historia de la conversación API se mantenga correctamente, incluyendo:
    - Eliminar mensajes Summary huérfanos cuando su condense_context se elimina
    - Eliminar marcadores de truncamiento huérfanos
    - Limpiar etiquetas huérfanas
    
    Uso (siempre acceder vía el getter message_manager del agente):
    ```python
    await agent.message_manager.rewind_to_timestamp(message_ts)
    ```
    """
    
    def __init__(self, agent_state: Any, history_manager: Any = None):
        """
        Inicializa el MessageManager.
        
        Args:
            agent_state: Referencia al AgentState del agente
            history_manager: Referencia al HistoryManager para persistencia
        """
        self.agent_state = agent_state
        self.history_manager = history_manager
        
        # Historia de API (para el LLM)
        self._api_history: List[ApiMessage] = []
        
        # Mensajes UI (para mostrar al usuario)
        self._ui_messages: List[BaseMessage] = []
        
        # Costos de API borrados (para tracking de costos)
        self._deleted_api_cost: float = 0.0
        
        # Eventos de contexto (condensaciones/truncamientos)
        self._context_events: List[ContextEvent] = []
        
        # Caché para el último mensaje
        self._last_message_ts: Optional[float] = None
        
        logger.info("[MessageManager] Inicializado")
    
    # ==================== Propiedades ====================
    
    @property
    def api_history(self) -> List[ApiMessage]:
        """Retorna la historia de API."""
        return self._api_history
    
    @property
    def ui_messages(self) -> List[BaseMessage]:
        """Retorna los mensajes UI."""
        return self._ui_messages
    
    @property
    def deleted_api_cost(self) -> float:
        """Retorna el costo total de API de mensajes borrados."""
        return self._deleted_api_cost
    
    # ==================== Sincronización ====================
    
    def sync_from_agent_state(self):
        """
        Sincroniza el MessageManager desde el AgentState actual.
        
        Debe llamarse al inicializar o restaurar una sesión.
        """
        if hasattr(self.agent_state, 'messages') and self.agent_state.messages:
            # Convertir mensajes del agente a formato interno
            self._ui_messages = list(self.agent_state.messages)
            self._api_history = self._convert_to_api_messages(self.agent_state.messages)
            
            # Actualizar timestamps
            if self._ui_messages:
                self._last_message_ts = self._ui_messages[-1].additional_kwargs.get('timestamp', time.time())
            
            logger.info(f"[MessageManager] Sincronizado desde AgentState: {len(self._ui_messages)} mensajes")
    
    def sync_to_agent_state(self):
        """
        Sincroniza el AgentState desde el MessageManager.
        
        Debe llamarse después de operaciones de rewind.
        """
        self.agent_state.messages = list(self._ui_messages)
        
        if self.history_manager:
            self.history_manager._save_history(self._ui_messages)
        
        logger.info(f"[MessageManager] Sincronizado a AgentState: {len(self._ui_messages)} mensajes")
    
    def _convert_to_api_messages(self, messages: List[BaseMessage]) -> List[ApiMessage]:
        """Convierte mensajes LangChain a formato interno ApiMessage."""
        api_msgs = []
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            elif isinstance(msg, ToolMessage):
                role = "tool"
            elif isinstance(msg, SystemMessage):
                role = "system"
            else:
                role = "unknown"
            
            # Extraer metadatos
            tool_calls = None
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                tool_calls = msg.tool_calls
            
            ts = msg.additional_kwargs.get('timestamp') if msg.additional_kwargs else None
            
            api_msgs.append(ApiMessage(
                role=role,
                content=str(msg.content),
                ts=ts,
                tool_calls=tool_calls
            ))
        
        return api_msgs
    
    # ==================== Rewind Operations ====================
    
    def rewind_to_timestamp(self, ts: float, include_target: bool = False) -> bool:
        """
        Rebobina la conversación a un timestamp específico.
        
        Este es el PUNTO DE ENTRADA ÚNICO para todas las operaciones de eliminación.
        
        Args:
            ts: El timestamp al que rebobinar
            include_target: Si True, incluye el mensaje objetivo en la eliminación
            
        Returns:
            True si el rewind fue exitoso
            
        Raises:
            ValueError: Si el timestamp no se encuentra
        """
        # Encontrar el índice en ui_messages
        ui_index = self._find_ui_message_index(ts)
        
        if ui_index == -1:
            raise ValueError(f"Mensaje con timestamp {ts} no encontrado en ui_messages")
        
        # Calcular el índice de corte
        cutoff_index = ui_index + 1 if include_target else ui_index
        
        return self._perform_rewind(cutoff_index, ts)
    
    def rewind_to_index(self, index: int, include_target: bool = False) -> bool:
        """
        Rebobina la conversación a un índice específico.
        
        Mantiene mensajes [0, index) y elimina [index, fin).
        
        Args:
            index: El índice al que rebobinar (exclusivo)
            include_target: Si True, incluye el mensaje índice en la eliminación
            
        Returns:
            True si el rewind fue exitoso
        """
        cutoff_index = index + 1 if include_target else index
        cutoff_ts = self._ui_messages[index].additional_kwargs.get('timestamp', time.time()) if index < len(self._ui_messages) else time.time()
        
        return self._perform_rewind(cutoff_index, cutoff_ts)
    
    def _perform_rewind(self, cutoff_index: int, cutoff_ts: float) -> bool:
        """
        Método interno que realiza el rewind real.
        
        1. Recolectar IDs de eventos de contexto a eliminar
        2. Truncar ui_messages
        3. Truncar api_history con cleanup
        """
        logger.info(f"[MessageManager] Realizando rewind al índice {cutoff_index}")
        
        # Paso 1: Recolectar IDs de eventos de contexto a eliminar
        removed_event_ids = self._collect_removed_context_event_ids(cutoff_index)
        
        # Paso 2: Truncar ui_messages
        self._truncate_ui_messages(cutoff_index)
        
        # Paso 3: Truncar api_history con cleanup
        self._truncate_api_history(cutoff_ts, removed_event_ids)
        
        # Sincronizar con AgentState
        self.sync_to_agent_state()
        
        logger.info(f"[MessageManager] Rewind completado: {len(self._ui_messages)} mensajes restantes")
        return True
    
    def _find_ui_message_index(self, ts: float) -> int:
        """Encuentra el índice del mensaje UI con el timestamp dado."""
        for i, msg in enumerate(self._ui_messages):
            msg_ts = msg.additional_kwargs.get('timestamp') if msg.additional_kwargs else None
            if msg_ts == ts:
                return i
        return -1
    
    def _collect_removed_context_event_ids(self, from_index: int) -> Dict[str, set]:
        """
        Recolecta condenseIds y truncationIds de eventos de contexto
        que serán eliminados durante el rewind.
        
        Esto es crítico para mantener el linkage entre:
        - condense_context (ui message) ↔ Summary (api message)
        - sliding_window_truncation (ui message) ↔ Truncation marker (api message)
        """
        condense_ids = set()
        truncation_ids = set()
        
        for i in range(from_index, len(self._ui_messages)):
            msg = self._ui_messages[i]
            
            # Recolectar condenseIds de eventos condense_context
            if hasattr(msg, 'additional_kwargs'):
                context_condense = msg.additional_kwargs.get('context_condense')
                if context_condense and isinstance(context_condense, dict):
                    condense_id = context_condense.get('condense_id')
                    if condense_id:
                        condense_ids.add(condense_id)
                        logger.info(f"[MessageManager] Encontrado condense_context a eliminar: {condense_id}")
            
            # Recolectar truncationIds de eventos sliding_window_truncation
            if hasattr(msg, 'additional_kwargs'):
                context_truncation = msg.additional_kwargs.get('context_truncation')
                if context_truncation and isinstance(context_truncation, dict):
                    truncation_id = context_truncation.get('truncation_id')
                    if truncation_id:
                        truncation_ids.add(truncation_id)
                        logger.info(f"[MessageManager] Encontrado sliding_window_truncation a eliminar: {truncation_id}")
        
        return {'condense_ids': condense_ids, 'truncation_ids': truncation_ids}
    
    def _truncate_ui_messages(self, to_index: int):
        """Trunca ui_messages al índice especificado."""
        removed = self._ui_messages[to_index:]
        self._ui_messages = self._ui_messages[:to_index]
        
        # Recolectar costos de mensajes borrados (si hay un history_manager)
        if self.history_manager:
            for msg in removed:
                if hasattr(msg, 'additional_kwargs'):
                    cost = msg.additional_kwargs.get('api_cost', 0)
                    if cost:
                        self._deleted_api_cost += cost
    
    def _truncate_api_history(self, cutoff_ts: float, removed_event_ids: Dict[str, set]):
        """
        Trunca api_history por timestamp, elimina summaries/marcadores huérfanos,
        y limpia etiquetas huérfanas - todo en una sola operación de escritura.
        """
        original_history = list(self._api_history)
        
        # Paso 1: Determinar el cutoff de timestamp real
        # Debida a la ejecución async durante streaming, los timestamps de ui_message
        # pueden no alinearse perfectamente con los timestamps de api_message
        has_exact_match = any(m.ts == cutoff_ts for m in self._api_history if m.ts)
        has_message_before_cutoff = any(m.ts and m.ts < cutoff_ts for m in self._api_history if m.ts)
        
        actual_cutoff = cutoff_ts
        
        if not has_exact_match and has_message_before_cutoff:
            # Buscar el primer mensaje de usuario en o después del cutoff
            for i, msg in enumerate(self._api_history):
                if msg.ts and msg.ts >= cutoff_ts and msg.role == "user":
                    actual_cutoff = msg.ts
                    break
        
        # Paso 2: Filtrar por cutoff de timestamp
        self._api_history = [m for m in self._api_history if not m.ts or m.ts < actual_cutoff]
        
        # Paso 3: Eliminar Summaries cuyos condense_context fue eliminado
        if removed_event_ids['condense_ids']:
            self._api_history = [
                m for m in self._api_history
                if not (m.is_summary and m.condense_id and m.condense_id in removed_event_ids['condense_ids'])
            ]
        
        # Paso 4: Eliminar marcadores de truncamiento cuyos sliding_window_truncation fue eliminado
        if removed_event_ids['truncation_ids']:
            self._api_history = [
                m for m in self._api_history
                if not (m.is_truncation_marker and m.truncation_id and m.truncation_id in removed_event_ids['truncation_ids'])
            ]
        
        # Solo escribir si la historia realmente cambió
        history_changed = (
            len(self._api_history) != len(original_history) or
            any(m1 != m2 for m1, m2 in zip(self._api_history, original_history))
        )
        
        if not history_changed:
            logger.info("[MessageManager] La historia no cambió, no se requiere escritura")
    
    # ==================== Agregar Mensajes ====================
    
    def add_message(self, message: BaseMessage, add_to_api: bool = True):
        """
        Agrega un mensaje a la conversación.
        
        Args:
            message: El mensaje a agregar
            add_to_api: Si True, también agrega a la historia de API
        """
        # Agregar timestamp si no existe
        if not message.additional_kwargs:
            message.additional_kwargs = {}
        
        if 'timestamp' not in message.additional_kwargs:
            message.additional_kwargs['timestamp'] = time.time()
        
        # Agregar a UI
        self._ui_messages.append(message)
        
        # Agregar a API si es necesario
        if add_to_api:
            api_msg = ApiMessage(
                role=self._get_role_from_message(message),
                content=str(message.content),
                ts=message.additional_kwargs.get('timestamp'),
                tool_calls=getattr(message, 'tool_calls', None)
            )
            self._api_history.append(api_msg)
        
        self._last_message_ts = message.additional_kwargs.get('timestamp')
        
        logger.debug(f"[MessageManager] Mensaje agregado: {type(message).__name__}")
    
    def add_api_message(self, role: str, content: str, **kwargs):
        """Agrega un mensaje directamente a la historia de API."""
        api_msg = ApiMessage(
            role=role,
            content=content,
            ts=kwargs.get('ts', time.time()),
            is_summary=kwargs.get('is_summary', False),
            condense_id=kwargs.get('condense_id'),
            is_truncation_marker=kwargs.get('is_truncation_marker', False),
            truncation_id=kwargs.get('truncation_id'),
            tool_calls=kwargs.get('tool_calls')
        )
        self._api_history.append(api_msg)
    
    def _get_role_from_message(self, message: BaseMessage) -> str:
        """Obtiene el rol de un mensaje LangChain."""
        if isinstance(message, HumanMessage):
            return "user"
        elif isinstance(message, AIMessage):
            return "assistant"
        elif isinstance(message, ToolMessage):
            return "tool"
        elif isinstance(message, SystemMessage):
            return "system"
        return "unknown"
    
    # ==================== Contexto Management ====================
    
    def add_context_event(self, event: ContextEvent):
        """Agrega un evento de contexto (condensación o truncamiento)."""
        self._context_events.append(event)
        logger.info(f"[MessageManager] Evento de contexto agregado: {event.event_type}")
    
    def get_effective_api_history(self) -> List[ApiMessage]:
        """
        Obtiene la historia de API efectiva filtrando mensajes condensados.
        
        Esto permite condensación no destructiva donde los mensajes se marcan
        pero no se eliminan, permitiendo operaciones de rewind precisas mientras
        se envía historial condensado a la API.
        """
        return [
            m for m in self._api_history
            if not m.is_summary
        ]
    
    # ==================== Utility Methods ====================
    
    def get_message_count(self) -> int:
        """Retorna el número de mensajes UI."""
        return len(self._ui_messages)
    
    def get_api_message_count(self) -> int:
        """Retorna el número de mensajes API."""
        return len(self._api_history)
    
    def clear(self):
        """Limpia todos los mensajes."""
        self._api_history.clear()
        self._ui_messages.clear()
        self._context_events.clear()
        self._deleted_api_cost = 0.0
        logger.info("[MessageManager] Todos los mensajes limpiados")
    
    def get_messages_summary(self) -> Dict[str, Any]:
        """Retorna un resumen del estado actual."""
        return {
            "ui_messages": len(self._ui_messages),
            "api_messages": len(self._api_history),
            "context_events": len(self._context_events),
            "deleted_api_cost": self._deleted_api_cost,
            "last_message_ts": self._last_message_ts
        }


def create_message_manager(agent_state: Any, history_manager: Any = None) -> MessageManager:
    """
    Factory function para crear un MessageManager.
    
    Args:
        agent_state: Referencia al AgentState del agente
        history_manager: Referencia al HistoryManager (opcional)
        
    Returns:
        MessageManager instanciado
    """
    manager = MessageManager(agent_state, history_manager)
    
    # Sincronizar desde el estado existente
    manager.sync_from_agent_state()
    
    return manager
