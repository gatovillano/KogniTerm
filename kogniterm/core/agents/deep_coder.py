from __future__ import annotations
import asyncio
import contextlib
import functools
import json
import logging
import os
import queue
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..llm_service import LLMService

logger = logging.getLogger(__name__)

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, END
from rich.console import Console, Group
from rich.rule import Rule
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.padding import Padding
from rich.text import Text
from rich.syntax import Syntax

from kogniterm.ui.terminal_ui import TerminalUI
from kogniterm.core.agent_state import AgentState
from kogniterm.ui.themes import ColorPalette, Icons

console = Console()

def process_file_references(content: str, workspace_directory: str) -> str:
    """Procesa referencias a archivos con @ y las reemplaza con su contenido."""
    def replace_file_ref(match):
        file_path = match.group(1)
        full_path = os.path.join(workspace_directory, file_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            return f"```{file_path}\n{file_content}\n```"
        except Exception as e:
            logger.warning(f"No se pudo leer el archivo {full_path}: {e}")
            return f"@ {file_path} (Error al leer archivo: {e})"
    
    # Reemplazar @ruta con el contenido del archivo
    return re.sub(r'@([^\s]+)', replace_file_ref, content)

# --- Mensaje de Sistema del Deep Coder ---
def get_deep_coder_system_prompt(llm_service: LLMService) -> str:
    prompt = """Eres el **KogniDeepCoder**, un motor de desarrollo de software de élite y miembro clave de un equipo multi-agente.
Tu misión es diseñar, implementar y validar soluciones técnicas de alta calidad.

**IMPORTANTE — CONTEXTO DE OPERACIÓN:**
No interactúas directamente con el usuario final. Tu receptor es el **Bash Agent (KogniTerm)**, quien coordina la ejecución global. Tu respuesta final DEBE ser un informe técnico detallado que el Bash Agent utilizará para finalizar la tarea.

Operas bajo un ciclo de vida de desarrollo de software (SDLC) comprimido y recursivo:

1. **Arquitectura (Planificación)**:
   - Analiza el requerimiento y define un plan de implementación.
   - Identifica archivos afectados y léelos antes de proponer cambios.

2. **Implementación y Validación**:
   - Escribe código limpio y documentado siguiendo las convenciones del proyecto.
   - Usa `advanced_file_editor` para aplicar cambios con precisión.
   - Valida SIEMPRE tus cambios (tests, revisión de sintaxis, ejecución de comandos).

## 🚀 OPTIMIZACIÓN Y VELOCIDAD (PARALELISMO)
Para ser eficiente y rápido, **DEBES ejecutar múltiples herramientas simultáneamente** cuando las acciones sean independientes. 
*Ejemplo:* Puedes leer 3 archivos en un solo turno emitiendo 3 llamadas a `file_read`. El sistema procesará todas en paralelo, ahorrando tiempo crítico.

## 📌 PROTOCOLO OBLIGATORIO: task_tracker
Este protocolo es CRÍTICO para que el sistema visualice tu progreso en el panel lateral.
Usa `task_tracker` para gestionar tu progreso con el `agent_name='Coder'`. 
1. **INIT**: Al inicio, registra tu plan de implementación con `action='init'`.
2. **UPDATE**: Marca cada paso como `in-progress` al comenzar y `done` al finalizar la validación.
3. **GET**: Antes de tu entrega final, verifica que el estado de tu plan sea consistente.

**ENTREGA DE RESULTADOS AL BASH AGENT:**
Tu respuesta final es el producto que entregas al Coordinador. Asegúrate de que incluya:
- Resumen de cambios realizados y archivos modificados.
- Resultados de las validaciones y pruebas ejecutadas.
- Cualquier instrucción adicional necesaria para el Bash Agent.
"""
    if not llm_service.is_thinking_model():
        prompt += "- **Explicación Técnica**: Justifica tus decisiones de diseño en tu pensamiento.\n"
    
    prompt += "\nResponde de forma profesional, técnica y directa al Bash Agent.\n"
    prompt += "\nTIP: Si necesitas modificar varios archivos, envíalos todos en un solo turno. El sistema los procesará en paralelo.\n"
    return prompt


# --- Nodo de Contexto Proactivo ---

def context_injection_node(state: AgentState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    """Inyecta contexto técnico relevante (estructura de archivos y RAG) solo en el primer
    mensaje del usuario. En turnos posteriores el contexto ya está en el historial y no
    se vuelve a calcular, evitando latencia innecesaria en cada ronda.
    """
    # 1. Contar mensajes del usuario. Si hay más de uno, ya no es el "primer mensaje"
    user_messages = [msg for msg in state.messages if isinstance(msg, HumanMessage)]
    
    # 2. Si ya existe el bloque de contexto o un resumen de compresión, no hacer nada.
    already_injected = any(
        isinstance(msg, SystemMessage) and 
        (
            "## 📁 CONTEXTO DEL PROYECTO" in str(msg.content) or 
            "📊 Resumen de conversación previa" in str(msg.content) or
            "Resumen de la conversación anterior" in str(msg.content) # Soporte para HistoryManager
        )
        for msg in state.messages
    )

    if len(user_messages) > 1 or already_injected:
        return {"messages": state.messages}

    if terminal_ui and hasattr(terminal_ui, "update_live"):
        from rich.padding import Padding
        from rich.panel import Panel
        terminal_ui.update_live(Padding(Panel(f"{Icons.RESEARCH} [bold]Sincronizando contexto técnico del proyecto...[/bold]", border_style="blue", padding=(0, 4), expand=True), (0, 0)))
        terminal_ui.stop_live()

    # 1. Asegurar que el contexto del workspace esté inicializado (Estructura de carpetas)
    if not llm_service.workspace_context_initialized:
        try:
            llm_service.initialize_workspace_context()
        except Exception as e:
            logger.warning(f"No se pudo inicializar el contexto del workspace: {e}")
    
    # 2. Búsqueda RAG para archivos relevantes
    task = ""
    for msg in state.messages:
        if isinstance(msg, HumanMessage):
            task = msg.content
            break
            
    rag_context = ""
    if task and hasattr(llm_service, 'vector_db_manager') and llm_service.vector_db_manager and hasattr(llm_service, 'embeddings_service') and llm_service.embeddings_service:
        try:
            # Obtener embedding de la tarea
            query_embedding = llm_service.embeddings_service.embed_query(task)
            # Buscar en la base de vectores
            results = llm_service.vector_db_manager.search(query_embedding, k=5)
            if results:
                rag_context = "\n\n**🔍 Hallazgos de Código Relevantes (RAG):**\n"
                for res in results:
                    meta = res.get('metadata', {})
                    path = meta.get('file_path', 'unknown')
                    rag_context += f"- `{path}` (líneas {meta.get('start_line', '?')}-{meta.get('end_line', '?')}):\n"
                    rag_context += f"  ```\n  {res.get('content', '')[:150]}...\n  ```\n"
        except Exception as e:
            logger.warning(f"Error en búsqueda RAG para contexto: {e}")

    # 3. Construir mensaje de contexto completo
    workspace_msg = llm_service._build_llm_context_message()
    full_context = ""
    if workspace_msg:
        full_context += workspace_msg.content
    if rag_context:
        full_context += rag_context

    if full_context:
        context_system_msg = SystemMessage(content=f"## 📁 CONTEXTO DEL PROYECTO\n{full_context}")
        # Insertar al principio para que sea la base del razonamiento
        state.messages.insert(0, context_system_msg)

    return {"messages": state.messages}


# --- Nodo de Verificación Técnica ---

def verification_node(state: AgentState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    """Nodo automático que valida cambios (sintaxis, linters) sin intervención del LLM."""
    
    # 1. Identificar archivos realmente MODIFICADOS buscando en las llamadas a herramientas del último AIMessage
    # El flujo es: call_model (AIMessage) -> execute_tool (ToolMessages) -> verify
    last_ai_msg = None
    for msg in reversed(state.messages):
        if isinstance(msg, AIMessage):
            last_ai_msg = msg
            break
            
    if not last_ai_msg or not last_ai_msg.tool_calls:
        return {"messages": state.messages}
        
    editing_tools = {
        "advanced_file_editor", 
        "write_to_file", 
        "replace_file_content", 
        "multi_replace_file_content",
        "file_update_tool",
        "file_create_tool"
    }
    
    modified_files = set()
    for tc in last_ai_msg.tool_calls:
        if tc['name'] in editing_tools:
            args = tc['args']
            # Intentar obtener la ruta de los argumentos comunes
            path = args.get('path') or args.get('TargetFile') or args.get('file_path') or args.get('target_file')
            if path:
                modified_files.add(path)

    if not modified_files:
        return {"messages": state.messages}

    # 2. Notificar en TUI solo si hay archivos para verificar
    if terminal_ui and hasattr(terminal_ui, "update_live"):
        from rich.padding import Padding
        terminal_ui.update_live(Padding(Panel(f"{Icons.CODE} [bold]Verificando integridad técnica de los cambios...[/bold]", border_style="yellow", padding=(0, 4), expand=True), (0, 0)))
        terminal_ui.stop_live()

    verification_results = []
    
    # Herramienta de ejecución para validaciones rápidas
    cmd_tool = llm_service.get_tool("execute_command")
    if not cmd_tool:
        return {"messages": state.messages}
    
    for file_path in modified_files:
        if file_path.endswith(".py"):
            # Verificación de sintaxis rápida para Python
            try:
                res = cmd_tool.invoke(command=f"python3 -m py_compile {file_path}")
                if "error" in res.lower() or "fail" in res.lower():
                    verification_results.append(f"❌ Error de sintaxis en {file_path}: {res}")
                else:
                    verification_results.append(f"✅ {file_path} pasó verificación de sintaxis.")
            except Exception as e:
                verification_results.append(f"⚠️ No se pudo verificar {file_path}: {e}")
    
    if verification_results:
        summary = "\n".join(verification_results)
        state.messages.append(ToolMessage(content=f"RESULTADOS DE VERIFICACIÓN AUTOMÁTICA:\n{summary}", tool_call_id="verification_node"))
        
    return {"messages": state.messages}


# --- Nodo de Razonamiento para el Deep Coder ---

def call_deep_coder_node(state: AgentState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None, interrupt_queue: Optional[queue.Queue] = None):
    """Llamada al LLM con el nuevo prompt de Deep Coder y soporte para TUI/CLI."""
    current_console = terminal_ui.console if terminal_ui else console
    is_tui = getattr(terminal_ui, "is_tui", False)

    # Notificación inmediata en TUI (antes de llamar al LLM)
    if is_tui and terminal_ui and hasattr(terminal_ui, "update_live"):
        terminal_ui.update_live(
            Panel(
                f"{Icons.CODE} [bold]DeepCoder: Analizando requerimiento y preparando solución...[/bold]",
                border_style="cyan",
                title="DeepCoder"
            )
        )

    messages = [SystemMessage(content=get_deep_coder_system_prompt(llm_service))] + state.messages
    
    # Procesar referencias a archivos en el último mensaje del usuario
    if state.messages and isinstance(state.messages[-1], HumanMessage):
        workspace_directory = os.getcwd()  # Asumir que el workspace es el cwd
        processed_content = process_file_references(state.messages[-1].content, workspace_directory)
        # Actualizar el mensaje en el estado con el contenido procesado
        state.messages[-1] = HumanMessage(content=processed_content)
        # Actualizar messages también
        messages = [SystemMessage(content=get_deep_coder_system_prompt(llm_service))] + state.messages
    
    full_response_content = ""
    full_thinking_content = ""
    final_ai_message = None
    TUI_BG = ColorPalette.GRAY_900

    # Iniciar KeyboardHandler para detectar ESC (solo CLI)
    kh = None
    if not is_tui and interrupt_queue:
        try:
            from kogniterm.terminal.keyboard_handler import KeyboardHandler
            kh = KeyboardHandler(interrupt_queue)
            kh.start()
        except Exception:
            pass

    def update_display(final: bool = False, initial: bool = False):
        """Construye y envía el renderable al panel o al Live"""
        renderables = []
        
        if initial:
            from kogniterm.terminal.visual_components import create_animated_spinner
            if is_tui:
                renderables.append(create_animated_spinner("CodeAgent Trabajando...", "dots"))
            else:
                renderables.append(create_animated_spinner("CodeAgent Trabajando...", "dots"))
        else:
            if full_thinking_content:
                if is_tui:
                    thinking_content = Markdown(full_thinking_content)
                    thought_panel = Panel(
                        thinking_content,
                        title=f"{Icons.THINKING} CodeAgent Pensando...",
                        border_style=ColorPalette.GRAY_700,
                        style=f"dim {ColorPalette.GRAY_500} on {TUI_BG}",
                        padding=(0, 4),
                        expand=True
                    )
                    renderables.append(thought_panel)
                else:
                    renderables.append(Panel(
                        Markdown(full_thinking_content),
                        title=f"[bold {ColorPalette.PRIMARY_LIGHT}]{Icons.THINKING} CodeAgent Pensando...[/]",
                        border_style=ColorPalette.PRIMARY_LIGHT,
                        padding=(0, 4),
                        expand=True
                    ))
            
            if full_response_content:
                renderables.append(Markdown(full_response_content))

        if renderables:
            if is_tui and terminal_ui and hasattr(terminal_ui, "update_live"):
                terminal_ui.update_live(Padding(Group(*renderables), (0, 0)))
            elif not is_tui and _live_ref[0] is not None:
                _live_ref[0].update(Padding(Group(*renderables), (0, 0)))

    # Usamos una lista mutable para acceder al live desde el closure
    _live_ref = [None]

    try:
        if not is_tui:
            live_ctx = Live(console=current_console, screen=False, refresh_per_second=10)
        else:
            @contextlib.contextmanager
            def _dummy_live():
                yield None
            live_ctx = _dummy_live()

        with live_ctx as live:
            _live_ref[0] = live

            update_display(initial=True)

            for part in llm_service.invoke(history=messages, interrupt_queue=interrupt_queue):
                if isinstance(part, AIMessage):
                    final_ai_message = part
                elif isinstance(part, str):
                    if part.startswith("__THINKING__:") or part.startswith("THINKING:"):
                        prefix = "__THINKING__:" if part.startswith("__THINKING__:") else "THINKING:"
                        full_thinking_content += part[len(prefix):]
                        update_display()
                    else:
                        full_response_content += part
                        update_display()

                if (interrupt_queue and not interrupt_queue.empty()) or llm_service.stop_generation_flag:
                    break

            # Llamada final para asegurar que todo se muestre (especialmente con throttling)
            update_display()

            if is_tui and terminal_ui and hasattr(terminal_ui, "stop_live"):
                terminal_ui.stop_live()
    finally:
        if kh:
            kh.stop()

    if final_ai_message:
        if not final_ai_message.content and full_response_content:
            final_ai_message.content = full_response_content
        state.messages.append(final_ai_message)
        try:
            state.save_history(llm_service)
        except Exception:
            pass

    return {"messages": state.messages}


# --- Construcción del Grafo ---

def create_deep_coder(llm_service: LLMService, terminal_ui: Any = None, interrupt_queue: Optional[queue.Queue] = None):
    from .code_agent import execute_tool_node, should_continue

    workflow = StateGraph(AgentState)

    workflow.add_node("inject_context", functools.partial(context_injection_node, llm_service=llm_service, terminal_ui=terminal_ui))
    workflow.add_node("call_model", functools.partial(call_deep_coder_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))
    workflow.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))
    workflow.add_node("verify", functools.partial(verification_node, llm_service=llm_service, terminal_ui=terminal_ui))

    workflow.set_entry_point("inject_context")
    workflow.add_edge("inject_context", "call_model")

    def coder_router(state: AgentState):
        route = should_continue(state)
        if route == "execute_tool":
            return "execute_tool"
        return END

    workflow.add_conditional_edges(
        "call_model",
        coder_router,
        {
            "execute_tool": "execute_tool",
            END: END
        }
    )

    # El flujo de ejecución ahora pasa por verificación antes de volver al modelo
    workflow.add_edge("execute_tool", "verify")
    workflow.add_edge("verify", "call_model")

    return workflow.compile()
