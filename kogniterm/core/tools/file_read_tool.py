import asyncio
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class FileReadTool(BaseTool):
    name: str = "file_read_tool"
    description: str = "Lee el contenido de un archivo."

    class FileReadInput(BaseModel):
        path: str = Field(description="La ruta del archivo a leer.")

    args_schema: Type[BaseModel] = FileReadInput

    def _run(self, path: str) -> str:
        logger.debug(f"FileReadTool - Leyendo archivo en ruta '{path}'.")
        try:
            with open(path, 'r') as f:
                file_content = f.read()
            return f"### Contenido de '{path}'\n```\n{file_content}\n```"
        except FileNotFoundError:
            return f"Error: El archivo '{path}' no fue encontrado."
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para leer el archivo '{path}'."
        except Exception as e:
            logger.error(f"Error inesperado en FileReadTool al leer '{path}': {e}", exc_info=True)
            return f"Error inesperado en FileReadTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, path: str) -> str:
        return await asyncio.to_thread(self._run, path)