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

    def get_action_description(self, **kwargs) -> str:
        file_path = kwargs.get("file_path", "llm_context.md")
        return f"Inicializando memoria contextual: {file_path}"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def _run(self, file_path: str = "llm_context.md") -> str:
        base_dir = os.getcwd()
        kogniterm_dir = os.path.join(base_dir, ".kogniterm")
        os.makedirs(kogniterm_dir, exist_ok=True)
        full_path = os.path.join(kogniterm_dir, file_path)

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
            logger.error(f"Error inesperado en MemoryInitTool al inicializar '{file_path}': {e}") # Eliminado exc_info=True
            return f"Error inesperado en MemoryInitTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, file_path: str = "llm_context.md") -> str:
        raise NotImplementedError("memory_init does not support async")
