from langchain_core.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

class TaskCompleteInput(BaseModel):
    """Input para la herramienta TaskCompleteTool."""
    final_message: str = Field(description="Mensaje final para el usuario, indicando que la tarea ha sido completada.")

class TaskCompleteTool(BaseTool):
    name: str = "task_complete"
    description: str = "Indica que la tarea del usuario ha sido completada y que no se necesitan más acciones."
    args_schema: Type[BaseModel] = TaskCompleteInput

    def _run(self, final_message: str) -> str:
        """Usa la herramienta para indicar que la tarea ha sido completada."""
        return f"Tarea completada: {final_message}"

    async def _arun(self, final_message: str) -> str:
        """Usa la herramienta para indicar que la tarea ha sido completada de forma asíncrona."""
        return await self._run(final_message)