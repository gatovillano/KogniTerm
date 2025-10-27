import difflib
import re
import os
import json # Importar json
from typing import Optional, Dict, Any, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

# Helper para simular la lectura de archivo (en el entorno real, usaría default_api.file_read_tool)
def _read_file_content(path: str) -> str:
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            raise FileNotFoundError(f"El archivo '{path}' no fue encontrado.")
    except Exception as e:
        raise RuntimeError(f"Error simulado al leer el archivo '{path}': {e}")

def _apply_advanced_update(path: str, content: str) -> Dict[str, Any]:
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"status": "success", "path": path, "message": f"Archivo '{path}' actualizado exitosamente."}
    except Exception as e:
        return {"status": "error", "path": path, "message": f"Error al aplicar la actualización: {e}"}

class AdvancedFileEditorTool(BaseTool):
    name: str = "advanced_file_editor"
    description: str = "Realiza operaciones de edición avanzadas en un archivo, como insertar, reemplazar con regex, o añadir contenido. Siempre requiere confirmación si hay cambios."

    class AdvancedFileEditorInput(BaseModel):
        path: str = Field(description="La ruta del archivo a editar.")
        action: str = Field(description="La operación a realizar: 'insert_line', 'replace_regex', 'prepend_content', 'append_content'.")
        content: Optional[str] = Field(default=None, description="El contenido a insertar, añadir o usar para reemplazar (para 'insert_line', 'prepend_content', 'append_content').")
        line_number: Optional[int] = Field(default=None, description="El número de línea para la acción 'insert_line' (basado en 1).")
        regex_pattern: Optional[str] = Field(default=None, description="El patrón de expresión regular a buscar para la acción 'replace_regex'.")
        replacement_content: Optional[str] = Field(default=None, description="El contenido de reemplazo para la acción 'replace_regex'.")

    args_schema: Type[BaseModel] = AdvancedFileEditorInput

    def _run(self, path: str, action: str, content: Optional[str] = None, line_number: Optional[int] = None, regex_pattern: Optional[str] = None, replacement_content: Optional[str] = None, confirm: bool = False) -> Dict[str, Any]:
        try:
            original_content = _read_file_content(path=path)
            original_lines = original_content.splitlines(keepends=True)
            modified_lines = list(original_lines)

            new_content = "" # Inicializar new_content aquí

            if action == 'insert_line':
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
                if not regex_pattern or replacement_content is None:
                    return {"error": "Se requieren 'regex_pattern' y 'replacement_content' para 'replace_regex'."}
                
                modified_content_str = re.sub(regex_pattern, replacement_content, original_content)
                modified_lines = modified_content_str.splitlines(keepends=True)

            elif action == 'prepend_content':
                if content is None:
                    return {"error": "El 'content' no puede ser None para 'prepend_content'."}
                prepend_content = content if content.endswith('\n') else content + '\n'
                modified_lines.insert(0, prepend_content)

            elif action == 'append_content':
                if content is None:
                    return {"error": "El 'content' no puede ser None para 'append_content'."}
                append_content = content if content.endswith('\n') else content + '\n'
                modified_lines.append(append_content)

            else:
                return {"error": f"Acción '{action}' no soportada. Las acciones válidas son 'insert_line', 'replace_regex', 'prepend_content', 'append_content'."}

            new_content = "".join(modified_lines)

            if confirm:
                # Si confirm es True, aplicar los cambios directamente
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
                return {"status": "success", "message": f"El archivo '{path}' no requirió cambios para la acción '{action}'."}

            from kogniterm.core.agents.bash_agent import UserConfirmationRequired # Importar aquí para evitar dependencia circular

            raise UserConfirmationRequired(
                message=f"Se detectaron cambios para '{path}'. Por favor, confirma para aplicar.",
                tool_name=self.name,
                tool_args={
                    "path": path,
                    "action": action,
                    "content": content,
                    "line_number": line_number,
                    "regex_pattern": regex_pattern,
                    "replacement_content": replacement_content,
                    "new_content": new_content, # Añadir new_content para la re-ejecución
                    "confirm": True, # Este 'confirm' es para la re-ejecución por el agente
                },
                raw_tool_output=json.dumps({ # Pasar el diff como raw_tool_output
                    "status": "requires_confirmation",
                    "tool_name": self.name,
                    "path": path,
                    "diff": diff,
                    "message": f"Se detectaron cambios para '{path}'. Por favor, confirma para aplicar.",
                    "new_content": new_content, # También en raw_tool_output para fácil acceso
                })
            )

        except FileNotFoundError:
            return {"error": f"El archivo '{path}' no fue encontrado."}
        except Exception as e:
            return {"error": f"Error al realizar la edición avanzada en '{path}': {e}"}

    async def _arun(self, *args, **kwargs) -> str:
        raise NotImplementedError("AdvancedFileEditorTool does not support async")
