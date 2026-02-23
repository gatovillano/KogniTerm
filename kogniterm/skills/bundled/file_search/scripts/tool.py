"""
File Search Skill - Busca archivos que coincidan con un patrón glob.

Esta es una skill migrada desde file_search_tool.py.
Provee funcionalidad para buscar archivos usando patrones glob.
"""

import os
import glob
from typing import List, Optional, Generator


# Metadata de la herramienta
name = "file_search"
description = "Busca archivos que coincidan con un patrón glob en un directorio específico o en el directorio de trabajo actual. Devuelve una lista de rutas de archivo absolutas."


def file_search(pattern: str, path: Optional[str] = None) -> Generator[str, None, None]:
    """
    Busca archivos que coincidan con un patrón glob en un directorio.

    Args:
        pattern: El patrón glob a buscar (ej. '*.txt', 'src/**/*.py')
        path: El directorio absoluto donde buscar. Si no se proporciona,
              busca en el directorio de trabajo actual

    Yields:
        str: Resultados de la búsqueda o mensajes de error

    Raises:
        ValueError: Si el path no es una ruta absoluta
    """
    if path and not os.path.isabs(path):
        yield f"Error: El 'path' debe ser una ruta absoluta. Se recibió: {path}\n"
        return

    try:
        search_path = path if path else os.getcwd()
        full_pattern = os.path.join(search_path, pattern)

        # Usar glob.glob directamente
        found_files = [os.path.abspath(f) for f in glob.glob(full_pattern, recursive=True)]

        if not found_files:
            yield f"No se encontraron archivos con el patrón '{pattern}' en '{search_path}'\n"
            return

        yield f"Encontrados {len(found_files)} archivo(s):\n"
        for file_path in found_files:
            yield f"- {file_path}\n"

    except Exception as e:
        yield f"Error al ejecutar la búsqueda de archivos: {e}\n"


# Función alternativa para ejecución síncrona
def file_search_sync(pattern: str, path: Optional[str] = None) -> str:
    """
    Versión síncrona de file_search.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in file_search(pattern, path):
        output.append(chunk)
    return "".join(output)


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "pattern": {
            "type": "string",
            "description": "El patrón glob a buscar (ej. '*.txt', 'src/**/*.py')"
        },
        "path": {
            "type": "string",
            "description": "El directorio absoluto donde buscar. Si no se proporciona, busca en el directorio de trabajo actual",
            "default": None
        }
    },
    "required": ["pattern"]
}
