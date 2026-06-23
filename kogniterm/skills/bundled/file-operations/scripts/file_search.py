import os
import re
import glob
from typing import Dict, Any, Optional

from ._utils import clean_path


def search_in_file_tool(path: str, pattern: str) -> Dict[str, Any]:
    """Busca un patrón (Regex) dentro de un archivo específico y devuelve las líneas con sus números."""
    path = clean_path(path)
    if not path or not pattern:
        return {"error": "Path o pattern no proporcionados"}

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
        return {
            "file_path": path, 
            "pattern": pattern, 
            "matches": matches, 
            "total_matches": len([m for m in matches if m['line_number'] != -1]) + (1 if len(matches) > 100 else 0)
        }
    except re.error as e:
        return {"error": f"Regex inválida '{pattern}': {e}"}
    except Exception as e:
        return {"error": f"Error al buscar en '{path}': {e}"}

def glob_search_tool(pattern: str, path: Optional[str] = None) -> Dict[str, Any]:
    """
    Busca archivos que coincidan con un patrón glob (ej. '**/*.py') en un directorio.
    Devuelve la lista de rutas encontradas.
    """
    path = clean_path(path) or os.getcwd()

    try:
        full_pattern = os.path.join(path, pattern)
        # Usar glob.glob con recursive=True
        found_files = [os.path.abspath(f) for f in glob.glob(full_pattern, recursive=True)]

        if not found_files:
            return {"message": f"No se encontraron archivos con el patrón '{pattern}' en '{path}'", "files": []}

        # Limitar a 100 archivos para evitar respuestas excesivas
        max_files = 100
        truncated = len(found_files) > max_files
        if truncated:
            found_files = found_files[:max_files]

        message = f"Encontrados {len(found_files)} archivo(s)"
        if truncated:
            message += f" (mostrando primeros {max_files} de {len(found_files) + max_files})"

        return {
            "message": message,
            "pattern": pattern,
            "path": path,
            "files": found_files,
            "truncated": truncated
        }

    except Exception as e:
        return {"error": f"Error al ejecutar la búsqueda de archivos: {e}"}

def get_action_description(pattern: str = "", query: str = "", path: str = "", **kwargs) -> str:
    """Devuelve una descripción legible de la acción para la TUI."""
    q = query or pattern or ""
    if path:
        return f"Buscando '{q}' en {path}..."
    return f"Buscando '{q}'..."

# Asignar explícitamente para que el SkillLoader lo detecte
search_in_file_tool.get_action_description = get_action_description
glob_search_tool.get_action_description = get_action_description

