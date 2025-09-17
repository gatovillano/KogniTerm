from .brave_search_tool import BraveSearchTool
from .web_fetch_tool import WebFetchTool
from .web_scraping_tool import WebScrapingTool
from .github_tool import GitHubTool
from .execute_command_tool import ExecuteCommandTool
from .memory_init_tool import MemoryInitTool
from .memory_read_tool import MemoryReadTool
from .memory_append_tool import MemoryAppendTool
from .memory_summarize_tool import MemorySummarizeTool
from .python_executor import PythonTool
from .file_search_tool import FileSearchTool
from .file_create_tool import FileCreateTool
from .file_delete_tool import FileDeleteTool
from .file_read_directory_tool import FileReadDirectoryTool
from .file_read_recursive_directory_tool import FileReadRecursiveDirectoryTool
from .file_read_tool import FileReadTool
from .file_update_tool import FileUpdateTool
from .file_operations_tool import FileOperationsTool # Importar FileOperationsTool

# You can also define a list of all tools here for easy access
# Las herramientas que necesitan la instancia de LLMService se inicializarán en LLMService
ALL_TOOLS_CLASSES = [
    BraveSearchTool,
    WebFetchTool,
    WebScrapingTool,
    GitHubTool,
    ExecuteCommandTool,
    MemoryInitTool,
    MemoryReadTool,
    MemoryAppendTool,
    MemorySummarizeTool,
    PythonTool,
    FileSearchTool,
    FileCreateTool,
    FileDeleteTool,
    FileReadDirectoryTool,
    FileReadRecursiveDirectoryTool,
    FileReadTool,
    FileUpdateTool,
    FileOperationsTool # Añadir FileOperationsTool
]

def get_callable_tools(llm_service_instance=None):
    # Instanciar las herramientas, pasando llm_service_instance si es necesario
    tools = []
    for ToolClass in ALL_TOOLS_CLASSES:
        if hasattr(ToolClass, '__init__') and 'llm_service' in ToolClass.__init__.__code__.co_varnames:
            tools.append(ToolClass(llm_service=llm_service_instance))
        elif hasattr(ToolClass, '__init__') and 'llm_service_instance' in ToolClass.__init__.__code__.co_varnames:
            tools.append(ToolClass(llm_service_instance=llm_service_instance))
        else:
            tools.append(ToolClass())
    return tools