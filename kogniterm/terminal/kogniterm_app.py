import os
import sys
import re
from dotenv import load_dotenv
from prompt_toolkit import PromptSession, HTML
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
logger.setLevel(logging.INFO)

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
from kogniterm.core.agents.bash_agent import AgentState, UserConfirmationRequired
from kogniterm.core.tools.file_operations_tool import FileOperationsTool
from kogniterm.core.tools.python_executor import PythonTool
from kogniterm.core.tools.advanced_file_editor_tool import AdvancedFileEditorTool # Importar AdvancedFileEditorTool
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage

from kogniterm.terminal.terminal_ui import TerminalUI
from kogniterm.terminal.meta_command_processor import MetaCommandProcessor
from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager
from kogniterm.terminal.command_approval_handler import CommandApprovalHandler

# Importar temas para estilos mejorados
try:
    from kogniterm.terminal.themes import ColorPalette, Icons
    THEMES_AVAILABLE = True
except ImportError:
    THEMES_AVAILABLE = False

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
            # logger.debug("FileCompleter: Bucle de eventos de asyncio obtenido.")
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
                # logger.debug("FileCompleter: Ya hay una carga de archivos en progreso.")
                return # Ya hay una carga en progreso

            if self._loop is None:
                logger.error("FileCompleter: No se puede iniciar la carga en segundo plano, no hay bucle de eventos.")
                return

            # logger.debug("FileCompleter: Iniciando carga de archivos para autocompletado en segundo plano...")
            self._loading_future = self._loop.run_in_executor(
                self._executor, # Usar el ThreadPoolExecutor
                self._do_load_files
            )

    def _do_load_files(self) -> List[str]:
        """Realiza la carga real de archivos de forma síncrona en un hilo secundario."""
        # logger.debug(f"FileCompleter: Ejecutando _do_load_files en hilo: {threading.current_thread().name}")
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
            
            # logger.debug(f"FileCompleter: Cargados {len(all_relative_items)} elementos en la caché.")
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

