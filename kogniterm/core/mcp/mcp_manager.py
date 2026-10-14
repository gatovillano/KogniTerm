import asyncio
import atexit
import inspect
import logging
import os
import threading
from contextlib import AsyncExitStack
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


class PersistentMCPTool:
    """Proxy de herramienta MCP que fija la ejecución al loop del MCPManager.

    `langchain-mcp-adapters` devuelve herramientas ligadas a una `ClientSession`
    que vive en un event loop concreto. Este proxy encola cada invocación en
    ese loop (vía `asyncio.run_coroutine_threadsafe`), de modo que la sesión —
    y con ella el estado del servidor (por ejemplo el navegador que mantiene
    abierto browser-use)— permanece vivo entre acciones del agente.

    Sin esto, cada invocación abriría una sesión nueva, arrancaría un servidor
    nuevo y lo mataría al terminar: el navegador se abriría y se cerraría
    inmediatamente sin continuidad entre acciones.
    """

    def __init__(self, tool: Any, manager: "MCPManager"):
        self._tool = tool
        self._manager = manager
        self.name = getattr(tool, "name", str(tool))
        self.description = getattr(tool, "description", "") or ""
        self.args_schema = getattr(tool, "args_schema", None)
        self.parameters_schema = getattr(tool, "parameters_schema", None)
        self.metadata = getattr(tool, "metadata", None)
        # Señalar herramienta async pura (llm_service usa `coroutine` y `func`
        # para decidir ejecutarla vía ainvoke en lugar de invoke síncrono).
        self.func = None
        self.coroutine = self.ainvoke

    def __getattr__(self, item: str) -> Any:
        # Delegar cualquier otro atributo en la herramienta original.
        if item.startswith("_"):
            raise AttributeError(item)
        return getattr(self._tool, item)

    def __repr__(self) -> str:
        return f"<PersistentMCPTool {self.name}>"

    async def ainvoke(self, *args, **kwargs):
        """Ejecuta la herramienta en el loop dedicado del MCPManager."""
        loop = self._manager._ensure_loop()
        inner = self._tool.ainvoke(*args, **kwargs)
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            # Ya estamos en el loop de la sesión: no re-encolar (evita deadlock).
            return await inner
        fut = asyncio.run_coroutine_threadsafe(inner, loop)
        return await asyncio.wrap_future(fut)

    def invoke(self, *args, **kwargs):
        """Variante síncrona: bloquea hasta que el loop de sesiones termine."""
        loop = self._manager._ensure_loop()
        if threading.current_thread() is self._manager._loop_thread:
            raise RuntimeError(
                f"No se puede invocar '{self.name}' síncronamente desde el loop MCP; usa await ainvoke()"
            )
        inner = self._tool.ainvoke(*args, **kwargs)
        return asyncio.run_coroutine_threadsafe(inner, loop).result()


