import asyncio
import os
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class FileReadDirectoryTool(BaseTool):
    name: str = "file_read_directory_tool"
    description: str = "Lee el contenido de un directorio (no recursivo)."

    class FileReadDirectoryInput(BaseModel):
        path: str = Field(description="La ruta del directorio a leer.")

    args_schema: Type[BaseModel] = FileReadDirectoryInput

    def get_action_description(self, **kwargs) -> str:
        path = kwargs.get("path", "")
        return f"Leyendo contenido del directorio: {path}"

    def _run(self, path: str) -> str:
        logger.debug(f"FileReadDirectoryTool - Intentando leer directorio en ruta '{path}'")
        try:
            if not os.path.isdir(path):
                return f"Error: La ruta '{path}' no es un directorio."
            
            output = f"### Contenido del directorio '{path}'\n"
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isfile(item_path):
                    output += f"- Archivo: {item}\n"
                elif os.path.isdir(item_path):
                    output += f"- Directorio: {item}/\n"
            return output
        except FileNotFoundError:
            return f"Error: El directorio '{path}' no fue encontrado."
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para leer el directorio '{path}'."
        except Exception as e:
            logger.error(f"Error inesperado en FileReadDirectoryTool al leer '{path}': {e}", exc_info=True)
            return f"Error inesperado en FileReadDirectoryTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, path: str) -> str:
        return await asyncio.to_thread(self._run, path)