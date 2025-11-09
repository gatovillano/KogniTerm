import logging
import sys

logger = logging.getLogger(__name__)

from kogniterm.core.llm_service import LLMService
from kogniterm.core.agents.bash_agent import create_bash_agent, AgentState, SYSTEM_MESSAGE
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig # Importar RunnableConfig
from typing import Dict, Any, Optional
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
        logger.info(f"invoke_agent - user_input: {user_input}")
        
        if user_input is not None:
            processed_input = user_input.strip()
            if processed_input.startswith('@'):
                processed_input = processed_input[1:]
            self.agent_state.messages.append(HumanMessage(content=processed_input))
        

        sys.stderr.flush()
        config = RunnableConfig(recursion_limit=100)
        
        # Bucle para asegurar que el LLM procese ToolMessages después de una confirmación
        while True:
            logger.info(f"invoke_agent - Invocando al agente con agent_state.messages: {[str(m)[:100] for m in self.agent_state.messages[-5:]]}")
            agent_response = self.bash_agent_app.invoke(self.agent_state, config)
            logger.info(f"invoke_agent - Respuesta cruda del agente (tipo: {type(agent_response)}): {str(agent_response)[:500]}")
            
            sys.stderr.flush()

            last_ai_message = None
            for msg in reversed(self.agent_state.messages):
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    last_ai_message = msg
                    break
            
            if last_ai_message:
                logger.info(f"invoke_agent - Último AIMessage con tool_calls encontrado en historial: {str(last_ai_message)[:500]}")
                self.agent_state.tool_call_id_to_confirm = last_ai_message.tool_calls[0]['id']
                logger.info(f"tool_call_id_to_confirm establecido en AgentInteractionManager: {self.agent_state.tool_call_id_to_confirm}")
                
                # Si el LLM generó una tool_call, y no es una respuesta final,
                # necesitamos que el KogniTermApp la maneje (posiblemente pidiendo confirmación).
                # Por lo tanto, salimos de este bucle para que KogniTermApp pueda procesarla.
                break 
            else:
                self.agent_state.tool_call_id_to_confirm = None
                logger.info("No se encontró un AIMessage con tool_calls en el historial del agente.")
                
                # Si no hay tool_calls, significa que el LLM ha generado una respuesta final
                # o está esperando más input del usuario. En este caso, salimos del bucle.
                break

        final_state_dict = agent_response if isinstance(agent_response, dict) else {}
        
        self.agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')
        self.agent_state.tool_code_to_confirm = final_state_dict.get('tool_code_to_confirm')
        self.agent_state.tool_code_tool_name = final_state_dict.get('tool_code_tool_name')
        self.agent_state.tool_code_tool_args = final_state_dict.get('tool_code_tool_args')
        self.agent_state.file_update_diff_pending_confirmation = final_state_dict.get('file_update_diff_pending_confirmation')
        
        return final_state_dict



