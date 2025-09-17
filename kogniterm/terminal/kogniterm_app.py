import os
import sys
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings

from rich.console import Console
from rich.padding import Padding

from kogniterm.core.llm_service import LLMService
from kogniterm.core.command_executor import CommandExecutor
from kogniterm.core.agents.bash_agent import AgentState
from kogniterm.core.tools.file_operations_tool import FileOperationsTool
from kogniterm.core.tools.python_executor import PythonTool # Para manejar la salida de PythonTool
from langchain_core.messages import ToolMessage # Para manejar la salida de PythonTool

from kogniterm.terminal.terminal_ui import TerminalUI
from kogniterm.terminal.meta_command_processor import MetaCommandProcessor
from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager
from kogniterm.terminal.command_approval_handler import CommandApprovalHandler

load_dotenv()

class FileCompleter(Completer):
    def __init__(self, file_operations_tool, show_indicator: bool = True):
        self.file_operations_tool = file_operations_tool
        self.show_indicator = show_indicator

    def get_completions(self, document, complete_event):
        text_before_cursor = document.text_before_cursor
        
        if '@' not in text_before_cursor:
            return # No estamos en modo de autocompletado de archivos

        current_input_part = text_before_cursor.split('@')[-1]
        
        base_path = os.getcwd()

        include_hidden = current_input_part.startswith('.')

        try:
            EXCLUDE_DIRS = ['build/', 'venv/', '.git/', '__pycache__/', 'kogniterm.egg-info/', 'src/']
            all_relative_items = self.file_operations_tool._list_directory(
                path=base_path, 
                recursive=True, 
                include_hidden=include_hidden, 
                silent_mode=not self.show_indicator
            )
            
            suggestions = []
            for relative_item_path in all_relative_items:
                # Excluir directorios específicos
                if any(relative_item_path.startswith(ed) for ed in EXCLUDE_DIRS):
                    continue

                absolute_item_path = os.path.join(base_path, relative_item_path)
                
                display_item = relative_item_path
                if os.path.isdir(absolute_item_path):
                    display_item += '/'

                if current_input_part.lower() in display_item.lower():
                    suggestions.append(display_item)
            
            suggestions.sort()

            for suggestion in suggestions:
                start_position = -len(current_input_part)
                yield Completion(suggestion, start_position=start_position)

        except Exception as e:
            print(f"Error en FileCompleter: {e}", file=sys.stderr)


