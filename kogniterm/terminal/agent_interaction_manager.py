import logging
import sys
import time
import threading
from kogniterm.core.config import settings
from rich.console import Console
from rich.spinner import Spinner
from rich.live import Live
from rich.text import Text

logger = logging.getLogger(__name__)

from kogniterm.core.llm_service import LLMService
from kogniterm.core.agents.bash_agent import create_bash_agent, AgentState, SYSTEM_MESSAGE
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import Dict, Any, Optional
import queue # Importar queue
from kogniterm.terminal.terminal_ui import TerminalUI # Importar TerminalUI
from kogniterm.terminal.keyboard_handler import KeyboardHandler # Importar KeyboardHandler

"""
This module contains the AgentInteractionManager class, responsible for
orchestrating AI agent interactions in the KogniTerm application.
"""

class AgentInteractionManager:
    def __init__(self, llm_service: LLMService, agent_state: AgentState, terminal_ui: TerminalUI, interrupt_queue: queue.Queue):
        self.llm_service = llm_service
        self.agent_state = agent_state
        self.terminal_ui = terminal_ui # Guardar la instancia de TerminalUI
        self.interrupt_queue = interrupt_queue # Guardar la cola de interrupción
        self.bash_agent_app = create_bash_agent(llm_service, terminal_ui, interrupt_queue) # Pasar terminal_ui e interrupt_queue
        
        # Asegurarse de que el SYSTEM_MESSAGE esté siempre al principio del historial.
        if not self.agent_state.messages or not (isinstance(self.agent_state.messages[0], SystemMessage) and self.agent_state.messages[0].content == SYSTEM_MESSAGE.content):
            if self.agent_state.messages and not (isinstance(self.agent_state.messages[0], SystemMessage) and self.agent_state.messages[0].content == SYSTEM_MESSAGE.content):
                self.agent_state.messages.insert(0, SYSTEM_MESSAGE)
            elif not self.agent_state.messages:
                self.agent_state.messages.append(SYSTEM_MESSAGE)
        
        # Filtrar cualquier SYSTEM_MESSAGE duplicado del historial si ya lo hemos añadido
        system_message_count = sum(1 for msg in self.agent_state.messages if isinstance(msg, SystemMessage) and msg.content == SYSTEM_MESSAGE.content)
        if system_message_count > 1:
            first_system_message_index = -1
            for i, msg in enumerate(self.agent_state.messages):
                if isinstance(msg, SystemMessage) and msg.content == SYSTEM_MESSAGE.content:
                    if first_system_message_index == -1:
                        first_system_message_index = i
                    else:
                        self.agent_state.messages.pop(i)
                        break

    def invoke_agent(self, user_input: Optional[str]) -> Dict[str, Any]:
        import os
        
        # El mensaje ya fue añadido al historial por KogniTermApp antes de llamar a este método.
        # No lo añadimos de nuevo para evitar duplicación.
        
        # Inyectar contexto dinámico del directorio de trabajo actual
        current_working_directory = os.getcwd()
        
        # Buscar si ya existe un SystemMessage de contexto dinámico previo y eliminarlo
        # para evitar acumulación de mensajes de contexto obsoletos
        messages_to_keep = []
        for msg in self.agent_state.messages:
            # Mantener todos los mensajes excepto los SystemMessages de contexto dinámico previos
            if isinstance(msg, SystemMessage) and "📂 **Directorio de Trabajo Actual:**" in msg.content:
                continue  # Saltar este mensaje (eliminarlo)
            messages_to_keep.append(msg)
        
        self.agent_state.messages = messages_to_keep
        
        # Crear el mensaje de contexto dinámico
        context_message = SystemMessage(content=f"""
📂 **Directorio de Trabajo Actual:** `{current_working_directory}`

Este es el directorio en el que estás trabajando actualmente. Todas las rutas relativas se resolverán desde aquí.
Cuando ejecutes comandos o manipules archivos, ten en cuenta esta ubicación.
""")
        
        # Insertar el contexto justo después del SYSTEM_MESSAGE principal (índice 1)
        # para que esté disponible para el agente pero no interfiera con el mensaje principal
        if len(self.agent_state.messages) > 1:
            self.agent_state.messages.insert(1, context_message)
        else:
            self.agent_state.messages.append(context_message)

        sys.stderr.flush()
        
        # Ya no iniciamos el KeyboardHandler aquí globalmente para evitar conflictos con comandos interactivos.
        # Se manejará granularmente dentro de los nodos del agente (call_model_node, etc.)
        
        try:
            # Ejecutar invoke sin timeout
            final_state_dict = self.bash_agent_app.invoke(self.agent_state, config={"recursion_limit": 200})
        finally:
            pass

        sys.stderr.flush()
        
        # Actualizar el estado del agente con los valores del final_state_dict
        self.agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')
        self.agent_state.tool_code_to_confirm = final_state_dict.get('tool_code_to_confirm')
        self.agent_state.tool_code_tool_name = final_state_dict.get('tool_code_tool_name')
        self.agent_state.tool_code_tool_args = final_state_dict.get('tool_code_tool_args')
        self.agent_state.file_update_diff_pending_confirmation = final_state_dict.get('file_update_diff_pending_confirmation')

        # Si hay una confirmación de archivo pendiente, la información ya está en final_state_dict
        # y será manejada por KogniTermApp.

        # Si no hay confirmación pendiente, actualizar los mensajes del agente
        if not self.agent_state.file_update_diff_pending_confirmation:
            self.agent_state.messages = final_state_dict['messages']
        
        # Capturar el tool_call_id del último AIMessage si existe
        last_ai_message = None
        for msg in reversed(self.agent_state.messages):
            if isinstance(msg, AIMessage):
                last_ai_message = msg
                break
        
        if last_ai_message and last_ai_message.tool_calls:
            # Asumiendo que solo hay una tool_call por AIMessage para simplificar
            self.agent_state.tool_call_id_to_confirm = last_ai_message.tool_calls[0]['id']
        else:
            self.agent_state.tool_call_id_to_confirm = None
        
        return final_state_dict



