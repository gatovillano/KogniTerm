"""
File Operations Skill - Operaciones CRUD en archivos y directorios.

Esta es una skill migrada desde file_operations_tool.py.
Provee funcionalidad para leer, escribir, eliminar y listar archivos.
"""

import os
import shutil
from typing import List, Dict, Any, Optional


# Metadata de la herramienta
name = "file_operations"
description = "Realiza operaciones CRUD en archivos y directorios."


# Directorios y archivos a ignorar por defecto
IGNORED_DIRECTORIES = ['venv', '.git', '__pycache__', '.venv', 'node_modules']


def _matches_ignore(item_name: str, is_dir: bool = False) -> bool:
    """Verifica si un item debe ser ignorado."""
    if is_dir and item_name in IGNORED_DIRECTORIES:
        return True
    if item_name.startswith('.'):  # Archivos/dirs ocultos
        return True
    return False


def file_operations(
    operation: str,
    path: Optional[str] = None,
    content: Optional[str] = None,
    paths: Optional[List[str]] = None,
    recursive: bool = False
) -> str | Dict[str, Any]:
    """
    Realiza operaciones CRUD en archivos y directorios.

    Args:
        operation: La operación a realizar (read_file, write_file, delete_file,
                  list_directory, read_many_files, create_directory)
        path: Ruta absoluta del archivo/directorio
        content: Contenido para escribir (write_file)
        paths: Lista de rutas para read_many_files
        recursive: Listar recursivamente (list_directory)

    Returns:
        str o Dict: Resultado de la operación
    """
    operation = operation.lower().strip()

    try:
        if operation == "read_file":
            return _read_file(path)
        elif operation == "write_file":
            return _write_file(path, content)
        elif operation == "delete_file":
            return _delete_file(path)
        elif operation == "list_directory":
            return _list_directory(path, recursive)
        elif operation == "read_many_files":
            return _read_many_files(paths or [])
        elif operation == "create_directory":
            return _create_directory(path)
        else:
            return f"Operación no soportada: {operation}"
    except FileNotFoundError as e:
        return f"Error: {e}"
    except PermissionError as e:
        return f"Error de permisos: {e}"
    except Exception as e:
        return f"Error en la operación '{operation}': {e}"


def _read_file(path: str) -> Dict[str, Any]:
    """Lee un archivo y devuelve su contenido."""
    if not path:
        return {"error": "Path no proporcionado"}

    path = path.strip().replace('@', '')

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"file_path": path, "content": content}
    except FileNotFoundError:
        return {"error": f"El archivo '{path}' no fue encontrado."}
    except Exception as e:
        return {"error": f"Error al leer '{path}': {e}"}


def _write_file(path: str, content: str) -> str:
    """Escribe contenido en un archivo."""
    if not path:
        return "Error: Path no proporcionado"
    if content is None:
        return "Error: Contenido no proporcionado"

    try:
        # Crear directorio padre si no existe
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Archivo escrito exitosamente: {path}"
    except Exception as e:
        return f"Error al escribir el archivo '{path}': {e}"


def _delete_file(path: str) -> str:
    """Elimina un archivo."""
    if not path:
        return "Error: Path no proporcionado"

    path = path.strip().replace('@', '')

    try:
        if not os.path.exists(path):
            return f"El archivo no existe: {path}"
        os.remove(path)
        return f"Archivo eliminado exitosamente: {path}"
    except Exception as e:
        return f"Error al eliminar el archivo '{path}': {e}"


def _list_directory(path: str, recursive: bool = False) -> str:
    """Lista el contenido de un directorio."""
    if not path:
        return "Error: Path no proporcionado"

    path = path.strip().replace('@', '')

    if not os.path.exists(path):
        return f"El directorio '{path}' no fue encontrado."
    if not os.path.isdir(path):
        return f"'{path}' no es un directorio."

    try:
        if recursive:
            items = []
            for root, dirs, files in os.walk(path):
                # Filtrar directorios ignorados
                dirs[:] = [d for d in dirs if not _matches_ignore(d, True)]

                rel_root = os.path.relpath(root, path)
                if rel_root == ".":
                    rel_root = ""

                for d in dirs:
                    items.append(os.path.join(rel_root, d) + "/")
                for f in files:
                    if not _matches_ignore(f):
                        items.append(os.path.join(rel_root, f))

            return "\n".join(items)
        else:
            items = []
            with os.scandir(path) as entries:
                for entry in entries:
                    if not _matches_ignore(entry.name, entry.is_dir()):
                        items.append(entry.name)
            return "\n".join(sorted(items))
    except Exception as e:
        return f"Error al listar el directorio '{path}': {e}"


def _read_many_files(paths: List[str]) -> Dict[str, Any]:
    """Lee múltiples archivos eficientemente."""
    if not paths:
        return {"error": "No se proporcionaron rutas"}

    results = []
    for p in paths:
        result = _read_file(p)
        results.append(result)

    return {"files": results}


def _create_directory(path: str) -> str:
    """Crea un directorio."""
    if not path:
        return "Error: Path no proporcionado"

    path = path.strip().replace('@', '')

    try:
        os.makedirs(path, exist_ok=True)
        return f"Directorio creado exitosamente: {path}"
    except Exception as e:
        return f"Error al crear el directorio '{path}': {e}"


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "description": "La operación a realizar",
            "enum": ["read_file", "write_file", "delete_file", "list_directory", "read_many_files", "create_directory"]
        },
        "path": {
            "type": "string",
            "description": "Ruta absoluta del archivo o directorio"
        },
        "content": {
            "type": "string",
            "description": "Contenido a escribir (para write_file)"
        },
        "paths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Lista de rutas para read_many_files"
        },
        "recursive": {
            "type": "boolean",
            "description": "Listar recursivamente (para list_directory)",
            "default": False
        }
    },
    "required": ["operation"]
}
