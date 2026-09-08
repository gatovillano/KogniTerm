import functools
import queue
import logging
from typing import Optional, Any
from langgraph.graph import StateGraph, END
from kogniterm.core.agent_state import AgentState
from kogniterm.core.llm_service import LLMService
from kogniterm.core.agents.base_agent import BaseAgentNode
from kogniterm.core.agents.tool_executor import ToolExecutor, should_continue
from kogniterm.core.agents.super_agent import SuperAgentRunner

logger = logging.getLogger(__name__)


class DynamicAgentRunner(SuperAgentRunner):
    """
    Motor asíncrono para agentes dinámicos configurados al vuelo con prompts personalizados.
    Basado en SuperAgentRunner para ejecución de alto rendimiento, streaming fluido y
    gestión limpia de herramientas.
    """

    def __init__(
        self,
        llm_service: LLMService,
        system_prompt: str,
        terminal_ui: Optional[Any] = None,
        interrupt_queue: Optional[queue.Queue] = None,
        command_approval_handler=None,
    ) -> None:
        super().__init__(
            llm_service=llm_service,
            terminal_ui=terminal_ui,
            interrupt_queue=interrupt_queue,
            command_approval_handler=command_approval_handler,
            custom_system_prompt=system_prompt,
        )


def call_dynamic_model_node(
    state: AgentState,
    llm_service: LLMService,
    system_prompt: str,
    terminal_ui: Optional[Any] = None,
    interrupt_queue: Optional[queue.Queue] = None,
):
    if state.completed:
        logger.info(
            "DynamicAgent: Ya completado (completed flag). Saltando llamada al modelo."
        )
        from langchain_core.messages import AIMessage

        if not state.messages or not isinstance(state.messages[-1], AIMessage):
            state.messages.append(
                AIMessage(content="Proceso finalizado a través de complete_task.")
            )
        return {"messages": state.messages, "completed": True}

    logger.info("DynamicAgent: Ejecutando nodo call_model...")
    return BaseAgentNode.call_model(
        state=state,
        llm_service=llm_service,
        system_prompt=system_prompt,
        terminal_ui=terminal_ui,
        interrupt_queue=interrupt_queue,
    )


def create_dynamic_agent(
    llm_service: LLMService,
    system_prompt: str,
    terminal_ui: Optional[Any] = None,
    interrupt_queue: Optional[queue.Queue] = None,
    command_approval_handler=None,
) -> DynamicAgentRunner:
    """Construye y devuelve un DynamicAgentRunner basado en SuperAgent."""
    return DynamicAgentRunner(
        llm_service=llm_service,
        system_prompt=system_prompt,
        terminal_ui=terminal_ui,
        interrupt_queue=interrupt_queue,
        command_approval_handler=command_approval_handler,
    )


def create_legacy_dynamic_agent_graph(
    llm_service: LLMService,
    system_prompt: str,
    terminal_ui: Optional[Any] = None,
    interrupt_queue: Optional[queue.Queue] = None,
):
    """Construye y compila un grafo LangGraph genérico para un agente dinámico (fallback legacy)."""
    workflow = StateGraph(AgentState)

    workflow.add_node(
        "call_model",
        functools.partial(
            call_dynamic_model_node,
            llm_service=llm_service,
            system_prompt=system_prompt,
            terminal_ui=terminal_ui,
            interrupt_queue=interrupt_queue,
        ),
    )
    workflow.add_node(
        "execute_tool",
        functools.partial(
            ToolExecutor.execute_tool_node,
            llm_service=llm_service,
            terminal_ui=terminal_ui,
            interrupt_queue=interrupt_queue,
        ),
    )

    workflow.set_entry_point("call_model")

    workflow.add_conditional_edges(
        "call_model", should_continue, {"execute_tool": "execute_tool", "call_model": "call_model", END: END}
    )

    workflow.add_edge("execute_tool", "call_model")

    return workflow.compile()
