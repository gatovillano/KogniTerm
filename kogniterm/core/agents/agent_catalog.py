"""Catálogo de agentes conversacionales nativos de KogniTerm.

Solo incluye los motores que pueden ejecutar un turno completo de chat con el
mismo contrato que `AgentInteractionManager`: historial LangChain, streaming,
herramientas y confirmaciones. Los crews de CrewAI, ejecutores, despachadores y
utilidades internas no son agentes principales seleccionables.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


DEFAULT_CHAT_AGENT = "super_agent"
SUPPORTED_CHAT_AGENTS = (
    "super_agent",
    "bash_agent",
    "code_agent",
    "researcher_agent",
)

_AGENT_ALIASES = {
    "super": "super_agent",
    "superagent": "super_agent",
    "orchestrator": "super_agent",
    "bash": "bash_agent",
    "bashagent": "bash_agent",
    "terminal": "bash_agent",
    "shell": "bash_agent",
    "code": "code_agent",
    "coder": "code_agent",
    "deepcoder": "code_agent",
    "deep_coder": "code_agent",
    "code_crew": "code_agent",
    "researcher": "researcher_agent",
    "researcheragent": "researcher_agent",
    "research": "researcher_agent",
    "deepresearcher": "researcher_agent",
    "deep_researcher": "researcher_agent",
    "build": "super_agent",
    "plan": "super_agent",
    "default": "super_agent",
}


@dataclass(frozen=True)
class AgentDescriptor:
    """Metadatos estables para el selector de agentes del cliente."""

    id: str
    name: str
    description: str
    engine: str


_AGENT_DESCRIPTORS = (
    AgentDescriptor(
        id="super_agent",
        name="SuperAgent",
        description="Orquestación general: terminal, código, investigación, herramientas y delegación.",
        engine="SuperAgentRunner",
    ),
    AgentDescriptor(
        id="bash_agent",
        name="BashAgent",
        description="Especialista en terminal, comandos, Python, memoria y coordinación de tareas.",
        engine="BashAgentRunner",
    ),
    AgentDescriptor(
        id="code_agent",
        name="DeepCoder",
        description="Diseño, implementación y validación de código con revisión técnica.",
        engine="DeepCoderRunner",
    ),
    AgentDescriptor(
        id="researcher_agent",
        name="DeepResearcher",
        description="Investigación profunda de código y web con informe técnico y fuentes.",
        engine="DeepResearcherRunner",
    ),
)


def normalize_agent_id(value: Optional[str], default: str = DEFAULT_CHAT_AGENT) -> str:
    """Normaliza alias comunes al identificador canónico del agente."""
    if value is None:
        return default
    candidate = str(value).strip().lower()
    if not candidate:
        return default
    if candidate in SUPPORTED_CHAT_AGENTS:
        return candidate
    if candidate in _AGENT_ALIASES:
        return _AGENT_ALIASES[candidate]
    raise ValueError(f"Agente no soportado: {value!r}")


def describe_agents() -> List[Dict[str, Any]]:
    """Devuelve el catálogo nativo sin instanciar ningún motor."""
    return [
        {
            "id": descriptor.id,
            "name": descriptor.name,
            "description": descriptor.description,
            "engine": descriptor.engine,
        }
        for descriptor in _AGENT_DESCRIPTORS
    ]


def create_agent_runner(
    agent_id: str,
    *,
    llm_service: Any,
    terminal_ui: Any = None,
    interrupt_queue: Any = None,
    command_approval_handler: Any = None,
) -> Any:
    """Instancia perezosamente el motor correspondiente al agente canónico."""
    normalized = normalize_agent_id(agent_id)
    if normalized == "super_agent":
        from .super_agent import create_super_agent

        return create_super_agent(
            llm_service,
            terminal_ui,
            interrupt_queue,
            command_approval_handler,
        )
    if normalized == "bash_agent":
        from .bash_agent import create_bash_agent

        return create_bash_agent(
            llm_service,
            terminal_ui,
            interrupt_queue,
            command_approval_handler,
        )
    if normalized == "code_agent":
        from .code_agent import create_code_agent

        return create_code_agent(
            llm_service,
            terminal_ui,
            interrupt_queue,
            command_approval_handler,
        )
    if normalized == "researcher_agent":
        from .researcher_agent import create_researcher_agent

        return create_researcher_agent(
            llm_service,
            terminal_ui,
            interrupt_queue,
            command_approval_handler,
        )
    raise ValueError(f"Agente no soportado: {agent_id!r}")
