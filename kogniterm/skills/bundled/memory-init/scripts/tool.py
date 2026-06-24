"""
Memory Init Skill - Inicializa la memoria contextual.

Esta es una skill migrada desde memory_init_tool.py.
Provee funcionalidad para crear archivos de memoria.
"""

import os


# Metadata de la herramienta
name = "memory_init"
description = "Inicializa la memoria contextual del proyecto creando un archivo 'llm_context.md' si no existe."


_llm_service = None


def set_llm_service(llm_service=None, *args, **kwargs):
    global _llm_service
    if llm_service is not None:
        _llm_service = llm_service
    
    # Si se llama como herramienta por error, delegar a memory_init
    if 'file_path' in kwargs or kwargs or args:
        file_path = kwargs.get('file_path', 'llm_context.md')
        return memory_init(file_path=file_path)



def memory_init(
    file_path: str = "llm_context.md",
    llm_service = None
) -> str:
    """
    Inicializa la memoria contextual del proyecto.

    Args:
        file_path: Ruta del archivo de memoria (default: "llm_context.md")
        llm_service: Servicio LLM inyectado (opcional)

    Returns:
        str: Mensaje de éxito o error
    """
    global _llm_service
    active_llm = llm_service or _llm_service
    
    base_dir = os.getcwd()
    kogniterm_dir = os.path.join(base_dir, ".kogniterm")
    os.makedirs(kogniterm_dir, exist_ok=True)
    
    # Extraer solo el nombre del archivo, no la ruta
    base_file_name = os.path.basename(file_path)
    full_path = os.path.join(kogniterm_dir, base_file_name)

    if os.path.exists(full_path):
        return f"La memoria '{base_file_name}' ya existe en el directorio actual. No se requiere inicialización."

    try:
        from kogniterm.core.context.project_memory_builder import ProjectMemoryBuilder
        builder = ProjectMemoryBuilder(base_dir)
        content = builder.build_markdown(llm_service=active_llm)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Memoria '{base_file_name}' inicializada exitosamente con investigación local."
    except PermissionError:
        return f"Error de Permisos: No se tienen los permisos necesarios para inicializar el archivo de memoria '{base_file_name}'. Asegúrate de que la aplicación tenga los permisos de escritura adecuados."
    except Exception as e:
        return f"Error inesperado al inicializar '{base_file_name}': {e}"


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Ruta del archivo de memoria a inicializar (default: 'llm_context.md')",
            "default": "llm_context.md"
        }
    },
    "required": []
}
