import os
import glob # ¡Nueva importación!
from typing import List, Optional, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, SkipValidation

class FileSearchInput(BaseModel):
    pattern: str = Field(description="El patrón glob a buscar (ej. '*.txt', 'src/**/*.py').")
    path: Optional[str] = Field(None, description="El directorio absoluto donde buscar. Si no se proporciona, busca en el directorio de trabajo actual.")

class FileSearchTool(BaseTool):
    name: str = "file_search"
    description: str = "Busca archivos que coincidan con un patrón glob en un directorio específico o en el directorio de trabajo actual. Devuelve una lista de rutas de archivo absolutas."
    args_schema: type[BaseModel] = FileSearchInput

    llm_service: SkipValidation[Any] # Esto es para la instancia de LLMService, no para la clase

    def __init__(self, llm_service, **kwargs):
        super().__init__(llm_service=llm_service, **kwargs)

    def _run(self, pattern: str, path: Optional[str] = None) -> List[str]:
        if path and not os.path.isabs(path):
            raise ValueError("El 'path' debe ser una ruta absoluta.")
        
        try:
            search_path = path if path else os.getcwd()
            full_pattern = os.path.join(search_path, pattern)
            
            # Usar glob.glob directamente
            found_files = [os.path.abspath(f) for f in glob.glob(full_pattern, recursive=True)]
            return found_files
        except Exception as e:
            return [f"Error al ejecutar la búsqueda de archivos: {e}"]

    async def _arun(self, pattern: str, path: Optional[str] = None) -> List[str]:
        # Implementar si se necesita una versión asíncrona
        raise NotImplementedError("file_search does not support async")
