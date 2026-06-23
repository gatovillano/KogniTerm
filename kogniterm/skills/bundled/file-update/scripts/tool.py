import os
from typing import Dict, Any, Optional
from kogniterm.skills.bundled.file_operations.scripts.file_write import write_file_tool

def _apply_file_update(path: str, content: str) -> str:
    """
    Aplica una actualización de archivo tras validación del usuario.
    """
    result = write_file_tool(path=path, content=content, confirm=True)
    if isinstance(result, dict):
        if "message" in result:
            return result["message"]
        if "error" in result:
            return f"Error: {result['error']}"
        return str(result)
    return str(result)

def file_update_tool(path: str, content: str, confirm: bool = False) -> Dict[str, Any]:
    """Actualiza el contenido de un archivo."""
    return write_file_tool(path=path, content=content, confirm=confirm)

name = "file_update"
description = "Actualiza el contenido de un archivo."
parameters_schema = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Ruta del archivo"},
        "content": {"type": "string", "description": "Nuevo contenido"},
        "confirm": {"type": "boolean", "default": False}
    },
    "required": ["path", "content"]
}
