import os
from typing import Dict, Any, Optional
from kogniterm.skills.bundled.file_operations.scripts.file_editor import advanced_file_editor

def _apply_advanced_update_with_validation(path: str, content: str) -> str:
    """
    Aplica una actualización completa de archivo tras validación del usuario.
    """
    result = advanced_file_editor(
        path=path,
        action="full_replacement",
        content=content,
        confirm=True
    )
    if isinstance(result, dict):
        if "message" in result:
            return result["message"]
        if "error" in result:
            return f"Error: {result['error']}"
        return str(result)
    return str(result)

_apply_advanced_update = _apply_advanced_update_with_validation

def advanced_file_editor_tool(**kwargs) -> Dict[str, Any]:
    return advanced_file_editor(**kwargs)

from kogniterm.skills.bundled.file_operations.scripts.file_editor import common_editor_schema
parameters_schema = common_editor_schema
name = "advanced_file_editor"
description = "Herramienta premium para edición de archivos. Soporta múltiples estrategias (bloques, líneas, regex)."
