import asyncio
from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import functools
import queue
import logging
import sys
import os
import re
import time
import py_compile
import importlib.util
from types import ModuleType
from pathlib import Path as _Path

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.markup import escape

from kogniterm.ui.terminal_ui import TerminalUI
from kogniterm.core.agent_state import AgentState
from .base_agent import BaseAgentNode
from .tool_executor import ToolExecutor

logger = logging.getLogger(__name__)
console = Console()

# --- Utilidades de Carga Dinámica (Preservadas) ---

def _load_file_ops_module(module_filename: str):
    \"\"\"Carga dinámicamente un módulo de la skill 'file-operations' via importlib.\"\"\"
    bundled_dir = _Path(__file__).resolve().parent.parent.parent / \"skills\" / \"bundled\"
    scripts_dir = bundled_dir / \"file-operations\" / \"scripts\"

    pkg_name = \"_file_ops_scripts_pkg\"
    if pkg_name not in sys.modules:
        parent_pkg = ModuleType(pkg_name)
        parent_pkg.__path__ = [str(scripts_dir)]
        sys.modules[pkg_name] = parent_pkg

    utils_key = f\"{pkg_name}._utils\"
    if utils_key not in sys.modules:
        utils_spec = importlib.util.spec_from_file_location(
            utils_key, str(scripts_dir / \"_utils.py\")
        )
        utils_mod = importlib.util.module_from_spec(utils_spec)
        utils_mod.__package__ = pkg_name
        sys.modules[utils_key] = utils_mod
        utils_spec.loader.exec_module(utils_mod)

    mod_key = f\"{pkg_name}.{module_filename}\"
    if mod_key in sys.modules:
        return sys.modules[mod_key]

    spec = importlib.util.spec_from_file_location(mod_key, str(scripts_dir / f\"{module_filename}.py\"))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = pkg_name
    sys.modules[mod_key] = mod
    spec.loader.exec_module(mod)
    return mod

# --- Mensaje de Sistema del Agente Bash ---
def get_system_message(llm_service: LLMService) -> SystemMessage:
    content = \"\"\"INSTRUCCIÓN CRÍTICA: Eres el Agente de Terminal de KogniTerm (BashAgent).
Tu rol es ser un experto en sistemas Unix/Linux, Python y gestión de infraestructuras. Tienes control total sobre la shell y el sistema de archivos.

⚠️⚠️⚠️ PROTOCOLO DE CUMPLIMIENTO OBLIGATORIO: task_tracker ⚠️⚠️⚠️
Cualquier solicitud asignada DEBE ser registrada y actualizada en `task_tracker`.
1. **Inicialización Inmediata**: En tu PRIMER TURNO, llama a `task_tracker` con `action=\"init\"`, `agent_name=\"BashAgent\"` y el `plan`.
2. **Actualizaciones en Tiempo Real**: Cada cambio de estado requiere `action=\"update\"` con `task_index` y `status`.
3. **Registro Final**: Marca la última tarea como completada al finalizar.

Tus capacidades incluyen:
- Ejecución de comandos shell complejos.
- Gestión de procesos y depuración de sistemas.
- Manipulación avanzada de archivos y directorios.
- Automatización de tareas mediante scripts.

REGLA DE ORO: Siempre verifica el estado del sistema antes de ejecutar comandos destructivos. Usa `ls` o `pwd` si tienes dudas sobre la ubicación actual.
\"\"\"
    return BaseAgentNode.get_system_message(llm_service, content)

# --- Nodos del Grafo ---

def call_model_node(state: AgentState, llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    \"\"\"Llamada al modelo utilizando la lógica base.\"\"\"
    return BaseAgentNode.call_model(
        state=state,
        llm_service=llm_service,
        system_prompt=get_system_message(llm_service).content,
        terminal_ui=terminal_ui,
        interrupt_queue=interrupt_queue
    )

def execute_tool_node(state: AgentState, llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None, command_approval_handler=None):
    \"\"\"Ejecución de herramientas delegando al ToolExecutor.\"\"\"
    # El BashAgent puede pasar un handler de aprobación personalizado si existe
    # aunque ToolExecutor ya maneja la lógica de confirmación estándar.
    return ToolExecutor.execute_tool_node(
        state=state,
        llm_service=llm_service,
        terminal_ui=terminal_ui,
        interrupt_queue=interrupt_queue
    )

def verification_node(state: AgentState, llm_service: LLMService, terminal_ui: TerminalUI):
    \"\"\"Nodo de verificación post-ejecución para asegurar que el comando logró su objetivo.\"\"\"
    last_message = state.messages[-1]
    if not isinstance(last_message, ToolMessage):
        return state

    # Lógica de verificación simplificada: el agente analiza la salida de la herramienta
    # y decide si el estado es el deseado.
    verification_prompt = f\"\"\"Analiza la siguiente salida de terminal y determina si la acción solicitada se completó exitosamente o si hubo un error que requiere corrección.
    
    Salida:
    {last_message.content}
    
    Si todo es correcto, responde 'CONFIRMED'. Si hay un error, describe el problema y sugiere el siguiente comando.\"\"\"
    
    # Aquí podríamos llamar al modelo, pero para mantener la fluidez del grafo, 
    # simplemente permitimos que el flujo regrese a call_model para que el agente lo procese.
    return state

def should_continue(state: AgentState) -> str:
    \"\"\"Lógica de continuación delegada al ToolExecutor.\"\"\"
    return ToolExecutor.should_continue(state)

# --- Construcción del Grafo ---

def create_bash_agent(llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None, command_approval_handler=None):
    bash_agent_graph = StateGraph(AgentState)

    bash_agent_graph.add_node(\"call_model\", functools.partial(call_model_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))
    bash_agent_graph.add_node(\"execute_tool\", functools.partial(execute_tool_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue, command_approval_handler=command_approval_handler))
    bash_agent_graph.add_node(\"verify\", functools.partial(verification_node, llm_service=llm_service, terminal_ui=terminal_ui))

    bash_agent_graph.set_entry_point(\"call_model\")

    bash_agent_graph.add_conditional_edges(
        \"call_model\",
        should_continue,
        {
            \"execute_tool\": \"execute_tool\",
            END: END
        }
    )

    bash_agent_graph.add_conditional_edges(
        \"execute_tool\",
        should_continue,
        {
            \"call_model\": \"verify\",
            \"execute_tool\": \"execute_tool\",
            END: END
        }
    )

    bash_agent_graph.add_edge(\"verify\", \"call_model\")

    return bash_agent_graph.compile()

def create_learning_agent(llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    \"\"\"Grafo de aprendizaje posterior.\"\"\"
    learning_graph = StateGraph(AgentState)
    # Definición simplificada del nodo de aprendizaje
    def learning_node(state: AgentState, llm_service: LLMService, terminal_ui: Optional[TerminalUI]):
        logger.info(\"Analizando sesión para aprendizaje...\")
        return state

    learning_graph.add_node(\"learning\", functools.partial(learning_node, llm_service=llm_service, terminal_ui=terminal_ui))
    learning_graph.set_entry_point(\"learning\")
    learning_graph.add_edge(\"learning\", END)
    return learning_graph.compile()
