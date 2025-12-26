from __future__ import annotations
from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING
if TYPE_CHECKING:
    from ..llm_service import LLMService
import functools
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from kogniterm.terminal.terminal_ui import TerminalUI
from kogniterm.core.agent_state import AgentState

console = Console()

# --- Mensaje de Sistema del Agente Investigador ---
SYSTEM_MESSAGE = SystemMessage(content="""INSTRUCCIÓN CRÍTICA: Eres el Agente Investigador de KogniTerm (ResearcherAgent).
Tu rol es ser un Detective de Código y Arquitecto de Sistemas. Tu objetivo NO es editar código, sino ENTENDERLO y EXPLICARLO.

**Tus Objetivos:**
1.  **Comprensión Profunda**: No te quedes en la superficie. Si ves una función, busca dónde se define, quién la llama y qué datos manipula.
2.  **Mapeo de Arquitectura**: Identifica los componentes principales, sus responsabilidades y cómo interactúan entre sí.
3.  **Diagnóstico de Problemas**: Si hay un error, rastrea su origen a través de las capas del sistema.
4.  **Búsqueda Exhaustiva**: Utiliza tanto búsqueda semántica (vectorial) como textual para no perder nada.

**Tu Flujo de Trabajo:** Este flujo es una referencia, pero debes buscar según la necesidad de consulta.
1.  **Exploración Inicial**:
    *   Usa `file_operation_tool` para obtener un mapa mental de la estructura del proyecto.
    *   Identifica archivos clave (entry points, configuración, core logic).
2.  **Investigación Dirigida**:
    *   Usa `codebase_search_tool` (Búsqueda Vectorial) para conceptos abstractos ("¿Cómo se maneja la autenticación?", "Lógica de reintentos").
    *   Usa `file_search_tool` (Grep) para encontrar usos exactos de variables, funciones o constantes.
    *   Usa `file_read_tool` para leer el contenido detallado de los archivos sospechosos o relevantes.
3.  **Síntesis**:
    *   Conecta los puntos. Explica la relación entre A y B.
    *   Genera informes claros en Markdown que respondan a la pregunta del usuario con evidencia del código.
    *   Si hay inconsistencias, repórtalas.
    *   Tu informe debe ser un documento de investigación, estructurad, y muy detallado. Explicativo de la arquitectura, el flujo de datos, y las relaciones entre componentes.
    *   Menciona dependencias entre archivos.
**Herramientas a tu disposición:**
*   `codebase_search_tool`: TU HERRAMIENTA ESTRELLA. Úsala para búsquedas semánticas y conceptuales.
*   `file_search_tool`: Para búsquedas exactas (grep).
*   `file_read_tool`: Para leer código.
*   `file_operations`: Para listar directorios específicos.
*   `code_analysis_tool`: Para analizar la complejidad del código.
*   `github_tool`: Para investigar repositorios de GitHub, obtener información del repo, listar contenidos, leer archivos y directorios.
**Instrucciones de Respuesta:**
*   Tus respuestas deben ser informes de investigación detallados y extensos.
*   Cita los archivos y líneas de código relevantes.
*   Si encuentras inconsistencias o "code smells", repórtalos.
*   Usa diagramas (Mermaid) si ayudan a explicar flujos complejos.
*   Siempre justifica tus conclusiones con evidencia del código.
*   Estructura tus respuestas en secciones claras con encabezados en Markdown.
*   Si no tienes suficiente información, explica qué más necesitas investigar.
*   Prioriza la precisión y profundidad sobre la brevedad.
*   Formatea todo en Markdown para facilitar la lectura.

Recuerda: Eres los ojos y el cerebro analítico de KogniTerm.
""")

# --- Funciones Auxiliares (Similares a CodeAgent/BashAgent) ---

