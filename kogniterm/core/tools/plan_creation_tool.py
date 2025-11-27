from typing import Optional, Type, Dict, Any, List
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
import json
from langchain_core.messages import HumanMessage

class PlanCreationToolSchema(BaseModel):
    """Schema for PlanCreationTool."""
    task_description: str = Field(description="A detailed description of the complex task for which a plan needs to be created.")

class PlanCreationTool(BaseTool):
    name: str = "plan_creation_tool"
    description: str = (
        "Generates a detailed, step-by-step plan for complex tasks. "
        "The plan will be presented to the user for confirmation before execution. "
        "Use this tool when a user's request involves multiple steps or requires a strategic approach."
    )
    args_schema: Type[BaseModel] = PlanCreationToolSchema
    llm_service: Optional[Any] = None

    def __init__(self, llm_service: Any = None, **kwargs):
        super().__init__(**kwargs)
        self.llm_service = llm_service

    def _run(self, task_description: str) -> str:
        """
        Generates a plan for a given task description using the LLM.
        Returns a JSON string with status "requires_confirmation" for the approval handler.
        """
        if not self.llm_service:
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
            messages = [HumanMessage(content=prompt)]
            # Use invoke with save_history=False to avoid polluting the main conversation history
            response_generator = self.llm_service.invoke(messages, save_history=False)
            
            full_content = ""
            for chunk in response_generator:
                if isinstance(chunk, str):
                    full_content += chunk
                elif hasattr(chunk, 'content'):
                    full_content += chunk.content
            
            # Parse JSON
            json_str = full_content.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            elif json_str.startswith("```"):
                json_str = json_str[3:]
            
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            
            json_str = json_str.strip()
            
            try:
                plan_data = json.loads(json_str)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return json.dumps({
                    "status": "error", 
                    "message": f"Failed to parse plan JSON: {full_content}"
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