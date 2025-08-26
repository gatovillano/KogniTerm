import asyncio
import os
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class FileDeleteTool(BaseTool):
    name: str = "file_delete_tool"
    description: str = "Elimina un archivo."

    class FileDeleteInput(BaseModel):
        path: str = Field(description="La ruta del archivo a eliminar.")

    args_schema: Type[BaseModel] = FileDeleteInput

    def _run(self, path: str) -> str:
        logger.debug(f"FileDeleteTool - Intentando eliminar archivo en ruta '{path}'")
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

    async def _arun(self, path: str) -> str:
        return await asyncio.to_thread(self._run, path)