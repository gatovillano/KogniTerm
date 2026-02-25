"""
Advanced File Editor Skill - Edición avanzada de archivos con validación de race conditions y confirmación.

Esta skill está migrada desde `kogniterm/core/tools/advanced_file_editor_tool.py`.
Provee una función `advanced_file_editor` que implementa la lógica de edición y devuelve
un diccionario con el resultado o, en caso de requerir confirmación, la información del diff.
"""

import os
import difflib
import re
import logging
from typing import Optional, Dict, Any

from kogniterm.core.race_condition_guard import RaceConditionGuard, RaceConditionDetected

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_file_content(path: str) -> Dict[str, Any]:
    """Lee el contenido del archivo indicado.

    Devuelve un dict con `status` y `content` o `message` en caso de error.
    """
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return {"status": "success", "content": f.read()}
        else:
            return {"status": "error", "message": f"El archivo '{path}' no fue encontrado."}
    except Exception as e:
        return {"status": "error", "message": f"Error al leer el archivo '{path}': {e}"}


def _apply_advanced_update_with_validation(path: str, content: str) -> Dict[str, Any]:
    """Escribe el nuevo contenido en *path* validando race conditions.

    Utiliza el `RaceConditionGuard` del core para asegurarse de que el archivo no
    haya sido modificado entre la lectura y la escritura.
    """
    # Intentamos obtener el estado del agente desde el LLM service si está disponible.
    agent_state = getattr(
        getattr(
            globals().get("llm_service", None), "_current_agent_state", None
        ),
        None,
    )

    if agent_state and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                current_content = f.read()
            is_safe, message = RaceConditionGuard.validate_write(
                agent_state, path, current_content
            )
            if not is_safe:
                raise RaceConditionDetected(message)
        except Exception as e:
            logger.warning(f"Race condition validation skipped: {e}")

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if agent_state:
            RaceConditionGuard.register_write(agent_state, path, content)
        return {
            "status": "success",
            "path": path,
            "message": f"Archivo '{path}' actualizado exitosamente.",
        }
    except Exception as e:
        return {"status": "error", "path": path, "message": f"Error al aplicar la actualización: {e}"}


# ---------------------------------------------------------------------------
# Main skill function
# ---------------------------------------------------------------------------

def advanced_file_editor(
    path: str,
    action: str,
    content: Optional[str] = None,
    line_number: Optional[int] = None,
    regex_pattern: Optional[str] = None,
    replacement_content: Optional[str] = None,
    confirm: bool = False,
) -> Dict[str, Any]:
    """Ejecuta la acción solicitada sobre *path*.

    Parámetros
    ----------
    path: Ruta del archivo a editar.
    action: Una de ``insert_line``, ``replace_regex``, ``prepend_content`` o ``append_content``.
    content: Texto a insertar o añadir (no usado en ``replace_regex``).
    line_number: Número de línea (1‑based) para ``insert_line``.
    regex_pattern: Patrón regex para ``replace_regex``.
    replacement_content: Texto de reemplazo para ``replace_regex``.
    confirm: Si ``True`` se asume que el usuario ya aprobó el diff.
    """
    logger.debug(
        f"AdvancedFileEditorSkill invoked: path={path}, action={action}, confirm={confirm}"
    )

    # Lectura del archivo original
    read_result = _read_file_content(path)
    if read_result["status"] == "error":
        return {"error": read_result.get("message", "Error desconocido")}

    original_content = read_result["content"]
    original_lines = original_content.splitlines(keepends=True)
    modified_lines = list(original_lines)

    # ---------------------------------------------------------------------
    # Aplicar la transformación solicitada
    # ---------------------------------------------------------------------
    if action == "insert_line":
        if not isinstance(line_number, int) or line_number < 1:
            return {"error": "line_number debe ser un entero positivo (basado en 1) para 'insert_line'."}
        if content is None:
            return {"error": "El 'content' no puede ser None para 'insert_line'."}
        insert_idx = line_number - 1
        insert_content = content if content.endswith("\n") else content + "\n"
        if insert_idx > len(modified_lines):
            modified_lines.append(insert_content)
        else:
            modified_lines.insert(insert_idx, insert_content)

    elif action == "replace_regex":
        if not regex_pattern or replacement_content is None:
            return {"error": "Se requieren 'regex_pattern' y 'replacement_content' para 'replace_regex'."}
        try:
            re.compile(regex_pattern)
            # Intentamos usar el replacement tal cual; si falla escapamos "\s"
            safe_replacement = replacement_content
            try:
                re.sub(regex_pattern, replacement_content, "")
            except Exception:
                safe_replacement = replacement_content.replace(r"\s", r"\\s")
            modified_content_str = re.sub(regex_pattern, safe_replacement, original_content)
            modified_lines = modified_content_str.splitlines(keepends=True)
        except re.error as e:
            return {"error": f"Error de expresión regular inválida: {e}"}
        except Exception as e:
            return {"error": f"Error al aplicar regex: {e}. Intenta escapar las barras invertidas en el contenido de reemplazo (ej. usa \\\\s en lugar de \\s)."}

    elif action == "prepend_content":
        if content is None:
            return {"error": "El 'content' no puede ser None para 'prepend_content'."}
        prepend_content = content if content.endswith("\n") else content + "\n"
        modified_lines.insert(0, prepend_content)

    elif action == "append_content":
        if content is None:
            return {"error": "El 'content' no puede ser None para 'append_content'."}
        append_content = content if content.endswith("\n") else content + "\n"
        modified_lines.append(append_content)

    else:
        return {"error": f"Acción '{action}' no soportada. Las acciones válidas son 'insert_line', 'replace_regex', 'prepend_content', 'append_content'."}

    new_content = "".join(modified_lines)

    # Si el llamador indica que ya confirmó, escribimos directamente.
    if confirm:
        return _apply_advanced_update_with_validation(path, new_content)

    # Generar diff para que el LLM lo presente al usuario.
    diff = "".join(
        difflib.unified_diff(
            original_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )

    if not diff:
        return {"status": "success", "message": f"El archivo '{path}' no requirió cambios para la acción '{action}'."}

    # Devolver la información necesaria para que la capa superior solicite confirmación.
    return {
        "status": "requires_confirmation",
        "action_description": f"aplicar edición avanzada en el archivo '{path}'",
        "operation": "advanced_file_editor",
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


def get_action_description(path: str, action: str, **kwargs) -> str:
    """Devuelve una descripción legible de la acción que realiza la herramienta."""
    path = path.strip().replace('@', '')
    if action == "insert_line":
        return f"Insertando línea en {path}..."
    elif action == "replace_regex":
        return f"Reemplazando contenido con regex en {path}..."
    elif action == "prepend_content":
        return f"Añadiendo contenido al inicio de {path}..."
    elif action == "append_content":
        return f"Añadiendo contenido al final de {path}..."
    return f"Editando archivo {path}..."


# ---------------------------------------------------------------------------
# Parámetros del LLM (schema JSON)
# ---------------------------------------------------------------------------

parameters_schema = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Ruta del archivo a editar"},
        "action": {
            "type": "string",
            "description": "Acción a realizar",
            "enum": ["insert_line", "replace_regex", "prepend_content", "append_content"],
        },
        "content": {"type": "string", "description": "Contenido a insertar o añadir"},
        "line_number": {"type": "integer", "description": "Número de línea (1‑based) para insert_line"},
        "regex_pattern": {"type": "string", "description": "Patrón regex para replace_regex"},
        "replacement_content": {"type": "string", "description": "Contenido de reemplazo para replace_regex"},
    },
    "required": ["path", "action"],
}

