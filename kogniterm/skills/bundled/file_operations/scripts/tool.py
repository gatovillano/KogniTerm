import os
from .file_write import write_file_tool
from .file_management import delete_file_tool
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

def file_operations(operation: str, **kwargs) -> str:
    """Main entry point for file_operations skill."""
    if operation == "write_file":
        return write_file_tool(**kwargs)
    elif operation == "delete_file":
        return delete_file_tool(**kwargs)
    return f"Error: Operación '{operation}' no reconocida."
