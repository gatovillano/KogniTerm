import asyncio
import os
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class FileReadRecursiveDirectoryTool(BaseTool):
    name: str = "file_read_recursive_directory_tool"
    description: str = "Lee el contenido de un directorio de forma recursiva, incluyendo subdirectorios y archivos."

    class FileReadRecursiveDirectoryInput(BaseModel):
        path: str = Field(description="La ruta del directorio a leer recursivamente.")

    args_schema: Type[BaseModel] = FileReadRecursiveDirectoryInput

    def _read_recursive_directory_internal(self, path: str, indent: int = 0) -> str:
        if not os.path.isdir(path):
            return f"Error: La ruta '{path}' no es un directorio."

        output = ""
        prefix = "  " * indent
        
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                output += f"{prefix}- Archivo: {item}\n"
                try:
                    with open(item_path, 'r') as f:
                        file_content = f.read()
                    output += f"{prefix}  ```\n{prefix}{file_content.replace('\\n', '\\n' + prefix)}\n{prefix}  ```\n"
                except Exception as e:
                    output += f"{prefix}  (Error al leer el archivo: {e})\n"
            elif os.path.isdir(item_path):
                output += f"{prefix}- Directorio: {item}/\n"
                output += self._read_recursive_directory_internal(item_path, indent + 1)
        return output

    def _run(self, path: str) -> str:
        logger.debug(f"FileReadRecursiveDirectoryTool - Intentando leer directorio recursivamente en ruta '{path}'")
        try:
            return f"### Contenido recursivo de '{path}'\n" + self._read_recursive_directory_internal(path)
        except FileNotFoundError:
            return f"Error: El directorio '{path}' no fue encontrado."
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para leer el directorio '{path}'."
        except Exception as e:
            logger.error(f"Error inesperado en FileReadRecursiveDirectoryTool al leer recursivamente '{path}': {e}", exc_info=True)
            return f"Error inesperado en FileReadRecursiveDirectoryTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, path: str) -> str:
        return await asyncio.to_thread(self._run, path)