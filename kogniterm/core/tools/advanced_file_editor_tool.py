import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

import difflib
import re
import os
import json
from typing import Optional, Dict, Any, Type # ¡Aquí va la importación de typing!
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

def _read_file_content(path: str) -> Dict[str, Any]:
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return {"status": "success", "content": f.read()}
        else:
            return {"status": "error", "message": f"El archivo '{path}' no fue encontrado."}
    except Exception as e:
        return {"status": "error", "message": f"Error al leer el archivo '{path}': {e}"}

def _apply_advanced_update(path: str, content: str) -> Dict[str, Any]:
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"status": "success", "path": path, "message": f"Archivo '{path}' actualizado exitosamente."}
    except Exception as e:
        return {"status": "error", "path": path, "message": f"Error al aplicar la actualización: {e}"}

class AdvancedFileEditorTool(BaseTool):
    name: str = "advanced_file_editor"
    description: str = "Realiza operaciones de edición avanzadas en un archivo, como insertar, reemplazar con regex, o añadir contenido. La confirmación de los cambios se gestiona de forma conversacional."

    class AdvancedFileEditorInput(BaseModel):
        path: str = Field(description="La ruta del archivo a editar.")
        action: str = Field(description="La operación a realizar: 'insert_line', 'replace_regex', 'prepend_content', 'append_content'.")
        content: Optional[str] = Field(default=None, description="El contenido a insertar, añadir o usar para reemplazar (para 'insert_line', 'prepend_content', 'append_content').")
        line_number: Optional[int] = Field(default=None, description="El número de línea para la acción 'insert_line' (basado en 1).")
        regex_pattern: Optional[str] = Field(default=None, description="El patrón de expresión regular a buscar para la acción 'replace_regex'.")
        replacement_content: Optional[str] = Field(default=None, description="El contenido de reemplazo para la acción 'replace_regex'.")
        confirm: bool = Field(default=False, description="Si es True, confirma la operación de escritura sin requerir aprobación adicional.")

    args_schema: Type[BaseModel] = AdvancedFileEditorInput

    def _run(self, path: str, action: str, content: Optional[str] = None, line_number: Optional[int] = None, regex_pattern: Optional[str] = None, replacement_content: Optional[str] = None, confirm: bool = False) -> Dict[str, Any]:
        logger.debug(f"Invocando AdvancedFileEditorTool para editar el archivo: '{path}' con la acción: '{action}'.")
        logger.debug(f"AdvancedFileEditorTool._run - Valor de confirm: {confirm}")
        # print(f"*** DEBUG PRINT: AdvancedFileEditorTool._run - Valor de confirm: {confirm} ***")
        try:
            read_result = _read_file_content(path=path)
            if read_result["status"] == "error":
                return {"error": f"Error al leer el archivo '{path}': {read_result["message"]}"}
            original_content = read_result["content"]
            original_lines = original_content.splitlines(keepends=True)
            modified_lines = list(original_lines)

            new_content = "" # Inicializar new_content aquí

            if action == 'insert_line':
                logger.debug(f"Insertando contenido en la línea {line_number} del archivo '{path}'.")
                if not isinstance(line_number, int) or line_number < 1:
                    return {"error": "line_number debe ser un entero positivo (basado en 1) para 'insert_line'."}
                if content is None:
                    return {"error": "El 'content' no puede ser None para 'insert_line'."}

                insert_idx = line_number - 1
                insert_content = content if content.endswith('\n') else content + '\n'

                if insert_idx > len(modified_lines):
                    modified_lines.append(insert_content)
                else:
                    modified_lines.insert(insert_idx, insert_content)

            elif action == 'replace_regex':
                logger.debug(f"Reemplazando contenido en el archivo '{path}' usando el patrón regex '{regex_pattern}'.")
                if not regex_pattern or replacement_content is None:
                    return {"error": "Se requieren 'regex_pattern' y 'replacement_content' para 'replace_regex'."}

                modified_content_str = re.sub(regex_pattern, replacement_content, original_content)
                modified_lines = modified_content_str.splitlines(keepends=True)

            elif action == 'prepend_content':
                logger.debug(f"Añadiendo contenido al principio del archivo '{path}'.")
                if content is None:
                    return {"error": "El 'content' no puede ser None para 'prepend_content'."}
                prepend_content = content if content.endswith('\n') else content + '\n'
                modified_lines.insert(0, prepend_content)

            elif action == 'append_content':
                logger.debug(f"Añadiendo contenido al final del archivo '{path}'.")
                if content is None:
                    return {"error": "El 'content' no puede ser None para 'append_content'."}
                append_content = content if content.endswith('\n') else content + '\n'
                modified_lines.append(append_content)

            else:
                return {"error": f"Acción '{action}' no soportada. Las acciones válidas son 'insert_line', 'replace_regex', 'prepend_content', 'append_content'."}

            new_content = "".join(modified_lines)

            if confirm:
                logger.debug(f"Aplicando la actualización al archivo '{path}'.")
                logger.debug("DEBUG: AdvancedFileEditorTool._run - Ejecutando _apply_advanced_update (confirm=True).")
                # print("*** DEBUG PRINT: AdvancedFileEditorTool._run - Ejecutando _apply_advanced_update (confirm=True). ***")
                return _apply_advanced_update(path, new_content)

            # La confirmación siempre es requerida por la herramienta si hay un diff
            diff = "".join(difflib.unified_diff(
                original_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm=''
            ))

            if not diff:
                logger.debug(f"No se requieren cambios en el archivo '{path}' para la acción '{action}'.")
                logger.debug(f"DEBUG: AdvancedFileEditorTool._run - No se requieren cambios para la acción '{action}'.")
                # print(f"*** DEBUG PRINT: AdvancedFileEditorTool._run - No se requieren cambios para la acción '{action}'. ***")
                return {"status": "success", "message": f"El archivo '{path}' no requirió cambios para la acción '{action}'."}

            logger.debug(f"DEBUG: AdvancedFileEditorTool._run - Devolviendo requires_confirmation. Diff: {diff[:200]}...")
            # print(f"*** DEBUG PRINT: AdvancedFileEditorTool._run - Devolviendo requires_confirmation. Diff: {diff[:200]}... ***")
            return {
                "status": "requires_confirmation",
                "action_description": f"aplicar edición avanzada en el archivo '{path}'",
                "operation": self.name,
                "args": {
                    "path": path,
                    "action": action,
                    "content": content,
                    "line_number": line_number,
                    "regex_pattern": regex_pattern,
                    "replacement_content": replacement_content,
                    "confirm": True,
                },
                "diff": diff,
                "new_content": new_content,
            }

        except FileNotFoundError:
            return {"error": f"El archivo '{path}' no fue encontrado."}
        except Exception as e:
            return {"error": f"Error al realizar la edición avanzada en '{path}': {e}"}

    async def _arun(self, *args, **kwargs) -> str:
        raise NotImplementedError("AdvancedFileEditorTool does not support async")