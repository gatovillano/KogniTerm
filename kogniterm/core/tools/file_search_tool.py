import os
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
            # Usar la función glob directamente, ya que es una herramienta de bajo nivel del entorno
            # Si no está disponible, esto causará un NameError o similar, que deberá ser manejado.
            glob_tool = self.llm_service.get_tool("glob")
            if not glob_tool:
                return [f"Error: La herramienta 'glob' no está disponible a través de LLMService."]
            result = glob_tool.invoke({"pattern": pattern, "path": path})
            
            # La función glob devuelve un diccionario con una clave 'glob_response'
            if isinstance(result, dict) and 'glob_response' in result and isinstance(result['glob_response'], list):
                return result['glob_response']
            else:
                # Manejar el caso donde la respuesta no es la esperada
                return [f"Error: La función glob devolvió un formato inesperado: {result}"]
        except NameError:
            return [f"Error: La función 'glob' no está disponible en el entorno."]
        except Exception as e:
            return [f"Error al ejecutar la búsqueda de archivos: {e}"]

    async def _arun(self, pattern: str, path: Optional[str] = None) -> List[str]:
        # Implementar si se necesita una versión asíncrona
        raise NotImplementedError("file_search does not support async")