class KogniTermApp:
    def __init__(self, llm_service: LLMService, command_executor: CommandExecutor, agent_state: AgentState, auto_approve: bool = False, workspace_directory: str = None):
        # Primero crear terminal_ui para que esté disponible
        self.terminal_ui = TerminalUI()
        
        # Usar el llm_service pasado como parámetro y configurarlo
        self.llm_service = llm_service
        self.llm_service.interrupt_queue = self.terminal_ui.get_interrupt_queue()
        self.llm_service.terminal_ui = self.terminal_ui
        
        # Inicializar el resto de atributos
        self.command_executor = command_executor
        self.agent_state = agent_state
        self.file_update_tool = FileUpdateTool()
        self.auto_approve = auto_approve
        self.workspace_directory = workspace_directory
        self.meta_command_processor = MetaCommandProcessor(self.llm_service, self.agent_state, self.terminal_ui, self)
        self.agent_interaction_manager = AgentInteractionManager(self.llm_service, self.agent_state, self.terminal_ui, self.terminal_ui.get_interrupt_queue())

        # Inicializar FileCompleter con el workspace_directory
        file_operations_tool = FileOperationsTool(llm_service=self.llm_service)
        self.completer = FileCompleter(file_operations_tool=file_operations_tool, workspace_directory=self.workspace_directory, show_indicator=False)
        
        # Estado de indexación para la barra de progreso
        self.indexing_status = None


        # Instanciar AdvancedFileEditorTool
        advanced_file_editor_tool = AdvancedFileEditorTool()

        # Definir un estilo mejorado para el prompt usando temas
        if THEMES_AVAILABLE:
            custom_style = Style.from_dict({
                'prompt': ColorPalette.PRIMARY_LIGHT,
                'rprompt': ColorPalette.TEXT_SECONDARY,
                'output': ColorPalette.TEXT_PRIMARY,
                'text': ColorPalette.TEXT_SECONDARY,
            })
        else:
            # Fallback al estilo original
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
            event.app.exit() # Salir del prompt actual, pero no de la aplicación

        # Combinar los KeyBindings
        combined_key_bindings = merge_key_bindings([kb_enter, kb_esc, self.terminal_ui.kb])

        self.prompt_session = PromptSession(
            history=FileHistory('.gemini_interpreter_history'),
            completer=self.completer,
            style=custom_style,
            key_bindings=combined_key_bindings,
            bottom_toolbar=self._get_bottom_toolbar, # Añadir bottom_toolbar
            refresh_interval=0.5 # Refrescar la UI cada 0.5s para actualizar la barra
        )

        self.command_approval_handler = CommandApprovalHandler(
            self.llm_service,
            self.command_executor,
            self.prompt_session,
            self.terminal_ui,
            self.agent_state,
            self.file_update_tool,
            advanced_file_editor_tool, # Pasar la instancia de advanced_file_editor_tool
            file_operations_tool # Pasar la instancia de file_operations_tool
        )

    def _get_bottom_toolbar(self):
        """Genera el contenido de la barra inferior (toolbar)."""
        if self.indexing_status:
            return HTML(f'<style bg="ansiblue" fg="white"> <b>Indexando:</b> {self.indexing_status} </style>')
        return None

    def _update_indexing_progress(self, current, total, description):
        """Callback para actualizar el estado de la indexación."""
        percentage = int((current / total) * 100) if total > 0 else 0
        self.indexing_status = f"{description} ({percentage}%)"
        # Forzar redibujado de la aplicación si es posible (prompt_toolkit lo hace con refresh_interval)

    def _process_file_tags(self, text: str) -> str:
        """
        Detecta etiquetas @archivo en el texto y reemplaza la etiqueta con el contenido del archivo.
        Esto permite al usuario referenciar archivos rápidamente para que el LLM los lea.
        """
        # Patrón para capturar @ruta/al/archivo
        # Se detiene ante espacios o fin de cadena.
        pattern = r'@(?P<path>[^\s]+)'
        
        # Función de reemplazo para re.sub
        def replace_match(match):
            file_path = match.group('path')
            # Resolver ruta relativa al CWD actual
            full_path = os.path.abspath(os.path.join(os.getcwd(), file_path))
            
            if os.path.isfile(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    self.terminal_ui.print_message(f"  📄 Inyectando contenido de: {file_path}", style="dim")
                    # Formatear el contenido para que el LLM lo entienda claramente
                    return f"\n\n--- CONTENIDO DEL ARCHIVO: {file_path} ---\n{content}\n--- FIN DEL ARCHIVO ---\n\n"
                except Exception as e:
                    self.terminal_ui.print_message(f"  ⚠️ Error al leer '{file_path}': {e}", style="red")
                    return match.group(0)
            else:
                return match.group(0)

        return re.sub(pattern, replace_match, text)

    async def _run_background_indexing(self):
        """Runs the codebase indexing in the background."""
        from kogniterm.core.context.codebase_indexer import CodebaseIndexer
        from kogniterm.core.context.vector_db_manager import VectorDBManager
        
        self.terminal_ui.print_message("Iniciando indexación del codebase en segundo plano... 🚀", style="cyan")
        
        vector_db = None
        try:
            indexer = CodebaseIndexer(self.workspace_directory)
            vector_db = VectorDBManager(self.workspace_directory)
            
            # Run async indexing silently but with callback
            chunks = await indexer.index_project(
                self.workspace_directory,
                show_progress=False,
                progress_callback=self._update_indexing_progress
            )
            
            if chunks:
                self.indexing_status = "Guardando en DB..."
                # Run vector db update in a thread to avoid blocking
                await asyncio.to_thread(vector_db.clear_collection)
                await asyncio.to_thread(vector_db.add_chunks, chunks)
                
                self.terminal_ui.print_message("¡Indexación en segundo plano completada con éxito! 🧠✨", style="green")
            else:
                self.terminal_ui.print_message("Indexación finalizada: No se encontraron archivos relevantes.", style="dim")
                
        except Exception as e:
            self.terminal_ui.print_message(f"Error durante la indexación en segundo plano: {e}", style="red")
        finally:
            if vector_db:
                vector_db.close()
            self.indexing_status = None # Limpiar estado al finalizar


    async def run(self): # Make run() async
        """Runs the main loop of the KogniTerm application."""
        self.terminal_ui.print_welcome_banner()

        if self.auto_approve:
            self.terminal_ui.print_message("Modo de auto-aprobación activado.", style="yellow")
        
        # --- Prompt for Codebase Indexing ---
        if self.workspace_directory:
            try:
                from kogniterm.core.context.vector_db_manager import VectorDBManager
                vector_db_check = VectorDBManager(self.workspace_directory)
                is_indexed = vector_db_check.is_indexed()
                
                prompt_msg = "¿Desea indexar el contenido de este directorio para búsquedas inteligentes? (s/n): "
                if is_indexed:
                    prompt_msg = "El directorio ya parece estar indexado. ¿Desea RE-INDEXAR? (s/n): "

                should_index = await self.prompt_session.prompt_async(prompt_msg)
                
                if should_index.lower().strip() == 's':
                    # Start background task
                    asyncio.create_task(self._run_background_indexing())
                    self.terminal_ui.print_message("La indexación se ejecutará en segundo plano. Ver barra inferior.", style="dim")
            except Exception as e:
                self.terminal_ui.print_message(f"Error al iniciar la indexación: {e}", style="red")
        # ------------------------------------

        try: # Mover el try para que englobe todo el bucle principal
            # No es necesario detectar cambios de directorio en el bucle si el historial es por directorio.
            # El historial se carga una vez al inicio del KogniTermApp para el CWD.
            # Si el usuario cambia de directorio usando 'cd', se iniciará una nueva instancia de KogniTermApp
            # o se deberá manejar explícitamente el cambio de directorio en una futura mejora.
            while True:
                cwd = os.getcwd() # Obtener el CWD actual para el prompt
                # Crear el prompt usando HTML de prompt_toolkit (no Rich markup)
                # prompt_toolkit usa HTML-like tags, no Rich markup
                from prompt_toolkit import HTML
                if THEMES_AVAILABLE:
                    # Usar HTML de prompt_toolkit con colores hexadecimales (sin emoji de robot)
                    prompt_text = HTML(f'<style fg="{ColorPalette.SECONDARY}">({os.path.basename(cwd)})</style> <style fg="{ColorPalette.PRIMARY}">›</style> ')
                else:
                    prompt_text = f"({os.path.basename(cwd)}) › "
                user_input = await self.prompt_session.prompt_async(prompt_text) # Use prompt_async

                if user_input is None:
                    if not self.terminal_ui.get_interrupt_queue().empty():
                        while not self.terminal_ui.get_interrupt_queue().empty():
                            self.terminal_ui.get_interrupt_queue().get_nowait() # Vaciar la cola
                        self.terminal_ui.print_message("Generación de respuesta cancelada por el usuario", style="yellow", status="warning")
                        self.llm_service.stop_generation_flag = False # Resetear la bandera
                        continue # Continuar el bucle para un nuevo prompt
                    else:
                        # Si user_input es None y no se ha establecido la bandera de stop_generation_flag,
                        # significa que el usuario ha salido del prompt de alguna otra manera (ej. Ctrl+D).
                        # En este caso, salimos de la aplicación.
                        break

                if not user_input.strip():
                    continue

                # Si el usuario ingresa un comando, se imprime como mensaje de usuario.
                # Si el agente propone un comando, no se imprime aquí, se maneja en CommandApprovalHandler.
                # Se determina si es un comando propuesto por el agente si self.agent_state.command_to_confirm es True.
                if not self.agent_state.command_to_confirm:
                    self.terminal_ui.print_message(user_input, is_user_message=True)

                # Limpiar el input después de enviar el mensaje
                self.prompt_session.app.current_buffer.text = ""
                self.prompt_session.app.current_buffer.cursor_position = 0

                if self.meta_command_processor.process_meta_command(user_input):
                    continue

                # Procesar etiquetas @archivo para inyectar contenido
                enhanced_user_input = self._process_file_tags(user_input)

                # Añadir el mensaje del usuario al historial del agente
                user_human_message = HumanMessage(content=enhanced_user_input)
                self.agent_state.messages.append(user_human_message)

                final_state_dict = self.agent_interaction_manager.invoke_agent(enhanced_user_input)
                
                # Actualizar el estado del agente con lo que devuelve el manager
                self.agent_state.messages = final_state_dict.get('messages', self.agent_state.messages)
                self.agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')
                self.agent_state.tool_call_id_to_confirm = final_state_dict.get('tool_call_id_to_confirm') # <<--- FIX: Propagar el ID del tool call

                # --- NUEVA LÓGICA PARA MANEJAR CONFIRMACIONES PENDIENTES ---
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

                    tool_message_for_agent = ToolMessage(
                        content=tool_message_content,
                        tool_call_id=f"confirmation_response_{os.urandom(8).hex()}"
                    )
                    self.agent_state.messages.append(tool_message_for_agent)
                    self.llm_service.conversation_history.append(tool_message_for_agent)

                    if action_approved:
                        self.terminal_ui.print_message("Acción aprobada por el usuario. El agente procesará la respuesta.", style="green")
                        self.terminal_ui.print_message("El agente continuará su flujo...", style="cyan")
                        self.agent_state.messages.append(HumanMessage(content="La herramienta anterior se ejecutó con éxito. Por favor, continúa con la tarea."))
                        final_state_after_reinvocation = self.agent_interaction_manager.invoke_agent("Procesa la salida de la herramienta que acaba de ser añadida al historial.")
                        
                        self.agent_state.reset_tool_confirmation()
                        self.agent_state.tool_call_id_to_confirm = None
                    else:
                        self.terminal_ui.print_message("Acción denegada por el usuario. El agente procesará la respuesta.", style="yellow")
                    
                    self.agent_state.reset_tool_confirmation()
                    self.agent_state.tool_call_id_to_confirm = None
                    continue # Reiniciar el bucle principal para que el agente procese el nuevo estado.
                # --- FIN DE LA NUEVA LÓGICA ---

                if self.agent_state.command_to_confirm:
                    command_to_execute = self.agent_state.command_to_confirm
                    self.agent_state.command_to_confirm = None # Limpiar después de usar


                    approval_result = await self.command_approval_handler.handle_command_approval(command_to_execute, self.auto_approve)
                    
                    # El ToolMessage ya fue añadido por CommandApprovalHandler al historial
                    # No es necesario sobrescribir agent_state.messages aquí
                    tool_message_content = approval_result['tool_message_content']

                    # Re-invocar al agente para procesar la salida de la herramienta
                    self.terminal_ui.print_message("Procesando salida del comando...", style="cyan", status="info")
                    
                    # Asegurar que tool_call_id_to_confirm siempre tenga un valor
                    if self.agent_state.tool_call_id_to_confirm is None:
                        self.agent_state.tool_call_id_to_confirm = f"manual_tool_call_{os.urandom(8).hex()}"
                        self.terminal_ui.print_message(f"Advertencia: tool_call_id_to_confirm era None. Generando ID temporal: {self.agent_state.tool_call_id_to_confirm}", style="yellow")

                    # El ToolMessage ya fue añadido por CommandApprovalHandler, no es necesario añadirlo de nuevo.
                    # Invocar al agente para que procese el ToolMessage que está en el historial
                    self.agent_interaction_manager.invoke_agent(None) # Invocar al agente sin un HumanMessage adicional
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
                elif isinstance(final_response_message, ToolMessage): # Para cualquier otra ToolMessage
                    self.terminal_ui.print_message(f"Herramienta '{final_response_message.tool_call_id}' ejecutada.", style="green")
                    continue
        except Exception as e:
            self.terminal_ui.print_message(f"Ocurrió un error inesperado: {e}", style="red")
            import traceback
            traceback.print_exc()
        finally:
            # Asegurarse de que el historial se guarde siempre al salir de la aplicación
            self.llm_service._save_history(self.llm_service.conversation_history)
            self.terminal_ui.print_message("Historial guardado al salir.", style="dim")
            # Asegurarse de que el FileCompleter se limpie al salir
            if self.completer:
                self.completer.dispose()

        