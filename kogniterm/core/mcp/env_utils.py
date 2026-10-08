import json
import logging
import os
import re
import shlex
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


def get_node_search_paths() -> List[str]:
    """Descubre rutas comunes de Node.js, npm, npx y gestores de versiones de entorno.

    Busca dinámicamente en NVM, FNM, ASDF, Volta, Bun, PNPM, Yarn global,
    npm global (~/.npm-global) y rutas estándares de usuario y sistema.
    """
    paths: List[str] = []
    home = Path.home()

    # 1. NVM (~/.nvm/versions/node/*/bin) - orden descendente de versión
    nvm_dir = home / ".nvm" / "versions" / "node"
    if nvm_dir.is_dir():
        try:
            node_vers = sorted(nvm_dir.glob("v*"), reverse=True)
            for v in node_vers:
                bin_dir = v / "bin"
                if bin_dir.is_dir():
                    paths.append(str(bin_dir))
        except Exception as e:
            logger.debug("Error leyendo directorios de NVM: %s", e)

    # 2. npm global (~/.npm-global/bin)
    npm_global_bin = home / ".npm-global" / "bin"
    if npm_global_bin.is_dir():
        paths.append(str(npm_global_bin))

    # 3. FNM (~/.fnm/current/bin, ~/.local/share/fnm/current/bin)
    for fnm_candidate in [
        home / ".fnm" / "current" / "bin",
        home / ".local" / "share" / "fnm" / "current" / "bin",
    ]:
        if fnm_candidate.is_dir():
            paths.append(str(fnm_candidate))

    # 4. ASDF (~/.asdf/shims, ~/.asdf/installs/nodejs/*/bin)
    asdf_shims = home / ".asdf" / "shims"
    if asdf_shims.is_dir():
        paths.append(str(asdf_shims))
    asdf_node = home / ".asdf" / "installs" / "nodejs"
    if asdf_node.is_dir():
        try:
            for v in sorted(asdf_node.glob("*"), reverse=True):
                bin_dir = v / "bin"
                if bin_dir.is_dir():
                    paths.append(str(bin_dir))
        except Exception as e:
            logger.debug("Error leyendo directorios de ASDF: %s", e)

    # 5. Volta (~/.volta/bin)
    volta_bin = home / ".volta" / "bin"
    if volta_bin.is_dir():
        paths.append(str(volta_bin))

    # 6. Bun (~/.bun/bin)
    bun_bin = home / ".bun" / "bin"
    if bun_bin.is_dir():
        paths.append(str(bun_bin))

    # 7. PNPM (~/.local/share/pnpm, ~/.pnpm)
    for pnpm_candidate in [home / ".local" / "share" / "pnpm", home / ".pnpm"]:
        if pnpm_candidate.is_dir():
            paths.append(str(pnpm_candidate))

    # 8. Yarn global (~/.yarn/bin, ~/.config/yarn/global/node_modules/.bin)
    for yarn_candidate in [
        home / ".yarn" / "bin",
        home / ".config" / "yarn" / "global" / "node_modules" / ".bin",
    ]:
        if yarn_candidate.is_dir():
            paths.append(str(yarn_candidate))

    # 9. Rutas de usuario (~/.local/bin, ~/bin, ~/.cargo/bin)
    for user_bin in [home / ".local" / "bin", home / "bin", home / ".cargo" / "bin"]:
        if user_bin.is_dir():
            paths.append(str(user_bin))

    # 10. Rutas del sistema estándar (/usr/local/bin, /opt/homebrew/bin, /usr/bin, /bin)
    for sys_bin in ["/usr/local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin"]:
        if os.path.isdir(sys_bin):
            paths.append(sys_bin)

    return paths


