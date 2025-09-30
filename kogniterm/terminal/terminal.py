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
from kogniterm.core.agents.bash_agent import AgentState # Importar AgentState
from kogniterm.core.tools.file_read_directory_tool import FileReadDirectoryTool
from kogniterm.core.tools.file_read_recursive_directory_tool import FileReadRecursiveDirectoryTool
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
    def __init__(self, *, file_read_directory_tool: FileReadDirectoryTool, file_read_recursive_directory_tool: FileReadRecursiveDirectoryTool, workspace_directory: str, show_indicator: bool = True):
        self.file_read_directory_tool = file_read_directory_tool
        self.file_read_recursive_directory_tool = file_read_recursive_directory_tool
        self.show_indicator = show_indicator
        self.workspace_directory = workspace_directory
        self._cached_files = None  # Caché para almacenar la lista de archivos
        self._cache_lock = threading.Lock() # Bloqueo para proteger el acceso a la caché

    def invalidate_cache(self):
        """Invalida la caché de archivos, forzando una recarga la próxima vez que se necesite."""
        with self._cache_lock:
            self._cached_files = None

    def _load_files_into_cache():
        """Carga todos los archivos y directorios relativos al workspace_directory en la caché."""
        with self._cache_lock:
            if self._cached_files is not None:
                return self._cached_files

            # console.print("[dim]Cargando archivos para autocompletado...[/dim]") # Eliminar este log
            raw_output = self.file_read_recursive_directory_tool._run(path=self.workspace_directory)
            
            # Asegurarse de que raw_output sea una cadena antes de intentar split
            # Esta lógica ya estaba, pero la haremos más robusta forzando la conversión a str
            # Asegurarse de que raw_output sea una cadena antes de intentar split
            # Esta lógica ya estaba, pero la haremos más robusta forzando la conversión a str
            all_relative_items_str = ""
            if isinstance(raw_output, list):
                all_relative_items_str = '\n'.join(raw_output)
            elif raw_output is not None:
                all_relative_items_str = str(raw_output)
            else: # Asegurarse de que siempre sea una cadena, incluso si raw_output es None
                all_relative_items_str = ""
            
            all_relative_items = []
            for line in all_relative_items_str.split('\n'): # Aquí ya es seguro llamar a split
                line = line.strip()
                if line.startswith('- Archivo: '):
                    all_relative_items.append(line[len('- Archivo: '):])
                elif line.startswith('- Directorio: '):
                    all_relative_items.append(line[len('- Directorio: '):].rstrip('/'))
            
            self._cached_files = all_relative_items
            # console.print(f"[dim]Cargados {len(self._cached_files)} elementos en la caché.[/dim]") # Eliminar este log
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
        if self._watcher:
            self._watcher.stop()
            # console.print("[dim]FileSystemWatcher detenido.[/dim]") # Eliminar este log





async def _main_async():
    """Función principal asíncrona para iniciar la terminal de KogniTerm."""
    auto_approve = '-y' in sys.argv or '--yes' in sys.argv
    
    # Obtener el directorio de trabajo actual
    workspace_directory = os.getcwd()

    llm_service_instance = LLMService() # Usar el project_context inicializado
    command_executor_instance = CommandExecutor() # Inicializar CommandExecutor
    agent_state_instance = AgentState(messages=llm_service_instance.conversation_history) # Inicializar AgentState

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
    
    asyncio.run(_main_async())

if __name__ == "__main__":
    main()