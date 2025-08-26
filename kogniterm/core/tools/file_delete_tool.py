import asyncio
import os
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class FileDeleteTool(BaseTool):
    name: str = "file_delete_tool"
    description: str = "Elimina un archivo."

    class FileDeleteInput(BaseModel):
        path: str = Field(description="La ruta del archivo a eliminar.")
        preview: Optional[bool] = Field(default=False, description="Si es True, devuelve una previsualización de la acción sin eliminar el archivo.")

    args_schema: Type[BaseModel] = FileDeleteInput

    def _run(self, path: str, preview: Optional[bool] = False) -> str:
        logger.debug(f"FileDeleteTool - Intentando eliminar archivo en ruta '{path}' (preview: {preview})")
        
        if not os.path.exists(path):
            return f"Error: El archivo '{path}' no existe para eliminar."

        if preview:
            return f"Previsualización de la eliminación del archivo '{path}'. Contenido actual:\n```\n{self._get_file_content_for_preview(path)}\n```\n(El archivo no ha sido eliminado. Para eliminarlo, llama a la herramienta sin 'preview=True' o con 'preview=False')."

        try:
            os.remove(path)
            return f"Archivo '{path}' eliminado exitosamente."
        except FileNotFoundError:
            return f"Error: El archivo '{path}' no fue encontrado para eliminar."
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para eliminar el archivo '{path}'."
        except Exception as e:
            logger.error(f"Error inesperado en FileDeleteTool al eliminar '{path}': {e}", exc_info=True)
            return f"Error inesperado en FileDeleteTool: {e}. Por favor, revisa los logs para más detalles."

    def _get_file_content_for_preview(self, path: str) -> str:
        try:
            with open(path, 'r') as f:
                return f.read()
        except Exception as e:
            return f"[No se pudo leer el contenido para previsualizar: {e}]"

    async def _arun(self, path: str, preview: Optional[bool] = False) -> str:
        return await asyncio.to_thread(self._run, path, preview)