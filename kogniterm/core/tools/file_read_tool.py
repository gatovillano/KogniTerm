import asyncio
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging
from kogniterm.core.context.workspace_context import WorkspaceContext

logger = logging.getLogger(__name__)

class FileReadTool(BaseTool):
    name: str = "file_read_tool"
    description: str = "Lee el contenido de un archivo. Ya no está restringido a archivos dentro del espacio de trabajo."
    workspace_context: Optional[WorkspaceContext] = Field(None, exclude=True) # Ahora es opcional

    class FileReadInput(BaseModel):
        path: str = Field(description="La ruta del archivo a leer.")

    args_schema: Type[BaseModel] = FileReadInput

    def _run(self, path: str) -> str:
        logger.debug(f"FileReadTool - Solicitud de lectura de archivo en ruta '{path}'.")

        resolved_path = path # Por defecto, si no hay contexto

        if self.workspace_context:
            resolved_path = self.workspace_context.resolvePath(path)
        else:
            logger.warning("FileReadTool - workspace_context no está inicializado. Leyendo directamente la ruta proporcionada.")
        
        logger.debug(f"FileReadTool - Leyendo archivo resuelto en ruta '{resolved_path}'.")
        print(f"Leyendo archivo: {resolved_path}") # Mostrar en terminal
        try:
            with open(resolved_path, 'r') as f:
                file_content = f.read()
            return f"### Contenido de '{resolved_path}'\n```\n{file_content}\n```"
        except FileNotFoundError:
            return f"Error: El archivo '{resolved_path}' no fue encontrado."
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para leer el archivo '{resolved_path}'."
        except Exception as e:
            logger.error(f"Error inesperado en FileReadTool al leer '{resolved_path}': {e}", exc_info=True)
            return f"Error inesperado en FileReadTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, path: str) -> str:
        return await asyncio.to_thread(self._run, path)