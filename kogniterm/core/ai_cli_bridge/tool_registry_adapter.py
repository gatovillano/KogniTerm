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
        self._register_bundled_task_tracker()

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

        return None

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

        if inspect.iscoroutinefunction(handler):
            return await handler(**args)

        return await asyncio.to_thread(handler, **args)


_default_adapter: Optional[ToolRegistryAdapter] = None


def get_default_adapter() -> ToolRegistryAdapter:
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = ToolRegistryAdapter()
    return _default_adapter
