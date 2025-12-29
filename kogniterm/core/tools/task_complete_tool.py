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

        history = self.llm_service.conversation_history
        summary_lines = []
        tool_calls_count = 0
        ai_messages_count = 0
        human_messages_count = 0

        summary_lines.append("--- Resumen de Acciones del Agente ---")

        for message in history:
            if isinstance(message, AIMessage):
                ai_messages_count += 1
                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        tool_calls_count += 1
                        summary_lines.append(f"🤖 LLM llamó a la herramienta: `{tool_call['name']}` con argumentos: `{tool_call['args']}`")
                elif message.content:
                    summary_lines.append(f"💬 LLM respondió: {message.content[:100]}...") # Truncar para brevedad
            elif isinstance(message, ToolMessage):
                summary_lines.append(f"🛠️ Herramienta `{message.tool_call_id}` respondió: {message.content[:100]}...") # Truncar para brevedad
            elif isinstance(message, HumanMessage):
                human_messages_count += 1
                # summary_lines.append(f"👤 Usuario dijo: {message.content[:100]}...") # Opcional: incluir mensajes de usuario

        summary_lines.append("\n--- Estadísticas ---")
        summary_lines.append(f"Total de mensajes del LLM: {ai_messages_count}")
        summary_lines.append(f"Total de llamadas a herramientas: {tool_calls_count}")
        summary_lines.append(f"Total de mensajes del usuario: {human_messages_count}")
        summary_lines.append("\n¡Tarea completada con éxito! 🎉")

        summary_markdown = "\n".join(summary_lines)

        console.print(
            Panel(
                Markdown(summary_markdown),
                title="✅ Tarea Completada",
                border_style="green",
                expand=False
            )
        )
        
        return {"status": "success", "message": "Resumen de la tarea mostrado al usuario."}

    async def _arun(self) -> Dict[str, Any]:
        """Async version of _run."""
        return self._run()
