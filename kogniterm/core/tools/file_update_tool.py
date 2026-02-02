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

    args_schema: Type[BaseModel] = FileUpdateInput

    def get_action_description(self, **kwargs) -> str:
        path = kwargs.get("path", "")
        return f"Actualizando archivo completo: {path}"

    def _apply_update(self, path: str, content: str) -> str:
        try:
            if not os.access(path, os.W_OK):
                raise PermissionError(f"No se tienen permisos de escritura en el archivo '{path}'.")
            print(f"🔄 Actualizando archivo: {path}")
            with open(path, 'w') as f:
                f.write(content)
            return json.dumps({"status": "success", "path": path, "message": f"Archivo '{path}' actualizado exitosamente."})
        except Exception as e:
            logger.error(f"Error al aplicar la actualización en '{path}': {e}", exc_info=True)
            return json.dumps({"status": "error", "path": path, "message": f"Error al aplicar la actualización: {e}"})

    def _run(self, path: str, content: Optional[str] = None, confirm: bool = False) -> str:
        logger.debug(f"FileUpdateTool - Intentando actualizar archivo en ruta '{path}' (confirm={confirm})")
        # Ignorar el parámetro 'confirm' cuando viene del LLM
        # Solo se debe usar 'confirm=True' cuando se re-ejecuta tras aprobación del usuario
        # Por lo tanto, siempre requerimos confirmación inicial
        if confirm:
            logger.warning(f"FileUpdateTool - El LLM intentó usar confirm=True. Ignorando y requiriendo confirmación del usuario.")
        try:
            if not os.path.exists(path):
                return f"Error: El archivo '{path}' no existe para actualizar."
            
            with open(path, 'r') as f:
                old_content = f.read()
            
            if content is None:
                return json.dumps({"status": "error", "path": path, "message": "Error: El contenido no puede ser None para la acción 'update'."})
            
            diff = list(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=f'a/{path}',
                tofile=f'b/{path}',
            ))
            
            if not diff:
                return json.dumps({"status": "no_changes", "path": path, "message": f"No hay cambios detectados para '{path}'. No se requiere actualización."})
            
            diff_output = "".join(diff)
            return json.dumps({"status": "requires_confirmation", "path": path, "diff": diff_output, "message": f"Se detectaron cambios para '{path}'. Por favor, confirma para aplicar."})
        except FileNotFoundError:
            return json.dumps({"status": "error", "path": path, "message": f"Error: El archivo '{path}' no fue encontrado para actualizar."})
        except PermissionError:
            return json.dumps({"status": "error", "path": path, "message": f"Error de Permisos: No se tienen los permisos necesarios para leer el archivo '{path}'."})
        except Exception as e:
            logger.error(f"Error inesperado en FileUpdateTool al actualizar '{path}': {e}", exc_info=True)
            return json.dumps({"status": "error", "path": path, "message": f"Error inesperado en FileUpdateTool: {e}. Por favor, revisa los logs para más detalles."})
            
    async def _arun(self, path: str, content: Optional[str] = None) -> str:        return await asyncio.to_thread(self._run, path, content)
