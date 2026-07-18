from __future__ import annotations
import asyncio
from langgraph.graph import StateGraph, END
from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from ..llm_service import LLMService
import functools
import queue
import logging

logger = logging.getLogger(__name__)

from langchain_core.messages import AIMessage, ToolMessage, SystemMessage
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from kogniterm.ui.terminal_ui import TerminalUI
from kogniterm.core.agent_state import AgentState
from .base_agent import BaseAgentNode
from .tool_executor import ToolExecutor

console = Console()

# --- Mensaje de Sistema del Agente de Código ---
def get_system_message(llm_service: LLMService) -> SystemMessage:
    content = \"\"\"INSTRUCCIÓN CRÍTICA: Eres el Agente de Código de KogniTerm (CodeAgent).
Tu rol es ser un Desarrollador Senior y Arquitecto de Software experto en Python, JavaScript/TypeScript y diseño de sistemas.

⚠️⚠️⚠️ PROTOCOLO DE CUMPLIMIENTO OBLIGATORIO: task_tracker ⚠️⚠️⚠️
Cualquier solicitud o tarea asignada (sin importar su complejidad) DEBE ser registrada y actualizada en la herramienta `task_tracker`.
1. **Inicialización Inmediata**: En tu PRIMER TURNO, antes de realizar cualquier otra acción o ejecutar cualquier herramienta (como leer archivos o buscar), DEBES llamar a `task_tracker` con `action="init"`, especificando `agent_name="Coder"` y la lista de tareas detallada en `plan`.
2. **Actualizaciones en Tiempo Real**: Cada vez que inicies, completes o cambie el estado de una tarea, DEBES llamar inmediatamente a `task_tracker` con `action="update"`, especificando el `task_index` y el nuevo `status` ("in-progress", "completed", "failed").
3. **Registro Final**: Al concluir el trabajo, asegúrate de marcar la última tarea como completada llamando a `task_tracker`.

Tus capacidades incluyen:
- Lectura y escritura de archivos con precisión quirúrgica.
- Búsqueda semántica y análisis de codebase.
- Refactorización y optimización de código.
- Implementación de tests y validación estática.

REGLA DE ORO: Lee siempre el archivo antes de editarlo. No asumas el contenido de una línea basándote en la memoria si el archivo es grande. Usa `advanced_file_editor` para cambios precisos.
\"\"\"
    return BaseAgentNode.get_system_message(llm_service, content)

# --- Nodos del Grafo ---

def call_model_node(state: AgentState, llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    """Nodo que llama al modelo utilizando la lógica base."""
    return BaseAgentNode.call_model(
        state=state,
        llm_service=llm_service,
        system_prompt=get_system_message(llm_service).content,
        terminal_ui=terminal_ui,
        interrupt_queue=interrupt_queue
    )

def execute_tool_node(state: AgentState, llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    """Nodo que ejecuta herramientas utilizando el ToolExecutor consolidado."""
    return ToolExecutor.execute_tool_node(
        state=state,
        llm_service=llm_service,
        terminal_ui=terminal_ui,
        interrupt_queue=interrupt_queue
    )

def should_continue(state: AgentState) -> str:
    """Decide si el agente debe continuar utilizando la lógica de ToolExecutor."""
    # El CodeAgent tiene validaciones adicionales de confirmación de archivos
    if state.file_update_diff_pending_confirmation is not None:
        return END
    
    return ToolExecutor.should_continue(state)

# --- Construcción del Grafo ---

def create_code_agent(
    llm_service: LLMService,
    terminal_ui: TerminalUI,
    interrupt_queue: Optional[queue.Queue] = None,
):
    workflow = StateGraph(AgentState)

    workflow.add_node(
        "call_model",
        functools.partial(
            call_model_node,
            llm_service=llm_service,
            terminal_ui=terminal_ui,
            interrupt_queue=interrupt_queue,
        ),
    )
    workflow.add_node(
        "execute_tool",
        functools.partial(
            execute_tool_node,
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
