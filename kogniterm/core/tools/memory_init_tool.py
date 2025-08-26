import asyncio
import os
import shutil
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class MemoryInitTool(BaseTool):
    name: str = "memory_init_tool"
    description: str = "Inicializa la memoria persistente de la sesión actual copiando un archivo base o creando uno vacío."

    class MemoryInitInput(BaseModel):
        base_memory_path: Optional[str] = Field(default=None, description="Ruta al archivo de memoria base/plantilla. Si no se proporciona, se crea un archivo vacío.")
        destination_filename: str = Field(default="llm_context.txt", description="El nombre del archivo de memoria a crear en el directorio actual (por defecto 'llm_context.txt').")

    args_schema: Type[BaseModel] = MemoryInitInput

    def _run(self, base_memory_path: Optional[str] = None, destination_filename: str = "llm_context.txt") -> str:
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
                return f"La memoria '{destination_filename}' ya existe en el directorio actual. No se requiere inicialización."
            
            if base_memory_path:
                if not os.path.exists(base_memory_path):
                    return f"Error: El archivo de memoria base '{base_memory_path}' no fue encontrado."
                shutil.copy(base_memory_path, dest_path)
                return f"Memoria '{destination_filename}' inicializada exitosamente copiando desde '{base_memory_path}'."
            else:
                with open(dest_path, 'w') as f:
                    f.write("# Memoria de Sesión del LLM\n\n") # Contenido inicial vacío o marcador
                return f"Memoria '{destination_filename}' inicializada exitosamente como archivo vacío."

        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para inicializar el archivo de memoria '{destination_filename}'."
        except Exception as e:
            logger.error(f"Error inesperado en MemoryInitTool al inicializar '{destination_filename}': {e}", exc_info=True)
            return f"Error inesperado en MemoryInitTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, base_memory_path: Optional[str] = None, destination_filename: str = "llm_context.txt") -> str:
        return await asyncio.to_thread(self._run, base_memory_path, destination_filename)