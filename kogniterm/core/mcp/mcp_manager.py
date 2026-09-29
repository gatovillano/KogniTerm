import asyncio
import logging
import os
import threading
from typing import Dict, Any, List, Optional
from kogniterm.terminal.config_manager import ConfigManager
from kogniterm.core.mcp.config import MCPServerConfig

logger = logging.getLogger(__name__)

# ── Aislamiento de stderr de los servidores MCP ─────────────────────────────
# `mcp.client.stdio.stdio_client` usa `errlog=sys.stderr` por defecto. En la TUI
# `sys.stderr` es la propia terminal de pantalla completa, así que cualquier
# banner/log de un servidor MCP (p.ej. el "FastMCP 4.0.9" de MuseScore) se
# dibuja encima de la interfaz y la corrompe. Redirigimos stderr a un log propio.
_MCP_ERRLOG_LOCK = threading.Lock()
_MCP_ERRLOG = None
_STDIO_PATCHED = False


def mcp_errlog_path() -> str:
    """Ruta del log de stderr de los servidores MCP."""
    base = os.environ.get("KOGNITERM_LOG_DIR") or os.path.join(
        os.path.expanduser("~"), ".kogniterm", "logs"
    )
    return os.path.join(base, "mcp-stderr.log")


def _get_mcp_errlog():
    """Devuelve el file object de stderr de MCP (abierto una sola vez)."""
    global _MCP_ERRLOG
    with _MCP_ERRLOG_LOCK:
        if _MCP_ERRLOG is not None and not _MCP_ERRLOG.closed:
            return _MCP_ERRLOG
        path = mcp_errlog_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            _MCP_ERRLOG = open(path, "a", encoding="utf-8", errors="replace", buffering=1)
            return _MCP_ERRLOG
        except Exception:
            try:
                _MCP_ERRLOG = open(os.devnull, "w", encoding="utf-8")
                return _MCP_ERRLOG
            except Exception:
                return None


def isolate_mcp_stderr() -> bool:
    """Fuerza a que los subprocesos MCP escriban en su log, no en la terminal.

    Idempotente. Devuelve True si el parche quedó aplicado.
    """
    global _STDIO_PATCHED
    if _STDIO_PATCHED:
        return True
    try:
        import langchain_mcp_adapters.sessions as _sessions

        current = getattr(_sessions, "stdio_client", None)
        if current is None:
            return False
        if getattr(current, "_kogniterm_isolated", False):
            _STDIO_PATCHED = True
            return True

        def _isolated_stdio_client(server, errlog=None, **kwargs):
            target = _get_mcp_errlog()
            return current(server, errlog=target, **kwargs)

        _isolated_stdio_client._kogniterm_isolated = True
        _sessions.stdio_client = _isolated_stdio_client
        _STDIO_PATCHED = True
        logger.debug("stderr de servidores MCP redirigido a %s", mcp_errlog_path())
        return True
    except Exception as exc:
        logger.debug("No se pudo aislar stderr de MCP: %s", exc)
        return False


