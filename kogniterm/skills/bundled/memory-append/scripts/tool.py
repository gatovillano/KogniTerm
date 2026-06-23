"""
Memory Append Skill - Añade contenido a la memoria contextual.

Esta es una skill migrada desde memory_append_tool.py.
Provee funcionalidad para guardar información en archivos de memoria.
"""

import os
from typing import Optional


# Metadata de la herramienta
name = "memory_append"
description = "Añade contenido a la memoria contextual del proyecto en 'llm_context.md'."


def memory_append(
    content: str,
    file_path: str = "llm_context.md"
) -> str:
    """
    Añade contenido a la memoria contextual del proyecto.

    Args:
        content: El contenido a añadir a la memoria
        file_path: Ruta del archivo de memoria (default: "llm_context.md")

    Returns:
        str: Mensaje de éxito o error
    """
    if not content:
        return "Error: Contenido no proporcionado"

    base_dir = os.getcwd()
    kogniterm_dir = os.path.join(base_dir, ".kogniterm")

    # Crear directorio .kogniterm si no existe
    os.makedirs(kogniterm_dir, exist_ok=True)

    # Extraer solo el nombre del archivo, no la ruta
    base_file_name = os.path.basename(file_path)
    full_path = os.path.join(kogniterm_dir, base_file_name)

    try:
        with open(full_path, 'a', encoding='utf-8') as f:
            f.write(f"\n{content}\n")
        return f"Contenido añadido exitosamente a la memoria '{base_file_name}'."
    except PermissionError:
        return f"Error de Permisos: No se tienen los permisos necesarios para escribir en '{base_file_name}'."
    except Exception as e:
        return f"Error inesperado al añadir contenido a '{base_file_name}': {e}"


# Función alternativa para añadir con timestamp
def memory_append_with_timestamp(
    content: str,
    file_path: str = "llm_context.md"
) -> str:
    """Añade contenido con timestamp automático."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return memory_append(f"[{timestamp}] {content}", file_path)


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "content": {
            "type": "string",
            "description": "El contenido a añadir a la memoria"
        },
        "file_path": {
            "type": "string",
            "description": "Ruta del archivo de memoria (default: 'llm_context.md')",
            "default": "llm_context.md"
        }
    },
    "required": ["content"]
}
