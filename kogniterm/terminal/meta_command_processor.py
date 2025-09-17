import sys
from kogniterm.core.llm_service import LLMService
from kogniterm.core.agents.bash_agent import AgentState, SYSTEM_MESSAGE
from kogniterm.terminal.terminal_ui import TerminalUI
from langchain_core.messages import AIMessage

"""
This module contains the MetaCommandProcessor class, responsible for handling
special meta-commands in the KogniTerm application.
"""

class MetaCommandProcessor:
    def __init__(self, llm_service: LLMService, agent_state: AgentState, terminal_ui: TerminalUI):
        self.llm_service = llm_service
        self.agent_state = agent_state
        self.terminal_ui = terminal_ui

    def process_meta_command(self, user_input: str) -> bool:
        """
        Processes meta-commands like %salir, %reset, %undo, %help, %compress.
        Returns True if a meta-command was processed, False otherwise.
        """
        if user_input.lower().strip() in ['%salir', 'salir', 'exit']:
            sys.exit()

        if user_input.lower().strip() == '%reset':
            self.agent_state.reset() # Reiniciar el estado
            # También reiniciamos el historial de llm_service al resetear la conversación
            self.llm_service.conversation_history = []
            self.llm_service._save_history(self.llm_service.conversation_history) # Guardar historial vacío
            # ¡IMPORTANTE! Re-añadir el SYSTEM_MESSAGE después de resetear
            self.llm_service.conversation_history.append(SYSTEM_MESSAGE)
            self.terminal_ui.print_message(f"Conversación reiniciada.", style="green")
            return True

        if user_input.lower().strip() == '%undo':
            if len(self.agent_state.messages) >= 3:
                self.agent_state.messages.pop() # Eliminar respuesta del AI
                self.agent_state.messages.pop() # Eliminar input del usuario
                self.terminal_ui.print_message("Última interacción deshecha.", style="green")
            else:
                self.terminal_ui.print_message("No hay nada que deshacer.", style="yellow")
            return True
        
        if user_input.lower().strip() == '%help':
            self.terminal_ui.print_message("""
Comandos disponibles:
  %help       Muestra este mensaje de ayuda.
  %reset      Reinicia la conversación del modo actual.
  %undo       Deshace la última interacción.
  %compress   Resume el historial de conversación actual.
  %salir      Sale del intérprete.
""", style="blue")
            return True

        if user_input.lower().strip() == '%compress':
            self.terminal_ui.print_message("Resumiendo historial de conversación...", style="yellow")
            
            summary = self.llm_service.summarize_conversation_history()
            
            if summary.startswith("Error") or summary.startswith("No se pudo"):
                self.terminal_ui.print_message(summary, style="red")
            else:
                self.llm_service.conversation_history = [SYSTEM_MESSAGE, AIMessage(content=summary)]
                self.agent_state.messages = self.llm_service.conversation_history
                self.llm_service._save_history(self.llm_service.conversation_history) # Guardar historial comprimido
                self.terminal_ui.print_message(f"Historial comprimido:\n{summary}", style="green")
            return True

        return False