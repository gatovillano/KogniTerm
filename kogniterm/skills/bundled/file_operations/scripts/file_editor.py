import os
import difflib
import re
import logging
from typing import Optional, Dict, Any, List, Tuple

from ._utils import clean_path


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

class FlexibleMatcher:
    """Busca coincidencias de texto de forma flexible (ignorando variaciones menores de espacios)."""
    
    @staticmethod
    def normalize(text: str) -> str:
        """Normaliza el texto eliminando espacios horizontales y unificando saltos de línea."""
        # Unificar saltos de línea y eliminar espacios al inicio/final de cada línea
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join([line for line in lines if line])

    @staticmethod
    def find_match(content: str, target: str) -> List[Tuple[int, int]]:
        """
        Busca el target en el contenido.
        Retorna una lista de tuplas (start_index, end_index).
        """
        # 1. Intentar coincidencia exacta
        matches = []
        start = 0
        while True:
            idx = content.find(target, start)
            if idx == -1: break
            matches.append((idx, idx + len(target)))
            start = idx + 1
        
        if matches:
            return matches

        # 2. Intentar coincidencia normalizada si falla la exacta
        norm_target = FlexibleMatcher.normalize(target)
        if not norm_target:
            return []

        # Dividir el contenido en bloques que puedan coincidir
        # Este es un enfoque simplificado: si el target normalizado aparece en el contenido normalizado
        # Pero necesitamos los índices originales.
        
        # Un enfoque más robusto: usar regex ignorando espacios
        # Escapar caracteres especiales del target pero permitir espacios flexibles entre tokens
        tokens = re.split(r'\s+', target.strip())
        pattern = r'\s*'.join([re.escape(t) for t in tokens if t])
        
        # Permitir cualquier tipo de whitespace (incluyendo saltos de línea) entre tokens
        regex_pattern = re.compile(pattern, re.DOTALL)
        
        for match in regex_pattern.finditer(content):
            matches.append(match.span())
            
        return matches