class MCPManager:
    """Gestor singleton para la administración de conexiones y herramientas MCP."""
    _instance: Optional["MCPManager"] = None

    def __init__(self):
        self.config_manager = ConfigManager()
        self.active_tools: List[Any] = []
        self.server_statuses: Dict[str, Dict[str, Any]] = {}
        self._on_reload_callbacks: List[Any] = []

    @classmethod
    def get_instance(cls) -> "MCPManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_on_reload_callback(self, callback: Any):
        """Registra una función a ejecutar cuando los servidores MCP se recarguen."""
        if callback not in self._on_reload_callbacks:
            self._on_reload_callbacks.append(callback)

    async def reload(self):
        """Sincroniza los servidores activos y carga sus herramientas."""
        servers = self.config_manager.get_mcp_servers()
        self.active_tools.clear()
        self.server_statuses.clear()
        
        for name, config_dict in servers.items():
            if config_dict.get("disabled", False):
                self.server_statuses[name] = {"status": "disabled", "tools": []}
                continue
            
            try:
                tools = await self._load_server_tools(name, config_dict)
                self.active_tools.extend(tools)
                self.server_statuses[name] = {
                    "status": "connected",
                    "tools": [getattr(t, "name", str(t)) for t in tools]
                }
            except Exception as e:
                logger.error(f"Error al conectar con servidor MCP {name}: {e}")
                self.server_statuses[name] = {"status": "error", "error": str(e), "tools": []}

        import inspect
        for cb in self._on_reload_callbacks:
            try:
                if inspect.iscoroutinefunction(cb):
                    await cb()
                elif callable(cb):
                    cb()
            except Exception as ex:
                logger.error(f"Error en callback de recarga de MCPManager: {ex}")

    async def _load_server_tools(self, name: str, config_dict: Dict[str, Any]) -> List[Any]:
        """Carga las herramientas de un servidor MCP por stdio o sse sin cerrar la sesión."""
        from langchain_mcp_adapters.tools import load_mcp_tools

        # Nunca dejar que la salida del subproceso MCP contamine la terminal.
        isolate_mcp_stderr()

        transport = config_dict.get("transport", "stdio")
        if transport == "stdio":
            cmd = config_dict.get("command")
            if not cmd:
                raise ValueError("Comando principal no especificado")
            conn = {
                "transport": "stdio",
                "command": cmd,
                "args": config_dict.get("args", []),
            }
            if config_dict.get("env"):
                conn["env"] = config_dict.get("env")
            return await load_mcp_tools(session=None, connection=conn, server_name=name)
        elif transport == "sse":
            url = config_dict.get("url")
            if not url:
                raise ValueError("URL de SSE no especificada")
            conn = {
                "transport": "sse",
                "url": url,
            }
            if config_dict.get("headers"):
                conn["headers"] = config_dict.get("headers")
            return await load_mcp_tools(session=None, connection=conn, server_name=name)
        return []

    async def test_connection(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Prueba la conexión con un servidor MCP sin guardar la configuración."""
        try:
            transport = config_dict.get("transport", "stdio")
            if transport == "stdio":
                cmd = config_dict.get("command")
                if not cmd:
                    return {"status": "error", "message": "Comando no especificado"}
                tools = await self._load_server_tools("test", config_dict)
                tool_names = [getattr(t, "name", str(t)) for t in tools]
                return {"status": "ok", "tools": tool_names}
            elif transport == "sse":
                url = config_dict.get("url")
                if not url:
                    return {"status": "error", "message": "URL de SSE no especificada"}
                tools = await self._load_server_tools("test", config_dict)
                tool_names = [getattr(t, "name", str(t)) for t in tools]
                return {"status": "ok", "tools": tool_names}
            return {"status": "error", "message": f"Transporte desconocido: {transport}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_all_servers_status(self) -> Dict[str, Any]:
        """Devuelve el estado de todos los servidores MCP configurados."""
        servers = self.config_manager.get_mcp_servers()
        result = {}
        for name, conf in servers.items():
            st = self.server_statuses.get(name, {"status": "disconnected", "tools": []})
            result[name] = {**conf, **st}
        return result

    def get_prompt_instructions(self) -> str:
        """Devuelve un bloque de directivas para el system prompt cuando hay herramientas MCP activas."""
        if not self.active_tools:
            return ""
        
        servers_info = []
        for name, info in self.server_statuses.items():
            if info.get("status") == "connected":
                tools = info.get("tools", [])
                tools_preview = ", ".join(f"`{t}`" for t in tools[:8])
                if len(tools) > 8:
                    tools_preview += f" y {len(tools) - 8} más"
                servers_info.append(f"  • Servidor **{name}** ({len(tools)} herramientas): {tools_preview}")

        lines = [
            "### 🔌 HERRAMIENTAS MCP (MODEL CONTEXT PROTOCOL) DISPONIBLES:",
            "Tienes servidores MCP conectados que te proveen herramientas nativas especializadas:",
            *servers_info,
            "",
            "⚠️ **DIRECTIVA OBLIGATORIA DE PRIORIDAD MCP**:",
            "- Cuando una tarea o consulta del usuario pueda resolverse usando cualquiera de tus herramientas MCP disponibles (por ejemplo: gestionar WordPress/Elementor, consultar tracks de Bitwig, bases de datos o servicios externos), **DEBES usar directamente la herramienta MCP nativa (`tool_call`)**.",
            "- **ESTÁ ESTRICTAMENTE PROHIBIDO usar `execute_command`, curl o escribir scripts de terminal ad-hoc** para simular acciones que ya están cubiertas por una herramienta MCP conectada."
        ]
        return "\n".join(lines) + "\n"

    def get_tool(self, name: str) -> Optional[Any]:
        """Busca una herramienta MCP activa por su nombre original o sanitizado."""
        from kogniterm.core.utils.tool_utils import sanitize_tool_name
        clean_target = sanitize_tool_name(name)
        for t in self.active_tools:
            t_name = getattr(t, "name", None) or getattr(t, "__name__", str(t))
            if t_name == name or sanitize_tool_name(t_name) == clean_target:
                return t
        return None


