import os
import sys
import re
import subprocess
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
import signal

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
        ".*/", "*/.*/",
        "*.pyc", "*.tmp", "*.log", ".env", ".DS_Store", "*.swp", "*.bak", "*.old", "*.fuse_hidden*",
        "node_modules/", "dist/", "out/", "coverage/", ".mypy_cache/", ".pytest_cache/",
    ]

    def __init__(self, skill_manager, workspace_directory: str, show_indicator: bool = True):
        self.skill_manager = skill_manager
        self.workspace_directory = workspace_directory
        self.show_indicator = show_indicator
        self._cached_files: Optional[List[str]] = None
        self._cached_containers: Optional[List[str]] = None
        self.cache_lock = threading.Lock()
        self._loading_future: Optional[concurrent.futures.Future] = None
        self._loading_containers_future: Optional[concurrent.futures.Future] = None
        try:
            self._loop = asyncio.get_event_loop()
            # logger.debug("FileCompleter: Bucle de eventos de asyncio obtenido.")
        except RuntimeError:
            logger.warning("FileCompleter: No hay un bucle de eventos de asyncio corriendo. Esto puede causar problemas.")
            self._loop = None # O manejar de otra forma si no hay loop
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2) # Aumentado a 2 para manejar Docker

        self._start_background_load_files() # Iniciar la carga inicial en segundo plano
        self._start_background_load_containers() # Iniciar la carga de contenedores

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
        try:
            all_relative_items = []
            for root, dirs, files in os.walk(self.workspace_directory):
                # Filtrar directorios ocultos y excluidos
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in (
                    'venv', '__pycache__', 'node_modules', 'build', 'dist',
                    'out', 'coverage', '.mypy_cache', '.pytest_cache',
                    'kogniterm.egg-info', '.git',
                )]
                rel_root = os.path.relpath(root, self.workspace_directory)
                if rel_root == ".":
                    rel_root = ""
                for d in dirs:
                    rel_path = os.path.join(rel_root, d) + os.sep if rel_root else d + os.sep
                    if not any(fnmatch.fnmatch(rel_path, pattern) for pattern in self.EXCLUDE_PATTERNS):
                        all_relative_items.append(rel_path)
                for f in files:
                    rel_path = os.path.join(rel_root, f) if rel_root else f
                    if not f.startswith('.') and not any(
                        f.endswith(ext) for ext in ('.pyc', '.tmp', '.log', '.swp', '.bak', '.old')
                    ):
                        if not any(fnmatch.fnmatch(rel_path, pattern) for pattern in self.EXCLUDE_PATTERNS):
                            all_relative_items.append(rel_path)

            with self.cache_lock:
                self._cached_files = all_relative_items
            return all_relative_items
        except Exception as e:
            logger.error(f"FileCompleter: Error al cargar archivos en segundo plano: {e}", exc_info=True)
            with self.cache_lock:
                self._cached_files = []
            return []

    def _start_background_load_containers(self):
        """Inicia la carga de contenedores Docker en un hilo secundario."""
        with self.cache_lock:
            if self._loading_containers_future is not None and not self._loading_containers_future.done():
                return 

            if self._loop is None:
                return

            self._loading_containers_future = self._loop.run_in_executor(
                self._executor,
                self._do_load_containers
            )

    def _do_load_containers(self) -> List[str]:
        """Obtiene la lista de contenedores Docker."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True, text=True, check=True
            )
            containers = [c.strip() for c in result.stdout.split('\n') if c.strip()]
            with self.cache_lock:
                self._cached_containers = containers
            return containers
        except Exception as e:
            logger.error(f"FileCompleter: Error al cargar contenedores Docker: {e}")
            with self.cache_lock:
                self._cached_containers = []
            return []

    MAGIC_COMMANDS = [
        ("/help", "Mostrar menú de ayuda interactivo"),
        ("/models", "Cambiar modelo de IA"),
        ("/provider", "Cambiar proveedor de LLM"),
        ("/reset", "Reiniciar conversación"),
        ("/undo", "Deshacer última acción"),
        ("/compress", "Resumir historial"),
        ("/theme", "Cambiar tema de colores"),
        ("/tema", "Cambiar tema de colores (alias)"),
        ("/init", "Inicializar contexto"),
        ("/keys", "Gestionar API Keys"),
        ("/session", "Gestión de sesiones"),
        ("/instructions", "Instrucciones del agente (global/workspace)"),
        ("/instruct", "Instrucciones del agente (alias)"),
        ("/resume", "Reanudar sesión guardada"),
        ("/skills", "Listar todas las skills disponibles"),
        ("/salir", "Salir de KogniTerm"),
        ("/mouse", "Alternar ratón"),
        ("/summarize", "Resumir historial para mejorar contexto"),
        ("/reasoning", "Ajustar nivel de razonamiento"),
        ("/summarymodel", "Cambiar modelo de resumen"),
        ("/embeddings", "Configurar embeddings"),
        ("/insights", "Analítica de uso")
    ]

    SESSION_SUBCOMMANDS = [
        ("list", "Listar sesiones guardadas"),
        ("save", "Guardar sesión actual"),
        ("load", "Cargar una sesión"),
        ("new", "Crear nueva sesión"),
        ("delete", "Eliminar una sesión")
    ]

    def get_completions(self, document, complete_event):
        text_before_cursor = document.text_before_cursor
        word_before_cursor = document.get_word_before_cursor(WORD=True)
        
        # 1. Autocompletado de Comandos Mágicos (/)
        if text_before_cursor.lstrip().startswith('/') or word_before_cursor.startswith('/'):
            stripped_text = text_before_cursor.lstrip()
            
            # Caso especial para subcomandos de /session
            if stripped_text.startswith('/session '):
                parts = stripped_text.split()
                # Si estamos escribiendo el subcomando (ej: "/session sa")
                if len(parts) == 2 and not stripped_text.endswith(' '):
                    current_subcmd = parts[1]
                    for subcmd, desc in self.SESSION_SUBCOMMANDS:
                        if subcmd.startswith(current_subcmd):
                            yield Completion(subcmd, start_position=-len(current_subcmd), display_meta=desc)
                    return
                # Si acabamos de escribir "/session " y queremos ver opciones
                elif len(parts) == 1 and stripped_text.endswith(' '):
                     for subcmd, desc in self.SESSION_SUBCOMMANDS:
                        yield Completion(subcmd, start_position=0, display_meta=desc)
                     return

            # Autocompletado de nombres de sesiones para /resume
            if stripped_text.startswith('/resume '):
                parts = stripped_text.split()
                try:
                    from kogniterm.core.session_manager import SessionManager
                    session_manager = SessionManager(self.workspace_directory or os.getcwd())
                    names = [session["name"] for session in session_manager.list_sessions()]
                except Exception:
                    names = []

                # Si estamos escribiendo el nombre (ej: "/resume proyecto")
                if len(parts) == 2 and not stripped_text.endswith(' '):
                    current_name = parts[1]
                    for name in names:
                        if name.startswith(current_name):
                            yield Completion(name, start_position=-len(current_name), display_meta='Sesión guardada')
                    return

                # Si acabamos de escribir "/resume " y queremos ver opciones
                if len(parts) == 1 and stripped_text.endswith(' '):
                    for name in names:
                        yield Completion(name, start_position=0, display_meta='Sesión guardada')
                    return

            # Determinar qué parte está escribiendo el usuario (comando principal)
            if ' ' not in stripped_text: # Solo si es la primera palabra
                current_input = stripped_text

                # Construir lista completa: comandos fijos + skills dinámicas del SkillManager
                all_commands = list(self.MAGIC_COMMANDS)
                if self.skill_manager:
                    try:
                        for skill_info in self.skill_manager.list_skills():
                            s_name = skill_info['name']
                            s_desc = skill_info.get('description', '')
                            s_loaded = skill_info.get('loaded', False)
                            icon = "✅" if s_loaded else "⏸"
                            entry = (f"/{s_name}", f"{icon} Skill: {s_desc[:40]}")
                            # Evitar duplicados con comandos del sistema
                            if not any(cmd == entry[0] for cmd, _ in all_commands):
                                all_commands.append(entry)
                    except Exception:
                        pass

                matches = [cmd for cmd, desc in all_commands if cmd.startswith(current_input)]
                # Si hay un único match y es exacto, no mostrar autocompletado
                if len(matches) == 1 and matches[0] == current_input:
                    return
                
                for cmd, desc in all_commands:
                    if cmd.startswith(current_input):
                        yield Completion(cmd, start_position=-len(current_input), display_meta=desc)
                return # Si estamos completando un comando, no buscamos archivos

        # 2. Autocompletado de Archivos (@)
        if '@' in text_before_cursor:
            current_input_part = text_before_cursor.split('@')[-1]

            # Intentar obtener los archivos de la caché
            with self.cache_lock:
                cached_files = self._cached_files

            if cached_files is None:
                if self._loading_future is None or self._loading_future.done():
                    self._start_background_load_files()
                if self.show_indicator:
                    yield Completion("(Cargando archivos...)", start_position=-len(current_input_part))
                return

            query = current_input_part.lower()

            # Detectar si el usuario está navegando en un subdirectorio (contiene '/')
            # En ese caso filtramos por prefijo de ruta
            path_prefix = ""
            basename_query = query
            if '/' in query:
                # Separar el prefijo de directorio de la parte de nombre a buscar
                path_prefix = query.rsplit('/', 1)[0] + '/'
                basename_query = query.rsplit('/', 1)[1]

            scored: List[tuple] = []  # (score, display_item, meta)
            for relative_item_path in cached_files:
                absolute_item_path = os.path.join(self.workspace_directory, relative_item_path)
                is_dir = os.path.isdir(absolute_item_path)
                display_item = relative_item_path
                if is_dir and not display_item.endswith('/'):
                    display_item += '/'

                display_lower = display_item.lower()

                # --- Filtro por prefijo de directorio ---
                if path_prefix and not display_lower.startswith(path_prefix):
                    continue

                # El segmento a evaluar: si hay prefijo, usar solo la parte tras él
                segment = display_lower[len(path_prefix):] if path_prefix else display_lower
                base_name = os.path.basename(display_item.rstrip('/')).lower()

                if not basename_query:
                    # Sin query de nombre → mostrar todo en el directorio actual
                    score = 100 if is_dir else 50
                elif base_name == basename_query or base_name.rstrip('/') == basename_query.rstrip('/'):
                    score = 200  # Coincidencia exacta en el nombre base
                elif base_name.startswith(basename_query):
                    score = 150  # Prefijo en el nombre base
                elif basename_query in base_name:
                    score = 100  # Subcadena en el nombre base
                elif basename_query in segment:
                    score = 50   # Subcadena en el path completo
                else:
                    continue  # No coincide

                # Bonus: directorios primero, archivos relevantes después
                if is_dir:
                    score += 10

                # Penalizar rutas muy largas/profundas para preferir lo más cercano
                depth = display_item.count('/')
                score -= depth

                # Meta: tipo de archivo
                ext = os.path.splitext(display_item)[1]
                if is_dir:
                    meta = "📁 dir"
                elif ext in ('.py',):
                    meta = "🐍 python"
                elif ext in ('.md', '.rst', '.txt'):
                    meta = "📝 texto"
                elif ext in ('.json', '.yaml', '.yml', '.toml', '.ini', '.env'):
                    meta = "⚙️ config"
                elif ext in ('.js', '.ts', '.jsx', '.tsx'):
                    meta = "🌐 js/ts"
                elif ext in ('.sh', '.bash'):
                    meta = "🖥️ shell"
                elif ext in ('.html', '.css'):
                    meta = "🎨 web"
                else:
                    meta = ext if ext else "📄 archivo"

                scored.append((-score, display_item, meta))

            # Ordenar por score descendente, luego alfabéticamente
            scored.sort(key=lambda x: (x[0], x[1]))

            # Limitar resultados para no saturar el menú
            MAX_COMPLETIONS = 30
            results = scored[:MAX_COMPLETIONS]

            # Si hay un único match y es exacto, no mostrar autocompletado
            if len(results) == 1:
                only = results[0][1]
                if only == current_input_part or only.rstrip('/') == current_input_part.rstrip('/'):
                    return

            for _, suggestion, meta in results:
                yield Completion(
                    suggestion,
                    start_position=-len(current_input_part),
                    display_meta=meta,
                )

        # 3. Autocompletado de Docker (:)
        if ':' in text_before_cursor:
            # Solo si el ':' no es parte de una ruta de archivo (ej. C:\ o similar en Windows, aunque aquí es Linux)
            # O si está al inicio de una palabra o después de un espacio
            parts = text_before_cursor.split(':')
            current_input_part = parts[-1]
            
            # Verificar si el ':' está precedido por un espacio o es el inicio
            if len(parts) > 1 and (text_before_cursor.endswith(':' + current_input_part)):
                with self.cache_lock:
                    cached_containers = self._cached_containers
                
                if cached_containers is None:
                    if self._loading_containers_future is None or self._loading_containers_future.done():
                        self._start_background_load_containers()
                    return

                matches = [c for c in cached_containers if current_input_part.lower() in c.lower()]
                # Si hay un único match y es exacto, no mostrar autocompletado
                if len(matches) == 1 and matches[0].lower() == current_input_part.lower():
                    return

                for container in matches:
                    yield Completion(container, start_position=-len(current_input_part), display_meta="Docker Container")

    def dispose(self):
        """Detiene el FileSystemWatcher y el ThreadPoolExecutor cuando la aplicación se cierra."""
        if self._executor:
            # wait=False prevents hanging if threads are blocked
            if sys.version_info >= (3, 9):
                self._executor.shutdown(wait=False, cancel_futures=True)
            else:
                self._executor.shutdown(wait=False)
            # print("ThreadPoolExecutor de autocompletado detenido.")


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
        self.workspace_directory = workspace_directory
        self.meta_command_processor = MetaCommandProcessor(self.llm_service, self.agent_state, self.terminal_ui, self)
        
        # Obtener herramientas desde ToolManager
        self.file_update_tool = self.llm_service.get_tool("file_update")
        file_operations_tool = self.llm_service.get_tool("file_operations")
        advanced_file_editor_tool = self.llm_service.get_tool("advanced_file_editor")

        # Inicializar SessionManager
        from kogniterm.core.session_manager import SessionManager
        self.session_manager = SessionManager(self.workspace_directory or os.getcwd())

        # Inicializar FileCompleter con el workspace_directory
        self.completer = FileCompleter(skill_manager=self.llm_service.skill_manager, workspace_directory=self.workspace_directory, show_indicator=False)
        
        # Estado de indexación para la barra de progreso
        self.indexing_status = None

        # Configurar manejadores de señales para redimensionamiento
        self._setup_signal_handlers()



        
        # Definir un estilo mejorado para el prompt usando temas (antes de prompt_session)
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

        # KeyBindings para la tecla Esc
        kb_esc = KeyBindings()
        @kb_esc.add('escape', eager=True)
        def _(event):
            # Enviar una señal de interrupción a la cola y establecer bandera de parada
            self.terminal_ui.get_interrupt_queue().put_nowait(True)
            self.llm_service.stop_generation_flag = True
            # Limpiar el buffer del prompt
            event.app.current_buffer.text = ""
            event.app.current_buffer.cursor_position = 0
            # Salir del prompt actual para que el bucle principal procese la interrupción
            event.app.exit() 

        # KeyBinding para conmutar auto-aprobación con Shift+Tab (s-tab)
        @self.terminal_ui.kb.add('s-tab', eager=True)
        def _(event):
            if hasattr(self, 'command_approval_handler'):
                old_state = self.command_approval_handler.auto_approve
                self.command_approval_handler.auto_approve = not self.command_approval_handler.auto_approve
                new_state = self.command_approval_handler.auto_approve
                # Mostrar feedback visual en la consola
                state_text = "ACTIVADO" if new_state else "DESACTIVADO"
                color = ColorPalette.SUCCESS if new_state else ColorPalette.ERROR
                self.terminal_ui.print_message(
                    f"Auto-aprobación {state_text} [dim](Shift+Tab para alternar)[/dim]",
                    style=f"bold {color}"
                )
                # Invalidar la aplicación para forzar el refresco de la barra de herramientas
                event.app.invalidate()

        # Combinar los KeyBindings (eliminamos kb_enter que causaba conflictos)
        combined_key_bindings = merge_key_bindings([kb_esc, self.terminal_ui.kb])

        # Crear prompt_session ANTES de command_approval_handler
        self.prompt_session = PromptSession(
            history=FileHistory('.gemini_interpreter_history'),
            completer=self.completer,
            style=custom_style,
            key_bindings=combined_key_bindings,
            bottom_toolbar=self._get_bottom_toolbar, # Añadir bottom_toolbar
            refresh_interval=0.5, # Refrescar la UI cada 0.5s para actualizar la barra
            erase_when_done=True
        )
        
        # Ahora podemos crear CommandApprovalHandler
        self.command_approval_handler = CommandApprovalHandler(
            self.llm_service,
            self.command_executor,
            self.prompt_session,
            self.terminal_ui,
            self.agent_state,
            self.file_update_tool,
            advanced_file_editor_tool,
            file_operations_tool
        )
        # Sincronizar el estado inicial de auto-aprobación
        self.command_approval_handler.auto_approve = auto_approve
        
        # Inyectar el manejador en el SkillManager y en CallAgentTool para que CrewAI pueda usarlo
        if hasattr(self.llm_service, 'skill_manager'):
            self.llm_service.skill_manager.approval_handler = self.command_approval_handler
            call_agent_tool = self.llm_service.get_tool("call_agent")
            if call_agent_tool:
                call_agent_tool.approval_handler = self.command_approval_handler
        
        # Ahora podemos inicializar AgentInteractionManager con el command_approval_handler
        self.agent_interaction_manager = AgentInteractionManager(
            self.llm_service, 
            self.agent_state, 
            self.terminal_ui, 
            self.terminal_ui.get_interrupt_queue(),
            self.command_approval_handler
        )
        
    def _auto_save_session(self):
        """Guarda automáticamente la sesión actual si hay mensajes."""
        if not self.session_manager:
            return
            
        history = self.llm_service.conversation_history
        if not history:
            return
            
        # Si no hay sesión activa, generar una
        if not self.session_manager.current_session_name:
            # Solo generar si hay al menos un mensaje humano (inicio real de charla)
            has_human = any(isinstance(m, HumanMessage) for m in history)
            if has_human:
                new_name = self.session_manager.generate_autosave_name(history)
                self.session_manager.current_session_name = new_name
                logger.info(f"Sesión iniciada automáticamente: {new_name}")
        
        # Guardar si hay un nombre activo
        if self.session_manager.current_session_name:
            self.session_manager.save_session(self.session_manager.current_session_name, history)


    def _setup_signal_handlers(self):
        """Configura los manejadores de señales para la aplicación."""
        if sys.platform != "win32":
            # Capturar señal de cambio de tamaño de ventana (Linux/macOS)
            try:
                loop = asyncio.get_event_loop()
                # Usar loop.add_signal_handler es la forma correcta en asyncio
                loop.add_signal_handler(signal.SIGWINCH, self._handle_sigwinch_async)
            except Exception as e:
                # Fallback al manejador estándar de signal si el loop no es compatible
                try:
                    signal.signal(signal.SIGWINCH, self._handle_sigwinch)
                except Exception as e2:
                    logger.warning(f"No se pudo configurar el manejador de SIGWINCH: {e2}")

    def _handle_sigwinch_async(self):
        """Versión asíncrona del manejador de redimensionamiento."""
        self._handle_sigwinch(None, None)

    def _handle_sigwinch(self, signum, frame):
        """Maneja la señal de redimensionamiento de la ventana."""
        if hasattr(self, 'terminal_ui'):
            self.terminal_ui.handle_resize()
            # Forzar el redibujado de prompt_toolkit para que recalculen posiciones
            if hasattr(self, 'prompt_session') and self.prompt_session.app:
                # invalidate() provoca que la UI se redibuje en el siguiente ciclo
                self.prompt_session.app.invalidate()


    def _get_bottom_toolbar(self):
        """Genera el contenido de la barra inferior (toolbar)."""
        model_name = self.llm_service.model_name
        # Limpiar el nombre del modelo para que se vea mejor (quitar prefijos largos si es necesario)
        display_model = model_name.replace("openrouter/", "OR/").replace("google/", "G/").replace("openai/", "OAI/").replace("anthropic/", "ANT/")
        
        # Colores y texto para auto-aprobación
        is_auto = self.command_approval_handler.auto_approve if hasattr(self, 'command_approval_handler') else False
        if THEMES_AVAILABLE:
            approve_color = ColorPalette.SUCCESS if is_auto else ColorPalette.ERROR
        else:
            approve_color = "#00ff00" if is_auto else "#ff0000"
            
        approve_text = "ON" if is_auto else "OFF"
        
        # Construir el contenido HTML para la barra
        html_content = f' 🤖 {display_model} | '
        html_content += f'Auto-Approve: <style fg="{approve_color}">[{approve_text}]</style> (Shift+Tab)'
        
        if self.indexing_status:
            html_content += f' | Indexando: {self.indexing_status} '
            
        return HTML(f'<style bg="#333333" fg="#ffffff">{html_content}</style>')

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

    def _process_docker_tags(self, text: str) -> str:
        """
        Detecta etiquetas :contenedor en el texto e inyecta información del contenedor.
        """
        pattern = r':(?P<container>[a-zA-Z0-9_-]+)'
        
        def replace_match(match):
            container_name = match.group('container')
            try:
                # Obtener estado y logs básicos
                inspect_res = subprocess.run(
                    ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
                    capture_output=True, text=True
                )
                if inspect_res.returncode != 0:
                    return match.group(0) # No es un contenedor válido o error
                
                status = inspect_res.stdout.strip()
                
                logs_res = subprocess.run(
                    ["docker", "logs", "--tail", "20", container_name],
                    capture_output=True, text=True
                )
                logs = logs_res.stdout.strip() or logs_res.stderr.strip() or "No hay logs recientes."
                
                self.terminal_ui.print_message(f"  🐳 Inyectando info de contenedor: {container_name}", style="blue")
                return f"\n\n--- INFO DOCKER: {container_name} ---\nEstado: {status}\nÚltimos 20 logs:\n{logs}\n--- FIN INFO DOCKER ---\n\n"
            except Exception as e:
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

        if self.command_approval_handler.auto_approve:
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
                
                # Actualizar el título de la terminal
                sys.stdout.write(f"\033]0;KogniTerm - {cwd}\007")
                sys.stdout.flush()
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
                # Limpiar el input después de recibirlo
                if hasattr(self.prompt_session, "app") and self.prompt_session.app:
                    self.prompt_session.app.current_buffer.text = ""
                    self.prompt_session.app.current_buffer.cursor_position = 0

                if await self.meta_command_processor.process_meta_command(user_input):
                    continue

                # Si el usuario ingresa un comando, se imprime como mensaje de usuario.
                # Si el agente propone un comando, no se imprime aquí, se maneja en CommandApprovalHandler.
                if not self.agent_state.command_to_confirm:
                    self.terminal_ui.print_message(user_input, is_user_message=True)

                # Procesar etiquetas @archivo para inyectar contenido
                enhanced_user_input = self._process_file_tags(user_input)
                # Procesar etiquetas :contenedor para inyectar info de Docker
                enhanced_user_input = self._process_docker_tags(enhanced_user_input)

                # Añadir el mensaje del usuario al historial del agente
                user_human_message = HumanMessage(content=enhanced_user_input)
                self.agent_state.messages.append(user_human_message)

                agent_query = enhanced_user_input
                
                # --- BUCLE DE TRABAJO DEL AGENTE ---
                # Este bucle permite que el agente realice múltiples acciones encadenadas
                # y maneje múltiples confirmaciones antes de volver a pedir input al usuario.
                while True:
                    final_state_dict = self.agent_interaction_manager.invoke_agent(agent_query)
                    
                    # Actualizar el estado del agente con lo que devuelve el manager
                    self.agent_state.messages = final_state_dict.get('messages', self.agent_state.messages)
                    self.agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')
                    self.agent_state.tool_call_id_to_confirm = final_state_dict.get('tool_call_id_to_confirm')
                    self.agent_state.file_update_diff_pending_confirmation = final_state_dict.get('file_update_diff_pending_confirmation')
                    self.agent_state.tool_pending_confirmation = final_state_dict.get('tool_pending_confirmation')
                    self.agent_state.tool_args_pending_confirmation = final_state_dict.get('tool_args_pending_confirmation')

                    # 1. Manejar confirmaciones de archivos/planes
                    if self.agent_state.file_update_diff_pending_confirmation:
                        raw_tool_output_dict = self.agent_state.file_update_diff_pending_confirmation
                        confirmation_message = raw_tool_output_dict.get("action_description", "Se requiere confirmación.")
                        
                        approval_result = self.command_approval_handler.handle_command_approval(
                            command_to_execute=f"confirm_action('{confirmation_message}')",
                            auto_approve=self.command_approval_handler.auto_approve,
                            is_user_confirmation=False,
                            is_file_update_confirmation=True,
                            confirmation_prompt=confirmation_message,
                            tool_name=self.agent_state.tool_pending_confirmation,
                            raw_tool_output=raw_tool_output_dict,
                            original_tool_args=self.agent_state.tool_args_pending_confirmation
                        )

                        if approval_result['approved']:
                            # Continuar desde el historial (ToolMessage ya añadido por handler)
                            self.agent_state.reset_tool_confirmation()
                            continue
                        else:
                            self.terminal_ui.print_message("Acción denegada.", style="yellow")
                            self.agent_state.reset_tool_confirmation()
                            break # Volver al input del usuario tras denegación

                    # 2. Manejar confirmaciones de comandos bash
                    if self.agent_state.command_to_confirm:
                        command_to_execute = self.agent_state.command_to_confirm
                        self.agent_state.command_to_confirm = None # Limpiar
                        
                        approval_result = self.command_approval_handler.handle_command_approval(
                            command_to_execute, self.command_approval_handler.auto_approve
                        )
                        
                        if approval_result['approved']:
                            agent_query = None # Continuar desde el historial
                            continue
                        else:
                            self.terminal_ui.print_message("Comando no ejecutado.", style="yellow")
                            break # Volver al input del usuario

                    # Si llegamos aquí, no hay más confirmaciones pendientes para esta ronda
                    break
                
                # --- FIN DEL BUCLE DE TRABAJO ---
                self.llm_service._save_history(self.llm_service.conversation_history)
                self._auto_save_session()

                # Manejo de la salida de PythonTool
                final_response_message = self.agent_state.messages[-1]
                if isinstance(final_response_message, ToolMessage) and final_response_message.tool_call_id == "python_executor":
                    try:
                        from kogniterm.skills.bundled.python_executor.scripts.tool import _get_last_structured_output
                        structured_output_raw = _get_last_structured_output()
                        
                        # Re-formatear para que coincida con lo que espera la UI (un dict con "result")
                        structured_output = {"result": structured_output_raw} if structured_output_raw else None
                        
                        if structured_output and "result" in structured_output:
                            self.terminal_ui.console.print(Padding(Panel("[bold green]Salida del Código Python:[/bold green]", border_style='green'), (1, 2)))
                            for item in structured_output["result"]:
                                if item['type'] == 'stream':
                                    self.terminal_ui.console.print(f"[cyan]STDOUT:[/cyan] {item['text']}")
                                elif item['type'] == 'error':
                                    self.terminal_ui.console.print(f"[red]ERROR ({item['ename']}):[/red] {item['evalue']}")
                                    self.terminal_ui.console.print(f"[red]TRACEBACK:[/red]\n{''.join(item['traceback'])}")
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
                        elif structured_output and "error" in structured_output:
                            self.terminal_ui.console.print(f"[red]Error en la ejecución de Python:[/red] {structured_output['error']}")
                    except Exception as e:
                        logger.error(f"Error al procesar salida estructurada de Python: {e}")
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
            self._auto_save_session()
            self.terminal_ui.print_message("Sesión y historial guardados al salir.", style="dim")
            # Asegurarse de que el FileCompleter se limpie al salir
            if self.completer:
                self.completer.dispose()

