import os
from typing import Dict, Any, Optional

IGNORED_DIRECTORIES = ['venv', '.git', '__pycache__', '.venv', 'node_modules']

def matches_ignore(item_name: str, is_dir: bool = False) -> bool:
    """Verifica si un item debe ser ignorado."""
    if is_dir and item_name in IGNORED_DIRECTORIES:
        return True
    if item_name.startswith('.'):  # Archivos/dirs ocultos
        return True
    return False

def clean_path(path: str) -> str:
    """Limpia la ruta de caracteres innecesarios."""
    if not path:
        return ""
    return path.strip().replace('@', '')


def list_directory_tool(path: str, recursive: bool = False) -> str | Dict[str, Any]:
    """
    Lista el contenido de un directorio.
    Soporta modo recursivo y omite archivos y directorios ocultos por defecto.
    """
    path = clean_path(path)
    if not path:
        return {"error": "Path no proporcionado"}

    if not os.path.exists(path):
        return {"error": f"El directorio '{path}' no fue encontrado."}
    if not os.path.isdir(path):
        return {"error": f"'{path}' no es un directorio."}

    try:
        if recursive:
            items = []
            for root, dirs, files in os.walk(path):
                # Filtrar directorios ignorados in-place
                dirs[:] = [d for d in dirs if not matches_ignore(d, True)]

                rel_root = os.path.relpath(root, path)
                if rel_root == ".":
                    rel_root = ""

                for d in dirs:
                    items.append(os.path.join(rel_root, d) + "/")
                for f in files:
                    if not matches_ignore(f):
                        items.append(os.path.join(rel_root, f))

            return "\n".join(items) if items else "(directorio vacío)"
        else:
            items = []
            with os.scandir(path) as entries:
                for entry in entries:
                    if not matches_ignore(entry.name, entry.is_dir()):
                        items.append(entry.name + ("/" if entry.is_dir() else ""))
            return "\n".join(sorted(items)) if items else "(directorio vacío)"
    except Exception as e:
        return {"error": f"Error al listar el directorio '{path}': {e}"}