def get_enhanced_path(current_path: Optional[str] = None) -> str:
    """Construye un PATH enriquecido con todas las rutas de Node/npm/npx descubiertas.

    Garantiza que Node y npx sean encontrados incluso si KogniTerm se ejecutó
    desde una sesión de escritorio o entorno sin login shell (.bashrc / .zshrc no cargados).
    """
    if current_path is None:
        current_path = os.environ.get("PATH", "")

    existing_parts = [p for p in current_path.split(os.pathsep) if p]
    discovered = get_node_search_paths()

    # Si `node` o `npx` no están en el PATH actual, priorizamos las rutas descubiertas
    has_node = shutil.which("node", path=current_path) is not None
    has_npx = shutil.which("npx", path=current_path) is not None

    seen = set()
    result: List[str] = []

    def _add(path_list: List[str]):
        for p in path_list:
            norm = os.path.normpath(p)
            if norm not in seen:
                seen.add(norm)
                result.append(norm)

    if not has_node or not has_npx:
        # Prepend descubiertas para garantizar que la versión de node del usuario tenga prioridad
        _add(discovered)
        _add(existing_parts)
    else:
        # Preservar el orden existente del usuario y añadir descubiertas que falten al final
        _add(existing_parts)
        _add(discovered)

    return os.pathsep.join(result)


def resolve_executable(command: str, custom_path: Optional[str] = None) -> str:
    """Resuelve la ruta absoluta al ejecutable usando el PATH enriquecido.

    Si no se encuentra un ejecutable o si ya es una ruta absoluta, retorna el comando original.
    """
    if not command:
        return ""
    if os.path.isabs(command):
        return command

    search_path = custom_path or get_enhanced_path()
    found = shutil.which(command, path=search_path)
    return found or command


