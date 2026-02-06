from typing import Optional, Type, Dict, Any, List
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
# from kogniterm.core.llm_service import LLMService # Eliminar esta línea
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage

console = Console()

class TaskCompleteToolSchema(BaseModel):
    """Schema for TaskCompleteTool."""
    # No arguments needed, as it will read from the agent's history
    pass

class TaskCompleteTool(BaseTool):
    name: str = "task_complete_tool"
    description: str = (
        "Signals that the current task is completed and provides a summary of the LLM's actions during the task. "
        "This tool should be called when the agent believes the user's request has been fully addressed."
    )
    args_schema: Type[BaseModel] = TaskCompleteToolSchema

    def get_action_description(self, **kwargs) -> str:
        return "Finalizando tarea y generando resumen"
    llm_service: Optional[Any] = None # Cambiar el tipo a Any para evitar la importación circular

    def __init__(self, llm_service: Any, **kwargs): # Cambiar el tipo a Any
        super().__init__(**kwargs)
        self.llm_service = llm_service

    def _run(self) -> Dict[str, Any]:
        """
        Generates a summary of the LLM's actions from the agent's history
        and displays it in a rich panel.
        """
        if not self.llm_service:
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
            for chunk in self.llm_service.invoke(system_message=summary_prompt, save_history=False):
                if isinstance(chunk, str):
                    summary_text += chunk
                elif hasattr(chunk, 'content'):
                    summary_text += chunk.content
            
            if not summary_text:
                summary_text = "¡Tarea completada con éxito! 🎉\nHe finalizado todas las acciones necesarias para cumplir con tu solicitud."
        except Exception as e:
            summary_text = f"¡Tarea completada con éxito! 🎉\n\n(Nota: No pude generar un resumen detallado debido a un pequeño error técnico, pero todo está listo para ti.)"

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

    async def _arun(self) -> Dict[str, Any]:
        """Async version of _run."""
        return self._run()