class MCPManager:
    """Gestor singleton para la administración de conexiones y herramientas MCP.

    Mantiene una sesión MCP persistente por servidor en un event loop dedicado
    en segundo plano, de forma que servidores con estado (browser-use,
    playwright, etc.) conservan su contexto — pestaña de navegador abierta,
    cookies, memoria de conversación — entre invocaciones consecutivas de
    herramientas del agente.
    """
    _instance: Optional["MCPManager"] = None

    def __init__(self):
        self.config_manager = ConfigManager()
        self.active_tools: List[Any] = []
        self.server_statuses: Dict[str, Dict[str, Any]] = {}
        self._on_reload_callbacks: List[Any] = []
        # Loop dedicado que mantiene vivas las sesiones MCP.
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._loop_lock = threading.Lock()
        self._reload_lock: Optional[asyncio.Lock] = None
        self._session_stacks: Dict[str, AsyncExitStack] = {}
        self._sessions: Dict[str, Any] = {}
        self._atexit_registered = False

    @classmethod
    def get_instance(cls) -> "MCPManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_on_reload_callback(self, callback: Any):
        """Registra una función a ejecutar cuando los servidores MCP se recarguen."""
        if callback not in self._on_reload_callbacks:
            self._on_reload_callbacks.append(callback)

    # ── Loop dedicado y sesiones persistentes ──────────────────────────────

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Devuelve el loop dedicado de sesiones MCP, creándolo si no existe."""
        with self._loop_lock:
            if (
                self._loop is not None
                and not self._loop.is_closed()
                and self._loop.is_running()
            ):
                return self._loop
            loop = asyncio.new_event_loop()
            ready = threading.Event()

            def _run_loop():
                asyncio.set_event_loop(loop)
                ready.set()
                try:
                    loop.run_forever()
                finally:
                    # Ejecutar los finalizadores pendientes y cerrar el loop
                    # para que un `_ensure_loop` posterior lo recree en lugar
                    # de devolver un loop detenido (colgaría run_coroutine_threadsafe).
                    try:
                        loop.run_until_complete(loop.shutdown_asyncgens())
                        loop.run_until_complete(loop.shutdown_default_executor())
                    except Exception:
                        pass
                    loop.close()

            self._loop_thread = threading.Thread(
                target=_run_loop, name="mcp-manager-loop", daemon=True
            )
            self._loop_thread.start()
            ready.wait(timeout=5)
            self._loop = loop
            if not self._atexit_registered:
                atexit.register(self.shutdown)
                self._atexit_registered = True
            logger.debug("Loop dedicado de sesiones MCP iniciado")
            return loop

    async def _reload_impl(self):
        """Recarga real; siempre se ejecuta en el loop dedicado de sesiones."""
        from kogniterm.core.mcp.env_utils import format_mcp_exception

        if self._reload_lock is None:
            self._reload_lock = asyncio.Lock()
        async with self._reload_lock:
            # Cerrar sesiones previas: mata subprocesos MCP y navegadores que
            # ya no corresponden a la configuración actual.
            await self._close_sessions()

            servers = self.config_manager.get_mcp_servers()
            stateless = os.environ.get("KOGNITERM_MCP_STATELESS", "").strip().lower() in (
                "1", "true", "yes"
            )
            new_tools: List[Any] = []
            new_statuses: Dict[str, Dict[str, Any]] = {}

            for name, config_dict in servers.items():
                if config_dict.get("disabled", False):
                    new_statuses[name] = {"status": "disabled", "tools": []}
                    continue
                try:
                    if stateless:
                        tools = await self._load_server_tools(name, config_dict)
                    else:
                        tools = await self._connect_persistent(name, config_dict)
                    new_tools.extend(tools)
                    new_statuses[name] = {
                        "status": "connected",
                        "tools": [getattr(t, "name", str(t)) for t in tools],
                    }
                except Exception as e:
                    err_msg = format_mcp_exception(e)
                    logger.error(f"Error al conectar con servidor MCP {name}: {err_msg}")
                    new_statuses[name] = {"status": "error", "error": err_msg, "tools": []}

            # Swap atómico (no clear+extend) para que los lectores en otros
            # hilos nunca vean la lista a medias.
            self.active_tools = new_tools
            self.server_statuses = new_statuses

        for cb in self._on_reload_callbacks:
            try:
                if inspect.iscoroutinefunction(cb):
                    await cb()
                elif callable(cb):
                    cb()
            except Exception as ex:
                logger.error(f"Error en callback de recarga de MCPManager: {ex}")

    async def _connect_persistent(self, name: str, config_dict: Dict[str, Any]) -> List[Any]:
        """Conecta un servidor MCP y mantiene la sesión abierta hasta el próximo reload.

        Las herramientas devueltas están envueltas en `PersistentMCPTool`, que
        serializa cada invocación en el loop dedicado donde vive la sesión.
        """
        from langchain_mcp_adapters.sessions import create_session
        from langchain_mcp_adapters.tools import load_mcp_tools
        from kogniterm.core.mcp.env_utils import normalize_mcp_config, format_mcp_exception

        isolate_mcp_stderr()
        norm_cfg = normalize_mcp_config(config_dict)
        conn = self._build_connection(norm_cfg)

        log_pos = 0
        try:
            log_pos = os.path.getsize(mcp_errlog_path())
        except Exception:
            pass

        stack = AsyncExitStack()
        try:
            session = await stack.enter_async_context(create_session(conn))
            await session.initialize()
            tools = await load_mcp_tools(session=session, server_name=name)
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            await stack.aclose()
            raise
        except BaseException as e:
            await stack.aclose()
            raise self._enrich_error(e, log_pos)
        self._session_stacks[name] = stack
        self._sessions[name] = session
        wrapped = [PersistentMCPTool(t, self) for t in tools]
        logger.debug(
            "Servidor MCP '%s' conectado con sesión persistente (%d herramientas)",
            name, len(wrapped),
        )
        return wrapped

    def _enrich_error(self, e: BaseException, log_pos: int) -> BaseException:
        """Enriquece una excepción de conexión MCP con lo que el subproceso escribió en stderr.

        Ej.: un `npx` que falla con 404 escribe el detalle en stderr, no en la
        excepción; sin esto la TUI solo muestra un genérico "Connection closed".
        """
        from kogniterm.core.mcp.env_utils import format_mcp_exception
        recent_err = self._read_stderr_tail(log_pos)
        base_err = format_mcp_exception(e)
        if recent_err and recent_err not in base_err:
            return RuntimeError(f"{recent_err} ({base_err})")
        return e if isinstance(e, Exception) else RuntimeError(base_err)

    @staticmethod
    def _read_stderr_tail(log_pos: int) -> str:
        """Devuelve las líneas 'interesantes' (errores) añadidas al log de stderr desde log_pos."""
        try:
            path = mcp_errlog_path()
            if not os.path.exists(path):
                return ""
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
            return " — ".join(candidates[:2])
        except Exception:
            return ""

    async def _close_sessions(self):
        """Cierra todas las sesiones persistentes (debe correr en el loop dedicado)."""
        stacks = list(self._session_stacks.values())
        self._session_stacks.clear()
        self._sessions.clear()
        for stack in stacks:
            try:
                await stack.aclose()
            except Exception as e:
                logger.debug("Error cerrando sesión MCP persistente: %s", e)

    def shutdown(self, timeout: float = 5.0):
        """Cierra sesiones MCP y detiene el loop dedicado (seguro para atexit)."""
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(self._close_sessions(), loop)
            fut.result(timeout=timeout)
        except Exception:
            pass
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            pass
        # Olvidar el loop para que un reload posterior lo recree limpiamente
        # en lugar de reutilizar uno que ya está muriendo.
        with self._loop_lock:
            if self._loop is loop:
                self._loop = None

    def _build_connection(self, norm_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Construye el dict de conexión de langchain-mcp-adapters desde un cfg normalizado."""
        transport = norm_cfg.get("transport", "stdio")
        if transport == "stdio":
            cmd = norm_cfg.get("command")
            if not cmd:
                raise ValueError("Comando principal no especificado")
            conn: Dict[str, Any] = {
                "transport": "stdio",
                "command": cmd,
                "args": norm_cfg.get("args", []),
            }
            if norm_cfg.get("env"):
                conn["env"] = norm_cfg.get("env")
            return conn
        if transport in ("sse", "http", "streamable_http", "websocket"):
            url = norm_cfg.get("url")
            if not url:
                raise ValueError(f"URL no especificada para transporte {transport}")
            conn = {"transport": transport, "url": url}
            if norm_cfg.get("headers"):
                conn["headers"] = norm_cfg.get("headers")
            return conn
        raise ValueError(f"Transporte desconocido: {transport}")

    async def reload(self):
        """Sincroniza los servidores activos y carga sus herramientas.

        La conexión real ocurre en el loop dedicado para que las sesiones
        persistan; este método solo espera el resultado sin bloquear el loop
        del llamante.
        """
        loop = self._ensure_loop()
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            await self._reload_impl()
            return
        fut = asyncio.run_coroutine_threadsafe(self._reload_impl(), loop)
        await asyncio.wrap_future(fut)

    async def _load_server_tools(self, name: str, config_dict: Dict[str, Any]) -> List[Any]:
        """Carga las herramientas de un servidor MCP en modo stateless (sesión por invocación).

        Se usa solo para `test_connection` y como fallback con
        `KOGNITERM_MCP_STATELESS=1`. El camino normal (`reload`) usa
        `_connect_persistent` para conservar el estado del servidor entre acciones.
        """
        from langchain_mcp_adapters.tools import load_mcp_tools
        from kogniterm.core.mcp.env_utils import normalize_mcp_config

        # Nunca dejar que la salida del subproceso MCP contamine la terminal.
        isolate_mcp_stderr()

        # Normalizar y auto-detectar transporte, npx flags, PATH de Node, etc.
        norm_cfg = normalize_mcp_config(config_dict)
        transport = norm_cfg.get("transport", "stdio")

        log_pos = 0
        try:
            log_pos = os.path.getsize(mcp_errlog_path())
        except Exception:
            pass

        try:
            if transport not in ("stdio", "sse", "http", "streamable_http", "websocket"):
                return []
            conn = self._build_connection(norm_cfg)
            return await load_mcp_tools(session=None, connection=conn, server_name=name)
        except Exception as e:
            raise self._enrich_error(e, log_pos)

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


