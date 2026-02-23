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
    tool_code: str, 
    instructions: str,
    version: str = "1.0.0"
) -> str:
    """
    Crea una nueva skill en el directorio de workspace y la registra en el sistema.
    """
    # 1. Definir rutas
    base_path = Path("kogniterm/skills/workspace") / skill_name
    scripts_path = base_path / "scripts"
    
    try:
        # 2. Crear directorios
        scripts_path.mkdir(parents=True, exist_ok=True)
        
        # 3. Preparar YAML Frontmatter para SKILL.md
        frontmatter = {
            "name": skill_name,
            "version": version,
            "author": "KogniTerm AI (Autonomous Generation)",
            "description": description,
            "category": "autonomous",
            "tags": ["autonomous", "generated"],
            "dependencies": [],
            "required_permissions": ["filesystem"],
            "security_level": "standard",
            "allowlist": False,
            "auto_approve": True,
            "sandbox_required": False
        }
        
        skill_md_content = "---\n" + yaml.dump(frontmatter) + "---\n\n" + instructions
        
        # 4. Escribir archivos
        (base_path / "SKILL.md").write_text(skill_md_content, encoding="utf-8")
        (scripts_path / "tool.py").write_text(tool_code, encoding="utf-8")
        
        # 5. Intentar refrescar el ToolManager (esto requiere acceso al objeto global o inyección)
        # En el contexto de ejecución de skills, solemos tener acceso a través de inyecciones
        # o buscando en el stack, pero la forma más limpia es que el orquestador 
        # detecte el éxito de esta tool y llame al refresco.
        
        return f"✅ Skill '{skill_name}' creada con éxito en {base_path}.\nPor favor, usa la herramienta 'think' o simplemente espera al siguiente turno para que el sistema refresque tu arsenal."

    except Exception as e:
        logger.error(f"Error en skill_factory: {e}", exc_info=True)
        return f"❌ Error al crear la skill: {str(e)}"

# Schema para el LLM
tool_schema = {
    "name": "skill_factory",
    "description": "Crea una nueva herramienta (skill) personalizada y la integra en tu sistema.",
    "parameters": {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "Nombre de la skill en snake_case (ej: image_tagger)."
            },
            "description": {
                "type": "string",
                "description": "Descripción de qué hace la herramienta."
            },
            "tool_code": {
                "type": "string",
                "description": "Código Python completo para la lógica de la herramienta."
            },
            "instructions": {
                "type": "string",
                "description": "Instrucciones detalladas en Markdown para el archivo SKILL.md."
            },
            "version": {
                "type": "string",
                "description": "Versión inicial (por defecto 1.0.0).",
                "default": "1.0.0"
            }
        },
        "required": ["skill_name", "description", "tool_code", "instructions"]
    }
}
