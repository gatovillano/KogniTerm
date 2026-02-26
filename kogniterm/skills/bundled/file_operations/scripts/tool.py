"""
File Operations Skill - Operaciones CRUD en archivos y directorios.

Esta es una skill migrada desde file_operations_tool.py.
Provee funcionalidad para leer, escribir, eliminar y listar archivos.
"""

import os
import shutil
import difflib
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
    recursive: bool = False,
    confirm: bool = False,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    destination: Optional[str] = None,
    pattern: Optional[str] = None
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
        confirm: Si True, se ejecuta la acción sin pedir confirmación adicional

    Returns:
        str o Dict: Resultado de la operación
    """
    operation = operation.lower().strip()

    try:
        if operation == "read_file":
            return _read_file(path, start_line, end_line)
        elif operation == "write_file":
            return _write_file(path, content, confirm)
        elif operation == "delete_file":
            return _delete_file(path, confirm)
        elif operation == "list_directory":
            return _list_directory(path, recursive)
        elif operation == "read_many_files":
            return _read_many_files(paths or [])
        elif operation == "create_directory":
            return _create_directory(path)
        elif operation == "move_file":
            return _move_file(path, destination, confirm)
        elif operation == "copy_file":
            return _copy_file(path, destination, confirm)
        elif operation == "append_file":
            return _append_file(path, content, confirm)
        elif operation == "get_file_info":
            return _get_file_info(path)
        elif operation == "search_in_file":
            return _search_in_file(path, pattern)
        else:
            return f"Operación no soportada: {operation}"
    except FileNotFoundError as e:
        return f"Error: {e}"
    except PermissionError as e:
        return f"Error de permisos: {e}"
    except Exception as e:
        return f"Error en la operación '{operation}': {e}"


def _read_file(path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
    """Lee un archivo y devuelve su contenido. Puede leer una sección si se indican start_line y end_line (1-indexed)."""
    if not path:
        return {"error": "Path no proporcionado"}

    path = path.strip().replace('@', '')

    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            total_lines = len(lines)
            
        if start_line is not None or end_line is not None:
            start = max(0, (start_line or 1) - 1)
            end = min(total_lines, (end_line or total_lines))
            
            if start >= total_lines or start >= end:
                content = ""
            else:
                content = "".join(lines[start:end])
                
            return {
                "file_path": path, 
                "content": content,
                "lines_read": f"{start + 1}-{end}",
                "total_lines": total_lines
            }

        content = "".join(lines)
        return {"file_path": path, "content": content, "total_lines": total_lines}
    except FileNotFoundError:
        return {"error": f"El archivo '{path}' no fue encontrado."}
    except Exception as e:
        return {"error": f"Error al leer '{path}': {e}"}


def _write_file(path: str, content: str, confirm: bool = False) -> str | Dict[str, Any]:
    """Escribe contenido en un archivo."""
    if not path:
        return "Error: Path no proporcionado"
    if content is None:
        return "Error: Contenido no proporcionado"
        
    path = path.strip().replace('@', '')

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
            diff = f"Nuevo archivo a crear:\n{content[:500]}..."

        return {
            "status": "requires_confirmation",
            "action_description": f"escribir en el archivo '{path}'",
            "operation": "file_operations",
            "args": {
                "operation": "write_file",
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
        return f"Error al escribir el archivo '{path}': {e}"


def _delete_file(path: str, confirm: bool = False) -> str | Dict[str, Any]:
    """Elimina un archivo."""
    if not path:
        return "Error: Path no proporcionado"

    path = path.strip().replace('@', '')

    if not os.path.exists(path):
        return f"El archivo no existe: {path}"

    if not confirm:
        return {
            "status": "requires_confirmation",
            "action_description": f"eliminar el archivo '{path}'",
            "operation": "file_operations",
            "args": {
                "operation": "delete_file",
                "path": path,
                "confirm": True
            },
            "diff": f"- Se eliminará permanentemente el archivo: {path}"
        }

    try:
        os.remove(path)
        return {"status": "success", "message": f"Archivo eliminado exitosamente: {path}"}
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


def _move_file(path: str, destination: str, confirm: bool = False) -> str | Dict[str, Any]:
    """Mueve o renombra un archivo o directorio."""
    if not path or not destination:
        return "Error: Path o destination no proporcionados"

    path = path.strip().replace('@', '')
    destination = destination.strip().replace('@', '')

    if not confirm:
        return {
            "status": "requires_confirmation",
            "action_description": f"mover/renombrar '{path}' a '{destination}'",
            "operation": "file_operations",
            "args": {
                "operation": "move_file",
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
        return f"Error al mover '{path}': {e}"


def _copy_file(path: str, destination: str, confirm: bool = False) -> str | Dict[str, Any]:
    """Copia un archivo o directorio de forma recursiva."""
    if not path or not destination:
        return "Error: Path o destination no proporcionados"

    path = path.strip().replace('@', '')
    destination = destination.strip().replace('@', '')

    if not confirm:
        return {
            "status": "requires_confirmation",
            "action_description": f"copiar '{path}' a '{destination}'",
            "operation": "file_operations",
            "args": {
                "operation": "copy_file",
                "path": path,
                "destination": destination,
                "confirm": True
            },
            "diff": f"+ Copiar a: {destination}"
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
        return f"Error al copiar '{path}': {e}"


def _append_file(path: str, content: str, confirm: bool = False) -> str | Dict[str, Any]:
    """Añade contenido al final de un archivo."""
    if not path:
        return "Error: Path no proporcionado"
    if content is None:
        return "Error: Contenido no proporcionado"

    path = path.strip().replace('@', '')

    if not confirm:
        return {
            "status": "requires_confirmation",
            "action_description": f"añadir contenido a '{path}'",
            "operation": "file_operations",
            "args": {
                "operation": "append_file",
                "path": path,
                "content": content,
                "confirm": True
            },
            "diff": f"+ {content[:200]}..."
        }

    try:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(content)
        return {"status": "success", "message": f"Contenido añadido exitosamente a: {path}"}
    except Exception as e:
        return f"Error al añadir a '{path}': {e}"


def _get_file_info(path: str) -> Dict[str, Any]:
    """Obtiene metadatos de un archivo o directorio."""
    if not path:
        return {"error": "Path no proporcionado"}

    path = path.strip().replace('@', '')

    if not os.path.exists(path):
        return {"error": f"La ruta '{path}' no existe."}

    try:
        stat_info = os.stat(path)
        return {
            "path": path,
            "is_dir": os.path.isdir(path),
            "size_bytes": stat_info.st_size,
            "size_mb": round(stat_info.st_size / (1024 * 1024), 2),
            "created": stat_info.st_ctime,
            "modified": stat_info.st_mtime
        }
    except Exception as e:
        return {"error": f"Error al obtener información de '{path}': {e}"}


def _search_in_file(path: str, pattern: str) -> Dict[str, Any]:
    """Busca una cadena de regex en un archivo."""
    import re
    if not path or not pattern:
        return {"error": "Path o pattern no proporcionados"}

    path = path.strip().replace('@', '')

    if not os.path.isfile(path):
        return {"error": f"El archivo '{path}' no existe o es un directorio."}

    matches = []
    try:
        regex = re.compile(pattern)
        with open(path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                if regex.search(line):
                    matches.append({"line_number": i, "content": line.rstrip()})
                    if len(matches) >= 100:
                        matches.append({"line_number": -1, "content": "...(más de 100 coincidencias, truncado)"})
                        break
        return {"file_path": path, "pattern": pattern, "matches": matches, "total_matches": len([m for m in matches if m['line_number'] != -1]) + (1 if len(matches) > 100 else 0)}
    except re.error as e:
        return {"error": f"Regex inválida '{pattern}': {e}"}
    except Exception as e:
        return {"error": f"Error al buscar en '{path}': {e}"}


def get_action_description(operation: str, path: Optional[str] = None, paths: Optional[List[str]] = None, **kwargs) -> str:
    """Devuelve una descripción legible de la acción que realiza la herramienta."""
    operation = operation.lower().strip()
    if path:
        path = path.strip().replace('@', '')
    
    if operation == "read_file":
        return f"Leyendo el archivo {path}..."
    elif operation == "write_file":
        return f"Escribiendo en el archivo {path}..."
    elif operation == "delete_file":
        return f"Eliminando el archivo {path}..."
    elif operation == "list_directory":
        return f"Listando el contenido de {path}..."
    elif operation == "read_many_files":
        count = len(paths) if paths else 0
        return f"Leyendo {count} archivos..."
    elif operation == "create_directory":
        return f"Creando el directorio {path}..."
    elif operation == "move_file":
        return f"Moviendo {path} a {kwargs.get('destination', 'nuevo destino')}..."
    elif operation == "copy_file":
        return f"Copiando {path} a {kwargs.get('destination', 'nuevo destino')}..."
    elif operation == "append_file":
        return f"Añadiendo contenido a {path}..."
    elif operation == "get_file_info":
        return f"Obteniendo información de {path}..."
    elif operation == "search_in_file":
        return f"Buscando patrón en {path}..."
    return f"Realizando operación {operation}..."


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "description": "La operación a realizar",
            "enum": ["read_file", "write_file", "delete_file", "list_directory", "read_many_files", "create_directory", "move_file", "copy_file", "append_file", "get_file_info", "search_in_file"]
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
        },
        "start_line": {
            "type": "integer",
            "description": "Línea de inicio para leer (1-indexed, opcional, para read_file)"
        },
        "end_line": {
            "type": "integer",
            "description": "Línea de fin para leer (1-indexed, opcional, para read_file)"
        },
        "destination": {
            "type": "string",
            "description": "Ruta destino (requerido para move_file y copy_file)"
        },
        "pattern": {
            "type": "string",
            "description": "Patrón Regex o texto a buscar (requerido para search_in_file)"
        }
    },
    "required": ["operation"]
}
