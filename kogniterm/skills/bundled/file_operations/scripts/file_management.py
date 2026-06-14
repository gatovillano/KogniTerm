import os
import shutil
from typing import Dict, Any, Optional

from ._utils import clean_path


def delete_file_tool(path: str, confirm: bool = False) -> str | Dict[str, Any]:
    """Elimina permanentemente un archivo o directorio."""
    path = clean_path(path)
    if not path:
        return {"error": "Path no proporcionado"}

    if not os.path.exists(path):
        return {"error": f"El archivo o directorio no existe: {path}"}

    if not confirm:
        return {
            "status": "requires_confirmation",
            "action_description": f"eliminar permanentemente '{path}'",
            "operation": "delete_file_tool",
            "args": {
                "path": path,
                "confirm": True
            },
            "diff": f"- Se eliminará permanentemente la ruta: {path}"
        }

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return {"status": "success", "message": f"Eliminado exitosamente: {path}"}
    except Exception as e:
        return {"error": f"Error al eliminar '{path}': {e}"}

def move_file_tool(path: str, destination: str, confirm: bool = False) -> str | Dict[str, Any]:
    """Mueve o renombra archivos y directorios de forma recursiva."""
    path = clean_path(path)
    destination = clean_path(destination)
    if not path or not destination:
        return {"error": "Origen o destino no proporcionados"}

    if not confirm:
        return {
            "status": "requires_confirmation",
            "action_description": f"mover/renombrar '{path}' a '{destination}'",
            "operation": "move_file_tool",
            "args": {
                "path": path,
                "destination": destination,
                "confirm": True
            },
            "diff": f"- {path}\n+ {destination}"
        }

    try:
        parent_dir = os.path.dirname(destination)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        shutil.move(path, destination)
        return {"status": "success", "message": f"Movido exitosamente a: {destination}"}
    except Exception as e:
        return {"error": f"Error al mover '{path}': {e}"}

def copy_file_tool(path: str, destination: str, confirm: bool = False) -> str | Dict[str, Any]:
    """Copia archivos y directorios de forma completa y recursiva."""
    path = clean_path(path)
    destination = clean_path(destination)
    if not path or not destination:
        return {"error": "Origen o destino no proporcionados"}

    if not confirm:
        return {
            "status": "requires_confirmation",
            "action_description": f"copiar '{path}' a '{destination}'",
            "operation": "copy_file_tool",
            "args": {
                "path": path,
                "destination": destination,
                "confirm": True
            },
            "diff": f"+ Copiar de '{path}' a '{destination}'"
        }

    try:
        if os.path.isdir(path):
            shutil.copytree(path, destination, dirs_exist_ok=True)
        else:
            parent_dir = os.path.dirname(destination)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            shutil.copy2(path, destination)
        return {"status": "success", "message": f"Copiado exitosamente a: {destination}"}
    except Exception as e:
        return {"error": f"Error al copiar '{path}': {e}"}
