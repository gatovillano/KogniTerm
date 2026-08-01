"""
prompt_processor.py — Procesamiento centralizado de referencias en prompts (@archivos y #skills procedimentales)
"""

import os
import re
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


def process_prompt_references(content: str, workspace_directory: Optional[str] = None, skill_manager: Optional[Any] = None) -> str:
    """
    Procesa referencias a archivos (@ruta) y a skills procedimentales (#nombre_skill)
    en el contenido del prompt enviando las instrucciones o contenido al agente.

    Args:
        content: Texto del mensaje del usuario.
        workspace_directory: Directorio raíz del proyecto para resolver rutas relativas @.
        skill_manager: Instancia de SkillManager para obtener instrucciones de skills.

    Returns:
        Texto procesado con el contenido de archivos e instrucciones de skills inyectadas.
    """
    if not isinstance(content, str) or not content:
        return content

    workspace_dir = workspace_directory or os.getcwd()

    # 1. Procesar referencias a skills procedimentales (#nombre_skill)
    if skill_manager and '#' in content:
        def replace_skill_ref(match):
            skill_name = match.group(1)
            instructions = None

            try:
                if hasattr(skill_manager, 'get_skill_instructions'):
                    instructions = skill_manager.get_skill_instructions(skill_name)
                elif hasattr(skill_manager, 'skills') and skill_name in skill_manager.skills:
                    skill = skill_manager.skills[skill_name]
                    if not getattr(skill, 'loaded', False):
                        if hasattr(skill_manager, 'load_skill'):
                            skill_manager.load_skill(skill_name)
                    instructions = getattr(skill, 'instructions', None) or getattr(skill, 'description', None)
            except Exception as e:
                logger.warning(f"Error obteniendo instrucciones de skill '{skill_name}': {e}")
                instructions = None

            if instructions:
                return f"\n\n### INSTRUCCIONES DE LA SKILL '{skill_name}' ###\n\n{instructions.strip()}\n\n"
            return match.group(0)

        content = re.sub(r'#([a-zA-Z0-9_-]+)', replace_skill_ref, content)

    # 2. Procesar referencias a archivos (@ruta)
    if '@' in content:
        def replace_file_ref(match):
            file_path = match.group(1)
            full_path = os.path.join(workspace_dir, file_path)
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                return f"```{file_path}\n{file_content}\n```"
            except Exception as e:
                logger.warning(f"No se pudo leer el archivo {full_path}: {e}")
                return f"@ {file_path} (Error al leer archivo: {e})"

        content = re.sub(r'@([^\s]+)', replace_file_ref, content)

    return content
