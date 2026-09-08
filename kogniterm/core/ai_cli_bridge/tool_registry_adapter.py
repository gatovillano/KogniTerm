import asyncio
import inspect
import json
from typing import Any, Dict, List, Optional

from kogniterm.capabilities.registry import ToolDefinition, default_tool_registry


class ToolRegistryAdapter:
    """Normaliza el registro existente para ejecución directa sin LangChain."""

    def __init__(self, registry=None) -> None:
        self._registry = registry or default_tool_registry

    def get_all(self):
        return self._registry.get_all()

    def get_schemas_for_litellm(self) -> List[Dict[str, Any]]:
        return self._registry.get_schemas_for_litellm()

    def get_handler(self, name: str):
        return self._registry.get_handler(name)

    async def execute(self, name: str, args: Dict[str, Any]) -> Any:
        handler = self.get_handler(name)
        if handler is None:
            raise KeyError(f"Herramienta no registrada: '{name}'")

        if inspect.iscoroutinefunction(handler):
            return await handler(**args)

        return await asyncio.to_thread(handler, **args)


_default_adapter: Optional[ToolRegistryAdapter] = None


def get_default_adapter() -> ToolRegistryAdapter:
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = ToolRegistryAdapter()
    return _default_adapter
