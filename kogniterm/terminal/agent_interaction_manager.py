import logging
import sys

logger = logging.getLogger(__name__)

from kogniterm.core.llm_service import LLMService
from kogniterm.core.agents.bash_agent import create_bash_agent, AgentState, SYSTEM_MESSAGE
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import Dict, Any, Optional
from typing import Dict, Any
import queue # Importar queue
from kogniterm.terminal.terminal_ui import TerminalUI # Importar TerminalUI

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
        
        # El SYSTEM_MESSAGE y la gestión del historial inicial se manejan ahora en AgentState y KogniTermApp.
        # No se necesita lógica de deduplicación o inserción aquí.

    def invoke_agent(self, user_input: Optional[str]) -> Dict[str, Any]:
        logger.debug(f"DEBUG: invoke_agent - user_input: {user_input}")
        
        if user_input is not None:
            processed_input = user_input.strip()
            if processed_input.startswith('@'):
                processed_input = processed_input[1:]
            self.agent_state.messages.append(HumanMessage(content=processed_input))
        

        sys.stderr.flush()
        # Siempre usaremos bash_agent_app por ahora
        final_state_dict = self.bash_agent_app.invoke(self.agent_state)

        sys.stderr.flush()
        
        # Actualizar el estado del agente con los valores del final_state_dict
        self.agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')
        self.agent_state.tool_code_to_confirm = final_state_dict.get('tool_code_to_confirm')
        self.agent_state.tool_code_tool_name = final_state_dict.get('tool_code_tool_name')
        self.agent_state.tool_code_tool_args = final_state_dict.get('tool_code_tool_args')
        self.agent_state.file_update_diff_pending_confirmation = final_state_dict.get('file_update_diff_pending_confirmation')

        # Si hay una confirmación de archivo pendiente, la información ya está en final_state_dict
        # y será manejada por KogniTermApp.

        # El historial de mensajes del agente se actualizará en KogniTermApp con el historial de AgentState.
        # No es necesario actualizarlo aquí.
        
        # Capturar el tool_call_id del último AIMessage si existe
        last_ai_message = None
        for msg in reversed(self.agent_state.messages):
            if isinstance(msg, AIMessage):
                last_ai_message = msg
                break
        
        if last_ai_message and last_ai_message.tool_calls:
            # Asumiendo que solo hay una tool_call por AIMessage para simplificar
            self.agent_state.tool_call_id_to_confirm = last_ai_message.tool_calls[0]['id']
            logger.debug(f"DEBUG: tool_call_id_to_confirm establecido en AgentInteractionManager: {self.agent_state.tool_call_id_to_confirm}")
        else:
            self.agent_state.tool_call_id_to_confirm = None
            logger.debug("DEBUG: No se encontró tool_call_id en el último AIMessage.")
        
        return final_state_dict



