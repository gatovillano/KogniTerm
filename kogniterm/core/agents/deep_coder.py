from __future__ import annotations
import asyncio
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Literal
if TYPE_CHECKING:
    from ..llm_service import LLMService
import functools
import queue
import json
from dataclasses import dataclass, field

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, END
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.padding import Padding
from rich.text import Text
from rich.syntax import Syntax

from kogniterm.core.agent_state import AgentState
from kogniterm.terminal.themes import ColorPalette, Icons

console = Console()

# --- Mensaje de Sistema del Deep Coder ---
def get_deep_coder_system_prompt(llm_service: LLMService) -> str:
    prompt = """Eres el **KogniDeepCoder**, un motor de desarrollo de software de élite. 
Tu misión es diseñar, implementar y validar soluciones técnicas de alta calidad.

Operas bajo un ciclo de vida de desarrollo de software (SDLC) comprimido y recursivo:

1. **Arquitectura (Planificación)**:
   - Analiza el requerimiento.
   - Identifica TODOS los archivos afectados.
   - Lee el contenido actual para entender el contexto ("Trust but Verify").
   - Define un plan de implementación detallado.

2. **Implementación**:
   - Escribe código limpio, eficiente y documentado.
   - Sigue las convenciones del proyecto (PEP8, ESLint, etc.).
   - Usa `advanced_file_editor` para aplicar cambios con precisión.

3. **QA y Validación (Recursivo)**:
   - Revisa el código en busca de bugs, errores de sintaxis o lógica.
   - Ejecuta tests si es posible usando `python_executor` o `execute_command`.
   - SI ALGO FALLA -> Vuelve al paso de Implementación inmediatamente con el error detallado. No entregues código roto.

**REGLAS DE ORO:**
- **NUNCA** asumas el contenido de un archivo. Si no lo has leído en este turno, léelo.
- **Micro-commits mentales**: Divide tareas grandes en pasos pequeños y verificables.
- **Seguridad**: Maneja excepciones y valida entradas.
"""
    if not llm_service.is_thinking_model():
        prompt += "- **Explicación Técnica**: Justifica tus decisiones de diseño en tu pensamiento.\n"
    
    prompt += "\nTu respuesta debe ser profesional, técnica y orientada a la solución perfecta.\n"
    return prompt

DEEP_CODER_SYSTEM_PROMPT = get_deep_coder_system_prompt(LLMService(use_multi_provider=False)) if 'LLMService' in globals() else ""

# --- Nodo de Razonamiento para el Deep Coder ---

def call_deep_coder_node(state: AgentState, llm_service: LLMService, interrupt_queue: Optional[queue.Queue] = None):
    """Llamada al LLM con el nuevo prompt de Deep Coder."""
    messages = [SystemMessage(content=get_deep_coder_system_prompt(llm_service))] + state.messages
    
    full_response_content = ""
    full_thinking_content = ""
    final_ai_message = None
    
    # Visualización estilo Deep Thinking
    with Live(refresh_per_second=10) as live:
        for part in llm_service.invoke(history=messages, interrupt_queue=interrupt_queue):
            if isinstance(part, AIMessage):
                final_ai_message = part
            elif isinstance(part, str):
                if part.startswith("__THINKING__:") or part.startswith("THINKING:"):
                    prefix = "__THINKING__:" if part.startswith("__THINKING__:") else "THINKING:"
                    full_thinking_content += part[len(prefix):]
                    live.update(Padding(Panel(
                        Markdown(full_thinking_content), 
                        title=f"{Icons.THINKING} [bold {ColorPalette.PRIMARY_LIGHT}]DeepCoder Razonando...[/]", 
                        border_style=ColorPalette.PRIMARY_LIGHT,
                        dim=True
                    ), (0, 4)))
                else:
                    full_response_content += part
                    # Mostrar pensamiento finalizado arriba y respuesta abajo
                    renderables = []
                    if full_thinking_content:
                        renderables.append(Panel(
                            Markdown(full_thinking_content),
                            title=f"{Icons.SUCCESS} [bold grey]Arquitectura y Planificación Completada[/]",
                            border_style="grey50",
                            dim=True
                        ))
                    renderables.append(Markdown(full_response_content))
                    live.update(Padding(Group(*renderables), (0, 4)))

    if final_ai_message:
        if not final_ai_message.content and full_response_content:
            final_ai_message.content = full_response_content
        state.messages.append(final_ai_message)
        state.save_history(llm_service)
            
    return {"messages": state.messages}

# --- Construcción del Grafo ---

def create_deep_coder(llm_service: LLMService, terminal_ui: Any = None, interrupt_queue: Optional[queue.Queue] = None):
    from .code_agent import execute_tool_node, should_continue
    
    workflow = StateGraph(AgentState)

    # Nodos principales
    workflow.add_node("call_model", functools.partial(call_deep_coder_node, llm_service=llm_service, interrupt_queue=interrupt_queue))
    workflow.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service, interrupt_queue=interrupt_queue))

    # Definir flujo
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
