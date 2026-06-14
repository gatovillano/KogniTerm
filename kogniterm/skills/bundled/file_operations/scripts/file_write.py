import os
import difflib
from typing import Dict, Any, Optional

from ._utils import clean_path


def write_file_tool(path: str, content: str, confirm: bool = False) -> str | Dict[str, Any]:
    """
    Escribe el contenido completo en un archivo.
    Si el archivo existe, mostrará un diff antes de sobrescribirlo para su confirmación.
    """
    path = clean_path(path)
    if not path:
        return {"error": "Path no proporcionado"}
    if content is None:
        return {"error": "Contenido no proporcionado"}

    if not confirm:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
                diff = "".join(difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                ))
            except Exception as e:
                diff = f"No se pudo generar diff: {e}"
        else:
            diff = "".join(difflib.unified_diff(
                [],
                content.splitlines(keepends=True),
                fromfile="/dev/null",
                tofile=f"b/{path}",
            ))
            if not diff:
                diff = f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +0,0 @@\n"

        if diff:
            return {
                "status": "requires_confirmation",
                "action_description": f"escribir en el archivo '{path}'",
                "operation": "write_file_tool",
                "args": {
                    "path": path,
                    "content": content,
                    "confirm": True
                },
                "diff": diff
            }

    try:
        # Crear directorio padre si no existe
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"status": "success", "message": f"Archivo escrito exitosamente: {path}"}
    except Exception as e:
        return {"error": f"Error al escribir el archivo '{path}': {e}"}

def append_file_tool(path: str, content: str, confirm: bool = False) -> str | Dict[str, Any]:
    """Añade contenido al final de un archivo existente."""
    path = clean_path(path)
    if not path:
        return {"error": "Path no proporcionado"}
    if content is None:
        return {"error": "Contenido no proporcionado"}

    if not confirm:
        return {
            "status": "requires_confirmation",
            "action_description": f"añadir contenido a '{path}'",
            "operation": "append_file_tool",
            "args": {
                "path": path,
                "content": content,
                "confirm": True
            },
            "diff": f"+ (Añadiendo {len(content)} caracteres al final)\n+ {content[:200]}..."
        }

    try:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(content)
        return {"status": "success", "message": f"Contenido añadido exitosamente a: {path}"}
    except Exception as e:
        return {"error": f"Error al añadir a '{path}': {e}"}

def create_directory_tool(path: str) -> str | Dict[str, Any]:
    """Crea un directorio y todos los directorios padres necesarios."""
    path = clean_path(path)
    if not path:
        return {"error": "Path no proporcionado"}

    try:
        os.makedirs(path, exist_ok=True)
        return {"status": "success", "message": f"Directorio creado exitosamente en: {path}"}
    except Exception as e:
        return {"error": f"Error al crear el directorio '{path}': {e}"}
