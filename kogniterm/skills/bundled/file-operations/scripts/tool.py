import os
from .file_write import write_file_tool, append_file_tool, create_directory_tool
from .file_management import delete_file_tool, move_file_tool, copy_file_tool
from .file_read import read_file_tool, read_many_files_tool, get_file_info_tool
from .file_list import list_directory_tool
from .file_search import search_in_file_tool, glob_search_tool
from .file_editor import advanced_file_editor

def _write_file(path: str, content: str) -> str:
    """Versión interna para ejecución directa tras aprobación."""
    result = write_file_tool(path=path, content=content, confirm=True)
    if isinstance(result, dict):
        return result.get("message", str(result))
    return str(result)

def _delete_file(path: str) -> str:
    """Versión interna para ejecución directa tras aprobación."""
    result = delete_file_tool(path=path, confirm=True)
    if isinstance(result, dict):
        return result.get("message", str(result))
    return str(result)

def file_operations(operation: str, **kwargs) -> str | dict:
    """Main entry point for file_operations skill."""
    if operation == "write_file":
        return write_file_tool(**kwargs)
    elif operation == "delete_file":
        return delete_file_tool(**kwargs)
    elif operation == "read_file":
        return read_file_tool(**kwargs)
    elif operation == "read_many_files":
        return read_many_files_tool(**kwargs)
    elif operation == "get_file_info":
        return get_file_info_tool(**kwargs)
    elif operation == "append_file":
        return append_file_tool(**kwargs)
    elif operation == "create_directory":
        return create_directory_tool(**kwargs)
    elif operation == "move_file":
        return move_file_tool(**kwargs)
    elif operation == "copy_file":
        return copy_file_tool(**kwargs)
    elif operation == "list_directory":
        return list_directory_tool(**kwargs)
    elif operation == "search_in_file":
        return search_in_file_tool(**kwargs)
    elif operation == "glob_search":
        return glob_search_tool(**kwargs)
    elif operation == "sophisticated_editor" or operation == "advanced_file_editor":
        return advanced_file_editor(**kwargs)
    return f"Error: Operación '{operation}' no reconocida."

