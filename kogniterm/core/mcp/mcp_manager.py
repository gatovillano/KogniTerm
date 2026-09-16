import asyncio
import logging
from typing import Dict, Any, List, Optional
from kogniterm.terminal.config_manager import ConfigManager
from kogniterm.core.mcp.config import MCPServerConfig

logger = logging.getLogger(__name__)

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
