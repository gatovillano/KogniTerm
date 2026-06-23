"""
Skill: task_complete
Señala que la tarea actual está completada y proporciona un resumen de las acciones del LLM
"""

import json
import logging
from typing import Optional, Type, Dict, Any, List
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

logger = logging.getLogger(__name__)

console = Console()

class TaskCompleteInput(BaseModel):
    """Schema de entrada para la herramienta task_complete"""
    # No arguments needed, as it will read from the agent's history
    pass

def task_complete_skill(llm_service: Any = None) -> Dict[str, Any]:
    """
    Función principal que implementa la funcionalidad de task_complete
    
    Args:
        llm_service: Servicio LLM para generar el resumen
    
    Returns:
        Dict: Estado y mensaje de la finalización
    """
    if not llm_service:
        return {"status": "error", "message": "LLMService not initialized for TaskCompleteTool."}

    # Prompt para generar un resumen amigable y humano
    summary_prompt = (
        "Eres un asistente virtual experto, amable y cercano. "
        "Has finalizado con éxito la tarea solicitada por el usuario. "
        "Tu objetivo ahora es generar un resumen elegante, cálido y profesional del trabajo realizado. "
        "Reglas para el resumen:\n"
        "1. Usa lenguaje natural y amigable (tutea al usuario si es apropiado).\n"
        "2. Destaca los hitos principales y el valor entregado.\n"
        "3. Usa emojis de forma moderada pero decorativa para dar calidez.\n"
        "4. Sé conciso pero completo (máximo 2 o 3 párrafos).\n"
        "5. NO incluyas detalles técnicos como IDs de llamadas a funciones o logs internos.\n"
        "6. Termina con un mensaje de cierre positivo y alentador.\n\n"
        "Basándote en el historial de las acciones que has realizado, genera este resumen final para el usuario:"
    )

    try:
        summary_text = ""
        # Invocamos al LLM para generar el resumen amigable sin guardar este paso en el historial
        for chunk in llm_service.invoke(system_message=summary_prompt, save_history=False):
            if isinstance(chunk, str):
                summary_text += chunk
            elif hasattr(chunk, 'content'):
                summary_text += chunk.content
        
        if not summary_text:
            summary_text = "¡Tarea completada con éxito! 🎉\nHe finalizado todas las acciones necesarias para cumplir con tu solicitud."
    except Exception as e:
        summary_text = "¡Tarea completada con éxito! 🎉\n\n(Nota: No pude generar un resumen detallado debido a un pequeño error técnico, pero todo está listo para ti.)"

    console.print(
        Panel(
            Markdown(summary_text),
            title="✨ Tarea Finalizada",
            border_style="cyan",
            padding=(1, 2),
            expand=False
        )
    )
    
    return {"status": "success", "message": "Resumen amigable generado y mostrado al usuario."}

# Schema para el LLM
tool_schema = {
    "name": "task_complete",
    "description": "Signals that the current task is completed and provides a summary of the LLM's actions during the task. This tool should be called when the agent believes the user's request has been fully addressed.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}