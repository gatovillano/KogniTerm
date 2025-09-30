import os
import logging
from typing import Type, Optional, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class MemoryAppendTool(BaseTool):
    name: str = "memory_append"
    description: str = "Añade contenido a la memoria contextual del proyecto en 'llm_context.md'. Si el archivo no existe, lo crea."

    class MemoryAppendInput(BaseModel):
        content: str = Field(description="El contenido a añadir a la memoria.")
        file_path: Optional[str] = Field(
            default="llm_context.md",
            description="La ruta del archivo de memoria a modificar (por defecto 'llm_context.md' en el directorio actual)."
        )

    args_schema: Type[BaseModel] = MemoryAppendInput

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def _run(self, content: str, file_path: str = "llm_context.md") -> str:
        base_dir = os.getcwd()
        kogniterm_dir = os.path.join(base_dir, ".kogniterm")
        os.makedirs(kogniterm_dir, exist_ok=True)
        # Asegurarse de que file_path sea solo el nombre del archivo, no una ruta relativa con .kogniterm/
        base_file_name = os.path.basename(file_path)
        full_path = os.path.join(kogniterm_dir, base_file_name)

        try:
            with open(full_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{content}\n")
            return f"Contenido añadido exitosamente a la memoria '{file_path}'."
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para escribir en el archivo de memoria '{file_path}'."
        except Exception as e:
            logger.error(f"Error inesperado en MemoryAppendTool al añadir contenido a '{file_path}': {e}", exc_info=True)
            return f"Error inesperado en MemoryAppendTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, content: str, file_path: str = "llm_context.md") -> str:
        raise NotImplementedError("memory_append does not support async")
