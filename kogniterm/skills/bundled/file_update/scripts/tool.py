"""
File Update Skill - Actualiza el contenido de un archivo existente.

Esta es una skill migrada desde file_update_tool.py.
Provee funcionalidad para actualizar archivos mostrando las diferencias.
"""

import os
import difflib
import json
import logging
from typing import Optional, Generator

# Configuración de logger
logger = logging.getLogger(__name__)


# Metadata de la herramienta
name = "file_update"
description = "Actualiza el contenido de un archivo existente, mostrando las diferencias antes de aplicar."


def _apply_update(path: str, content: str) -> str:
    """
    Aplica la actualización al archivo después de la confirmación.

    Args:
        path: Ruta del archivo
        content: Nuevo contenido

    Returns:
        str: Resultado en formato JSON
    """
    try:
        if not os.access(path, os.W_OK):
            return json.dumps({
                "status": "error",
                "path": path,
                "message": f"No se tienen permisos de escritura en el archivo '{path}'."
            })

        with open(path, 'w') as f:
            f.write(content)

        return json.dumps({
            "status": "success",
            "path": path,
            "message": f"Archivo '{path}' actualizado exitosamente."
        })
    except Exception as e:
        logger.error(f"Error al aplicar la actualización en '{path}': {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "path": path,
            "message": f"Error al aplicar la actualización: {e}"
        })


def file_update(path: str, content: str) -> Generator[str, None, None]:
    """
    Actualiza el contenido de un archivo existente.

    Muestra las diferencias (diff) y requiere confirmación del usuario
    antes de aplicar los cambios.

    Args:
        path: La ruta del archivo a actualizar
        content: El nuevo contenido del archivo

    Yields:
        str: Resultados de la operación o mensajes de error

    Raises:
        FileNotFoundError: Si el archivo no existe
        PermissionError: Si no hay permisos suficientes
    """
    logger.debug(f"FileUpdate - Intentando actualizar archivo en ruta '{path}'")

    try:
        if not os.path.exists(path):
            yield f"Error: El archivo '{path}' no existe para actualizar.\n"
            return

        # Leer contenido actual
        with open(path, 'r') as f:
            old_content = f.read()

        if content is None:
            yield json.dumps({
                "status": "error",
                "path": path,
                "message": "Error: El contenido no puede ser None para la acción 'update'."
            })
            return

        # Generar diff
        diff = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f'a/{path}',
            tofile=f'b/{path}',
        ))

        if not diff:
            yield json.dumps({
                "status": "no_changes",
                "path": path,
                "message": f"No hay cambios detectados para '{path}'. No se requiere actualización."
            })
            return

        diff_output = "".join(diff)

        # Mostrar diff y requerir confirmación
        yield json.dumps({
            "status": "requires_confirmation",
            "path": path,
            "diff": diff_output,
            "message": f"Se detectaron cambios para '{path}'. Por favor, confirma para aplicar."
        })

    except FileNotFoundError:
        yield json.dumps({
            "status": "error",
            "path": path,
            "message": f"Error: El archivo '{path}' no fue encontrado para actualizar."
        })
    except PermissionError:
        yield json.dumps({
            "status": "error",
            "path": path,
            "message": f"Error de Permisos: No se tienen los permisos necesarios para leer el archivo '{path}'."
        })
    except Exception as e:
        logger.error(f"Error inesperado en FileUpdate al actualizar '{path}': {e}", exc_info=True)
        yield json.dumps({
            "status": "error",
            "path": path,
            "message": f"Error inesperado en FileUpdate: {e}. Por favor, revisa los logs para más detalles."
        })


# Función alternativa para ejecución síncrona
def _file_update_sync(path: str, content: str) -> str:
    """
    Versión síncrona de file_update.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in file_update(path, content):
        output.append(chunk)
    return "".join(output)


# Función para aplicar la actualización (usada después de confirmación)
def _apply_file_update(path: str, content: str) -> str:
    """
    Aplica la actualización después de la confirmación del usuario.

    Args:
        path: La ruta del archivo
        content: El nuevo contenido

    Returns:
        str: Resultado en formato JSON
    """
    return _apply_update(path, content)


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "La ruta del archivo a actualizar"
        },
        "content": {
            "type": "string",
            "description": "El nuevo contenido del archivo"
        }
    },
    "required": ["path", "content"]
}
