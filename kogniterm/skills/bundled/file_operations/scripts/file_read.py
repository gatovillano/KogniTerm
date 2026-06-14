import os
from typing import List, Dict, Any, Optional

from ._utils import clean_path


def read_file_tool(path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
    """
    Lee un archivo y devuelve su contenido.
    Puede leer una sección si se indican start_line y end_line (1-indexed).
    """
    path = clean_path(path)
    if not path:
        return {"error": "Path no proporcionado"}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            total_lines = len(lines)
            
        if start_line is not None or end_line is not None:
            start = max(0, (start_line or 1) - 1)
            end = min(total_lines, (end_line or total_lines))
            
            if start >= total_lines or start >= end:
                content = ""
            else:
                content = "".join(lines[start:end])
                
            return {
                "file_path": path, 
                "content": content,
                "lines_read": f"{start + 1}-{end}",
                "total_lines": total_lines
            }

        content = "".join(lines)
        return {"file_path": path, "content": content, "total_lines": total_lines}
    except FileNotFoundError:
        return {"error": f"El archivo '{path}' no fue encontrado."}
    except Exception as e:
        return {"error": f"Error al leer '{path}': {e}"}

def read_many_files_tool(paths: List[str]) -> Dict[str, Any]:
    """Lee múltiples archivos de forma eficiente en una sola llamada."""
    if not paths:
        return {"error": "No se proporcionaron rutas"}

    results = []
    for p in paths:
        results.append(read_file_tool(p))

    return {"files": results}

def get_file_info_tool(path: str) -> Dict[str, Any]:
    """Obtiene metadatos detallados (tamaño, fechas, tipo) de un archivo o directorio."""
    path = clean_path(path)
    if not path:
        return {"error": "Path no proporcionado"}

    if not os.path.exists(path):
        return {"error": f"La ruta '{path}' no existe."}

    try:
        stat_info = os.stat(path)
        return {
            "path": path,
            "is_dir": os.path.isdir(path),
            "size_bytes": stat_info.st_size,
            "size_mb": round(stat_info.st_size / (1024 * 1024), 2),
            "created": stat_info.st_ctime,
            "modified": stat_info.st_mtime
        }
    except Exception as e:
        return {"error": f"Error al obtener información de '{path}': {e}"}

# Metadata para el sistema de skills
# El sistema extraerá atomáticamente los esquemas de parámetros si no se proporcionan,
# pero al terminar en _tool, el SkillLoader las detectará automáticamente.
