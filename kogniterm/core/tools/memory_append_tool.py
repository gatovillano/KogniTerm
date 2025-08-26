import asyncio
import os
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, FunctionMessage, ToolMessage
import logging
import json

logger = logging.getLogger(__name__)

class MemoryAppendTool(BaseTool):
    name: str = "memory_append_tool"
    description: str = "Añade un mensaje (humano o de IA) al historial de la memoria persistente de la sesión actual."

    class MemoryAppendInput(BaseModel):
        message_type: str = Field(description="El tipo de mensaje a añadir (human, ai, system, function, tool).")
        content: str = Field(description="El contenido del mensaje.")
        filename: str = Field(default="llm_context.json", description="El nombre del archivo de memoria (por defecto 'llm_context.json').")
        name: Optional[str] = Field(default=None, description="El nombre del autor del mensaje (solo para mensajes de función/herramienta).")
        tool_call_id: Optional[str] = Field(default=None, description="El ID de la llamada a la herramienta (solo para mensajes de herramienta).")

    args_schema: Type[BaseModel] = MemoryAppendInput

    def _run(self, message_type: str, content: str, filename: str = "llm_context.json", name: Optional[str] = None, tool_call_id: Optional[str] = None) -> str:
        logger.debug(f"MemoryAppendTool - Intentando añadir mensaje a la memoria '{filename}'")
        try:
            path = os.path.join(os.getcwd(), filename)
            
            # Asegurarse de que el archivo de memoria exista y esté inicializado
            if not os.path.exists(path):
                return f"Error: La memoria '{filename}' no ha sido inicializada. Por favor, inicialícela primero."

            history = FileChatMessageHistory(file_path=path)

            if message_type == "human":
                history.add_user_message(content)
            elif message_type == "ai":
                history.add_ai_message(content)
            elif message_type == "system":
                history.add_message(SystemMessage(content=content))
            elif message_type == "function":
                # LangChain usa FunctionMessage para la salida de la función
                if not name:
                    return "Error: Los mensajes de tipo 'function' requieren el parámetro 'name'."
                history.add_message(FunctionMessage(content=content, name=name))
            elif message_type == "tool":
                # LangChain usa ToolMessage para la salida de la herramienta
                if not tool_call_id:
                    return "Error: Los mensajes de tipo 'tool' requieren el parámetro 'tool_call_id'."
                history.add_message(ToolMessage(content=content, tool_call_id=tool_call_id))
            else:
                return f"Tipo de mensaje '{message_type}' no soportado. Use 'human', 'ai', 'system', 'function', o 'tool'."
            
            logger.info(f"MemoryAppendTool - Mensaje '{message_type}' añadido a '{filename}'.")
            return f"Mensaje añadido exitosamente a la memoria '{filename}'."
        except Exception as e:
            logger.error(f"Error inesperado en MemoryAppendTool al añadir contenido a '{filename}': {e}", exc_info=True)
            return f"Error inesperado en MemoryAppendTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, message_type: str, content: str, filename: str = "llm_context.json", name: Optional[str] = None, tool_call_id: Optional[str] = None) -> str:
        return await asyncio.to_thread(self._run, message_type, content, filename, name, tool_call_id)