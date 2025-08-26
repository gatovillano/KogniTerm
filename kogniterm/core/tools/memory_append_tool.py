import asyncio
import os
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class MemoryAppendTool(BaseTool):
    name: str = "memory_append_tool"
    description: str = "Añade contenido al final de la memoria persistente de la sesión actual. Si el archivo no existe, lo crea."

    class MemoryAppendInput(BaseModel):
        content: str = Field(description="El contenido a añadir a la memoria.")
        filename: str = Field(default="llm_context.txt", description="El nombre del archivo de memoria (por defecto 'llm_context.txt').")

    args_schema: Type[BaseModel] = MemoryAppendInput

    def _run(self, content: str, filename: str = "llm_context.txt") -> str:
        logger.debug(f"MemoryAppendTool - Intentando añadir contenido a la memoria '{filename}'")
        try:
            path = os.path.join(os.getcwd(), filename)
            dir_name = os.path.dirname(path)
            
            if dir_name and not os.path.exists(dir_name):
                logger.debug(f"MemoryAppendTool - Creando directorios para '{dir_name}'")
                os.makedirs(dir_name, exist_ok=True)
            
            if dir_name and not os.access(dir_name, os.W_OK):
                raise PermissionError(f"No se tienen permisos de escritura en el directorio '{dir_name}'.")

            with open(path, 'a') as f: # 'a' for append mode
                f.write(content + "\n") # Add newline for clarity
            logger.info(f"MemoryAppendTool - Contenido añadido a '{filename}':\n{content[:200]}...") # Log parcial
            return f"Contenido añadido exitosamente a la memoria '{filename}'."
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para añadir contenido al archivo de memoria '{filename}'."
        except Exception as e:
            logger.error(f"Error inesperado en MemoryAppendTool al añadir contenido a '{filename}': {e}", exc_info=True)
            return f"Error inesperado en MemoryAppendTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, content: str, filename: str = "llm_context.txt") -> str:
        return await asyncio.to_thread(self._run, content, filename)