def normalize_mcp_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza y valida la configuración de un servidor MCP.

    Características clave:
    1. Si `command` tiene espacios (ej. 'npx -y @modelcontextprotocol/server-memory'),
       lo separa limpiamente en ejecutable y lista de argumentos usando `shlex.split`.
    2. Si el comando es `npx`, asegura automáticamente que incluya el flag `-y`
       (non-interactive) para que npx no se congele esperando confirmación por stdin.
    3. Resuelve la ruta completa del comando ejecutable en entornos nvm, fnm, npm global, etc.
    4. Inyecta el PATH enriquecido y flags anti-prompt (`npm_config_yes=true`, `CI=1`) en `env`.
    5. Detecta automáticamente si una URL fue puesta en `command` o `url` para activar transporte SSE.
    """
    if not isinstance(config_dict, dict):
        return {}

    cfg = dict(config_dict)

    # 1. Detección de transporte SSE / HTTP / remoto por URL o tipo
    cmd_val = (cfg.get("command") or "").strip()
    url_val = (cfg.get("url") or "").strip()
    type_val = (cfg.get("type") or "").strip().lower()

    if url_val or cmd_val.startswith("http://") or cmd_val.startswith("https://") or type_val in ("http", "sse", "streamable_http"):
        target_transport = "http" if type_val == "http" else (cfg.get("transport") or "sse")
        cfg["transport"] = target_transport
        cfg["url"] = url_val or cmd_val
        cfg.pop("command", None)
        cfg.pop("args", None)
        cfg.pop("type", None)
        return cfg

    # 2. Transporte stdio
    cfg["transport"] = cfg.get("transport", "stdio")
    if cfg["transport"] == "stdio":
        raw_cmd = cfg.get("command", "")
        args = list(cfg.get("args") or [])

        if isinstance(raw_cmd, str) and raw_cmd.strip():
            raw_cmd = raw_cmd.strip()
            # Si el comando contiene espacios, separamos con shlex
            if " " in raw_cmd or "\t" in raw_cmd:
                try:
                    parts = shlex.split(raw_cmd)
                    if parts:
                        base_cmd = parts[0]
                        extra_args = parts[1:]
                        args = extra_args + args
                        raw_cmd = base_cmd
                except Exception as e:
                    logger.debug("Error aplicando shlex.split a comando '%s': %s", raw_cmd, e)
                    parts = raw_cmd.split()
                    if parts:
                        raw_cmd = parts[0]
                        args = parts[1:] + args

        base_name = os.path.basename(raw_cmd).lower() if raw_cmd else ""

        # Manejo especializado de `npx`:
        if base_name in ("npx", "npx.cmd", "npx.exe"):
            # Asegurar flag `-y` para evitar que npx bloquee en stdin preguntando
            # "Need to install the following packages: ... Ok to proceed? (y)"
            if "-y" not in args and "--yes" not in args:
                args.insert(0, "-y")

        # Inyectar PATH enriquecido en variables de entorno del servidor
        env = dict(cfg.get("env") or {})
        enhanced_path = get_enhanced_path(env.get("PATH"))
        env["PATH"] = enhanced_path

        # Si es npx o npm, configurar variables que desactivan prompts interactivos
        if "npx" in base_name or "npm" in base_name:
            env.setdefault("npm_config_yes", "true")
            env.setdefault("CI", "1")

        # Resolver ruta absoluta al ejecutable si es posible
        resolved_cmd = resolve_executable(raw_cmd, custom_path=enhanced_path)

        cfg["command"] = resolved_cmd
        cfg["args"] = args
        cfg["env"] = env

    return cfg


def parse_claude_or_mcp_json(
    raw_data: Union[str, Dict[str, Any]], fallback_name: str = "mcp-server"
) -> List[Tuple[str, Dict[str, Any]]]:
    """Parsea configuraciones en formato Claude Desktop / Cursor / mcpservers.org o JSON libre.

    Formatos soportados:
    1. Archivo/bloque Claude Desktop estándar:
       {"mcpServers": {"server-a": {"command": "npx", "args": [...]}}}
    2. Mapa de servidores:
       {"server-a": {"command": "npx", "args": [...]}}
    3. Configuración de servidor individual:
       {"command": "npx", "args": ["-y", "hyperresearch-ai-docs-mcp"]}
    4. Comando en texto plano:
       "npx -y hyperresearch-ai-docs-mcp"
    """
    if isinstance(raw_data, str):
        text = raw_data.strip()
        if not text:
            return []
        # Intentar parsear como JSON
        try:
            parsed = json.loads(text)
            return parse_claude_or_mcp_json(parsed, fallback_name=fallback_name)
        except json.JSONDecodeError:
            # Es una línea de comando en texto plano
            cfg = normalize_mcp_config({"transport": "stdio", "command": text, "args": []})
            return [(fallback_name, cfg)]

    if not isinstance(raw_data, dict):
        return []

    data = raw_data

    # Formato Claude Desktop oficial: {"mcpServers": { ... }}
    if "mcpServers" in data and isinstance(data["mcpServers"], dict):
        results = []
        for name, srv_conf in data["mcpServers"].items():
            if isinstance(srv_conf, dict):
                norm = normalize_mcp_config(srv_conf)
                results.append((name, norm))
        return results

    # Formato servidor único con 'command' o 'url'
    if "command" in data or "url" in data:
        norm = normalize_mcp_config(data)
        return [(fallback_name, norm)]

    # Formato mapa simple {"mi-servidor": {"command": ...}}
    results = []
    for k, v in data.items():
        if isinstance(v, dict) and ("command" in v or "url" in v or "transport" in v):
            norm = normalize_mcp_config(v)
            results.append((k, norm))

    if results:
        return results

    # Fallback genérico
    return [(fallback_name, normalize_mcp_config(data))]


def format_mcp_exception(exc: BaseException) -> str:
    """Extrae un mensaje de error legible y limpio de una excepción, desenvolviendo ExceptionGroup."""
    if hasattr(exc, "exceptions"):
        # Python 3.11+ ExceptionGroup / BaseExceptionGroup
        subs = []
        for sub in getattr(exc, "exceptions", []):
            subs.append(format_mcp_exception(sub))
        return "; ".join(subs) if subs else str(exc)

    msg = str(exc).strip()
    return msg or type(exc).__name__
