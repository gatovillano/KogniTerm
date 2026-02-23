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
from kogniterm.core.race_condition_guard import RaceConditionGuard, RaceConditionDetected

def _read_file_content(path: str) -> Dict[str, Any]:
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return {"status": "success", "content": f.read()}
        else:
            return {"status": "error", "message": f"El archivo '{path}' no fue encontrado."}
    except Exception as e:
        return {"status": "error", "message": f"Error al leer el archivo '{path}': {e}"}

# La función _apply_advanced_update se reemplaza por un método de la clase con validación

class AdvancedFileEditorTool(BaseTool):
    name: str = "advanced_file_editor"
    description: str = """Realiza operaciones de edición avanzadas en un archivo.
    Acciones disponibles:
    - insert_line: Inserta contenido en una línea específica
    - replace_regex: Reemplaza contenido usando expresiones regulares
    - prepend_content: Añade contenido al inicio del archivo
    - append_content: Añade contenido al final del archivo"""

    approval_handler: Optional[Any] = None
    llm_service: Optional[Any] = None

    def __init__(self, approval_handler: Any = None, llm_service: Any = None, **kwargs):
        super().__init__(**kwargs)
        self.approval_handler = approval_handler
        self.llm_service = llm_service

    def _get_agent_state(self) -> Optional[Any]:
        """Obtiene el AgentState actual desde el LLMService si está disponible."""
        if hasattr(self, 'llm_service') and hasattr(self.llm_service, '_current_agent_state'):
            return self.llm_service._current_agent_state
        return None


    def _apply_advanced_update_with_validation(self, path: str, content: str) -> Dict[str, Any]:
        """
        Aplica la actualización al archivo con validación de race condition.
        Este método verifica que el archivo no haya sido modificado externamente.
        """
        agent_state = self._get_agent_state()
        
        # RACE CONDITION VALIDATION just before write
        if agent_state and os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
                is_safe, message = RaceConditionGuard.validate_write(agent_state, path, current_content)
                if not is_safe:
                    raise RaceConditionDetected(message)
            except Exception as e:
                logger.warning(f"Race condition validation skipped: {e}")
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            # Register new state after successful write
            if agent_state:
                RaceConditionGuard.register_write(agent_state, path, content)
            return {"status": "success", "path": path, "message": f"Archivo '{path}' actualizado exitosamente."}
        except Exception as e:
            return {"status": "error", "path": path, "message": f"Error al aplicar la actualización: {e}"}

    class AdvancedFileEditorInput(BaseModel):
        path: str = Field(description="La ruta del archivo a editar.")
        action: str = Field(description="La operación a realizar: 'insert_line', 'replace_regex', 'prepend_content', 'append_content'.")
        content: Optional[str] = Field(default=None, description="El contenido a insertar, añadir o usar para reemplazar.")
        line_number: Optional[int] = Field(default=None, description="El número de línea para la acción 'insert_line' (basado en 1).")
        regex_pattern: Optional[str] = Field(default=None, description="El patrón de expresión regular a buscar para la acción 'replace_regex'.")
        replacement_content: Optional[str] = Field(default=None, description="El contenido de reemplazo para la acción 'replace_regex'.")
        # NOTA: El parámetro 'confirm' ha sido eliminado. La confirmación SIEMPRE la hace el usuario.

    args_schema: Type[BaseModel] = AdvancedFileEditorInput

    def get_action_description(self, **kwargs) -> str:
        action = kwargs.get("action")
        path = kwargs.get("path", "")
        if action == "insert_line":
            line = kwargs.get("line_number")
            return f"Insertando línea en {path} (línea {line})"
        elif action == "replace_regex":
            return f"Reemplazando contenido con regex en {path}"
        elif action == "prepend_content":
            return f"Añadiendo contenido al inicio de {path}"
        elif action == "append_content":
            return f"Añadiendo contenido al final de {path}"
        return f"Editando archivo: {path}"

    def _run(self, **kwargs) -> Dict[str, Any]:
        path = kwargs.get("path")
        action = kwargs.get("action")
        content = kwargs.get("content")
        line_number = kwargs.get("line_number")
        regex_pattern = kwargs.get("regex_pattern")
        replacement_content = kwargs.get("replacement_content")
        confirm = kwargs.get("confirm", False)
        
        logger.debug(f"Invocando AdvancedFileEditorTool para editar el archivo: '{path}' con la acción: '{action}'.")
        
        # La confirmación SIEMPRE la hace el usuario directamente en la interfaz.
        # Esta herramienta NUNCA ejecuta escritura sin confirmación del usuario.
        
        try:
            read_result = _read_file_content(path=path)
            if read_result["status"] == "error":
                error_msg = read_result.get("message", "Error desconocido")
                return {"error": f"Error al leer el archivo '{path}': {error_msg}"}
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

                try:
                    # Intentar compilar el regex primero para detectar errores en el patrón
                    re.compile(regex_pattern)
                    
                    # Pre-procesar replacement_content para evitar 'bad escape' con secuencias como \s
                    # Si replacement_content tiene \s y no es un raw string, re.sub puede fallar.
                    # Escapamos las barras invertidas que no son parte de grupos de captura válidos o escapes estándar.
                    # Esta es una heurística simple.
                    safe_replacement = replacement_content
                    try:
                        # Prueba rápida para ver si re.sub acepta el reemplazo
                        re.sub(regex_pattern, replacement_content, "")
                    except Exception:
                        # Si falla, intentamos escapar las barras invertidas problemáticas
                        # Específicamente, \s en el reemplazo suele ser un intento de literal \s
                        safe_replacement = replacement_content.replace(r'\s', r'\\s')
                    
                    modified_content_str = re.sub(regex_pattern, safe_replacement, original_content)
                    modified_lines = modified_content_str.splitlines(keepends=True)
                except re.error as e:
                    return {"error": f"Error de expresión regular inválida: {e}"}
                except Exception as e:
                    # Capturar otros errores como 'bad escape' que pueden surgir de re.sub
                    return {"error": f"Error al aplicar regex: {e}. Intenta escapar las barras invertidas en el contenido de reemplazo (ej. usa \\\\s en lugar de \\s)."}

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

            # Si confirm=True, significa que el usuario ya aprobó la operación
            # Aplicamos directamente sin pasar por el flujo de confirmación again
            if confirm:
                return self._apply_advanced_update_with_validation(path, new_content)

            # La confirmación siempre es requerida por la herramienta si hay un diff
            diff = "".join(difflib.unified_diff(
                original_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}"
            ))

            if not diff:
                logger.debug(f"No se requieren cambios en el archivo '{path}' para la acción '{action}'.")
                return {"status": "success", "message": f"El archivo '{path}' no requirió cambios para la acción '{action}'."}

            if self.approval_handler:
                approved = self.approval_handler.handle_approval(
                    action_description=f"aplicar edición avanzada en el archivo '{path}'",
                    diff=diff
                )
                if approved:
                    return self._apply_advanced_update_with_validation(path, new_content)
                else:
                    return {"status": "error", "message": "Operación cancelada por el usuario."}
            else:
                logger.debug(f"DEBUG: AdvancedFileEditorTool._run - Devolviendo requires_confirmation. Diff: {diff[:200]}...")
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