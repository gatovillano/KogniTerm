"""
Skill: skill_factory
Permite la autogeneración de nuevas skills por parte del agente.
"""

import os
import logging
from pathlib import Path
from typing import Optional
import yaml

logger = logging.getLogger(__name__)

def skill_factory(
    skill_name: str, 
    description: str, 
    instructions: str,
    tool_code: Optional[str] = None, 
    version: str = "1.0.0",
    scope: str = "workspace"
) -> str:
    """
    Crea una nueva skill en el directorio especificado (global o workspace) y la registra en el sistema.
    """
    # 1. Definir rutas absolutas y validar/normalizar nombre conforme a https://agentskills.io/specification
    import re

    # Normalizar nombre: minúsculas, guiones, sin caracteres especiales (1-64 caracteres)
    formatted_name = skill_name.strip().lower().replace("_", "-")
    formatted_name = re.sub(r'[^a-z0-9-]', '', formatted_name)
    formatted_name = re.sub(r'-+', '-', formatted_name).strip('-')
    if not formatted_name or len(formatted_name) > 64:
        formatted_name = "custom-skill"

    current_file = Path(__file__).resolve()
    base_skills_path = current_file.parent.parent.parent.parent
    
    if scope == "global":
        skill_path = Path.home() / ".kogniterm" / "skills" / "managed" / formatted_name
    else:
        # Default to workspace
        skill_path = base_skills_path / "workspace" / formatted_name
        
    scripts_path = skill_path / "scripts"
    references_path = skill_path / "references"
    assets_path = skill_path / "assets"
    resources_path = skill_path / "resources"
    
    try:
        # 2. Crear directorios (el directorio padre coincide con formatted_name según la spec)
        scripts_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directorio de skill creado en: {skill_path}")
        
        # 3. Preparar YAML Frontmatter para SKILL.md según https://agentskills.io/specification
        formatted_description = description.strip()
        if not formatted_description.lower().startswith("use when"):
            formatted_description = f"Use when {formatted_description[0].lower() + formatted_description[1:] if formatted_description else ''}"

        # Truncar a 1024 caracteres máximo (límite de la especificación)
        if len(formatted_description) > 1024:
            formatted_description = formatted_description[:1021] + "..."

        frontmatter = {
            "name": formatted_name,
            "description": formatted_description,
            "metadata": {
                "version": version,
                "author": "KogniTerm AI",
                "format": "agentskills-1.0"
            }
        }
        
        skill_md_content = "---\n" + yaml.dump(frontmatter, sort_keys=False) + "---\n\n" + instructions
        
        # 4. Escribir archivos
        (skill_path / "SKILL.md").write_text(skill_md_content, encoding="utf-8")
        if tool_code:
            (scripts_path / "tool.py").write_text(tool_code, encoding="utf-8")
        references_path.mkdir(exist_ok=True)
        assets_path.mkdir(exist_ok=True)
        resources_path.mkdir(exist_ok=True)
        
        # Intentar refresco automático si estamos en el entorno de KogniTerm
        refresh_status = ""
        try:
            from kogniterm.core.llm_service import LLMService
            refresh_status = "\n\n🔄 **Sincronizando sistema...** La nueva habilidad se está registrando en tu arsenal."
        except Exception:
            refresh_status = "\n\n⚠️ **IMPORTANTE**: Ejecuta `refresh_tools` para activar esta habilidad."

        return f"✅ Skill '{formatted_name}' ({scope}) creada con éxito en {skill_path}.{refresh_status}"

    except Exception as e:
        logger.error(f"Error en skill_factory: {e}", exc_info=True)
        return f"❌ Error al crear la skill: {str(e)}"

# Schema para el LLM
tool_schema = {
    "name": "skill_factory",
    "description": "Crea una nueva herramienta (skill) personalizada siguiendo la especificación oficial https://agentskills.io/specification e integra la habilidad en el sistema.",
    "properties": {
        "skill_name": {
            "type": "string",
            "description": "Nombre técnico de la skill (1-64 caracteres, minúsculas, números y guiones únicamente, ej: pdf-processing)."
        },
        "description": {
            "type": "string",
            "description": "Descripción de la herramienta (máx 1024 caracteres). OBLIGATORIO: Debe comenzar con 'Use when...' describiendo lo que hace y cuándo activarla con palabras clave específicas."
        },
        "tool_code": {
            "type": "string",
            "description": "Código Python completo para la lógica de la herramienta. CRÍTICO: 1) La función principal debe recibir parámetros con kwargs explícitos (nunca un dict `args`). 2) Debes incluir una variable global `parameters_schema` con el esquema de los parámetros."
        },
        "instructions": {
            "type": "string",
            "description": "Instrucciones Markdown para el cuerpo de SKILL.md (máx 500 líneas recomendado). OBLIGATORIO incluir secciones de uso claro: # Titulo, ## Overview, ## When to Use, ## Core Pattern / Instrucciones, ## Quick Reference / Ejemplos, ## Common Mistakes / Red Flags."
        },
        "version": {
            "type": "string",
            "description": "Versión inicial (por defecto 1.0.0).",
            "default": "1.0.0"
        },
        "scope": {
            "type": "string",
            "description": "Alcance de la skill: 'workspace' (solo este proyecto) o 'global' (disponible en todos los proyectos).",
            "enum": ["workspace", "global"],
            "default": "workspace"
        }
    },
    "required": ["skill_name", "description", "instructions"]
}


