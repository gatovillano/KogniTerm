from enum import Enum
from typing import FrozenSet, Dict

class AgentRole(Enum):
    LEAF = "leaf"                 # No puede delegar, mutar la memoria contextual, ni ejecutar comandos destructivos/riesgosos
    ORCHESTRATOR = "orchestrator"  # Acceso completo a herramientas y capacidad de delegación

# Herramientas bloqueadas por defecto para cada rol
DEFAULT_BLOCKED_TOOLS: Dict[AgentRole, FrozenSet[str]] = {
    AgentRole.LEAF: frozenset([
        "call_agent",            # Delegación simple
        "call_agents_parallel",  # Delegación paralela
        "skill_factory",         # Creación dinámica de nuevas herramientas/skills
        "refresh_tools",         # Recarga de herramientas
        "memory_append",         # Modificación de llm_context.md
        "memory_init",           # Inicialización de llm_context.md
        "memory_summarize",      # Resumen de llm_context.md
    ]),
    AgentRole.ORCHESTRATOR: frozenset()
}
