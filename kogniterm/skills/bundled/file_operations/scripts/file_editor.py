import os
import difflib
import re
import logging
from typing import Optional, Dict, Any, List

def clean_path(path: str) -> str:
    """Limpia la ruta de caracteres innecesarios."""
    if not path:
        return ""
    return path.strip().replace('@', '')


# Intentar importar RaceConditionGuard del core
try:
    from kogniterm.core.race_condition_guard import RaceConditionGuard, RaceConditionDetected
except ImportError:
    # Fallback si no está disponible (ej: entorno de test incompleto)
    class RaceConditionGuard:
        @staticmethod
        def validate_write(state, path, content): return True, ""
        @staticmethod
        def register_write(state, path, content): pass
    class RaceConditionDetected(Exception): pass

logger = logging.getLogger(__name__)

def sophisticated_editor_tool(
    path: str,
    action: str,
    content: Optional[str] = None,
    line_number: Optional[int] = None,
    regex_pattern: Optional[str] = None,
    replacement_content: Optional[str] = None,
    confirm: bool = False,
) -> Dict[str, Any]:
    """
    Herramienta premium de edición de archivos.
    Soporta múltiples estrategias: inserción por línea, reemplazo regex, añadir al inicio/final o reemplazo total.
    Incluye protección contra Race Conditions y previsualización de cambios.
    """
    path = clean_path(path)
    if not path:
        return {"error": "Path no proporcionado"}

    # 1. Leer contenido actual
    try:
        if not os.path.exists(path):
            if action in ["prepend_content", "append_content", "full_replacement"]:
                original_content = ""
            else:
                return {"error": f"El archivo '{path}' no existe para la acción '{action}'."}
        else:
            with open(path, "r", encoding="utf-8") as f:
                original_content = f.read()
    except Exception as e:
        return {"error": f"Error al leer '{path}': {e}"}

    original_lines = original_content.splitlines(keepends=True)
    modified_lines = list(original_lines)

    # 2. Aplicar transformación
    try:
        if action == "insert_line":
            if not isinstance(line_number, int) or line_number < 1:
                return {"error": "line_number debe ser entero positivo (1-based)."}
            if content is None:
                return {"error": "Se requiere 'content' para 'insert_line'."}
            
            insert_idx = line_number - 1
            text_to_insert = content if content.endswith("\n") else content + "\n"
            
            if insert_idx >= len(modified_lines):
                modified_lines.append(text_to_insert)
            else:
                modified_lines.insert(insert_idx, text_to_insert)

        elif action == "replace_regex":
            if not regex_pattern or replacement_content is None:
                return {"error": "Se requieren 'regex_pattern' y 'replacement_content'."}
            
            re.compile(regex_pattern) # Validar regex
            modified_content_str = re.sub(regex_pattern, replacement_content, original_content)
            modified_lines = modified_content_str.splitlines(keepends=True)

        elif action == "prepend_content":
            if content is None: return {"error": "Se requiere 'content'."}
            text = content if content.endswith("\n") else content + "\n"
            modified_lines.insert(0, text)

        elif action == "append_content":
            if content is None: return {"error": "Se requiere 'content'."}
            text = content if content.endswith("\n") else content + "\n"
            modified_lines.append(text)

        elif action == "full_replacement":
            if content is None: return {"error": "Se requiere 'content' para reemplazo total."}
            modified_lines = content.splitlines(keepends=True)
            # Asegurar newline final si el original lo tenía o si es un archivo no vacío
            if content and not content.endswith("\n"):
                modified_lines[-1] += "\n"

        else:
            return {"error": f"Acción '{action}' no soportada."}
            
    except Exception as e:
        return {"error": f"Error al transformar contenido: {e}"}

    new_content = "".join(modified_lines)

    # 3. Generar Diff y manejar confirmación
    diff = "".join(difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    ))

    if not diff:
        return {"status": "no_changes", "message": "No se detectaron cambios a realizar."}

    if not confirm:
        return {
            "status": "requires_confirmation",
            "action_description": f"editar sofisticadamente el archivo '{path}' ({action})",
            "operation": "sophisticated_editor_tool",
            "args": {
                "path": path,
                "action": action,
                "content": content,
                "line_number": line_number,
                "regex_pattern": regex_pattern,
                "replacement_content": replacement_content,
                "confirm": True
            },
            "diff": diff
        }

    # 4. Aplicar cambios con Race Condition Guard
    # Intentamos obtener el estado del agente (inyectado por el SkillManager)
    # En el sistema de skills, el SkillManager inyecta 'agent_state' si la herramienta tiene el atributo
    agent_state = getattr(sophisticated_editor_tool, 'agent_state', None)

    if agent_state and os.path.exists(path):
        try:
            is_safe, msg = RaceConditionGuard.validate_write(agent_state, path, original_content)
            if not is_safe:
                return {"status": "error", "message": f"RACE CONDITION DETECTADA: {msg}"}
        except Exception as e:
            logger.warning(f"Error en validación de Race Condition: {e}")

    try:
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
            
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        if agent_state:
            RaceConditionGuard.register_write(agent_state, path, new_content)
            
        return {
            "status": "success",
            "path": path,
            "message": f"Archivo '{path}' actualizado exitosamente usando '{action}'.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Error al escribir cambios: {e}"}

# Permitir que el SkillManager inyecte el estado del agente
sophisticated_editor_tool.agent_state = None
