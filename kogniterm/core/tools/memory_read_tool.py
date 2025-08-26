import asyncio
import os
from typing import Type, Optional, List
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.messages import BaseMessage
import logging
import json

logger = logging.getLogger(__name__)

class MemoryReadTool(BaseTool):
    name: str = "memory_read_tool"
    description: str = "Lee el historial de mensajes de la memoria persistente de la sesión actual."

    class MemoryReadInput(BaseModel):
        filename: str = Field(default="llm_context.json", description="El nombre del archivo de memoria (por defecto 'llm_context.json').")

    args_schema: Type[BaseModel] = MemoryReadInput

    def _run(self, filename: str = "llm_context.json") -> List[BaseMessage]:
        logger.debug(f"MemoryReadTool - Intentando leer memoria desde '{filename}'")
        try:
            path = os.path.join(os.getcwd(), filename)
            
            if not os.path.exists(path):
                return [] # Retorna una lista vacía si el archivo no existe o no ha sido inicializado.

            history = FileChatMessageHistory(file_path=path)
            return history.messages
        except PermissionError:
            logger.error(f"Error de Permisos: No se tienen los permisos necesarios para leer el archivo de memoria '{filename}'.", exc_info=True)
            return []
        except json.JSONDecodeError:
            logger.error(f"Error de formato JSON en el archivo de memoria '{filename}'. El archivo podría estar corrupto.", exc_info=True)
            # Podrías considerar hacer un backup del archivo corrupto y retornar vacío
            return []
        except Exception as e:
            logger.error(f"Error inesperado en MemoryReadTool al leer '{filename}': {e}", exc_info=True)
            return []

    async def _arun(self, filename: str = "llm_context.json") -> List[BaseMessage]:
        return await asyncio.to_thread(self._run, filename)