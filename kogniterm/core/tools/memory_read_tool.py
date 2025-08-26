import asyncio
import os
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class MemoryReadTool(BaseTool):
    name: str = "memory_read_tool"
    description: str = "Lee el contenido de la memoria persistente de la sesión actual."

    class MemoryReadInput(BaseModel):
        filename: str = Field(default="llm_context.txt", description="El nombre del archivo de memoria (por defecto 'llm_context.txt').")

    args_schema: Type[BaseModel] = MemoryReadInput

    def _run(self, filename: str = "llm_context.txt") -> str:
        logger.debug(f"MemoryReadTool - Intentando leer memoria desde '{filename}'")
        try:
            path = os.path.join(os.getcwd(), filename)
            with open(path, 'r') as f:
                memory_content = f.read()
            return f"### Contenido de la memoria '{filename}'\n```\n{memory_content}\n```"
        except FileNotFoundError:
            return f"Memoria '{filename}' no encontrada. La memoria está vacía o no ha sido inicializada."
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para leer el archivo de memoria '{filename}'."
        except Exception as e:
            logger.error(f"Error inesperado en MemoryReadTool al leer '{filename}': {e}", exc_info=True)
            return f"Error inesperado en MemoryReadTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, filename: str = "llm_context.txt") -> str:
        return await asyncio.to_thread(self._run, filename)