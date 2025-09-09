from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class SetLLMInstructionsInput(BaseModel):
    """Input for SetLLMInstructionsTool."""
    instructions: str = Field(..., description="Las instrucciones o reglas que se deben dar al LLM para guiar su comportamiento.")

class SetLLMInstructionsTool(BaseTool):
    name: str = "set_llm_instructions"
    description: str = (
        "Permite al usuario establecer instrucciones o reglas personalizadas para el LLM, "
        "modificando su comportamiento en las interacciones futuras. "
        "Útil para definir el tono, el formato de respuesta, o cualquier directriz específica."
    )
    args_schema: type[BaseModel] = SetLLMInstructionsInput

    def _run(self, instructions: str) -> str:
        """Sincrónicamente establece las instrucciones del LLM."""
        return instructions

    async def _arun(self, instructions: str) -> str:
        """Asincrónicamente establece las instrucciones del LLM."""
        return instructions