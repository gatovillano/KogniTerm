"""Capa de ejecución mínima estilo KAI-CLI / SuperAgent para KogniTerm.

Esta subpaquete implementa el camino de baja latencia y alta velocidad:
- ToolRegistry unificado (Capabilities)
- LLMBridge delgado sobre LiteLLM
- SuperAgent con bucle agéntico nativo
- SuperAgentRunner para integración con AgentInteractionManager
"""

from kogniterm.core.ai_cli_bridge.llm_bridge import LLMBridge
from kogniterm.core.ai_cli_bridge.tool_registry_adapter import (
    ToolRegistryAdapter,
    get_default_adapter,
)


def __getattr__(name: str):
    if name in ("SuperAgent", "SuperAgentRunner", "create_super_agent"):
        from kogniterm.core.agents.super_agent import (
            SuperAgent,
            SuperAgentRunner,
            create_super_agent,
        )

        mapping = {
            "SuperAgent": SuperAgent,
            "SuperAgentRunner": SuperAgentRunner,
            "create_super_agent": create_super_agent,
        }
        return mapping[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "LLMBridge",
    "SuperAgent",
    "SuperAgentRunner",
    "create_super_agent",
    "ToolRegistryAdapter",
    "get_default_adapter",
]
