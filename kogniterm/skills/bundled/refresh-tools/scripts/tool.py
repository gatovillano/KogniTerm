"""
Skill: refresh_tools
Permite disparar el refresco del arsenal de herramientas.
"""

import logging

logger = logging.getLogger(__name__)

def refresh_tools() -> str:
    """
    Sincroniza las herramientas disponibles en el sistema.
    """
    # Nota: El orquestador de KogniTerm interceptará esta llamada 
    # si ve que el nombre coincide y ejecutará ToolManager.refresh_skills()
    return "🔄 Arsenal de herramientas actualizado. En tu próximo turno deberías ver las nuevas skills disponibles en tu esquema de herramientas."

# Schema para el LLM
tool_schema = {
    "name": "refresh_tools",
    "description": "Recarga el arsenal de herramientas del agente.",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}
