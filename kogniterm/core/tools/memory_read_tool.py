import os
import logging
from typing import Type, Optional, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class MemoryReadTool(BaseTool):
    name: str = "memory_read"
    description: str = "Lee el contenido de la memoria contextual del proyecto desde 'llm_context.md'."

    class MemoryReadInput(BaseModel):
        file_path: Optional[str] = Field(
            default="llm_context.md",
            description="La ruta del archivo de memoria a leer (por defecto 'llm_context.md' en el directorio actual)."
        )

    args_schema: Type[BaseModel] = MemoryReadInput

    def get_action_description(self, **kwargs) -> str:
        file_path = kwargs.get("file_path", "llm_context.md")
        return f"Leyendo memoria contextual: {file_path}"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def _run(self, file_path: str = "llm_context.md") -> str:
        base_dir = os.getcwd()
        kogniterm_dir = os.path.join(base_dir, ".kogniterm")
        os.makedirs(kogniterm_dir, exist_ok=True)
        # Asegurarse de que file_path sea solo el nombre del archivo, no una ruta relativa con .kogniterm/
        base_file_name = os.path.basename(file_path)
        full_path = os.path.join(kogniterm_dir, base_file_name)
        logger.debug(f"MemoryReadTool - Intentando leer memoria desde '{full_path}'")

        if not os.path.exists(full_path):
            return f"Error: El archivo de memoria '{file_path}' no fue encontrado."
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"### Contenido de la Memoria Contextual ({file_path})\n```markdown\n{content}\n```"
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para leer el archivo de memoria '{file_path}'."
        except Exception as e:
            logger.error(f"Error inesperado en MemoryReadTool al leer '{file_path}': {e}", exc_info=True)
            return f"Error inesperado en MemoryReadTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, file_path: str = "llm_context.md") -> str:
        raise NotImplementedError("memory_read does not support async")
