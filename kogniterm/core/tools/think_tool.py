import sys
from langchain.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

class ThinkInput(BaseModel):
    thought: str = Field(..., description="El razonamiento detallado o análisis antes de realizar una acción.")

class ThinkTool(BaseTool):
    name: str = "think_tool"
    description: str = "Usa esta herramienta para razonar, planificar y analizar antes de tomar decisiones o ejecutar otras herramientas. Es obligatoria para procesos de pensamiento profundo."
    args_schema: Type[BaseModel] = ThinkInput

    def _run(self, thought: str) -> str:
        """Usa el razonamiento proporcionado."""
        return f"Razonamiento procesado: {thought}"

    async def _arun(self, thought: str) -> str:
        """Usa el razonamiento proporcionado de forma asíncrona."""
        print(f"Pensando: {thought}", file=sys.stderr)
        return self._run(thought)
