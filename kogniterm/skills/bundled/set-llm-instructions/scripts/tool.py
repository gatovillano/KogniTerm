"""
Skill: set_llm_instructions
Permite establecer instrucciones o reglas personalizadas para el LLM
"""

import json
import logging
from typing import Optional, Type, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class SetLLMInstructionsInput(BaseModel):
    """Schema de entrada para la herramienta set_llm_instructions"""
    instructions: str = Field(..., description="Las instrucciones o reglas que se deben dar al LLM para guiar su comportamiento.")

def set_llm_instructions_skill(instructions: str) -> str:
    """
    Función principal que implementa la funcionalidad de set_llm_instructions
    
    Args:
        instructions: Las instrucciones o reglas que se deben dar al LLM
    
    Returns:
        str: Las instrucciones establecidas
    """
    # Sincrónicamente establece las instrucciones del LLM
    return instructions

# Schema para el LLM
tool_schema = {
    "name": "set_llm_instructions",
    "description": "Permite al usuario establecer instrucciones o reglas personalizadas para el LLM, modificando su comportamiento en las interacciones futuras. Útil para definir el tono, el formato de respuesta, o cualquier directriz específica.",
    "parameters": {
        "type": "object",
        "properties": {
            "instructions": {
                "type": "string",
                "description": "Las instrucciones o reglas que se deben dar al LLM para guiar su comportamiento."
            }
        },
        "required": ["instructions"]
    }
}