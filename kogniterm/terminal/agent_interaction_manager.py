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
from kogniterm.core.agents.bash_agent import create_bash_agent, create_learning_agent, AgentState, get_system_message
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
    def __init__(self, llm_service: LLMService, agent_state: AgentState, terminal_ui: TerminalUI, interrupt_queue: queue.Queue, command_approval_handler=None):
        logger.info(f"AgentInteractionManager init: terminal_ui class={type(terminal_ui)}")
        self.llm_service = llm_service
        self.agent_state = agent_state
        self.terminal_ui = terminal_ui # Guardar la instancia de TerminalUI
        self.interrupt_queue = interrupt_queue # Guardar la cola de interrupción
        self.bash_agent_app = create_bash_agent(llm_service, terminal_ui, interrupt_queue, command_approval_handler) # Pasar command_approval_handler
        self.learning_agent_app = create_learning_agent(llm_service, terminal_ui)
        
        # Obtener el SYSTEM_MESSAGE dinámico para este llm_service
        current_system_message = get_system_message(self.llm_service)
        
        # Asegurarse de que el SYSTEM_MESSAGE esté siempre al principio del historial.
        if not self.agent_state.messages or not (isinstance(self.agent_state.messages[0], SystemMessage) and self.agent_state.messages[0].content == current_system_message.content):
            if self.agent_state.messages and not (isinstance(self.agent_state.messages[0], SystemMessage) and self.agent_state.messages[0].content == current_system_message.content):
                self.agent_state.messages.insert(0, current_system_message)
            elif not self.agent_state.messages:
                self.agent_state.messages.append(current_system_message)
        
        # Filtrar cualquier SYSTEM_MESSAGE duplicado del historial si ya lo hemos añadido
        system_message_count = sum(1 for msg in self.agent_state.messages if isinstance(msg, SystemMessage) and msg.content == current_system_message.content)
        if system_message_count > 1:
            first_system_message_index = -1
            for i, msg in enumerate(self.agent_state.messages):
                if isinstance(msg, SystemMessage) and msg.content == current_system_message.content:
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
        
        # Mantener los mensajes existentes pero limpiar contextos dinámicos previos in-place
        i = 0
        while i < len(self.agent_state.messages):
            msg = self.agent_state.messages[i]
            if isinstance(msg, SystemMessage) and "📂 **Directorio de Trabajo Actual:**" in msg.content:
                self.agent_state.messages.pop(i)
            else:
                i += 1
        
        # Crear el mensaje de contexto dinámico
        context_message = SystemMessage(content=f"""
📂 **Directorio de Trabajo Actual:** `{current_working_directory}`

Este es el directorio en el que estás trabajando actualmente. Todas las rutas relativas se resolverán desde aquí.
Cuando ejecutes comandos o manipules archivos, ten en cuenta esta ubicación.
""")
        
        # Insertar el contexto en una posición segura (justo después del sistema principal)
        # Si el historial ya tiene un sistema en el índice 0, lo ponemos en el 1.
        insertion_idx = 0
        if self.agent_state.messages and isinstance(self.agent_state.messages[0], SystemMessage):
            insertion_idx = 1
        self.agent_state.messages.insert(insertion_idx, context_message)

        sys.stderr.flush()
        
        try:
            # Ejecutar invoke sin timeout
            final_state_dict = self.bash_agent_app.invoke(self.agent_state, config={"recursion_limit": 1000})
        finally:
            pass

        sys.stderr.flush()
        
        # Actualizar el estado del agente con los valores del final_state_dict
        self.agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')
        self.agent_state.tool_code_to_confirm = final_state_dict.get('tool_code_to_confirm')
        self.agent_state.tool_code_tool_name = final_state_dict.get('tool_code_tool_name')
        self.agent_state.tool_code_tool_args = final_state_dict.get('tool_code_tool_args')
        self.agent_state.file_update_diff_pending_confirmation = final_state_dict.get('file_update_diff_pending_confirmation')

        # Actualizar los mensajes in-place siempre para evitar pérdida de referencias
        if 'messages' in final_state_dict:
            self.agent_state.messages[:] = final_state_dict['messages']

        
        # 1. Intentar capturar del final_state_dict (prioridad si el agente lo estableció explícitamente)
        if 'tool_call_id_to_confirm' in final_state_dict and final_state_dict['tool_call_id_to_confirm']:
            self.agent_state.tool_call_id_to_confirm = final_state_dict['tool_call_id_to_confirm']
        else:
            # 2. Fallback: capturar del último AIMessage si tiene tool_calls
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

        # Grafo de aprendizaje posterior: se ejecuta al final de un turno cuando no hay herramientas pendientes
        last_msg = self.agent_state.messages[-1] if self.agent_state.messages else None
        has_tool_calls = isinstance(last_msg, AIMessage) and bool(last_msg.tool_calls)
        
        if (hasattr(self, "learning_agent_app") and self.learning_agent_app and 
            not self.agent_state.command_to_confirm and 
            not getattr(self.agent_state, 'tool_pending_confirmation', None) and 
            not self.agent_state.file_update_diff_pending_confirmation and
            not getattr(self.agent_state, 'tool_code_to_confirm', None) and
            not has_tool_calls):
            try:
                logger.info("Ejecutando el grafo de aprendizaje posterior...")
                self.learning_agent_app.invoke(self.agent_state)
            except Exception as e:
                logger.error(f"Error al ejecutar el grafo de aprendizaje: {e}")
        
        return final_state_dict



