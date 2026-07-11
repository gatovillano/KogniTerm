import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict, Any


def _load_advanced_file_editor():
    """Carga advanced_file_editor_tool desde la skill hermana via importlib."""
    this_dir = Path(__file__).resolve().parent          # file-update/scripts/
    bundled_dir = this_dir.parent.parent                # skills/bundled/
    adv_scripts = bundled_dir / "advanced-file-editor" / "scripts"

    # Necesitamos que file-operations esté registrado también
    file_ops_scripts = bundled_dir / "file-operations" / "scripts"

    parent_pkg_name = "_file_ops_scripts_pkg"
    if parent_pkg_name not in sys.modules:
        parent_pkg = ModuleType(parent_pkg_name)
        parent_pkg.__path__ = [str(file_ops_scripts)]
        sys.modules[parent_pkg_name] = parent_pkg

        utils_path = file_ops_scripts / "_utils.py"
        utils_spec = importlib.util.spec_from_file_location(
            f"{parent_pkg_name}._utils", str(utils_path)
        )
        utils_module = importlib.util.module_from_spec(utils_spec)
        utils_module.__package__ = parent_pkg_name
        sys.modules[f"{parent_pkg_name}._utils"] = utils_module
        utils_spec.loader.exec_module(utils_module)

    adv_pkg_name = "_adv_file_editor_scripts_pkg"
    if adv_pkg_name not in sys.modules:
        adv_pkg = ModuleType(adv_pkg_name)
        adv_pkg.__path__ = [str(adv_scripts)]
        sys.modules[adv_pkg_name] = adv_pkg

    tool_path = adv_scripts / "tool.py"
    tool_spec = importlib.util.spec_from_file_location(
        f"{adv_pkg_name}.tool", str(tool_path),
        submodule_search_locations=[str(adv_scripts)],
    )
    tool_module = importlib.util.module_from_spec(tool_spec)
    tool_module.__package__ = adv_pkg_name
    sys.modules[f"{adv_pkg_name}.tool"] = tool_module
    tool_spec.loader.exec_module(tool_module)

    return tool_module.advanced_file_editor_tool


advanced_file_editor_tool = _load_advanced_file_editor()


def _apply_file_update(path: str, content: str) -> str:
    """
    Aplica una actualización de archivo tras validación del usuario.
    Delega a advanced_file_editor_tool con action='full_replacement'.
    """
    result = advanced_file_editor_tool(path=path, action="full_replacement", content=content, confirm=True)
    if isinstance(result, dict):
        if "message" in result:
            return result["message"]
        if "error" in result:
            return f"Error: {result['error']}"
        return str(result)
    return str(result)


def file_update_tool(path: str, content: str, confirm: bool = False) -> Dict[str, Any]:
    """Actualiza el contenido completo de un archivo. Delega a advanced_file_editor_tool."""
    return advanced_file_editor_tool(path=path, action="full_replacement", content=content, confirm=confirm)


name = "file_update"
description = "Actualiza el contenido de un archivo (reemplazo completo). Delega a advanced_file_editor."
parameters_schema = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Ruta del archivo"},
        "content": {"type": "string", "description": "Nuevo contenido"},
        "confirm": {"type": "boolean", "default": False}
    },
    "required": ["path", "content"]
}