def advanced_file_editor(
    path: str,
    action: str,
    content: Optional[str] = None,
    line_number: Optional[int] = None,
    regex_pattern: Optional[str] = None,
    replacement_content: Optional[str] = None,
    target_content: Optional[str] = None,
    end_line: Optional[int] = None,
    confirm: bool = False,
) -> Dict[str, Any]:
    """
    Herramienta premium de edición de archivos.
    Soporta múltiples estrategias: inserción por línea, reemplazo regex, reemplazo de bloque literal, 
    añadir al inicio/final o reemplazo total.
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

        elif action == "replace_block":
            if target_content is None or replacement_content is None:
                return {"error": "Se requieren 'target_content' (texto a buscar) y 'replacement_content' (texto nuevo)."}
            
            matches = FlexibleMatcher.find_match(original_content, target_content)
            
            if not matches:
                return {"error": f"No se encontró 'target_content' en el archivo. Verifique que el fragmento sea exacto o use 'replace_lines'."}
            
            if len(matches) > 1:
                return {"error": f"Se encontraron {len(matches)} coincidencias para 'target_content'. Sea más específico para evitar reemplazos accidentales."}
            
            start, end = matches[0]
            modified_content_str = original_content[:start] + replacement_content + original_content[end:]
            modified_lines = modified_content_str.splitlines(keepends=True)

        elif action == "replace_lines":
            if not isinstance(line_number, int) or line_number < 1:
                return {"error": "line_number (inicio) debe ser entero positivo."}
            if replacement_content is None:
                return {"error": "Se requiere 'replacement_content'."}
            
            start_idx = line_number - 1
            end_idx = (end_line - 1) if isinstance(end_line, int) else start_idx
            
            if start_idx >= len(modified_lines):
                return {"error": f"line_number {line_number} está fuera de rango."}
            
            # Si se proporciona target_content, validamos que el contenido de las líneas coincida
            if target_content:
                actual_content = "".join(modified_lines[start_idx : end_idx + 1])
                if not FlexibleMatcher.find_match(actual_content, target_content):
                     return {"error": f"El contenido de las líneas {line_number}-{end_line or line_number} no coincide con 'target_content'."}

            new_text_lines = replacement_content.splitlines(keepends=True)
            if replacement_content.endswith("\n") and not new_text_lines[-1].endswith("\n"):
                 new_text_lines[-1] += "\n"
            
            modified_lines[start_idx : end_idx + 1] = new_text_lines

        elif action == "insert_after_match":
            if target_content is None or content is None:
                return {"error": "Se requieren 'target_content' (punto de referencia) y 'content' (texto a insertar)."}
            
            matches = FlexibleMatcher.find_match(original_content, target_content)
            if not matches:
                return {"error": f"No se encontró 'target_content' en el archivo."}
            if len(matches) > 1:
                return {"error": f"Múltiples coincidencias de 'target_content'. Sea más específico."}
            
            start, end = matches[0]
            text_to_insert = content if content.endswith("\n") else content + "\n"
            # Asegurar que haya un salto de línea si el match no termina en uno
            prefix = "" if original_content[end-1] == "\n" else "\n"
            
            modified_content_str = original_content[:end] + prefix + text_to_insert + original_content[end:]
            modified_lines = modified_content_str.splitlines(keepends=True)

        elif action == "insert_before_match":
            if target_content is None or content is None:
                return {"error": "Se requieren 'target_content' (punto de referencia) y 'content' (texto a insertar)."}
            
            matches = FlexibleMatcher.find_match(original_content, target_content)
            if not matches:
                return {"error": f"No se encontró 'target_content' en el archivo."}
            if len(matches) > 1:
                return {"error": f"Múltiples coincidencias de 'target_content'. Sea más específico."}
            
            start, end = matches[0]
            text_to_insert = content if content.endswith("\n") else content + "\n"
            
            modified_content_str = original_content[:start] + text_to_insert + original_content[start:]
            modified_lines = modified_content_str.splitlines(keepends=True)

        elif action == "delete_lines":
            if not isinstance(line_number, int) or line_number < 1:
                return {"error": "line_number (inicio) debe ser entero positivo."}
            
            start_idx = line_number - 1
            end_idx = (end_line - 1) if isinstance(end_line, int) else start_idx
            
            if start_idx >= len(modified_lines):
                return {"error": f"line_number {line_number} está fuera de rango."}
            
            del modified_lines[start_idx : end_idx + 1]

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
            "operation": "advanced_file_editor",
            "args": {
                "path": path,
                "action": action,
                "content": content,
                "line_number": line_number,
                "regex_pattern": regex_pattern,
                "replacement_content": replacement_content,
                "target_content": target_content,
                "end_line": end_line,
                "confirm": True
            },
            "diff": diff
        }

    # 4. Aplicar cambios con Race Condition Guard
    agent_state = getattr(advanced_file_editor, 'agent_state', None)

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

# Alias para compatibilidad con diferentes versiones de prompts de agentes
sophisticated_editor_tool = advanced_file_editor
replace_file_content = advanced_file_editor

# Permitir que el SkillManager inyecte el estado del agente en todos los alias
advanced_file_editor.agent_state = None
sophisticated_editor_tool.agent_state = None
replace_file_content.agent_state = None

# Esquema explícito y robusto para guiar al LLM y evitar errores de parámetros
common_editor_schema = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Ruta del archivo a editar (puede ser absoluta o relativa al directorio de trabajo)."},
        "action": {
            "type": "string", 
            "description": "Estrategia de edición a utilizar.",
            "enum": [
                "insert_line", "replace_block", "replace_lines", 
                "insert_after_match", "insert_before_match", 
                "replace_regex", "delete_lines", "prepend_content", 
                "append_content", "full_replacement"
            ]
        },
        "content": {"type": "string", "description": "Texto a insertar (usar en insert_line, insert_after_match, insert_before_match, prepend, append, full_replacement)."},
        "target_content": {"type": "string", "description": "Bloque de texto exacto a BUSCAR (usar en replace_block, insert_after/before_match, replace_lines)."},
        "replacement_content": {"type": "string", "description": "Texto NUEVO que reemplazará al objetivo (usar en replace_block, replace_lines, replace_regex)."},
        "line_number": {"type": "integer", "description": "Línea de inicio (1-based)."},
        "end_line": {"type": "integer", "description": "Línea de fin (1-based) para rangos."},
        "regex_pattern": {"type": "string", "description": "Patrón regex para replace_regex."},
        "confirm": {"type": "boolean", "description": "Confirmación automática.", "default": False}
    },
    "required": ["path", "action"]
}

# Registrar esquemas para todos los nombres posibles
advanced_file_editor.parameters_schema = common_editor_schema
sophisticated_editor_tool.parameters_schema = common_editor_schema
replace_file_content.parameters_schema = common_editor_schema

# También definir tool_schema a nivel de módulo para el SkillManager
tool_schema = {
    "name": "advanced_file_editor",
    "description": "Herramienta premium para edición de archivos. Soporta múltiples estrategias (bloques, líneas, regex).",
    "parameters": common_editor_schema
}
