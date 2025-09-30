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
    FileReadTool,
    FileUpdateTool,
    FileOperationsTool # Añadir FileOperationsTool
]

import queue
from typing import Optional

from pydantic import BaseModel # Importar BaseModel

class ToolManager:
    def __init__(self, llm_service=None, interrupt_queue: Optional[queue.Queue] = None):
        self.llm_service = llm_service
        self.interrupt_queue = interrupt_queue
        self.tools = []
        self.tool_map = {}

    def load_tools(self):
        for ToolClass in ALL_TOOLS_CLASSES:
            tool_kwargs = {}
            if hasattr(ToolClass, '__init__'):
                init_signature = ToolClass.__init__.__code__.co_varnames
                if 'llm_service' in init_signature:
                    tool_kwargs['llm_service'] = self.llm_service
                if 'llm_service_instance' in init_signature:
                    tool_kwargs['llm_service_instance'] = self.llm_service
                if 'interrupt_queue' in init_signature:
                    tool_kwargs['interrupt_queue'] = self.interrupt_queue
            
            tool_instance = ToolClass(**tool_kwargs)
            self.tools.append(tool_instance)
            self.tool_map[tool_instance.name] = tool_instance

    def get_tools(self):
        return self.tools

    def get_tool(self, tool_name: str):
        return self.tool_map.get(tool_name)

# Eliminar la función get_callable_tools ya que su lógica se moverá a ToolManager
# def get_callable_tools(llm_service_instance=None, interrupt_queue: Optional[queue.Queue] = None, workspace_context=None):
#     # Instanciar las herramientas, pasando llm_service_instance si es necesario
#     tools = []
#     for ToolClass in ALL_TOOLS_CLASSES:
#         tool_kwargs = {}
#         if hasattr(ToolClass, '__init__'):
#             init_signature = ToolClass.__init__.__code__.co_varnames
#             if 'llm_service' in init_signature:
#                 tool_kwargs['llm_service'] = llm_service_instance
#             if 'llm_service_instance' in init_signature:
#                 tool_kwargs['llm_service_instance'] = llm_service_instance
#             if 'interrupt_queue' in init_signature: # Pasar interrupt_queue si la herramienta lo acepta
#                 tool_kwargs['interrupt_queue'] = interrupt_queue
        
#         # Nueva lógica para manejar campos Pydantic como workspace_context
#         # Verificar si la clase de la herramienta es una subclase de BaseModel
#         # y si 'workspace_context' es un campo definido en ella.
#         if issubclass(ToolClass, BaseModel) and 'workspace_context' in ToolClass.model_fields: # Usar model_fields para Pydantic v2
#             # Solo pasar workspace_context si no es None
#             if workspace_context is not None:
#                 tool_kwargs['workspace_context'] = workspace_context
#             # else:
#                 # Si workspace_context es None, no lo pasamos para evitar el error de validación
#                 # La herramienta deberá manejar la ausencia de workspace_context si es opcional
#         tools.append(ToolClass(**tool_kwargs))
#     return tools
