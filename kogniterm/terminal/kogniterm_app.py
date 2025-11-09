import os
import sys
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings # Importar merge_key_bindings
import queue
import threading # Nueva importación para el FileCompleter
import concurrent.futures # Nueva importación para el FileCompleter
import asyncio # Nueva importación para el FileCompleter
from typing import Optional, List # Nuevas importaciones para el FileCompleter
import fnmatch # Nueva importación para el FileCompleter
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

# Configurar un StreamHandler para la consola
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel

from kogniterm.core.llm_service import LLMService
from kogniterm.core.command_executor import CommandExecutor
from kogniterm.core.agent_state import AgentState
from kogniterm.core.agents.bash_agent import UserConfirmationRequired
from kogniterm.core.tools.file_operations_tool import FileOperationsTool
from kogniterm.core.tools.python_executor import PythonTool
from kogniterm.core.tools.advanced_file_editor_tool import AdvancedFileEditorTool # Importar AdvancedFileEditorTool
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage
from kogniterm.core.agents.bash_agent import SYSTEM_MESSAGE # Importar SYSTEM_MESSAGE

from kogniterm.terminal.terminal_ui import TerminalUI
from kogniterm.terminal.meta_command_processor import MetaCommandProcessor
from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager
from kogniterm.terminal.command_approval_handler import CommandApprovalHandler

load_dotenv()

class FileCompleter(Completer):
    EXCLUDE_PATTERNS = [
        "build/", "venv/", ".git/", "__pycache__/", "kogniterm.egg-info/", "src/",
        "*/build/*", "*/venv/*", "*/.git/*", "*/__pycache__/*", "*/kogniterm.egg-info/*", "*/src/*",
        ".*/", "*/.*/", # Patrones para directorios ocultos en la raíz y subdirectorios
        "*.pyc", "*.tmp", "*.log", ".env", ".DS_Store", "*.swp", "*.bak", "*.old", "*.fuse_hidden*",
        "node_modules/", "dist/", "out/", "coverage/", ".mypy_cache/", "kogniterm.egg-info/", "src/", "%.*/", ".*/",
        "*.pyc", "*.tmp", "*.log", ".env", ".DS_Store", "*.swp", "*.bak", "*.old", "*.fuse_hidden*",
        "node_modules/", "dist/", "out/", "coverage/", ".mypy_cache/", ".pytest_cache/",
        # "docs/", "examples/", "tests/", # Comentar si se quieren incluir estos directorios
    ]

    def __init__(self, file_operations_tool: FileOperationsTool, workspace_directory: str, show_indicator: bool = True):
        self.file_operations_tool = file_operations_tool
        self.workspace_directory = workspace_directory
        self.show_indicator = show_indicator
        self._cached_files: Optional[List[str]] = None
        self.cache_lock = threading.Lock()
        self._loading_future: Optional[concurrent.futures.Future] = None
        try:
            self._loop = asyncio.get_event_loop()

        except RuntimeError:
            logger.warning("FileCompleter: No hay un bucle de eventos de asyncio corriendo. Esto puede causar problemas.")
            self._loop = None # O manejar de otra forma si no hay loop
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1) # Ejecutor para tareas de IO

        self._start_background_load_files() # Iniciar la carga inicial en segundo plano

    def invalidate_cache(self):
        """Invalida la caché de archivos, forzando una recarga la próxima vez que se necesite."""
        with self.cache_lock:
            self._cached_files = None
            # logger.debug("FileCompleter: Caché de autocompletado invalidada.")
        # Si no hay una carga en progreso, iniciar una nueva carga.
        if self._loading_future is None or self._loading_future.done():
            self._start_background_load_files()

    def _start_background_load_files(self):
        """Inicia la carga de archivos en un hilo secundario."""
        with self.cache_lock:
            if self._loading_future is not None and not self._loading_future.done():
    
                return # Ya hay una carga en progreso

            if self._loop is None:
                logger.error("FileCompleter: No se puede iniciar la carga en segundo plano, no hay bucle de eventos.")
                return


            self._loading_future = self._loop.run_in_executor(
                self._executor, # Usar el ThreadPoolExecutor
                self._do_load_files
            )

    def _do_load_files(self) -> List[str]:
        """Realiza la carga real de archivos de forma síncrona en un hilo secundario."""

        try:
            raw_items = self.file_operations_tool._list_directory(
                path=self.workspace_directory,
                recursive=True,
                include_hidden=False, # No permitir incluir archivos ocultos
                silent_mode=True
            )
            
            all_relative_items = []
            for item in raw_items:
                item = item.strip()
                if item:
                    if any(fnmatch.fnmatch(item, pattern) for pattern in self.EXCLUDE_PATTERNS):
                        continue
                    all_relative_items.append(item)
            

            with self.cache_lock:
                self._cached_files = all_relative_items
            return all_relative_items
        except Exception as e:
            logger.error(f"FileCompleter: Error al cargar archivos en segundo plano: {e}", exc_info=True)
            with self.cache_lock:
                self._cached_files = []
            return []

    def get_completions(self, document, complete_event):
        text_before_cursor = document.text_before_cursor
        
        if '@' not in text_before_cursor:
            return # No estamos en modo de autocompletado de archivos

        current_input_part = text_before_cursor.split('@')[-1]
        
        # Intentar obtener los archivos de la caché
        with self.cache_lock:
            cached_files = self._cached_files
        
        if cached_files is None:
            # Si la caché está vacía, iniciar la carga en segundo plano si no está ya en progreso
            if self._loading_future is None or self._loading_future.done():
                self._start_background_load_files()
            
            # Mientras se carga, podemos ofrecer una sugerencia básica o ninguna
            if self.show_indicator:
                yield Completion("(Cargando archivos...)", start_position=-len(current_input_part))
            return

        suggestions = []
        for relative_item_path in cached_files:
            # Construir la ruta absoluta para verificar si es un directorio
            absolute_item_path = os.path.join(self.workspace_directory, relative_item_path)
            
            display_item = relative_item_path
            # Solo añadir '/' si es un directorio real y no un patrón excluido que podría parecer un directorio
            if os.path.isdir(absolute_item_path) and not display_item.endswith('/'):
                 display_item += '/'

            if current_input_part.lower() in display_item.lower():
                suggestions.append(display_item)
        
        suggestions.sort()

        for suggestion in suggestions:
            start_position = -len(current_input_part)
            yield Completion(suggestion, start_position=start_position)

    def dispose(self):
        """Detiene el FileSystemWatcher y el ThreadPoolExecutor cuando la aplicación se cierra."""
        if self._executor:
            self._executor.shutdown(wait=True)
            # print("ThreadPoolExecutor de autocompletado detenido.")

