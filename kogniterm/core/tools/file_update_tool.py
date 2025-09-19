import asyncio
import os
import difflib
import json
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging

# Códigos ANSI para colores
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_RESET = "\033[0m"

logger = logging.getLogger(__name__)

class FileUpdateTool(BaseTool):
    name: str = "file_update_tool"
    description: str = "Actualiza el contenido de un archivo existente. Requiere confirmación si hay cambios."

    class FileUpdateInput(BaseModel):
        path: str = Field(description="La ruta del archivo a actualizar.")
        content: Optional[str] = Field(default=None, description="El nuevo contenido del archivo.")
        confirm: Optional[bool] = Field(default=False, description="Confirmación para aplicar la actualización.")

    args_schema: Type[BaseModel] = FileUpdateInput

    def _run(self, path: str, content: Optional[str] = None, confirm: Optional[bool] = False) -> str:
        logger.debug(f"FileUpdateTool - Intentando actualizar archivo en ruta '{path}'")
        try:
            if not os.path.exists(path):
                return f"Error: El archivo '{path}' no existe para actualizar."
            
            with open(path, 'r') as f:
                old_content = f.read()

            if content is None:
                return "Error: El contenido no puede ser None para la acción 'update'."

            if not confirm:
                diff = list(difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f'a/{path}',
                    tofile=f'b/{path}',
                ))
                if not diff:
                    # Este bloque debe estar indentado correctamente
                    return f"No hay cambios detectados para '{path}'. No se requiere actualización."
                
                colorized_diff_lines = []
                for line in diff:
                    if line.startswith('-'):
                        colorized_diff_lines.append(f"{COLOR_RED}{line}{COLOR_RESET}")
                    elif line.startswith('+'):
                        colorized_diff_lines.append(f"{COLOR_GREEN}{line}{COLOR_RESET}")
                    else:
                        colorized_diff_lines.append(line)
                
                colorized_diff_output = "".join(colorized_diff_lines)

                return f"Se detectaron cambios para '{path}'. Por favor, confirma para aplicar:\n{colorized_diff_output}"
            else:
                if not os.access(path, os.W_OK):
                    raise PermissionError(f"No se tienen permisos de escritura en el archivo '{path}'.")
                with open(path, 'w') as f:
                    f.write(content)
                return f"Archivo '{path}' actualizado exitosamente."
        except FileNotFoundError:
            return f"Error: El archivo '{path}' no fue encontrado para actualizar."
        except PermissionError:
            return f"Error de Permisos: No se tienen los permisos necesarios para actualizar el archivo '{path}'."
        except Exception as e:
            logger.error(f"Error inesperado en FileUpdateTool al actualizar '{path}': {e}", exc_info=True)
            return f"Error inesperado en FileUpdateTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, path: str, content: Optional[str] = None, confirm: Optional[bool] = False) -> str:
        return await asyncio.to_thread(self._run, path, content, confirm)
