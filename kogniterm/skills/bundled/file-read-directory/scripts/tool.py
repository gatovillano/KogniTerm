"""
File Read Directory Skill - Lee el contenido de un directorio.

Esta es una skill migrada desde file_read_directory_tool.py.
Provee funcionalidad para listar el contenido de un directorio (no recursivo).
"""

import os
import logging
from typing import Generator

# Configuración de logger
logger = logging.getLogger(__name__)


# Metadata de la herramienta
name = "file_read_directory"
description = "Lee el contenido de un directorio (no recursivo)."


def file_read_directory(path: str) -> Generator[str, None, None]:
    """
    Lee el contenido de un directorio y lo lista.

    Args:
        path: La ruta del directorio a leer

    Yields:
        str: Contenido del directorio formateado

    Raises:
        FileNotFoundError: Si el directorio no existe
        PermissionError: Si no hay permisos suficientes
    """
    logger.debug(f"FileReadDirectory - Intentando leer directorio en ruta '{path}'")

    try:
        if not os.path.isdir(path):
            yield f"Error: La ruta '{path}' no es un directorio.\n"
            return

        output = f"### Contenido del directorio '{path}'\n"

        items = sorted(os.listdir(path))
        if not items:
            yield f"El directorio está vacío.\n"
            return

        for item in items:
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                output += f"- Archivo: {item}\n"
            elif os.path.isdir(item_path):
                output += f"- Directorio: {item}/\n"

        yield output

    except FileNotFoundError:
        yield f"Error: El directorio '{path}' no fue encontrado.\n"
    except PermissionError:
        yield f"Error de Permisos: No se tienen los permisos necesarios para leer el directorio '{path}'.\n"
    except Exception as e:
        logger.error(f"Error inesperado en FileReadDirectory al leer '{path}': {e}", exc_info=True)
        yield f"Error inesperado en FileReadDirectory: {e}. Por favor, revisa los logs para más detalles.\n"


# Función alternativa para ejecución síncrona
def file_read_directory_sync(path: str) -> str:
    """
    Versión síncrona de file_read_directory.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in file_read_directory(path):
        output.append(chunk)
    return "".join(output)


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "La ruta del directorio a leer"
        }
    },
    "required": ["path"]
}
