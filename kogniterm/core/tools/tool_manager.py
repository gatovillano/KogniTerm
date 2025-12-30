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
from .file_operations_tool import FileOperationsTool
from .advanced_file_editor_tool import AdvancedFileEditorTool
from .pc_interaction_tool import PCInteractionTool
from .plan_creation_tool import PlanCreationTool
from .task_complete_tool import TaskCompleteTool
from .call_agent_tool import CallAgentTool
from .codebase_search_tool import CodebaseSearchTool
from .file_update_tool import FileUpdateTool
from .file_read_directory_tool import FileReadDirectoryTool
from .search_memory_tool import SearchMemoryTool
from .set_llm_instructions_tool import SetLLMInstructionsTool
from .code_analysis_tool import CodeAnalysisTool
from .tavily_search_tool import TavilySearchTool
from .think_tool import ThinkTool

# Lista de todas las clases de herramientas para fácil acceso
ALL_TOOLS_CLASSES = [
    CodeAnalysisTool,
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
    FileOperationsTool,
    AdvancedFileEditorTool,
    PCInteractionTool,
    PlanCreationTool,
    TaskCompleteTool,
    CallAgentTool,
    CodebaseSearchTool,
    FileUpdateTool,
    FileReadDirectoryTool,
    SearchMemoryTool,
    SetLLMInstructionsTool,
    TavilySearchTool,
    ThinkTool
]

import queue
from typing import Optional
from pydantic import BaseModel

class ToolManager:
    def __init__(self, llm_service=None, interrupt_queue: Optional[queue.Queue] = None, terminal_ui=None, embeddings_service=None, vector_db_manager=None):
        self.llm_service = llm_service
        self.interrupt_queue = interrupt_queue
        self.terminal_ui = terminal_ui
        self.embeddings_service = embeddings_service
        self.vector_db_manager = vector_db_manager
        self.tools = []
        self.tool_map = {}

    def load_tools(self):
        for ToolClass in ALL_TOOLS_CLASSES:
            tool_kwargs = {}
            
            import inspect
            try:
                init_params = inspect.signature(ToolClass.__init__).parameters
            except ValueError:
                init_params = {}
            
            if 'llm_service' in init_params:
                tool_kwargs['llm_service'] = self.llm_service
            if 'llm_service_instance' in init_params:
                tool_kwargs['llm_service_instance'] = self.llm_service
            if 'interrupt_queue' in init_params:
                tool_kwargs['interrupt_queue'] = self.interrupt_queue
            if 'terminal_ui' in init_params:
                tool_kwargs['terminal_ui'] = self.terminal_ui
            if 'embeddings_service' in init_params:
                tool_kwargs['embeddings_service'] = self.embeddings_service
            if 'vector_db_manager' in init_params:
                tool_kwargs['vector_db_manager'] = self.vector_db_manager
            
            try:
                tool_instance = ToolClass(**tool_kwargs)
                # Ensure unique tool name to avoid duplicate function declarations in LLM metadata
                base_name = getattr(tool_instance, 'name', ToolClass.__name__)
                unique_name = base_name
                suffix = 1
                while unique_name in self.tool_map:
                    unique_name = f"{base_name}_{suffix}"
                    suffix += 1
                if unique_name != base_name:
                    try:
                        setattr(tool_instance, 'name', unique_name)
                    except Exception:
                        pass
                    print(f"Warning: duplicate tool name '{base_name}' renamed to '{unique_name}'")
                self.tools.append(tool_instance)
                self.tool_map[unique_name] = tool_instance
            except Exception as e:
                print(f"Error al instanciar herramienta {ToolClass.__name__}: {e}")

    def register_tool(self, tool_instance):
        base_name = getattr(tool_instance, 'name', None) or tool_instance.__class__.__name__
        unique_name = base_name
        suffix = 1
        while unique_name in self.tool_map:
            unique_name = f"{base_name}_{suffix}"
            suffix += 1
        if unique_name != base_name:
            try:
                setattr(tool_instance, 'name', unique_name)
            except Exception:
                pass
            print(f"Warning: duplicate tool name '{base_name}' renamed to '{unique_name}'")
        if unique_name not in self.tool_map:
            self.tools.append(tool_instance)
            self.tool_map[unique_name] = tool_instance

    def get_tools(self):
        return self.tools

    def get_tool(self, tool_name: str):
        return self.tool_map.get(tool_name)

    def set_agent_state(self, agent_state):
        for tool in self.tools:
            if hasattr(tool, 'agent_state'):
                tool.agent_state = agent_state
