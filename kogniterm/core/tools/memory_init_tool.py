import os
import logging
from typing import Type, Optional, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class MemoryInitTool(BaseTool):
    name: str = "memory_init"
    description: str = "Inicializa la memoria contextual del proyecto creando un archivo 'llm_context.md' si no existe."

    class MemoryInitInput(BaseModel):
        file_path: Optional[str] = Field(
            default="llm_context.md",
            description="La ruta del archivo de memoria a inicializar (por defecto 'llm_context.md' en el directorio actual)."
        )

    args_schema: Type[BaseModel] = MemoryInitInput

    def _run(self, file_path: str = "llm_context.md") -> str:
        full_path = os.path.join(os.getcwd(), file_path)
        dir_name = os.path.dirname(full_path)

        if not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name, exist_ok=True)
                logger.debug(f"MemoryInitTool - Creando directorios para '{file_path}'")
            except OSError as e:
                return f"Error de Permisos: No se tienen permisos de escritura en el directorio '{dir_name}'. {e}"

        if os.path.exists(full_path):
            return f"La memoria '{file_path}' ya existe en el directorio actual. No se requiere inicialización."
        
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write("# Memoria Contextual del Proyecto\n\n")
            logger.info(f"Memoria '{file_path}' inicializada exitosamente como archivo de historial de chat vacío.")
            return f"Memoria '{file_path}' inicializada exitosamente."
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para inicializar el archivo de memoria '{file_path}'. Asegúrate de que la aplicación tenga los permisos de escritura adecuados."
        except Exception as e:
            logger.error(f"Error inesperado en MemoryInitTool al inicializar '{file_path}': {e}", exc_info=True)
            return f"Error inesperado en MemoryInitTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, file_path: str = "llm_context.md") -> str:
        raise NotImplementedError("memory_init does not support async")
