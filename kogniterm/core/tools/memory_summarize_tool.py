import os
import logging
from typing import Type, Optional, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class MemorySummarizeTool(BaseTool):
    name: str = "memory_summarize"
    description: str = "Resume el contenido de la memoria contextual del proyecto en 'llm_context.md'. (Nota: La implementación actual es un placeholder y no realiza una sumarización real con LLM)."

    class MemorySummarizeInput(BaseModel):
        file_path: Optional[str] = Field(
            default="llm_context.md",
            description="La ruta del archivo de memoria a resumir (por defecto 'llm_context.md' en el directorio actual)."
        )
        max_length: Optional[int] = Field(
            default=500,
            description="Longitud máxima deseada para el resumen (en caracteres)."
        )

    args_schema: Type[BaseModel] = MemorySummarizeInput

    def _run(self, file_path: str = "llm_context.md", max_length: int = 500) -> str:
        kogniterm_dir = os.path.join(os.getcwd(), ".kogniterm")
        os.makedirs(kogniterm_dir, exist_ok=True)
        full_path = os.path.join(kogniterm_dir, file_path)

        if not os.path.exists(full_path):
            return f"Error: El archivo de memoria '{file_path}' no fue encontrado para resumir."
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Placeholder for actual LLM summarization
            if len(content) > max_length:
                summarized_content = content[:max_length] + "... [Contenido resumido - Placeholder]"
            else:
                summarized_content = content

            # Overwrite the file with the summarized content
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(summarized_content)

            return f"Memoria '{file_path}' resumida exitosamente. Nuevo contenido: {summarized_content}"
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para resumir el archivo de memoria '{file_path}'."
        except Exception as e:
            logger.error(f"Error inesperado en MemorySummarizeTool al resumir '{file_path}': {e}", exc_info=True)
            return f"Error inesperado en MemorySummarizeTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, file_path: str = "llm_context.md", max_length: int = 500) -> str:
        raise NotImplementedError("memory_summarize does not support async")
