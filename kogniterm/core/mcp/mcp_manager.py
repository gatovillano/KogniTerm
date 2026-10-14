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

        # Sesiones MCP persistentes (como KognitoAI): mantener vivo el subproceso
        # (y el navegador) entre llamadas, con chequeo de salud y reconexión.
        self._session_ctxs: Dict[str, Any] = {}
        self._sessions: Dict[str, Any] = {}
        self._session_configs: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> "MCPManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_on_reload_callback(self, callback: Any):
        """Registra una función a ejecutar cuando los servidores MCP se recarguen."""
        if callback not in self._on_reload_callbacks:
            self._on_reload_callbacks.append(callback)

    def is_session_alive(self, name: str) -> bool:
        """Verifica si la sesión MCP del servidor sigue abierta y saludable."""
        session = self._sessions.get(name)
        if not session:
            return False
        write_stream = getattr(session, "_write_stream", None)
        if write_stream is not None:
            if getattr(write_stream, "_closed", False):
                return False
            try:
                stats = write_stream.statistics()
                if stats.open_receive_streams == 0:
                    return False
            except Exception:
                pass
        read_stream = getattr(session, "_read_stream", None)
        if read_stream is not None and getattr(read_stream, "_closed", False):
            return False
        return True

    async def disconnect_server(self, name: str):
        """Cierra una sesión MCP persistente de forma segura."""
        cm = self._session_ctxs.pop(name, None)
        if cm is not None:
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._sessions.pop(name, None)
        self._session_configs.pop(name, None)

    async def connect_server(self, name: str, config_dict: Dict[str, Any]) -> bool:
        """Abre (o reutiliza) una sesión MCP persistente para el servidor."""
        if self.is_session_alive(name):
            return True

        await self.disconnect_server(name)
        from kogniterm.core.mcp.env_utils import normalize_mcp_config

        norm_cfg = normalize_mcp_config(config_dict)
        self._session_configs[name] = config_dict
        transport = norm_cfg.get("transport", "stdio")

        try:
            from langchain_mcp_adapters.sessions import create_session
            if transport == "stdio":
                cmd = norm_cfg.get("command")
                if not cmd:
                    raise ValueError("Comando principal no especificado")
                conn = {
                    "transport": "stdio",
                    "command": cmd,
                    "args": norm_cfg.get("args", []),
                }
                if norm_cfg.get("env"):
                    conn["env"] = norm_cfg.get("env")
            elif transport in ("sse", "http", "streamable_http", "websocket"):
                url = norm_cfg.get("url")
                if not url:
                    raise ValueError(f"URL no especificada para transporte {transport}")
                conn = {"transport": transport, "url": url}
                if norm_cfg.get("headers"):
                    conn["headers"] = norm_cfg.get("headers")
            else:
                raise ValueError(f"Transporte desconocido: {transport}")

            cm = create_session(conn)
            session = await cm.__aenter__()
            await session.initialize()
            self._session_ctxs[name] = cm
            self._sessions[name] = session
            return True
        except Exception as exc:
            logger.error(f"Error conectando sesión MCP {name}: {exc}")
            await self.disconnect_server(name)
            return False

    async def reload(self):
        """Sincroniza los servidores activos y carga sus herramientas."""
        from kogniterm.core.mcp.env_utils import format_mcp_exception
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
                err_msg = format_mcp_exception(e)
                logger.error(f"Error al conectar con servidor MCP {name}: {err_msg}")
                self.server_statuses[name] = {"status": "error", "error": err_msg, "tools": []}

        # Limpiar sesiones de servidores eliminados/deshabilitados
        for old_name in list(self._session_ctxs.keys()):
            if old_name not in servers:
                await self.disconnect_server(old_name)

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
        """Carga las herramientas de un servidor MCP usando una sesión persistente."""
        from langchain_mcp_adapters.tools import load_mcp_tools, _convert_call_tool_result
        from kogniterm.core.mcp.env_utils import normalize_mcp_config, format_mcp_exception

        isolate_mcp_stderr()

        norm_cfg = normalize_mcp_config(config_dict)
        log_pos = 0
        try:
            log_pos = os.path.getsize(mcp_errlog_path())
        except Exception:
            pass

        try:
            # Abrir/reutilizar sesión persistente (mantiene ventana/proceso vivo)
            connected = await self.connect_server(name, config_dict)
            if not connected:
                raise RuntimeError("No se pudo abrir la sesión MCP persistente")
            session = self._sessions[name]

            tools = await load_mcp_tools(session, server_name=name)

            for tool in tools:
                # Preservar formato multimodal (screenshots) como content y no texto
                if hasattr(tool, "response_format"):
                    tool.response_format = "content"

                orig_coro = getattr(tool, "coroutine", None)
                if orig_coro:
                    tool_name = getattr(tool, "name", "")

                    async def make_resilient_call(**arguments: Any):
                        nonlocal orig_coro
                        srv_name = name
                        if not self.is_session_alive(srv_name):
                            cfg = self._session_configs.get(srv_name, config_dict)
                            await self.disconnect_server(srv_name)
                            if not await self.connect_server(srv_name, cfg):
                                raise RuntimeError(f"Sesión MCP {srv_name} no disponible")
                        try:
                            return await asyncio.wait_for(orig_coro(**arguments), timeout=300.0)
                        except Exception as exc:
                            exc_name = type(exc).__name__
                            if "ClosedResourceError" in exc_name or "ClosedResourceError" in str(exc):
                                logger.warning(
                                    f"Conexión perdida con servidor MCP {name} ({tool_name}). Reconectando y reintentando..."
                                )
                                cfg = self._session_configs.get(srv_name, config_dict)
                                await self.disconnect_server(srv_name)
                                if await self.connect_server(srv_name, cfg):
                                    new_session = self._sessions.get(srv_name)
                                    if new_session is not None:
                                        result = await new_session.call_tool(tool_name, arguments)
                                        return _convert_call_tool_result(result)
                            raise

                    tool.coroutine = make_resilient_call

            return tools
        except Exception as e:
            recent_err = ""
            try:
                path = mcp_errlog_path()
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(log_pos)
                        new_content = f.read()
                        err_lines = [
                            l.strip()
                            for l in new_content.splitlines()
                            if l.strip() and not l.strip().startswith(("│", "╭", "╰", "FastMCP"))
                        ]
                        meaningful = [
                            l for l in err_lines
                            if "not found" in l.lower() or "error" in l.lower() or "failed" in l.lower()
                        ]
                        candidates = meaningful if meaningful else err_lines
                        if candidates:
                            recent_err = " — ".join(candidates[:2])
            except Exception:
                pass

            base_err = format_mcp_exception(e)
            if recent_err and recent_err not in base_err:
                raise RuntimeError(f"{recent_err} ({base_err})") from e
            raise RuntimeError(base_err) from e

    async def test_connection(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Prueba la conexión con un servidor MCP sin guardar la configuración."""
        from kogniterm.core.mcp.env_utils import normalize_mcp_config, format_mcp_exception
        try:
            norm_cfg = normalize_mcp_config(config_dict)
            transport = norm_cfg.get("transport", "stdio")
            if transport == "stdio":
                cmd = norm_cfg.get("command")
                if not cmd:
                    return {"status": "error", "message": "Comando no especificado"}
                tools = await self._load_server_tools("test", norm_cfg)
                tool_names = [getattr(t, "name", str(t)) for t in tools]
                return {"status": "ok", "tools": tool_names}
            elif transport in ("sse", "http", "streamable_http", "websocket"):
                url = norm_cfg.get("url")
                if not url:
                    return {"status": "error", "message": f"URL no especificada para transporte {transport}"}
                tools = await self._load_server_tools("test", norm_cfg)
                tool_names = [getattr(t, "name", str(t)) for t in tools]
                return {"status": "ok", "tools": tool_names}
            return {"status": "error", "message": f"Transporte desconocido: {transport}"}
        except Exception as e:
            return {"status": "error", "message": format_mcp_exception(e)}

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


