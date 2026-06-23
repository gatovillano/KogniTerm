"""
Skill: plan_creation
Genera planes detallados y paso a paso para tareas complejas
"""

import json
import logging
from typing import Optional, Type, Dict, Any, List
from pydantic import BaseModel, Field
import re
import json

logger = logging.getLogger(__name__)

class PlanCreationInput(BaseModel):
    """Schema de entrada para la herramienta plan_creation"""
    task_description: str = Field(description="A detailed description of the complex task for which a plan needs to be created.")

def plan_creation_skill(task_description: str, llm_service: Any = None) -> str:
    """
    Función principal que implementa la funcionalidad de plan_creation
    
    Args:
        task_description: Descripción detallada de la tarea compleja
        llm_service: Servicio LLM para generar el plan
    
    Returns:
        str: Plan en formato JSON
    """
    if not llm_service:
        return json.dumps({
            "status": "error", 
            "message": "LLMService not initialized for PlanCreationTool."
        })

    # Prompt the LLM to generate a plan
    prompt = (
        f"Eres un experto planificador de tareas. Genera un plan detallado y paso a paso para la siguiente tarea. "
        f"El plan debe ser una lista numerada de acciones claras y concisas. "
        f"Cada paso debe ser una acción específica que el agente pueda ejecutar. "
        f"La tarea es: '{task_description}'\n\n"
        f"Formato de salida (JSON):\n"
        f"{{\n"
        f'  "plan_title": "Título del Plan",\n'
        f'  "steps": [\n'
        f'    {{"step": 1, "description": "Descripción del paso 1"}},\n'
        f'    {{"step": 2, "description": "Descripción del paso 2"}}\n'
        f'  ]\n'
        f"}}\n"
        f"Responde SOLO con el JSON válido."
    )

    try:
        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content=prompt)]
        
        # Use invoke with save_history=False to avoid polluting the main conversation history
        response_generator = llm_service.invoke(messages, save_history=False)
        
        full_content = ""
        for chunk in response_generator:
            if isinstance(chunk, str):
                full_content += chunk
            elif hasattr(chunk, 'content'):
                full_content += chunk.content
        
        # Parse JSON
        # Try to find a JSON block enclosed in ```json ... ``` or ``` ... ```
        json_match = re.search(r"```json\s*(.*?)\s*```", full_content, re.DOTALL)
        if not json_match:
            json_match = re.search(r"```\s*(.*?)\s*```", full_content, re.DOTALL)
        
        json_str_to_parse = ""
        if json_match:
            json_str_to_parse = json_match.group(1).strip()
        else:
            # Fallback: try to find the first { and last }
            start_idx = full_content.find('{')
            end_idx = full_content.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str_to_parse = full_content[start_idx : end_idx + 1].strip()
            else:
                # If no JSON structure is found, raise an error
                return json.dumps({
                    "status": "error",
                    "message": f"No JSON content found in LLM response. Original content: {full_content}"
                })

        try:
            plan_data = json.loads(json_str_to_parse)
        except json.JSONDecodeError as e:
            return json.dumps({
                "status": "error",
                "message": f"Failed to parse plan JSON: {e}. Content attempted to parse: {json_str_to_parse}. Original content: {full_content}"
            })
        
        # Extract plan details
        title = plan_data.get("plan_title", "Plan Propuesto")
        steps = plan_data.get("steps", [])
        
        # Return in the format expected by CommandApprovalHandler
        return json.dumps({
            "status": "requires_confirmation",
            "operation": "plan_creation",
            "plan_title": title,
            "plan_steps": steps,
            "message": f"Se ha generado un plan para: {task_description}",
            "task_description": task_description
        })

    except Exception as e:
        return json.dumps({
            "status": "error", 
            "message": f"Error generating plan: {e}"
        })

# Schema para el LLM
tool_schema = {
    "name": "plan_creation",
    "description": "Generates a detailed, step-by-step plan for complex tasks. The plan will be presented to the user for confirmation before execution. Use this tool when a user's request involves multiple steps or requires a strategic approach.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": "A detailed description of the complex task for which a plan needs to be created."
            }
        },
        "required": ["task_description"]
    }
}