def call_model_node(state: AgentState, llm_service: LLMService, interrupt_queue: Optional[queue.Queue] = None):
    """Llama al LLM (ResearcherAgent)."""
    messages = [SYSTEM_MESSAGE] + state.messages
    
    full_response_content = ""
    final_ai_message = None
    
    try:
        from kogniterm.terminal.visual_components import create_processing_spinner
        spinner = create_processing_spinner()
    except ImportError:
        from rich.spinner import Spinner
        spinner = Spinner("dots", text="ResearcherAgent investigando...")

    with Live(spinner, console=console, screen=False, refresh_per_second=10) as live:
        for part in llm_service.invoke(history=messages, interrupt_queue=interrupt_queue):
            if isinstance(part, AIMessage):
                final_ai_message = part
            elif isinstance(part, str):
                full_response_content += part
                live.update(Padding(Markdown(full_response_content), (0, 4)))

    if final_ai_message:
        if not final_ai_message.content and full_response_content:
             final_ai_message.content = full_response_content
        state.messages.append(final_ai_message)
        llm_service._save_history(state.messages)
            
    return {"messages": state.messages}

def execute_single_tool(tc, llm_service, interrupt_queue):
    """Ejecuta una herramienta individual con verbosidad."""
    tool_name = tc['name']
    tool_args = tc['args']
    tool_id = tc['id']
    
    # Mostrar qué se está ejecutando
    args_json = json.dumps(tool_args, indent=2, ensure_ascii=False)
    console.print(Panel(
        Syntax(args_json, "json", theme="monokai", line_numbers=False),
        title=f"[bold cyan]🛠️ Ejecutando: {tool_name}[/bold cyan]",
        border_style="cyan",
        padding=(0, 2)
    ))
    
    tool = llm_service.get_tool(tool_name)
    if not tool:
        return tool_id, f"Error: Herramienta '{tool_name}' no encontrada.", None

    try:
        # _invoke_tool_with_interrupt es un generador, debemos iterar para obtener el resultado final
        output_str = ""
        for part in llm_service._invoke_tool_with_interrupt(tool, tool_args):
            if part is not None:
                output_str += str(part)
        
        # Mostrar un resumen de la salida si es muy larga
        display_output = output_str if len(output_str) < 500 else output_str[:500] + "\n... (truncado para brevedad)"
        console.print(Panel(
            display_output,
            title=f"[bold green]✅ Resultado de {tool_name}[/bold green]",
            border_style="green",
            padding=(0, 2)
        ))
        
        return tool_id, output_str, None
    except Exception as e:
        console.print(f"[bold red]❌ Error en {tool_name}: {e}[/bold red]")
        return tool_id, f"Error en {tool_name}: {e}", e

def execute_tool_node(state: AgentState, llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    """Nodo de ejecución de herramientas."""
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return state

    tool_messages = []
    executor = ThreadPoolExecutor(max_workers=5)
    futures = []
    
    # Mostrar encabezado de fase de análisis
    console.print(Padding(Text("🕵️‍♂️ Fase de Investigación: Ejecutando herramientas...", style="bold magenta underline"), (1, 0)))

    for tool_call in last_message.tool_calls:
        if interrupt_queue and not interrupt_queue.empty():
            interrupt_queue.get()
            state.reset_temporary_state()
            return state
        futures.append(executor.submit(execute_single_tool, tool_call, llm_service, interrupt_queue))

    for future in as_completed(futures):
        tool_id, content, exception = future.result()
        tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))

    state.messages.extend(tool_messages)
    llm_service._save_history(state.messages)
    return state

def should_continue(state: AgentState) -> str:
    """Decide si el agente debe continuar."""
    last_message = state.messages[-1]
    
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "execute_tool"
    elif isinstance(last_message, ToolMessage):
        return "call_model"
    
    return END

# --- Construcción del Grafo ---

def create_researcher_agent(llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    workflow = StateGraph(AgentState)

    workflow.add_node("call_model", functools.partial(call_model_node, llm_service=llm_service, interrupt_queue=interrupt_queue))
    workflow.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))

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
