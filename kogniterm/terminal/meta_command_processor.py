import sys
import asyncio
import os
import threading
from kogniterm.core.llm_service import LLMService
from kogniterm.core.agents.bash_agent import AgentState, SYSTEM_MESSAGE
from kogniterm.terminal.terminal_ui import TerminalUI
from langchain_core.messages import AIMessage
from rich.panel import Panel
from rich.markdown import Markdown
from kogniterm.terminal.themes import set_kogniterm_theme, get_available_themes


"""
This module contains the MetaCommandProcessor class, responsible for handling
special meta-commands in the KogniTerm application.
"""

class MetaCommandProcessor:
    def __init__(self, llm_service: LLMService, agent_state: AgentState, terminal_ui: TerminalUI, kogniterm_app):
        self.llm_service = llm_service
        self.agent_state = agent_state
        self.terminal_ui = terminal_ui
        self.kogniterm_app = kogniterm_app # Referencia a la instancia de KogniTermApp

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
            # ¡IMPORTANTE! Re-añadir el SYSTEM_MESSAGE después de resetear
            self.llm_service.conversation_history.append(SYSTEM_MESSAGE)
            # Guardar historial CON el SYSTEM_MESSAGE
            self.llm_service._save_history(self.llm_service.conversation_history)
            # Sincronizar agent_state.messages con el historial
            self.agent_state.messages = self.llm_service.conversation_history.copy()
            
            # Limpiar la pantalla de la terminal
            os.system('cls' if os.name == 'nt' else 'clear')
            self.kogniterm_app.terminal_ui.print_welcome_banner() # Volver a imprimir el banner de bienvenida
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
        
        if user_input.lower().strip().startswith('%init'):
            command_parts = user_input.strip().split(' ', 1)
            files_to_include = None
            if len(command_parts) > 1:
                files_to_include = [f.strip() for f in command_parts[1].split(',')]
            
            self.terminal_ui.print_message("Inicializando contexto del espacio de trabajo... Esto puede tardar un momento. ⏳", style="yellow")
            try:
                self.llm_service.initialize_workspace_context(files_to_include=files_to_include)
                self.terminal_ui.print_message("Contexto del espacio de trabajo inicializado correctamente. ✨", style="green")
            except Exception as e:
                self.terminal_ui.print_message(f"Error al inicializar el contexto del espacio de trabajo: {e} ❌", style="red")
            return True

        if user_input.lower().strip().startswith('%theme') or user_input.lower().strip().startswith('%tema'):
            parts = user_input.strip().split()
            if len(parts) > 1:
                theme_name = parts[1].lower()
                try:
                    set_kogniterm_theme(theme_name)
                    # Update console theme if necessary
                    if hasattr(self.terminal_ui, 'refresh_theme'):
                         self.terminal_ui.refresh_theme()
                    
                    self.terminal_ui.print_message(f"Tema cambiado a '{theme_name}'. ✨", style="green")
                    # Reprint banner to show off new colors
                    self.terminal_ui.print_welcome_banner()
                except ValueError:
                     self.terminal_ui.print_message(f"Tema '{theme_name}' no encontrado. Temas disponibles: {', '.join(get_available_themes())}", style="red")
            else:
                self.terminal_ui.print_message(f"Temas disponibles: {', '.join(get_available_themes())}", style="blue")
            return True


        if user_input.lower().strip() == '%help':
            self.terminal_ui.print_message("""
Comandos disponibles:
  %help         Muestra este mensaje de ayuda.
  %init [archivos] Inicializa el contexto del proyecto. Opcionalmente, puedes especificar archivos a incluir (ej: %init README.md,src/main.py).
  %reset        Reinicia la conversación del modo actual.
  %undo         Deshace la última interacción.
  %compress     Resume el historial de conversación actual.
  %theme [nombre] Cambia el tema de colores (ej: %theme ocean).
  %salir        Sale del intérprete.
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
                self.terminal_ui.console.print(Panel(Markdown(f"Historial comprimido:\n{summary}"), border_style="green", title="[bold green]Historial Comprimido[/bold green]"))
            return True

        return False