import logging # Importar logging al principio
import sys
import os
from dotenv import load_dotenv # Importar load_dotenv
from prompt_toolkit.completion import Completer, Completion
from rich.text import Text
from rich.syntax import Syntax
import re

load_dotenv() # Cargar variables de entorno al inicio

# New helper function
def _format_text_with_basic_markdown(text: str) -> Text:
    """Applies basic Markdown-like formatting to a string using rich.Text."""
    formatted_text = Text()
    
    lines = text.split('\n')
    
    in_code_block = False
    code_block_lang = ""
    code_block_content = []

    for line in lines:
        code_block_match = re.match(r"```(\w*)", line)
        if code_block_match:
            if in_code_block: # End of code block
                in_code_block = False
                if code_block_content:
                    code_str = "\n".join(code_block_content)
                    lexer = code_block_lang if code_block_lang else "plaintext"
                    formatted_text.append(Text.from_ansi(str(Syntax(code_str, lexer, theme="monokai", line_numbers=False))))
                    code_block_content = []
                formatted_text.append("\n")
            else: # Start of code block
                in_code_block = True
                code_block_lang = code_block_match.group(1) if code_block_match.group(1) else ""
                formatted_text.append("\n")
        elif in_code_block:
            code_block_content.append(line)
        else:
            # Apply inline formatting (bold)
            parts = re.split(r"(\*\*.*?\*\*)", line)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    formatted_text.append(part[2:-2], style="bold")
                else:
                    formatted_text.append(part)
            formatted_text.append("\n")

    if in_code_block and code_block_content:
        code_str = "\n".join(code_block_content)
        lexer = code_block_lang if code_block_lang else "plaintext"
        formatted_text.append(Text.from_ansi(str(Syntax(code_str, lexer, theme="monokai", line_numbers=False))))

    return formatted_text

# --- Importar KogniTermApp ---
from kogniterm.terminal.kogniterm_app import KogniTermApp
from kogniterm.core.llm_service import LLMService
from kogniterm.core.command_executor import CommandExecutor # Importar CommandExecutor
from kogniterm.core.agent_state import AgentState # Importar AgentState
from kogniterm.core.tools.file_read_directory_tool import FileReadDirectoryTool
from prompt_toolkit.completion import Completer, Completion
import os
from rich.text import Text
from rich.syntax import Syntax
from rich.console import Console
from rich.padding import Padding
from rich.live import Live
from rich.markdown import Markdown
from rich.status import Status
import json
import asyncio
import re
import sys
import os
import asyncio
import threading # Importar threading para el watcher

from .agent_interaction_manager import AgentInteractionManager
from .command_approval_handler import CommandApprovalHandler
from .meta_command_processor import MetaCommandProcessor
from .terminal_ui import TerminalUI

console = Console()

class FileCompleter(Completer):
    def __init__(self, *, file_read_directory_tool: FileReadDirectoryTool, workspace_directory: str, show_indicator: bool = True):
        self.file_read_directory_tool = file_read_directory_tool
        self.show_indicator = show_indicator
        self.workspace_directory = workspace_directory
        self._cached_files = None  # Caché para almacenar la lista de archivos
        self._cache_lock = threading.Lock() # Bloqueo para proteger el acceso a la caché

    def invalidate_cache(self):
        """Invalida la caché de archivos, forzando una recarga la próxima vez que se necesite."""
        with self._cache_lock:
            self._cached_files = None

    def _load_files_into_cache(self):
        """Carga todos los archivos y directorios relativos al workspace_directory en la caché."""
        with self._cache_lock:
            if self._cached_files is not None:
                return self._cached_files

            all_relative_items = []
            for root, dirs, files in os.walk(self.workspace_directory):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), self.workspace_directory)
                    all_relative_items.append(rel_path)
                for dir in dirs:
                    rel_path = os.path.relpath(os.path.join(root, dir), self.workspace_directory)
                    all_relative_items.append(rel_path + '/')
            self._cached_files = all_relative_items
            return self._cached_files

    def get_completions(self, document, complete_event):
        text_before_cursor = document.text_before_cursor
        
        if '@' not in text_before_cursor:
            return # No estamos en modo de autocompletado de archivos

        current_input_part = text_before_cursor.split('@')[-1]
        
        # Asegurarse de que la caché se cargue solo cuando se necesite
        if self._cached_files is None:
            self._load_files_into_cache()
            # self._start_watcher() # Iniciar el watcher solo después de la primera carga

        all_relative_items = self._cached_files # Usar la caché
            
        suggestions = []
        for relative_item_path in all_relative_items:
            # Construir la ruta absoluta para verificar si es un directorio
            absolute_item_path = os.path.join(self.workspace_directory, relative_item_path)
            
            display_item = relative_item_path
            if os.path.isdir(absolute_item_path): # Verificar si es directorio para añadir '/'
                display_item += '/'

            if current_input_part.lower() in display_item.lower():
                suggestions.append(display_item)
        
        suggestions.sort()

        for suggestion in suggestions:
            start_position = -len(current_input_part)
            yield Completion(suggestion, start_position=start_position)

    def dispose(self):
        """Detiene el FileSystemWatcher cuando la aplicación se cierra."""
        pass