class KogniTermApp:
    def __init__(self, auto_approve: bool = False):
        self.auto_approve = auto_approve
        self.console = Console()
        self.llm_service = LLMService()
        self.command_executor = CommandExecutor()
        self.agent_state = AgentState(messages=self.llm_service.conversation_history)
        
        # Inicializar TerminalUI
        self.terminal_ui = TerminalUI(console=self.console)

        # Establecer la consola en el servicio LLM para permitir el streaming
        if hasattr(self.llm_service, 'set_console'):
            self.llm_service.set_console(self.console)

        # Inicializar FileCompleter
        file_operations_tool = self.llm_service.get_tool("file_operations")
        if not file_operations_tool:
            self.terminal_ui.print_message("Advertencia: La herramienta 'file_operations' no se encontró. El autocompletado de archivos no estará disponible.", style="yellow")
            completer = None
        else:
            completer = FileCompleter(file_operations_tool, show_indicator=False)

        # Definir un estilo para el prompt
        custom_style = Style.from_dict({
            'prompt': '#aaaaaa',
            'rprompt': '#aaaaaa',
            'output': '#aaaaaa',
        })

        # Crear key bindings personalizados
        kb = KeyBindings()

        @kb.add('escape', eager=True)
        def _(event):
            self.llm_service.stop_generation_flag = True
            event.app.exit()

        @kb.add('enter', eager=True)
        def _(event):
            buffer = event.app.current_buffer
            if buffer.complete_state:
                if buffer.complete_state.current_completion:
                    buffer.apply_completion(buffer.complete_state.current_completion)
                elif buffer.complete_state.completions:
                    buffer.apply_completion(buffer.complete_state.completions[0])
            buffer.validate_and_handle()

        self.prompt_session = PromptSession(
            history=FileHistory('.gemini_interpreter_history'),
            completer=completer,
            style=custom_style,
            key_bindings=kb
        )

        # Inicializar los otros componentes
        self.meta_command_processor = MetaCommandProcessor(self.llm_service, self.agent_state, self.terminal_ui)
        self.agent_interaction_manager = AgentInteractionManager(self.llm_service, self.agent_state)
        self.command_approval_handler = CommandApprovalHandler(self.llm_service, self.command_executor, self.prompt_session, self.terminal_ui, self.agent_state)

    def run(self):
        """Runs the main loop of the KogniTerm application."""
        self.terminal_ui.print_welcome_banner()

        if self.auto_approve:
            self.terminal_ui.print_message("Modo de auto-aprobación activado.", style="yellow")

        while True:
            try:
                cwd = os.getcwd()
                prompt_text = f"({self.agent_state.current_agent_mode}) ({os.path.basename(cwd)}) > " # Asumiendo que agent_state tendrá un current_agent_mode
                user_input = self.prompt_session.prompt(prompt_text)

                if not user_input.strip():
                    continue

                if self.meta_command_processor.process_meta_command(user_input):
                    continue

                final_state_dict = self.agent_interaction_manager.invoke_agent(user_input)
                
                # Actualizar el estado del agente con lo que devuelve el manager
                self.agent_state.messages = final_state_dict['messages']
                self.agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')

                if self.agent_state.command_to_confirm:
                    command_to_execute = self.agent_state.command_to_confirm
                    self.agent_state.command_to_confirm = None # Limpiar después de usar

                    approval_result = self.command_approval_handler.handle_command_approval(command_to_execute, self.auto_approve)
                    
                    # Actualizar el estado del agente con los mensajes devueltos por el handler
                    self.agent_state.messages = approval_result['messages']
                    tool_message_content = approval_result['tool_message_content']

                    # Re-invocar al agente para procesar la salida de la herramienta
                    self.terminal_ui.print_message("Procesando salida del comando...", style="cyan")
                    # No necesitamos el resultado de esta invocación aquí, solo que actualice el agent_state
                    self.agent_interaction_manager.invoke_agent(tool_message_content) # Pasar el tool_message_content como input

                # Manejo de la salida de PythonTool
                final_response_message = self.agent_state.messages[-1]
                if isinstance(final_response_message, ToolMessage) and final_response_message.tool_call_id == "python_executor":
                    python_tool_instance = self.llm_service.get_tool("python_executor")
                    if isinstance(python_tool_instance, PythonTool) and hasattr(python_tool_instance, 'get_last_structured_output'):
                        structured_output = python_tool_instance.get_last_structured_output()
                        if structured_output and "result" in structured_output:
                            self.terminal_ui.console.print(Padding(Panel("[bold green]Salida del Código Python:[/bold green]", border_style='green'), (1, 2)))
                            for item in structured_output["result"]:
                                if item['type'] == 'stream':
                                    self.terminal_ui.console.print(f"[cyan]STDOUT:[/cyan] {item['text']}")
                                elif item['type'] == 'error':
                                    self.terminal_ui.console.print(f"[red]ERROR ({item['ename']}):[/red] {item['evalue']}")
                                    self.terminal_ui.console.print(f"[red]TRACEBACK:[/red]\n{"".join(item['traceback'])}")
                                elif item['type'] == 'execute_result':
                                    data_str = item['data'].get('text/plain', str(item['data']))
                                    self.terminal_ui.console.print(f"[green]RESULTADO:[/green] {data_str}")
                                elif item['type'] == 'display_data':
                                    if 'image/png' in item['data']:
                                        self.terminal_ui.console.print("[magenta]IMAGEN PNG GENERADA[/magenta]")
                                    elif 'text/html' in item['data']:
                                        self.terminal_ui.console.print(f"[magenta]HTML GENERADO:[/magenta] {item['data']['text/html'][:100]}...")
                                    else:
                                        self.terminal_ui.console.print(f"[magenta]DATOS DE VISUALIZACIÓN:[/magenta] {str(item['data'])}")
                            self.terminal_ui.console.print(Padding(Panel("[bold green]Fin de la Salida Python[/bold green]", border_style='green'), (1, 2)))
                        elif "error" in structured_output:
                            self.terminal_ui.console.print(f"[red]Error en la ejecución de Python:[/red] {structured_output['error']}")
                    continue
                elif isinstance(final_response_message, ToolMessage) and final_response_message.tool_call_id == "file_operations":
                    continue

                self.llm_service._save_history(self.agent_state.messages)

            except KeyboardInterrupt:
                self.terminal_ui.print_message("\nSaliendo...", style="yellow")
                break
            except Exception as e:
                self.terminal_ui.print_message(f"Ocurrió un error inesperado: {e}", style="red")
                import traceback
                traceback.print_exc()
