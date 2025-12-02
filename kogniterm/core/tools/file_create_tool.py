import asyncio
import os
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class FileCreateTool(BaseTool):
    name: str = "file_create_tool"
    description: str = "Crea un nuevo archivo o sobrescribe uno existente con el contenido proporcionado."

    class FileCreateInput(BaseModel):
        path: str = Field(description="La ruta del archivo a crear.")
        content: Optional[str] = Field(default=None, description="El contenido del archivo.")
        preview: Optional[bool] = Field(default=False, description="Si es True, devuelve una previsualización del contenido a crear sin crear el archivo.")

    args_schema: Type[BaseModel] = FileCreateInput

    def _run(self, path: str, content: Optional[str] = None, preview: Optional[bool] = False) -> str:
        logger.debug(f"FileCreateTool - Intentando crear archivo en ruta '{path}' (preview: {preview})")
        
        content_to_write = content if content is not None else ""

        if preview:
            return f"Previsualización de la creación del archivo '{path}':\n```\n{content_to_write}\n```\n(El archivo no ha sido creado. Para crearlo, llama a la herramienta sin 'preview=True' o con 'preview=False')."

        try:
            dir_name = os.path.dirname(path)
            if dir_name and not os.path.exists(dir_name):
                logger.debug(f"FileCreateTool - Creando directorios para '{dir_name}'")
                os.makedirs(dir_name, exist_ok=True)
            
            # Verificar permisos de escritura en el directorio antes de intentar abrir el archivo
            if dir_name and not os.access(dir_name, os.W_OK):
                raise PermissionError(f"No se tienen permisos de escritura en el directorio '{dir_name}'.")

            logger.debug(f"FileCreateTool - Abriendo archivo '{path}' en modo escritura.")
            print(f"📝 Creando archivo: {path}")
            with open(path, 'w') as f:
                f.write(content_to_write)
            logger.info(f"FileCreateTool - Contenido escrito en '{path}':\n{content_to_write[:200]}...") # Log parcial para evitar saturación
            return f"Archivo '{path}' creado/sobrescrito exitosamente."
        except FileNotFoundError:
            return f"Error: El archivo o directorio '{path}' no fue encontrado. Esto puede indicar una ruta inválida o un problema de acceso en un directorio padre."
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para crear el archivo '{path}'. Asegúrate de que la aplicación tenga los permisos de escritura adecuados."
        except Exception as e:
            logger.error(f"Error inesperado en FileCreateTool al crear '{path}': {e}", exc_info=True)
            return f"Error inesperado en FileCreateTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, path: str, content: Optional[str] = None, preview: Optional[bool] = False) -> str:
        return await asyncio.to_thread(self._run, path, content, preview)