async def _main_async():
    """Función principal asíncrona para iniciar la terminal de KogniTerm."""
    from kogniterm.terminal.config_manager import ConfigManager
    from kogniterm.terminal.themes import set_kogniterm_theme
    
    # Cargar configuración y aplicar tema guardado antes de iniciar nada
    config_manager = ConfigManager()
    saved_theme = config_manager.get_config("theme")
    if saved_theme:
        try:
            set_kogniterm_theme(saved_theme)
        except ValueError:
            # Si el tema guardado ya no es válido, se mantiene el default
            pass

    auto_approve = '-y' in sys.argv or '--yes' in sys.argv
    
    # Obtener el directorio de trabajo actual
    workspace_directory = os.getcwd()

    llm_service_instance = LLMService() # Usar el project_context inicializado
    command_executor_instance = CommandExecutor() # Inicializar CommandExecutor
    agent_state_instance = AgentState(messages=llm_service_instance.conversation_history) # Inicializar AgentState
    llm_service_instance.tool_manager.set_agent_state(agent_state_instance) # Vincular estado del agente a las herramientas

    app = KogniTermApp(
        llm_service=llm_service_instance,
        command_executor=command_executor_instance, # Pasar la instancia
        agent_state=agent_state_instance, # Pasar la instancia
        auto_approve=auto_approve,
        workspace_directory=workspace_directory # Pasar el directorio de trabajo
    )
    try:
        await app.run()
    finally:
        # Asegurarse de que el FileCompleter se limpie al salir
        if app.prompt_session.completer and hasattr(app.prompt_session.completer, 'dispose'):
            app.prompt_session.completer.dispose()

def main():
    """Función principal síncrona para el punto de entrada de KogniTerm."""
    import logging
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
    
    # Desactivar el logger de litellm por completo y establecer nivel CRITICAL
    litellm_logger = logging.getLogger('litellm')
    litellm_logger.propagate = False
    litellm_logger.disabled = True
    litellm_logger.setLevel(logging.CRITICAL) # Establecer nivel CRITICAL
    # Eliminar cualquier manejador existente que litellm pueda haber añadido
    for handler in list(litellm_logger.handlers):
        litellm_logger.removeHandler(handler)

    logging.getLogger('kogniterm.terminal.kogniterm_app').setLevel(logging.WARNING)
    
    # Handle config commands
    if len(sys.argv) > 1 and sys.argv[1] == 'config':
        from kogniterm.terminal.config_manager import ConfigManager
        config_manager = ConfigManager()
        
        if len(sys.argv) < 3:
            print("Usage: kogniterm config [project] set <key> <value> | get <key> | list")
            return

        command = sys.argv[2]
        
        if command == 'set':
            if len(sys.argv) != 5:
                print("Usage: kogniterm config set <key> <value>")
                return
            key = sys.argv[3]
            value = sys.argv[4]
            config_manager.set_global_config(key, value)
            print(f"Global config '{key}' set to '{value}'")
            
        elif command == 'project':
            if len(sys.argv) < 4:
                print("Usage: kogniterm config project set <key> <value>")
                return
            subcommand = sys.argv[3]
            if subcommand == 'set':
                if len(sys.argv) != 6:
                    print("Usage: kogniterm config project set <key> <value>")
                    return
                key = sys.argv[4]
                value = sys.argv[5]
                config_manager.set_project_config(key, value)
                print(f"Project config '{key}' set to '{value}'")
            else:
                print(f"Unknown project subcommand: {subcommand}")

        elif command == 'get':
             if len(sys.argv) != 4:
                print("Usage: kogniterm config get <key>")
                return
             key = sys.argv[3]
             value = config_manager.get_config(key)
             print(f"{key}: {value}")

        elif command == 'list':
            import json
            print(json.dumps(config_manager.get_all_config(), indent=4))
            
        else:
            print(f"Unknown config command: {command}")
            
        return

    # Handle index commands
    if len(sys.argv) > 1 and sys.argv[1] == 'index':
        if len(sys.argv) < 3:
            print("Usage: kogniterm index refresh")
            return
        
        command = sys.argv[2]
        
        if command == 'refresh':
            from kogniterm.core.context.codebase_indexer import CodebaseIndexer
            from kogniterm.core.context.vector_db_manager import VectorDBManager
            
            workspace_directory = os.getcwd()
            print(f"Indexing codebase in {workspace_directory}...")
            
            try:
                indexer = CodebaseIndexer(workspace_directory)
                vector_db = VectorDBManager(workspace_directory)
                
                # Run async indexing
                chunks = asyncio.run(indexer.index_project(workspace_directory))
                
                if chunks:
                    print(f"Generated {len(chunks)} chunks. Storing in Vector DB...")
                    vector_db.clear_collection() # Clear existing before adding new
                    vector_db.add_chunks(chunks)
                    print("Indexing complete!")
                else:
                    print("No code files found or no chunks generated.")
                    
            except Exception as e:
                print(f"Error during indexing: {e}")
                import traceback
                traceback.print_exc()
                
        else:
            print(f"Unknown index command: {command}")
            
        return

    asyncio.run(_main_async())

if __name__ == "__main__":
    main()