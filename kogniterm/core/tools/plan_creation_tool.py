from typing import Optional, Type, Dict, Any, List
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
# from kogniterm.core.llm_service import LLMService # Eliminar esta línea
import json

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
    llm_service: Optional[Any] = None # Cambiar el tipo a Any para evitar la importación circular

    def __init__(self, llm_service: Any, **kwargs): # Cambiar el tipo a Any
        super().__init__(**kwargs)
        self.llm_service = llm_service

    def _run(self, task_description: str) -> Dict[str, Any]:
        """
        Generates a plan for a given task description using the LLM.
        The plan is then formatted for user confirmation.
        """
        if not self.llm_service:
            return {"status": "error", "message": "LLMService not initialized for PlanCreationTool."}

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
        )