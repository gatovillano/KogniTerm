import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def discover_external_mcp_servers(project_dir: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Descubre automáticamente servidores MCP configurados en otras herramientas de IA.

    Soporta:
    1. Claude Code (~/.claude.json): Servidores globales y por proyecto (añadidos con `claude mcp add` o `npx add-mcp`).
    2. Proyectos con .mcp.json (estándar de Claude Code y Cursor en raíz de proyecto).
    3. Claude Desktop (claude_desktop_config.json en Linux, macOS y Windows).
    4. Cursor (~/.cursor/mcp.json o .cursor/mcp.json).

    Retorna un diccionario de configuraciones normalizadas compatibles con KogniTerm.
    """
    from kogniterm.core.mcp.env_utils import normalize_mcp_config

    discovered: Dict[str, Dict[str, Any]] = {}
    home = Path.home()
    target_project = os.path.abspath(project_dir or os.getcwd())

    # 1. Claude Code (~/.claude.json)
    claude_json_path = home / ".claude.json"
    if claude_json_path.exists():
        try:
            with open(claude_json_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)

            # Servidores globales de Claude Code
            global_mcp = data.get("mcpServers", {})
            if isinstance(global_mcp, dict):
                for name, conf in global_mcp.items():
                    if isinstance(conf, dict):
                        norm = normalize_mcp_config(conf)
                        norm["source"] = "claude_code"
                        discovered[name] = norm

            # Servidores por proyecto en Claude Code
            projects = data.get("projects", {})
            if isinstance(projects, dict):
                # Buscar coincidencias con el proyecto actual
                for proj_path, proj_data in projects.items():
                    if isinstance(proj_data, dict):
                        norm_proj = os.path.normpath(proj_path)
                        if norm_proj == target_project or target_project.startswith(norm_proj):
                            proj_mcp = proj_data.get("mcpServers", {})
                            if isinstance(proj_mcp, dict):
                                for name, conf in proj_mcp.items():
                                    if isinstance(conf, dict):
                                        norm = normalize_mcp_config(conf)
                                        norm["source"] = "claude_code_project"
                                        discovered[name] = norm
        except Exception as e:
            logger.debug("Error leyendo ~/.claude.json: %s", e)

    # 2. Archivo .mcp.json en la raíz del proyecto o directorios padres
    curr = Path(target_project)
    checked_count = 0
    while curr and checked_count < 4:
        proj_mcp_json = curr / ".mcp.json"
        if proj_mcp_json.exists():
            try:
                with open(proj_mcp_json, "r", encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
                srvs = data.get("mcpServers", {}) if "mcpServers" in data else data
                if isinstance(srvs, dict):
                    for name, conf in srvs.items():
                        if isinstance(conf, dict) and name not in discovered:
                            norm = normalize_mcp_config(conf)
                            norm["source"] = "project_mcp_json"
                            discovered[name] = norm
            except Exception as e:
                logger.debug("Error leyendo %s: %s", proj_mcp_json, e)
            break
        if curr.parent == curr:
            break
        curr = curr.parent
        checked_count += 1

    # 3. Claude Desktop config (claude_desktop_config.json)
    desktop_candidates = []
    if sys.platform == "darwin":
        desktop_candidates.append(home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            desktop_candidates.append(Path(appdata) / "Claude" / "claude_desktop_config.json")
    else:  # Linux
        desktop_candidates.append(home / ".config" / "Claude" / "claude_desktop_config.json")
        desktop_candidates.append(home / ".config" / "claude" / "claude_desktop_config.json")

    for desk_path in desktop_candidates:
        if desk_path.exists():
            try:
                with open(desk_path, "r", encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
                desk_srvs = data.get("mcpServers", {})
                if isinstance(desk_srvs, dict):
                    for name, conf in desk_srvs.items():
                        if isinstance(conf, dict) and name not in discovered:
                            norm = normalize_mcp_config(conf)
                            norm["source"] = "claude_desktop"
                            discovered[name] = norm
            except Exception as e:
                logger.debug("Error leyendo %s: %s", desk_path, e)

    # 4. Cursor (~/.cursor/mcp.json)
    cursor_mcp_json = home / ".cursor" / "mcp.json"
    if cursor_mcp_json.exists():
        try:
            with open(cursor_mcp_json, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            cur_srvs = data.get("mcpServers", {}) if "mcpServers" in data else data
            if isinstance(cur_srvs, dict):
                for name, conf in cur_srvs.items():
                    if isinstance(conf, dict) and name not in discovered:
                        norm = normalize_mcp_config(conf)
                        norm["source"] = "cursor"
                        discovered[name] = norm
        except Exception as e:
            logger.debug("Error leyendo ~/.cursor/mcp.json: %s", e)

    return discovered
