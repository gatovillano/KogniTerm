import os
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional


def _load_write_file_tool():
    """Carga write_file_tool desde la skill hermana file-operations via importlib."""
    # Resolver la ruta del directorio hermano file-operations
    this_dir = Path(__file__).resolve().parent          # file-update/scripts/
    bundled_dir = this_dir.parent.parent                # skills/bundled/
    file_ops_scripts = bundled_dir / "file-operations" / "scripts"

    # Cargar _utils primero (dependencia de file_write)
    utils_path = file_ops_scripts / "_utils.py"
    utils_spec = importlib.util.spec_from_file_location(
        "_file_ops_utils", str(utils_path)
    )
    utils_module = importlib.util.module_from_spec(utils_spec)
    utils_spec.loader.exec_module(utils_module)

    # Cargar file_write inyectando _utils como dependencia relativa
    fw_path = file_ops_scripts / "file_write.py"
    fw_spec = importlib.util.spec_from_file_location(
        "_file_ops_file_write", str(fw_path),
        submodule_search_locations=[str(file_ops_scripts)]
    )
    fw_module = importlib.util.module_from_spec(fw_spec)
    # Registrar _utils para que el import relativo `from ._utils import ...` funcione
    import sys
    from types import ModuleType
    parent_pkg_name = "_file_ops_scripts_pkg"
    parent_pkg = ModuleType(parent_pkg_name)
    parent_pkg.__path__ = [str(file_ops_scripts)]
    sys.modules[parent_pkg_name] = parent_pkg
    sys.modules[f"{parent_pkg_name}._utils"] = utils_module
    fw_module.__package__ = parent_pkg_name
    fw_spec.loader.exec_module(fw_module)

    return fw_module.write_file_tool


write_file_tool = _load_write_file_tool()

def _apply_file_update(path: str, content: str) -> str:
    """
    Aplica una actualización de archivo tras validación del usuario.
    """
    result = write_file_tool(path=path, content=content, confirm=True)
    if isinstance(result, dict):
        if "message" in result:
            return result["message"]
        if "error" in result:
            return f"Error: {result['error']}"
        return str(result)
    return str(result)

def file_update_tool(path: str, content: str, confirm: bool = False) -> Dict[str, Any]:
    """Actualiza el contenido de un archivo."""
    return write_file_tool(path=path, content=content, confirm=confirm)

name = "file_update"
description = "Actualiza el contenido de un archivo."
parameters_schema = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Ruta del archivo"},
        "content": {"type": "string", "description": "Nuevo contenido"},
        "confirm": {"type": "boolean", "default": False}
    },
    "required": ["path", "content"]
}