from kogniterm.core.tools.file_update_tool import FileUpdateTool
from kogniterm.core.tools.file_create_tool import FileCreateTool

class KogniTermApp:
    def __init__(self, llm_service: LLMService, command_executor: CommandExecutor, agent_state: AgentState, auto_approve: bool = False, workspace_directory: str = None):
        self.llm_service = llm_service
        self.command_executor = command_executor
        self.agent_state = agent_state
        self.agent_state.llm_service = self.llm_service
        self.terminal_ui = TerminalUI()
        self.file_update_tool = FileUpdateTool()
        self.file_create_tool = FileCreateTool() # Inicializar FileCreateTool
        self.auto_approve = auto_approve
        self.workspace_directory = workspace_directory
        self.meta_command_processor = MetaCommandProcessor(self.llm_service, self.agent_state, self.terminal_ui, self)
        self.agent_interaction_manager = AgentInteractionManager(self.llm_service, self.agent_state, self.terminal_ui, self.terminal_ui.get_interrupt_queue())

        # Asegurarse de que el interrupt_queue se pase al LLMService
        self.llm_service.interrupt_queue = self.terminal_ui.get_interrupt_queue()

        # Inicializar FileCompleter con el workspace_directory
        file_operations_tool = FileOperationsTool(llm_service=self.llm_service)
        self.completer = FileCompleter(file_operations_tool=file_operations_tool, workspace_directory=self.workspace_directory, show_indicator=False)

        # Cargar el historial del agente al inicio, pasándole el SYSTEM_MESSAGE
        self.agent_state.load_history(SYSTEM_MESSAGE)

        # Instanciar AdvancedFileEditorTool
        advanced_file_editor_tool = AdvancedFileEditorTool()

        # Definir un estilo para el prompt
        custom_style = Style.from_dict({
            'prompt': '#aaaaaa',
            'rprompt': '#aaaaaa',
            'output': 'grey',
            'text': '#808080',
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

        # Nuevo KeyBindings para la tecla Esc
        kb_esc = KeyBindings()
        @kb_esc.add('escape', eager=True)
        def _(event):
            # Enviar una señal de interrupción a la cola
            self.terminal_ui.get_interrupt_queue().put_nowait(True)
            self.agent_interrupted = True # Establecer la bandera de interrupción del agente
            event.app.exit() # Salir del prompt actual, pero no de la aplicación

        # Combinar los KeyBindings
        combined_key_bindings = merge_key_bindings([kb_enter, kb_esc, self.terminal_ui.kb])

        self.prompt_session = PromptSession(
            history=FileHistory('.gemini_interpreter_history'),
            completer=self.completer,
            style=custom_style,
            key_bindings=combined_key_bindings
        )

        self.command_approval_handler = CommandApprovalHandler(
            self.llm_service,
            self.command_executor,
            self.prompt_session,
            self.terminal_ui,
            self.agent_state,
            self.file_update_tool,
            advanced_file_editor_tool, # Pasar la instancia de advanced_file_editor_tool
            file_operations_tool, # Pasar la instancia de file_operations_tool
            self.file_create_tool # Pasar la instancia de file_create_tool
        )
        self.agent_interrupted = False # Bandera para la interrupción del agente

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
                if self.agent_interrupted:
                    self.agent_interrupted = False # Resetear la bandera
                    self.terminal_ui.print_message("Agente interrumpido por el usuario. 🛑", style="yellow")
                    self.llm_service.stop_generation_flag = False # Resetear la bandera del LLM
                    # Vaciar la cola de interrupción si hay algo
                    while not self.terminal_ui.get_interrupt_queue().empty():
                        self.terminal_ui.get_interrupt_queue().get_nowait()
                    # No continuar con el procesamiento del input si se interrumpió
                    continue # Volver al prompt principal

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

                if self.meta_command_processor.process_meta_command(user_input):
                    continue

                # Iniciar el ciclo de interacción del agente con la entrada del usuario
                current_user_input = user_input
                
                while True:
                    if self.agent_interrupted:
                        self.terminal_ui.print_message("Agente interrumpido por el usuario. 🛑", style="yellow")
                        self.llm_service.stop_generation_flag = False # Resetear la bandera del LLM
                        # Vaciar la cola de interrupción si hay algo
                        while not self.terminal_ui.get_interrupt_queue().empty():
                            self.terminal_ui.get_interrupt_queue().get_nowait()
                        break # Salir del bucle de ejecución continua del agente

                    if not self.terminal_ui.get_interrupt_queue().empty():
                        while not self.terminal_ui.get_interrupt_queue().empty():
                            self.terminal_ui.get_interrupt_queue().get_nowait() # Vaciar la cola
                        self.terminal_ui.print_message("Generación de respuesta cancelada por el usuario. 🛑", style="yellow")
                        self.llm_service.stop_generation_flag = False # Resetear la bandera
                        break # Salir del bucle de ejecución continua

                    final_state_dict = self.agent_interaction_manager.invoke_agent(current_user_input)
                    current_user_input = None # Las invocaciones subsiguientes no deben usar el input original del usuario

                    # Actualizar el estado del agente con lo que devuelve el manager
                    self.agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')
                    self.agent_state.tool_code_to_confirm = final_state_dict.get('tool_code_to_confirm')
                    self.agent_state.tool_code_tool_name = final_state_dict.get('tool_code_tool_name')
                    self.agent_state.tool_code_tool_args = final_state_dict.get('tool_code_tool_args')
                    self.agent_state.file_update_diff_pending_confirmation = final_state_dict.get('file_update_diff_pending_confirmation')

                    # --- Lógica para manejar confirmaciones pendientes (archivos y comandos) ---
                    if self.agent_state.file_update_diff_pending_confirmation:
                        confirmation_message = self.agent_state.file_update_diff_pending_confirmation.get("action_description", "Se requiere confirmación para una operación de archivo.")
                        self.terminal_ui.print_message(f"Se requiere confirmación para: {confirmation_message}", style="yellow")
                        
                        tool_name_to_confirm = self.agent_state.tool_pending_confirmation
                        tool_args_to_confirm = self.agent_state.tool_args_pending_confirmation
                        raw_tool_output_dict = self.agent_state.file_update_diff_pending_confirmation

                        approval_result = await self.command_approval_handler.handle_command_approval(
                            command_to_execute=f"confirm_action('{confirmation_message}')", # Comando dummy
                            auto_approve=self.auto_approve,
                            is_user_confirmation=False,
                            is_file_update_confirmation=True,
                            confirmation_prompt=confirmation_message,
                            tool_name=tool_name_to_confirm,
                            raw_tool_output=raw_tool_output_dict,
                            original_tool_args=tool_args_to_confirm
                        )

                        tool_message_content = approval_result['tool_message_content']
                        action_approved = approval_result['approved']

                        # Eliminar el ToolMessage anterior de requires_confirmation si existe
                        if self.agent_state.tool_call_id_to_confirm:
                            for i in range(len(self.agent_state.messages) - 1, -1, -1):
                                msg = self.agent_state.messages[i]
                                if isinstance(msg, ToolMessage) and msg.tool_call_id == self.agent_state.tool_call_id_to_confirm:
                                    if "requires_confirmation" in msg.content:
                                        self.agent_state.messages.pop(i)
                                        break

                        tool_message_for_agent = ToolMessage(
                            content=tool_message_content,
                            tool_call_id=self.agent_state.tool_call_id_to_confirm
                        )
                        # Verificar si ya existe un ToolMessage con el mismo tool_call_id
                        if not any(isinstance(msg, ToolMessage) and msg.tool_call_id == tool_message_for_agent.tool_call_id for msg in self.agent_state.messages):
                            self.agent_state.messages.append(tool_message_for_agent)

                        if action_approved:
                            self.terminal_ui.print_message("Acción aprobada por el usuario. El agente procesará la respuesta.", style="green")
                        else:
                            self.terminal_ui.print_message("Acción denegada por el usuario. El agente procesará la respuesta.", style="yellow")
                        
                        self.agent_state.reset_tool_confirmation()
                        self.agent_state.tool_call_id_to_confirm = None
                        continue # Continuar el bucle de ejecución continua para que el agente procese el nuevo estado.

                    elif self.agent_state.command_to_confirm:
                        command_to_execute = self.agent_state.command_to_confirm
                        self.agent_state.command_to_confirm = None # Limpiar después de usar

                        approval_result = await self.command_approval_handler.handle_command_approval(command_to_execute, self.auto_approve)
                        
                        # Actualizar el estado del agente con los mensajes devueltos por el handler
                        tool_message_content = approval_result['tool_message_content']

                        self.terminal_ui.print_message("Procesando salida del comando...", style="cyan")

                        # Asegurar que tool_call_id_to_confirm siempre tenga un valor
                        if self.agent_state.tool_call_id_to_confirm is None:
                            self.agent_state.tool_call_id_to_confirm = f"manual_tool_call_{os.urandom(8).hex()}"
                            self.terminal_ui.print_message(f"Advertencia: tool_call_id_to_confirm era None. Generando ID temporal: {self.agent_state.tool_call_id_to_confirm}", style="yellow")

                        # Eliminar el ToolMessage anterior de requires_confirmation si existe
                        if self.agent_state.tool_call_id_to_confirm:
                            for i in range(len(self.agent_state.messages) - 1, -1, -1):
                                msg = self.agent_state.messages[i]
                                if isinstance(msg, ToolMessage) and msg.tool_call_id == self.agent_state.tool_call_id_to_confirm:
                                    if "requires_confirmation" in msg.content:
                                        self.agent_state.messages.pop(i)
                                        break

                        # Construir el ToolMessage con el tool_call_id correcto
                        tool_message_for_agent = ToolMessage(
                            content=tool_message_content,
                            tool_call_id=self.agent_state.tool_call_id_to_confirm
                        )
                        self.agent_state.messages.append(tool_message_for_agent)

                        continue # Continuar el bucle de ejecución continua para que el agente procese el nuevo estado.
                    
                    elif self.agent_state.tool_call_id_to_confirm:
                        # Si hay un tool_call_id_to_confirm pero no un command_to_confirm o file_update_diff_pending_confirmation,
                        # significa que el agente ha generado una tool_call que no requiere confirmación explícita del usuario
                        # (ej. una herramienta interna que ya se ejecutó y solo necesita que el agente procese su resultado).
                        # En este caso, simplemente continuamos el bucle para que el agente procese el ToolMessage
                        # que ya debería haber sido añadido al historial por la herramienta.
                        continue

                    else:
                        # Si no hay command_to_confirm ni file_update_diff_pending_confirmation ni tool_call_id_to_confirm,
                        # significa que el agente ha terminado su turno o está esperando una nueva instrucción del usuario.
                        break # Salir del bucle de ejecución continua
                
                # Limpiar el estado de confirmación después de que el bucle de ejecución continua haya terminado
                self.agent_state.reset_tool_confirmation()
                self.agent_state.tool_call_id_to_confirm = None

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

        except KeyboardInterrupt:
            self.terminal_ui.print_message("\nSaliendo...", style="yellow")
        except Exception as e:
            self.terminal_ui.print_message(f"Ocurrió un error inesperado: {e}", style="red")
            import traceback
            traceback.print_exc()
        finally:
            # Asegurarse de que el historial se guarde siempre al salir de la aplicación
            self.agent_state.save_history() # Guardar el historial desde AgentState
            self.terminal_ui.print_message("Historial guardado al salir.", style="dim")
            # Asegurarse de que el FileCompleter se limpie al salir
            if self.completer:
                self.completer.dispose()