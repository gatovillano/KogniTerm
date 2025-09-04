from .brave_search_tool import BraveSearchTool
from .web_fetch_tool import WebFetchTool
from .web_scraping_tool import WebScrapingTool
from .github_tool import GitHubTool
from .execute_command_tool import ExecuteCommandTool
from .memory_init_tool import MemoryInitTool
from .memory_read_tool import MemoryReadTool
from .memory_append_tool import MemoryAppendTool
from .memory_summarize_tool import MemorySummarizeTool
from .file_operations_tool import FileOperationsTool # Nuevo import

# You can also define a list of all tools here for easy access
ALL_TOOLS = [
    BraveSearchTool(),
    WebFetchTool(),
    WebScrapingTool(),
    GitHubTool(),
    ExecuteCommandTool(),
    MemoryInitTool(),
    MemoryReadTool(),
    MemoryAppendTool(),
    MemorySummarizeTool(),
    FileOperationsTool() # Nueva herramienta
]

def get_callable_tools():
    return ALL_TOOLS