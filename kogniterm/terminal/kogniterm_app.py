import os
import sys
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
import queue # Importar el módulo queue

from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel

from kogniterm.core.llm_service import LLMService
from kogniterm.core.command_executor import CommandExecutor
from kogniterm.core.agents.bash_agent import AgentState, UserConfirmationRequired
from kogniterm.core.tools.file_operations_tool import FileOperationsTool
from kogniterm.core.tools.python_executor import PythonTool # Para manejar la salida de PythonTool
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage # Para manejar la salida de PythonTool y el mensaje de confirmación

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


from kogniterm.core.tools.file_update_tool import FileUpdateTool

# ... (otras importaciones)

class KogniTermApp:
    def __init__(self, llm_service: LLMService, command_executor: CommandExecutor, agent_state: AgentState, auto_approve: bool = False, project_context: dict = None, workspace_directory: str = None):
        self.llm_service = llm_service
        self.command_executor = command_executor
        self.agent_state = agent_state
        self.terminal_ui = TerminalUI()
        self.file_update_tool = FileUpdateTool() # Instanciar FileUpdateTool
        self.auto_approve = auto_approve
        self.project_context = project_context
        self.workspace_directory = workspace_directory
        self.meta_command_processor = MetaCommandProcessor(self.llm_service, self.agent_state, self.terminal_ui, self) # Inicializar meta_command_processor
        self.agent_interaction_manager = AgentInteractionManager(self.llm_service, self.agent_state, self.terminal_ui.get_interrupt_queue()) # Inicializar agent_interaction_manager

        # Inicializar FileCompleter
        # Asegurarse de que FileOperationsTool tenga acceso al contexto del proyecto si lo necesita
        file_operations_tool = FileOperationsTool(llm_service=self.llm_service, workspace_context=self.project_context) # Instanciar FileOperationsTool con llm_service
        completer = FileCompleter(file_operations_tool=file_operations_tool, show_indicator=False)


        # Definir un estilo para el prompt
        custom_style = Style.from_dict({
            'prompt': '#aaaaaa',
            'rprompt': '#aaaaaa',
            'output': 'grey',
            'text': '#808080', # Color gris para el texto del usuario
        })

        kb_enter = KeyBindings()
        @kb_enter.add('enter', eager=True)
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
            key_bindings=self.terminal_ui.kb # Usar los KeyBindings de TerminalUI
        )

        self.command_approval_handler = CommandApprovalHandler(self.llm_service, self.command_executor, self.prompt_session, self.terminal_ui, self.agent_state, self.file_update_tool)

    async def run(self): # Make run() async
        """Runs the main loop of the KogniTerm application."""
        self.terminal_ui.print_welcome_banner()

        if self.auto_approve:
            self.terminal_ui.print_message("Modo de auto-aprobación activado.", style="yellow")
        
        try: # Mover el try para que englobe todo el bucle principal
            # No es necesario detectar cambios de directorio en el bucle si el historial es por directorio.
            # El historial se carga una vez al inicio del KogniTermApp para el CWD.
            # Si el usuario cambia de directorio usando 'cd', se iniciará una nueva instancia de KogniTermApp
            # o se deberá manejar explícitamente el cambio de directorio en una futura mejora.
            while True:
                try:
                    cwd = os.getcwd() # Obtener el CWD actual para el prompt
                    prompt_text = f"({os.path.basename(cwd)}) > " # Eliminado el indicador de modo de agente
                    user_input = await self.prompt_session.prompt_async(prompt_text) # Use prompt_async

                    if user_input is None:
                        if not self.terminal_ui.get_interrupt_queue().empty():
                            while not self.terminal_ui.get_interrupt_queue().empty():
                                self.terminal_ui.get_interrupt_queue().get_nowait() # Vaciar la cola
                            self.terminal_ui.print_message("Generación de respuesta cancelada por el usuario. 🛑", style="yellow")
                            self.llm_service.stop_generation_flag = False # Resetear la bandera
                            continue # Continuar el bucle para un nuevo prompt
                        else:
                            # Si user_input es None y no se ha establecido la bandera de stop_generation_flag,
                            # significa que el usuario ha salido del prompt de alguna otra manera (ej. Ctrl+D).
                            # En este caso, salimos de la aplicación.
                            break

                    if not user_input.strip():
                        continue

                    # Imprimir el mensaje del usuario en un panel gris
                    self.terminal_ui.print_message(user_input, is_user_message=True)

                    # Limpiar el input después de enviar el mensaje
                    self.prompt_session.app.current_buffer.text = ""
                    self.prompt_session.app.current_buffer.cursor_position = 0

                    if self.meta_command_processor.process_meta_command(user_input): # Eliminar await
                        continue

                    try:
                        final_state_dict = self.agent_interaction_manager.invoke_agent(user_input)
                        
                        # Actualizar el estado del agente con lo que devuelve el manager
                        self.agent_state.messages = self.llm_service.conversation_history # Asegurarse de que siempre apunte al historial del LLMService
                        self.agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')

                    except UserConfirmationRequired as e:
                        # Capturar la solicitud de confirmación del usuario
                        confirmation_message = e.message
                        self.terminal_ui.print_message(f"Se requiere confirmación para: {confirmation_message}", style="yellow")
                        
                        # Usar CommandApprovalHandler para obtener la confirmación
                        # Necesitamos un tool_call_id para el ToolMessage que se generará
                        # Si no hay un AIMessage previo con tool_calls, generamos uno temporal
                        last_ai_message = None
                        for msg in reversed(self.agent_state.messages):
                            if isinstance(msg, ToolMessage): # Ignorar ToolMessages
                                continue
                            if isinstance(msg, HumanMessage): # Ignorar HumanMessages
                                continue
                            if isinstance(msg, AIMessage):
                                last_ai_message = msg
                                break
                        
                        tool_call_id = None
                        if last_ai_message and last_ai_message.tool_calls and last_ai_message.tool_calls[0] and 'id' in last_ai_message.tool_calls[0]:
                            tool_call_id = last_ai_message.tool_calls[0]['id']
                        else:
                            tool_call_id = f"manual_tool_call_{os.urandom(8).hex()}"
                            self.terminal_ui.print_message(f"Advertencia: No se encontró un tool_call_id asociado para la confirmación. Generando ID temporal: {tool_call_id}", style="yellow")

                        self.agent_state.tool_call_id_to_confirm = tool_call_id # Asignar el tool_call_id al estado del agente

                        # Capturar la operación pendiente y sus argumentos para re-invocación
                        # Esta información debe ser pasada por la excepción UserConfirmationRequired
                        tool_name_to_confirm = e.tool_name
                        tool_args_to_confirm = e.tool_args

                        # Simular la ejecución de un comando para el CommandApprovalHandler
                        dummy_command_to_execute = f"confirm_action('{confirmation_message}')"
                        approval_result = await self.command_approval_handler.handle_command_approval(
                            dummy_command_to_execute, self.auto_approve, is_user_confirmation=True, confirmation_prompt=confirmation_message
                        )

                        tool_message_content = approval_result['tool_message_content']
                        self.agent_state.messages = self.llm_service.conversation_history # Asegurarse de que siempre apunte al historial del LLMService
                        # self.agent_state.messages = approval_result['messages'] # Ya se actualiza a través de llm_service.conversation_history

                        # Determinar si la acción fue aprobada
                        action_approved = "Aprobado" in tool_message_content

                        if action_approved:
                            self.terminal_ui.print_message("Acción aprobada por el usuario. Reintentando operación...", style="green")
                            self.agent_interaction_manager.invoke_agent(f"Confirmación para '{confirmation_message}' recibida: {tool_message_content}. Por favor, procede con la operación original si fue aprobada.")
                        else:
                            self.terminal_ui.print_message("Acción denegada por el usuario.", style="yellow")
                            self.agent_interaction_manager.invoke_agent(f"Confirmación para '{confirmation_message}' recibida: {tool_message_content}.")
                        
                        continue # Continuar al siguiente ciclo del bucle principal

                    if self.agent_state.command_to_confirm:
                        command_to_execute = self.agent_state.command_to_confirm
                        self.agent_state.command_to_confirm = None # Limpiar después de usar

                        approval_result = await self.command_approval_handler.handle_command_approval(command_to_execute, self.auto_approve)
                        
                        # Actualizar el estado del agente con los mensajes devueltos por el handler
                        self.agent_state.messages = self.llm_service.conversation_history # Asegurarse de que siempre apunte al historial del LLMService
                        # self.agent_state.messages = approval_result['messages']
                        tool_message_content = approval_result['tool_message_content']

                        # Re-invocar al agente para procesar la salida de la herramienta
                        self.terminal_ui.print_message("Procesando salida del comando...", style="cyan")
                        
                        # Asegurar que tool_call_id_to_confirm siempre tenga un valor
                        if self.agent_state.tool_call_id_to_confirm is None:
                            self.agent_state.tool_call_id_to_confirm = f"manual_tool_call_{os.urandom(8).hex()}"
                            self.terminal_ui.print_message(f"Advertencia: tool_call_id_to_confirm era None. Generando ID temporal: {self.agent_state.tool_call_id_to_confirm}", style="yellow")

                        # Construir el ToolMessage con el tool_call_id correcto
                        tool_message_for_agent = ToolMessage(
                            content=tool_message_content,
                            tool_call_id=self.agent_state.tool_call_id_to_confirm # Usar el tool_call_id guardado
                        )
                        self.agent_state.messages.append(tool_message_for_agent) # Añadir al historial
                        self.agent_interaction_manager.invoke_agent("Procesa la salida de la herramienta que acaba de ser añadida al historial.") # Invocar al agente con una instrucción de texto
                        self.agent_state.tool_call_id_to_confirm = None # Limpiar el tool_call_id después de usarlo

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

                    # self.llm_service._save_history(self.agent_state.messages) # No es necesario aquí, ya se guarda en finally

                except KeyboardInterrupt:
                    self.terminal_ui.print_message("\nSaliendo...", style="yellow")
                    break
                except Exception as e:
                    self.terminal_ui.print_message(f"Ocurrió un error inesperado: {e}", style="red")
                    import traceback
                    traceback.print_exc()
                    break # Salir del bucle en caso de error inesperado
        finally: # Mover finally para que englobe todo el método run()
            # Asegurarse de que el historial se guarde siempre al salir de la aplicación
            self.llm_service._save_history(self.llm_service.conversation_history) # Guardar el historial del LLMService
            self.terminal_ui.print_message("Historial guardado al salir.", style="dim")
