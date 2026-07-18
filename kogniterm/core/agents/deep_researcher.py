from __future__ import annotations
import asyncio
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Literal
import functools
import queue
import json
import logging
import os
import re
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ..llm_service import LLMService

logger = logging.getLogger(__name__)

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
from langgraph.graph import StateGraph, END
from rich.console import Console, Group
from rich.rule import Rule
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.padding import Padding
from rich.text import Text

from kogniterm.core.agent_state import AgentState
from kogniterm.ui.themes import ColorPalette, Icons
from kogniterm.ui.terminal_ui import TerminalUI
from .base_agent import BaseAgentNode
from .tool_executor import ToolExecutor

console = Console()

def process_file_references(content: str, workspace_directory: str) -> str:
    \"\"\"Procesa referencias a archivos con @ y las reemplaza con su contenido.\"\"\"
    def replace_file_ref(match):
        file_path = match.group(1)
        full_path = os.path.join(workspace_directory, file_path)
        try:
            with open(full_path, \"r\", encoding=\"utf-8\") as f:
                file_content = f.read()
            return f\"```{file_path}\\n{file_content}\\n```\"
        except Exception as e:
            logger.warning(f\"No se pudo leer el archivo {full_path}: {e}\")
            return f\"@ {file_path} (Error al leer archivo: {e})\"

    return re.sub(r\"@([^\\s]+)\", replace_file_ref, content)

# --- Estado Extendido para Deep Research ---
@dataclass
class DeepResearchState(AgentState):
    research_plan: List[str] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    completed: bool = False
    iteration_count: int = 0
    max_iterations: int = 10

# --- Mensaje de Sistema ---
def get_system_message(llm_service: LLMService) -> SystemMessage:
    content = \"\"\"Eres el Agente de Investigación Profunda (DeepResearcher) de KogniTerm.
Tu objetivo es realizar investigaciones exhaustivas, analizar múltiples fuentes de información y sintetizar conclusiones precisas.

METODOLOGÍA:
1. Planificación: Divide la consulta en sub-preguntas y pasos de investigación.
2. Ejecución: Utiliza las herramientas de búsqueda y lectura de archivos para recolectar evidencia.
3. Reflexión: Analiza si la información recolectada es suficiente o si hay lagunas.
4. Síntesis: Crea un reporte final estructurado y detallado.

⚠️⚠️⚠️ PROTOCOLO task_tracker ⚠️⚠️⚠️
Cualquier investigación debe ser registrada en `task_tracker` (init $\rightarrow$ update $\rightarrow$ done).

Sé meticuloso, cita tus fuentes y no asumas información que no haya sido verificada mediante herramientas.
\"\"\"
    return BaseAgentNode.get_system_message(llm_service, content)

# --- Nodos del Grafo ---

def planning_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: TerminalUI):
    \"\"\"Genera un plan de investigación inicial.\"\"\"
    # Lógica de planificación específica de DeepResearch
    # (Se mantiene la lógica de negocio, pero se usa BaseAgentNode para la llamada si es necesario)
    # Por simplicidad en este refactor, delegamos la generación del plan a una llamada de modelo
    
    prompt = f\"Crea un plan de investigación detallado para la siguiente consulta: {state.messages[-1].content}. Devuelve el plan como una lista de pasos numerados.\"
    response = BaseAgentNode.call_model(
        state=state,
        llm_service=llm_service,
        system_prompt=get_system_message(llm_service).content,
        terminal_ui=terminal_ui
    )
    
    # Extraer pasos del plan (simplificado)
    plan = response.content.split('\\n')
    return {**response, \"research_plan\": plan, \"iteration_count\": 0}

def research_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    \"\"\"Procesa los hallazgos de la investigación.\"\"\"
    last_msg = state.messages[-1]
    if isinstance(last_msg, ToolMessage):
        # Guardar hallazgo
        finding = {\"step\": state.research_plan[min(state.iteration_count, len(state.research_plan)-1)], \"content\": last_msg.content}
        return {\"findings\": state.findings + [finding], \"iteration_count\": state.iteration_count + 1}
    return state

def reflection_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: TerminalUI):
    \"\"\"Reflexiona sobre la calidad de la investigación.\"\"\"
    # Lógica de reflexión...
    return {\"completed\": True}

def synthesis_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: TerminalUI):
    \"\"\"Sintetiza todos los hallazgos en un reporte final.\"\"\"
    # Lógica de síntesis final...
    return state

def call_deep_model_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    \"\"\"Llamada al modelo delegada a BaseAgentNode.\"\"\"
    return BaseAgentNode.call_model(
        state=state,
        llm_service=llm_service,
        system_prompt=get_system_message(llm_service).content,
        terminal_ui=terminal_ui,
        interrupt_queue=interrupt_queue
    )

def execute_tool_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    \"\"\"Ejecución de herramientas delegada a ToolExecutor.\"\"\"
    return ToolExecutor.execute_tool_node(
        state=state,
        llm_service=llm_service,
        terminal_ui=terminal_ui,
        interrupt_queue=interrupt_queue
    )

# --- Construcción del Grafo ---

def create_deep_researcher(
    llm_service: LLMService,
    terminal_ui: Any = None,
    interrupt_queue: Optional[queue.Queue] = None,
):
    workflow = StateGraph(DeepResearchState)

    workflow.add_node(\"planning\", functools.partial(planning_node, llm_service=llm_service, terminal_ui=terminal_ui))
    workflow.add_node(\"research\", functools.partial(research_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))
    workflow.add_node(\"reflection\", functools.partial(reflection_node, llm_service=llm_service, terminal_ui=terminal_ui))
    workflow.add_node(\"synthesis\", functools.partial(synthesis_node, llm_service=llm_service, terminal_ui=terminal_ui))
    workflow.add_node(\"call_model\", functools.partial(call_deep_model_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))
    workflow.add_node(\"execute_tool\", functools.partial(execute_tool_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))

    workflow.set_entry_point(\"planning\")
    workflow.add_edge(\"planning\", \"call_model\")
    workflow.add_edge(\"execute_tool\", \"research\")
    workflow.add_edge(\"research\", \"call_model\")

    def deep_research_router(state: DeepResearchState):
        if state.completed:
            return \"synthesis\"
        if ToolExecutor.should_continue(state) == \"execute_tool\":
            return \"execute_tool\"
        if state.findings and len(state.findings) >= len(state.research_plan):
            return \"reflection\"
        return \"call_model\"

    workflow.add_conditional_edges(
        \"call_model\",
        deep_research_router,
        {
            \"execute_tool\": \"execute_tool\",
            \"reflection\": \"reflection\",
            \"call_model\": \"call_model\",
        },
    )

    workflow.add_edge(\"reflection\", \"synthesis\")
    workflow.add_edge(\"synthesis\", END)

    return workflow.compile()
