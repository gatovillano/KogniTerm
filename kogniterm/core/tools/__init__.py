import logging
from typing import Any
from langchain_core.tools import BaseTool

# Importar cada herramienta individualmente
from .brave_search_tool import BraveSearchTool
from .web_fetch_tool import WebFetchTool
from .web_scraping_tool import WebScrapingTool
from .github_tool import GitHubTool
from .execute_command_tool import ExecuteCommandTool
from .file_create_tool import FileCreateTool
from .file_read_tool import FileReadTool
from .file_update_tool import FileUpdateTool
from .file_delete_tool import FileDeleteTool
from .file_read_directory_tool import FileReadDirectoryTool
from .file_read_recursive_directory_tool import FileReadRecursiveDirectoryTool
from .memory_read_tool import MemoryReadTool
from .memory_append_tool import MemoryAppendTool
from .memory_init_tool import MemoryInitTool

# Configuración básica del logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Esta función será llamada por interpreter.py para obtener las funciones ejecutables reales
def get_callable_tools():
    return [
        BraveSearchTool(),
        WebFetchTool(),
        WebScrapingTool(),
        GitHubTool(),
        ExecuteCommandTool(),
        FileCreateTool(),
        FileReadTool(),
        FileUpdateTool(),
        FileDeleteTool(),
        FileReadDirectoryTool(),
        FileReadRecursiveDirectoryTool(),
        MemoryReadTool(),
        MemoryAppendTool(),
        MemoryInitTool()
    ]