from kogniterm.core.llm_service import LLMService
from kogniterm.core.agents.bash_agent import create_bash_agent, AgentState, SYSTEM_MESSAGE
from langchain_core.messages import HumanMessage, SystemMessage

"""
This module contains the AgentInteractionManager class, responsible for
orchestrating AI agent interactions in the KogniTerm application.
"""

class AgentInteractionManager:
    def __init__(self, llm_service: LLMService, agent_state: AgentState):
        self.llm_service = llm_service
        self.agent_state = agent_state
        self.bash_agent_app = create_bash_agent(llm_service) # Inicializar el agente bash
        
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

    def invoke_agent(self, user_input: str) -> dict:
        """Invokes the active agent with the user's input."""
        processed_input = user_input.strip()
        if processed_input.startswith('@'):
            processed_input = processed_input[1:]

        self.agent_state.messages.append(HumanMessage(content=processed_input))
        
        # Siempre usaremos bash_agent_app por ahora
        final_state_dict = self.bash_agent_app.invoke(self.agent_state)
        
        self.agent_state.messages = final_state_dict['messages']
        self.llm_service._save_history(self.agent_state.messages)
        self.agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')
        
        return final_state_dict