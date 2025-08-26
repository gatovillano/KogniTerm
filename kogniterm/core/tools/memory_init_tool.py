import asyncio
import os
import shutil
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_community.chat_message_histories import FileChatMessageHistory
import logging

logger = logging.getLogger(__name__)

class MemoryInitTool(BaseTool):
    name: str = "memory_init_tool"
    description: str = "Inicializa la memoria persistente de la sesión actual creando un archivo de historial de chat de LangChain vacío. Si ya existe, no hace nada."

    class MemoryInitInput(BaseModel):
        destination_filename: str = Field(default="llm_context.json", description="El nombre del archivo de memoria (por defecto 'llm_context.json'). Se recomienda usar '.json'.")

    args_schema: Type[BaseModel] = MemoryInitInput

    def _run(self, destination_filename: str = "llm_context.json") -> str:
        logger.debug(f"MemoryInitTool - Intentando inicializar memoria '{destination_filename}'")
        try:
            dest_path = os.path.join(os.getcwd(), destination_filename)
            dir_name = os.path.dirname(dest_path)

            if dir_name and not os.path.exists(dir_name):
                logger.debug(f"MemoryInitTool - Creando directorios para '{dir_name}'")
                os.makedirs(dir_name, exist_ok=True)
            
            if dir_name and not os.access(dir_name, os.W_OK):
                raise PermissionError(f"No se tienen permisos de escritura en el directorio '{dir_name}'.")

            if os.path.exists(dest_path):
                # Check if it's a valid LangChain chat history file. If not, maybe re-initialize?
                # For now, we'll assume if it exists, it's valid.
                return f"La memoria '{destination_filename}' ya existe en el directorio actual. No se requiere inicialización."
            
            # Initialize an empty FileChatMessageHistory which creates the file
            FileChatMessageHistory(file_path=dest_path)
            return f"Memoria '{destination_filename}' inicializada exitosamente como archivo de historial de chat vacío."

        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para inicializar el archivo de memoria '{destination_filename}'."
        except Exception as e:
            logger.error(f"Error inesperado en MemoryInitTool al inicializar '{destination_filename}': {e}", exc_info=True)
            return f"Error inesperado en MemoryInitTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, destination_filename: str = "llm_context.json") -> str:
        return await asyncio.to_thread(self._run, destination_filename)