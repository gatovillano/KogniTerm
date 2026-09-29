import asyncio
import inspect
import json
import logging
from pathlib import Path
import sys
import importlib.util
from typing import Any, Callable, Dict, List, Optional

from kogniterm.capabilities.registry import ToolDefinition, default_tool_registry

logger = logging.getLogger(__name__)


def _load_bundled_task_tracker_and_schema():
    try:
        bundled_dir = Path(__file__).resolve().parent.parent.parent / "skills" / "bundled"
        tt_path = bundled_dir / "task-tracker" / "scripts" / "tool.py"
        mod_key = "_task_tracker_bundled_tool"
        if mod_key in sys.modules:
            mod = sys.modules[mod_key]
        else:
            spec = importlib.util.spec_from_file_location(mod_key, str(tt_path))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_key] = mod
            spec.loader.exec_module(mod)
        fn = getattr(mod, "task_tracker", None)
        raw_schema = getattr(mod, "tool_schema", None)
        schema = {"type": "function", "function": raw_schema} if raw_schema else None
        return fn, schema
    except Exception as exc:
        logger.debug(f"No se pudo cargar task_tracker desde bundled: {exc}")
        return None, None


def _load_bundled_task_tracker():
    fn, _ = _load_bundled_task_tracker_and_schema()
    return fn


def bind_task_tracker_context(terminal_ui: Any = None, llm_service: Any = None) -> None:
    """Vincula la instancia activa de TerminalUI o LLMService al módulo de task_tracker para actualizar la UI."""
    try:
        mod = sys.modules.get("_task_tracker_bundled_tool")
        if mod is None:
            _load_bundled_task_tracker_and_schema()
            mod = sys.modules.get("_task_tracker_bundled_tool")
        if mod:
            if terminal_ui is not None:
                setattr(mod, "_terminal_ui", terminal_ui)
                mod.__dict__["_terminal_ui"] = terminal_ui
            if llm_service is not None:
                setattr(mod, "_llm_service", llm_service)
                mod.__dict__["_llm_service"] = llm_service
    except Exception as exc:
        logger.debug(f"No se pudo vincular contexto a task_tracker: {exc}")


