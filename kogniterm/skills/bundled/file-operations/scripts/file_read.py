import os
from typing import List, Dict, Any, Optional

from ._utils import clean_path


def read_file_tool(
    path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    with_line_numbers: bool = True,
) -> Dict[str, Any]:
    """Lee un archivo y devuelve su contenido.

    Cambios (2026-07): por defecto devuelve lineas numeradas en formato
    "  12 | codigo". Esto es lo que el LLM necesita para usar
    replace_lines con precision (la causa #1 de ediciones erraticas
    era que el LLM tenia que adivinar numeros de linea).

    Si with_line_numbers=False, devuelve el contenido crudo.
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

            numbered = _number_lines(content, start + 1) if with_line_numbers else content
            return {
                "file_path": path,
                "content": numbered,
                "raw_content": content if with_line_numbers else None,
                "with_line_numbers": with_line_numbers,
                "lines_read": f"{start + 1}-{end}",
                "total_lines": total_lines,
            }

        content = "".join(lines)
        numbered = _number_lines(content, 1) if with_line_numbers else content
        return {
            "file_path": path,
            "content": numbered,
            "raw_content": content if with_line_numbers else None,
            "with_line_numbers": with_line_numbers,
            "total_lines": total_lines,
        }
    except FileNotFoundError:
        return {"error": f"El archivo '{path}' no fue encontrado."}
    except Exception as e:
        return {"error": f"Error al leer '{path}': {e}"}


def _number_lines(content: str, first_line: int) -> str:
    """Numera cada linea: '  12 | codigo'. Ancho minimo 4 digitos."""
    if not content:
        return ""
    lines = content.splitlines()
    width = max(4, len(str(first_line + len(lines) - 1)))
    out = []
    for i, line in enumerate(lines):
        num = first_line + i
        # Mantener saltos originales: re-anhadimos \n al final de cada linea.
        out.append(f"{num:>{width}} | {line}")
    return "\n".join(out) + ("\n" if content.endswith("\n") else "")


def read_many_files_tool(paths: List[str], with_line_numbers: bool = True) -> Dict[str, Any]:
    """Lee multiples archivos de forma eficiente en una sola llamada."""
    if not paths:
        return {"error": "No se proporcionaron rutas"}

    results = []
    for p in paths:
        results.append(read_file_tool(p, with_line_numbers=with_line_numbers))

    return {"files": results}


def get_file_info_tool(path: str) -> Dict[str, Any]:
    """Obtiene metadatos detallados (tamano, fechas, tipo) de un archivo o directorio."""
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
        return {"error": f"Error al obtener informacion de '{path}': {e}"}


# Schemas (para el sistema de skills / LLM tool_choice)
read_file_tool.parameters_schema = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Ruta del archivo a leer."},
        "start_line": {"type": "integer", "description": "Linea inicial 1-based (opcional)."},
        "end_line": {"type": "integer", "description": "Linea final 1-based (opcional)."},
        "with_line_numbers": {
            "type": "boolean",
            "description": "Prefijar cada linea con su numero. Default: true.",
            "default": True,
        },
    },
    "required": ["path"],
}
