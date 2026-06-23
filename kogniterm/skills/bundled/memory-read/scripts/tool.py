"""
Memory Read Skill - Lee la memoria contextual.

Esta es una skill migrada desde memory_read_tool.py.
Provee funcionalidad para leer archivos de memoria.
"""

import os


# Metadata de la herramienta
name = "memory_read"
description = "Lee el contenido de la memoria contextual del proyecto desde 'llm_context.md'."


def memory_read(
    file_path: str = "llm_context.md"
) -> str:
    """
    Lee la memoria contextual del proyecto.

    Args:
        file_path: Ruta del archivo de memoria (default: "llm_context.md")

    Returns:
        str: Contenido del archivo de memoria o mensaje de error
    """
    base_dir = os.getcwd()
    kogniterm_dir = os.path.join(base_dir, ".kogniterm")
    os.makedirs(kogniterm_dir, exist_ok=True)

    # Extraer solo el nombre del archivo, no la ruta
    base_file_name = os.path.basename(file_path)
    full_path = os.path.join(kogniterm_dir, base_file_name)

    if not os.path.exists(full_path):
        return f"Error: El archivo de memoria '{base_file_name}' no fue encontrado."

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return f"### Contenido de la Memoria Contextual ({base_file_name})\n```markdown\n{content}\n```"
    except PermissionError:
        return f"Error de Permisos: No se tienen los permisos necesarios para leer el archivo de memoria '{base_file_name}'."
    except Exception as e:
        return f"Error inesperado al leer '{base_file_name}': {e}"


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Ruta del archivo de memoria a leer (default: 'llm_context.md')",
            "default": "llm_context.md"
        }
    },
    "required": []
}
