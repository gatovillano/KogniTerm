import difflib
import re
import os
from typing import Optional, Dict, Any

# Asumiendo que default_api.file_read_tool y default_api.file_update_tool están disponibles
# a través del contexto de ejecución de KogniTerm.
# En una implementación real, estas serían llamadas a las funciones de la API de KogniTerm.

# Helper para simular la lectura de archivo (en el entorno real, usaría default_api.file_read_tool)
def _read_file_content(path: str) -> str:
    # Esta es una simulación. En el entorno real, KogniTerm inyectaría la herramienta de lectura.
    # Para el propósito de esta función, asumimos que file_read_tool está disponible.
    try:
        # Aquí se haría la llamada real a la herramienta de lectura de archivos de KogniTerm
        # Por ejemplo:
        # from default_api import file_read_tool
        # response = file_read_tool(path=path)
        # if "file_read_tool_response" in response and "content" in response["file_read_tool_response"]:
        #     return response["file_read_tool_response"]["content"]
        # else:
        #     raise FileNotFoundError(f"No se pudo leer el contenido del archivo {path}")
        
        # Para la demostración y evitar dependencias circulares en este snippet,
        # leeremos directamente del sistema de archivos si existe, o simularemos.
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            raise FileNotFoundError(f"El archivo '{path}' no fue encontrado.")
    except Exception as e:
        raise RuntimeError(f"Error simulado al leer el archivo '{path}': {e}")


def advanced_file_editor_tool(
    path: str,
    action: str,
    content: Optional[str] = None,
    line_number: Optional[int] = None,
    regex_pattern: Optional[str] = None,
    replacement_content: Optional[str] = None,
) -> Dict[str, Any]:
    """Realiza operaciones de edición avanzadas en un archivo, como insertar, reemplazar con regex, o añadir contenido.
    Requiere confirmación si hay cambios.

    Args:
      path: La ruta del archivo a editar.
      action: La operación a realizar: 'insert_line', 'replace_regex', 'prepend_content', 'append_content'.
      content: El contenido a insertar, añadir o usar para reemplazar (para 'insert_line', 'prepend_content', 'append_content').
      line_number: El número de línea para la acción 'insert_line' (basado en 1).
      regex_pattern: El patrón de expresión regular a buscar para la acción 'replace_regex'.
      replacement_content: El contenido de reemplazo para la acción 'replace_regex'.
    """
    try:
        # 1. Leer el contenido original del archivo
        original_content = _read_file_content(path=path)
        original_lines = original_content.splitlines(keepends=True)
        modified_lines = list(original_lines) # Copia para modificar

        # 2. Generar el contenido modificado según la acción
        if action == 'insert_line':
            if not isinstance(line_number, int) or line_number < 1:
                return {"error": "line_number debe ser un entero positivo (basado en 1) para 'insert_line'."}
            if content is None: # Permitir cadena vacía, pero no None
                return {"error": "El 'content' no puede ser None para 'insert_line'."}
            
            # Ajustar line_number a índice de lista (0-basado)
            insert_idx = line_number - 1
            
            # Asegurarse de que el contenido a insertar termina con un salto de línea si no lo tiene
            insert_content = content if content.endswith('\n') else content + '\n'

            if insert_idx > len(modified_lines):
                # Si el número de línea es mayor que el total de líneas, añadir al final
                modified_lines.append(insert_content)
            else:
                modified_lines.insert(insert_idx, insert_content)

        elif action == 'replace_regex':
            if not regex_pattern or replacement_content is None:
                return {"error": "Se requieren 'regex_pattern' y 'replacement_content' para 'replace_regex'."}
            
            # Reemplazar usando expresiones regulares
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

        # 3. Calcular el diff
        diff = "".join(difflib.unified_diff(
            original_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm='' # Para evitar dobles saltos de línea si ya están en splitlines
        ))

        # Si no hay cambios, no necesitamos confirmación
        if not diff:
            return {"status": "success", "message": f"El archivo '{path}' no requirió cambios para la acción '{action}'."}

        # 4. Devolver el resultado para confirmación
        return {
            "status": "pending_confirmation",
            "tool_name": "advanced_file_editor_tool",
            "path": path,
            "action": action,
            "content": new_content, # El contenido final para aplicar si se confirma
            "diff": diff,
            "message": f"Confirmación requerida para la edición avanzada del archivo '{path}'.",
            "original_tool_args": {
                "path": path,
                "action": action,
                "content": content,
                "line_number": line_number,
                "regex_pattern": regex_pattern,
                "replacement_content": replacement_content,
            }
        }

    except FileNotFoundError:
        return {"error": f"El archivo '{path}' no fue encontrado."}
    except Exception as e:
        return {"error": f"Error al realizar la edición avanzada en '{path}': {e}"}
