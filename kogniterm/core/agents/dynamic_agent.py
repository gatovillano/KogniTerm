import functools
import queue
import logging
from typing import Optional, Any
from langgraph.graph import StateGraph, END
from kogniterm.core.agent_state import AgentState
from kogniterm.core.llm_service import LLMService
from kogniterm.core.agents.base_agent import BaseAgentNode
from kogniterm.core.agents.tool_executor import ToolExecutor, should_continue

logger = logging.getLogger(__name__)

def call_dynamic_model_node(
    state: AgentState, 
    llm_service: LLMService, 
    system_prompt: str, 
    terminal_ui: Optional[Any] = None, 
    interrupt_queue: Optional[queue.Queue] = None
):
    """Nodo de ejecución para invocar el LLM con un prompt del sistema dinámico."""
    logger.info("DynamicAgent: Ejecutando nodo call_model...")
    return BaseAgentNode.call_model(
        state=state,
        llm_service=llm_service,
        system_prompt=system_prompt,
        terminal_ui=terminal_ui,
        interrupt_queue=interrupt_queue
    )

def create_dynamic_agent(
    llm_service: LLMService, 
    system_prompt: str, 
    terminal_ui: Optional[Any] = None, 
    interrupt_queue: Optional[queue.Queue] = None
):
    """Construye y compila un grafo LangGraph genérico para un agente dinámico bajo demanda."""
    workflow = StateGraph(AgentState)

    workflow.add_node("call_model", functools.partial(
        call_dynamic_model_node, 
        llm_service=llm_service, 
        system_prompt=system_prompt, 
        terminal_ui=terminal_ui, 
        interrupt_queue=interrupt_queue
    ))
    workflow.add_node("execute_tool", functools.partial(
        ToolExecutor.execute_tool_node, 
        llm_service=llm_service, 
        terminal_ui=terminal_ui, 
        interrupt_queue=interrupt_queue
    ))

    workflow.set_entry_point("call_model")

    workflow.add_conditional_edges(
        "call_model",
        should_continue,
        {
            "execute_tool": "execute_tool",
            END: END
        }
    )

    workflow.add_edge("execute_tool", "call_model")

    return workflow.compile()