class ToolRegistryAdapter:
    """Normaliza el registro existente para ejecución directa sin LangChain."""

    def __init__(self, registry=None) -> None:
        self._registry = registry or default_tool_registry
        self._custom_handlers: Dict[str, Callable[..., Any]] = {}
        self._custom_schemas: Dict[str, Dict[str, Any]] = {}
        self._llm_service: Any = None
        self._register_bundled_task_tracker()

    def bind_llm_service(self, llm_service: Any) -> None:
        """Vincula el LLMService activo para exponer las herramientas de sus skills.

        Sin este enlace el adapter solo conoce capabilities, task_tracker y MCP, por lo que
        herramientas de skills (call_agents_parallel, refresh_tools, skill_factory, ...)
        nunca llegan al esquema del modelo aunque esten cargadas en el SkillManager.
        """
        self._llm_service = llm_service

    def _get_skill_manager(self):
        if self._llm_service is None:
            return None
        return getattr(self._llm_service, "skill_manager", None)

    def _register_bundled_task_tracker(self) -> None:
        tt_fn, tt_schema = _load_bundled_task_tracker_and_schema()
        if tt_fn and tt_schema:
            self.register_handler("task_tracker", tt_fn, schema=tt_schema)

    def register_handler(
        self,
        name: str,
        handler: Callable[..., Any],
        schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Registra un manejador dinámico o externo con su esquema LiteLLM."""
        self._custom_handlers[name] = handler
        if schema:
            self._custom_schemas[name] = schema

    def get_all(self):
        return self._registry.get_all()

    def get_schemas_for_litellm(self) -> List[Dict[str, Any]]:
        base_schemas = list(self._registry.get_schemas_for_litellm())
        for name, schema in self._custom_schemas.items():
            if not any(s.get("function", {}).get("name") == name for s in base_schemas):
                base_schemas.append(schema)

        # Integrar esquemas de herramientas de servidores MCP activos
        try:
            from kogniterm.core.mcp.mcp_manager import MCPManager
            from kogniterm.core.utils.tool_utils import convert_langchain_tool_to_litellm, sanitize_tool_name
            mcp_mgr = MCPManager.get_instance()
            for tool in mcp_mgr.active_tools:
                raw_name = getattr(tool, "name", None) or getattr(tool, "__name__", str(tool))
                clean_name = sanitize_tool_name(raw_name)
                # Evitar duplicados si ya está registrado
                if not any(s.get("function", {}).get("name") in (raw_name, clean_name) for s in base_schemas):
                    try:
                        schema = convert_langchain_tool_to_litellm(tool)
                        base_schemas.append(schema)
                    except Exception as e:
                        logger.debug(f"Error convirtiendo esquema para herramienta MCP {raw_name}: {e}")
        except Exception as exc:
            logger.debug(f"No se pudieron cargar herramientas MCP en get_schemas_for_litellm: {exc}")

        # Integrar herramientas de skills cargadas en el SkillManager (code tools).
        # Sin este bloque el modelo solo ve capabilities + task_tracker + MCP.
        skill_manager = self._get_skill_manager()
        if skill_manager is not None:
            existing = {
                s.get("function", {}).get("name")
                for s in base_schemas
                if isinstance(s, dict)
            }
            for tool in skill_manager.get_tools():
                raw_name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
                if not raw_name:
                    continue
                clean_name = sanitize_tool_name(raw_name)
                if raw_name in existing or clean_name in existing:
                    continue
                try:
                    schema = convert_langchain_tool_to_litellm(tool)
                    name = schema.get("function", {}).get("name")
                    if not name or name in existing:
                        continue
                    base_schemas.append(schema)
                    existing.add(name)
                except Exception as e:
                    logger.debug(f"Error convirtiendo esquema para herramienta de skill {raw_name}: {e}")

        return base_schemas

    def get_handler(self, name: str) -> Optional[Callable[..., Any]]:
        if name in self._custom_handlers:
            return self._custom_handlers[name]

        try:
            return self._registry.get_handler(name)
        except (KeyError, AttributeError):
            pass

        if name == "task_tracker":
            tt_fn, tt_schema = _load_bundled_task_tracker_and_schema()
            if tt_fn:
                self.register_handler("task_tracker", tt_fn, schema=tt_schema)
                return tt_fn

        # Búsqueda en herramientas de servidores MCP activos
        try:
            from kogniterm.core.mcp.mcp_manager import MCPManager
            mcp_tool = MCPManager.get_instance().get_tool(name)
            if mcp_tool is not None:
                return mcp_tool
        except Exception:
            pass

        # Búsqueda en herramientas de skills cargadas en el SkillManager
        skill_manager = self._get_skill_manager()
        if skill_manager is not None:
            try:
                skill_tool = skill_manager.get_tool(name)
            except Exception:
                skill_tool = None
            if skill_tool is not None:
                return skill_tool

        return None

    def _inject_dependencies(self, handler: Callable[..., Any], args: Dict[str, Any]) -> Dict[str, Any]:
        """Inyecta las dependencias que el LLM no conoce en los parámetros del esquema.

        Las herramientas de skills declaran parámetros como llm_service, terminal_ui,
        interrupt_queue o approval_handler que nunca aparecen en el tool schema. Sin esta
        inyección se ejecutarían como None y fallarían al construir sus subagentes.
        """
        call_args = dict(args or {})
        llm_service = self._llm_service
        if llm_service is None:
            return call_args

        try:
            params = inspect.signature(handler).parameters
        except (TypeError, ValueError):
            return call_args

        skill_manager = getattr(llm_service, "skill_manager", None)

        # terminal_ui e interrupt_queue viven en objetos distintos: el LLMService solo
        # guarda interrupt_queue, mientras terminal_ui lo mantiene el SkillManager.
        terminal_ui = getattr(llm_service, "terminal_ui", None) or getattr(
            skill_manager, "terminal_ui", None
        )
        interrupt_queue = getattr(llm_service, "interrupt_queue", None) or getattr(
            skill_manager, "interrupt_queue", None
        )
        approval_handler = getattr(skill_manager, "approval_handler", None)

        candidates = {
            "llm_service": llm_service,
            "terminal_ui": terminal_ui,
            "interrupt_queue": interrupt_queue,
            "approval_handler": approval_handler,
        }

        for param_name, value in candidates.items():
            if param_name in params and param_name not in call_args and value is not None:
                call_args[param_name] = value

        return call_args

    async def execute(self, name: str, args: Dict[str, Any]) -> Any:
        handler = self.get_handler(name)
        if handler is None:
            raise KeyError(f"Herramienta no registrada: '{name}'")

        if name == "task_tracker":
            # Normalizar y proteger argumentos para task_tracker
            call_args = dict(args)
            if not call_args.get("agent_name"):
                call_args["agent_name"] = "SuperAgent"
            valid_keys = {"action", "agent_name", "plan", "task_index", "status", "updates"}
            filtered_args = {k: v for k, v in call_args.items() if k in valid_keys}
            if inspect.iscoroutinefunction(handler):
                return await handler(**filtered_args)
            return await asyncio.to_thread(handler, **filtered_args)

        injected = self._inject_dependencies(handler, args)

        # Si es una herramienta LangChain (BaseTool / StructuredTool de MCP)
        if hasattr(handler, "ainvoke"):
            try:
                raw_res = await handler.ainvoke(injected)
            except Exception:
                raw_res = await asyncio.to_thread(handler.invoke, injected)
            if hasattr(raw_res, "content"):
                return raw_res.content
            return raw_res
        elif hasattr(handler, "invoke"):
            raw_res = await asyncio.to_thread(handler.invoke, injected)
            if hasattr(raw_res, "content"):
                return raw_res.content
            return raw_res

        if inspect.iscoroutinefunction(handler):
            return await handler(**injected)

        return await asyncio.to_thread(handler, **injected)


_default_adapter: Optional[ToolRegistryAdapter] = None


def get_default_adapter() -> ToolRegistryAdapter:
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = ToolRegistryAdapter()
    return _default_adapter
