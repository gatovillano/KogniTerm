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

from kogniterm.core.agent_state import AgentState
from kogniterm.terminal.themes import ColorPalette, Icons

console = Console()

# --- Estado Extendido para Deep Research ---
class DeepResearchState(AgentState):
    research_plan: List[str] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 5
    current_focus: str = ""

# --- Prompts ---
def get_deep_research_system_prompt(llm_service: LLMService) -> str:
    prompt = """Eres el **KogniDeepResearcher**, un motor de investigación de élite diseñado para realizar análisis técnicos profundos y exhaustivos.

Tu objetivo es resolver consultas complejas mediante un proceso iterativo de:
1. **Planificación**: Desglosar la consulta en sub-preguntas lógicas.
2. **Exploración**: Utilizar búsquedas web, análisis de código y GitHub para encontrar respuestas.
"""
    if not llm_service.is_thinking_model():
        prompt += "3. **Razonamiento Crítico**: Evaluar la información obtenida. Si encuentras contradicciones o lagunas, DEBES investigar más profundo.\n"
    
    prompt += """4. **Síntesis**: Crear un informe técnico magistral con citas, fragmentos de código y arquitectura.

**REGLAS DE ORO:**
- **No te conformes**: Si una búsqueda no da resultados claros, cambia los términos de búsqueda o busca en archivos relacionados.
- **Deep Dive**: Si ves una referencia a un componente que no conoces, ¡investígalo! No asumas.
- **Evidencia**: Cada afirmación en tu reporte final debe estar respaldada por código local, documentación oficial o resultados de búsqueda.
- **Estructura**: Usa Mermaid para diagramas, tablas para comparativas y bloques de código para ejemplos.
- **Evolución**: Como motor de investigación avanzado, puedes automatizar tus propios flujos. Si necesitas realizar análisis especializados repetitivos, usa `skill_factory` para crear herramientas de investigación a medida y úsalas de forma nativa.
"""
    
    if not llm_service.is_thinking_model():
        prompt += """
**Tu proceso mental:**
- "¿Qué necesito saber exactamente para responder esto?"
- "¿Dónde es más probable que esté esta información?"
- "¿Lo que he encontrado confirma o desmiente mi hipótesis inicial?"
- "¿Qué nuevas preguntas surgen de este descubrimiento?"
"""
    return prompt

DEEP_RESEARCH_SYSTEM_PROMPT = get_deep_research_system_prompt(LLMService(use_multi_provider=False)) if 'LLMService' in globals() else ""

# --- Nodos del Grafo ---

def planning_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    """Genera un plan de investigación inicial."""
    current_console = terminal_ui.console if terminal_ui else console

    last_message = state.messages[-1].content
    
    prompt = f"""Basado en la siguiente consulta: '{last_message}'
    Genera un plan de investigación detallado. Divide el problema en al menos 3 sub-tareas o áreas de enfoque.
    Responde ÚNICAMENTE con un objeto JSON con el formato:
    {{
        "plan": ["sub-tarea 1", "sub-tarea 2", ...],
        "rationale": "Breve explicación de por qué este enfoque."
    }}
    """
    
    response = llm_service.invoke_structured_output(
        prompt=prompt,
        system_prompt=get_deep_research_system_prompt(llm_service),
        response_model=None # Usaremos JSON directo por ahora o un esquema
    )
    
    try:
        # Intentar limpiar la respuesta si viene con markdown
        content = response.content if hasattr(response, 'content') else str(response)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        data = json.loads(content)
        state.research_plan = data.get("plan", [])
        state.current_focus = state.research_plan[0] if state.research_plan else ""
    except Exception as e:
        console.print(f"[red]Error en planning: {e}[/red]")
        state.research_plan = [last_message]
        state.current_focus = last_message

    try:
        from kogniterm.terminal.themes import ColorPalette, Icons
        
        # Visualización minimalista del plan
        plan_text = Text()
        plan_text.append(f"\n{Icons.RESEARCH} ", style=ColorPalette.SECONDARY)
        plan_text.append("Plan de investigación: ", style="bold")
        plan_text.append(f"{len(state.research_plan)} objetivos\n", style="dim")
        
        for i, tarea in enumerate(state.research_plan):
            plan_text.append(f"  {i+1}. ", style="dim")
            plan_text.append(f"{tarea}\n", style="italic")
            
        current_console.print(Padding(plan_text, (0, 4)))
    except ImportError:
        current_console.print(f"\n[dim]• Plan: {', '.join(state.research_plan)}[/dim]")
    
    return state

def research_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None, interrupt_queue: Optional[queue.Queue] = None):
    """Ejecuta herramientas para el foco actual."""
    current_console = terminal_ui.console if terminal_ui else console

    state.iteration_count += 1
    focus = state.current_focus or "General"
    
    # Notificación minimalista de iteración
    try:
        from kogniterm.terminal.themes import ColorPalette
        status_text = Text()
        status_text.append("🔍 ", style=ColorPalette.SECONDARY)
        status_text.append("Foco: ", style="dim")
        status_text.append(focus, style="italic")
        status_text.append(f" ({state.iteration_count}/{state.max_iterations})", style="dim")
        current_console.print(Padding(status_text, (1, 4)))
    except ImportError:
        current_console.print(f"\n[dim]🔍 {focus} ({state.iteration_count}/{state.max_iterations})[/dim]")
    
    # Aquí llamamos al modelo para que use herramientas
    messages = [SystemMessage(content=get_deep_research_system_prompt(llm_service))] + state.messages
    messages.append(HumanMessage(content=f"Enfócate ahora en investigar: {focus}. Utiliza herramientas si es necesario."))
    
    return state

def synthesis_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    """Compila todos los hallazgos en el reporte final."""
    current_console = terminal_ui.console if terminal_ui else console

    all_findings_summary = ""
    for idx, finding in enumerate(state.findings):
        all_findings_summary += f"### Hallazgo {idx+1}: {finding.get('focus')}\n{finding.get('content')}\n\n"
        
    prompt = f"""Como experto Sintetizador Técnico, utiliza toda la información recopilada para crear el informe final.
    
    HISTORIAL DE INVESTIGACIÓN:
    {all_findings_summary}
    
    CONSULTA ORIGINAL: {state.messages[0].content}
    
    REQUISITOS DEL INFORME:
    1. Estructura clara (Introducción, Arquitectura/Flujo, Detalles Técnicos, Conclusión).
    2. Cita archivos, líneas de código y URLs encontradas.
    3. Usa Mermaid para diagramas de secuencia o flujo.
    4. Proporcina recomendaciones o advertencias 'KogniInsight'.
    """
    
    # Llamada final al modelo
    response = llm_service.invoke(history=[SystemMessage(content=get_deep_research_system_prompt(llm_service)), HumanMessage(content=prompt)])
    
    # Recolectar la respuesta y mostrarla visualmente
    full_content = ""
    
    from rich.status import Status
    with Status("[dim]Sintetizando reporte final...[/dim]", spinner="dots") as status:
        for part in response:
            if isinstance(part, AIMessage):
                final_ai_message = part
            elif isinstance(part, str):
                full_content += part
            
    # Mostrar el resultado final de forma limpia
    current_console.print(Padding(Markdown(f"## 🔬 Informe de Investigación\n\n{full_content}"), (1, 4)))
            
    state.messages.append(AIMessage(content=f"## 🔬 Informe de Deep Research\n\n{full_content}"))
    return state

# --- Implementación principal conceptualmente basada en agentes previos pero con lógica mejorada ---

def call_deep_model_node(state: AgentState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None, interrupt_queue: Optional[queue.Queue] = None):
    """Llama al LLM de Deep Research con soporte completo para TUI/CLI."""
    current_console = terminal_ui.console if terminal_ui else console
    is_tui = getattr(terminal_ui, "is_tui", False)

    # Inyectar el prompt de Deep Research al principio si no está
    messages = [SystemMessage(content=get_deep_research_system_prompt(llm_service))] + state.messages
    
    full_response_content = ""
    full_thinking_content = ""
    final_ai_message = None
    text_streamed = False

    # Importar componentes visuales
    try:
        from kogniterm.terminal.visual_components import create_processing_spinner
        from kogniterm.terminal.themes import ColorPalette, Icons
        spinner = create_processing_spinner()
    except ImportError:
        from rich.spinner import Spinner
        spinner = Spinner("dots", text="[dim]Investigando...[/dim]")
        class Icons: THINKING = "🤔"; RESEARCH = "🔍"
        class ColorPalette: PRIMARY_LIGHT = "cyan"; SECONDARY = "blue"; GRAY_800 = "#333333"; GRAY_600 = "#666666"; GRAY_900 = "#1e1e1e"

    # Iniciar KeyboardHandler para detectar ESC (solo CLI)
    kh = None
    if not is_tui:
        from kogniterm.terminal.keyboard_handler import KeyboardHandler
        kh = KeyboardHandler(interrupt_queue)
        kh.start()

    try:
        import contextlib
        if not is_tui:
            live_context = Live(spinner, console=current_console, screen=False, refresh_per_second=10)
        else:
            @contextlib.contextmanager
            def dummy_live(): 
                yield type('DummyLive', (), {'update': lambda self, x: None})()
            live_context = dummy_live()

        with live_context as live:
            TUI_BG = ColorPalette.GRAY_900 if 'ColorPalette' in globals() else "#1e1e1e"

            def update_display():
                renderables = []
                if full_thinking_content:
                    if is_tui:
                        thinking_content = Markdown(full_thinking_content)
                        thought_panel = Panel(
                            thinking_content,
                            title=f"{Icons.THINKING} KogniResearcher Pensando...",
                            border_style=ColorPalette.GRAY_700,
                            style=f"dim {ColorPalette.GRAY_500} on {TUI_BG}",
                            padding=(0, 2),
                        )

                        renderables.append(thought_panel)
                    else:
                        renderables.append(Panel(
                            Markdown(full_thinking_content),
                            title=f"[bold {ColorPalette.PRIMARY_LIGHT}]{Icons.THINKING} Investigación en curso...[/bold {ColorPalette.PRIMARY_LIGHT}]",
                            border_style=ColorPalette.PRIMARY_LIGHT,
                            padding=(0, 1),
                            dim=True
                        ))
                
                if full_response_content:
                    if full_thinking_content:
                        renderables.append(Text(""))
                    renderables.append(Markdown(full_response_content))
                
                if is_tui:
                    group = Group(*renderables)
                    terminal_ui.update_live(Padding(group, (0, 4)))
                else:
                    final_renderable = Padding(Group(*renderables), (0, 4)) if renderables else spinner
                    live.update(final_renderable)

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
                        text_streamed = True
                        update_display()
                
                if (interrupt_queue and not interrupt_queue.empty()) or llm_service.stop_generation_flag:
                    break

            if is_tui:
                terminal_ui.stop_live()
    finally:
        if kh: kh.stop()

    if final_ai_message:
        # Asegurar que el contenido procesado se guarde en el mensaje
        if not final_ai_message.content and full_response_content:
            final_ai_message.content = full_response_content
        state.messages.append(final_ai_message)
        state.save_history(llm_service)
            
    return {"messages": state.messages}

def create_deep_researcher(llm_service: LLMService, terminal_ui: Any = None, interrupt_queue: Optional[queue.Queue] = None):
    from .code_agent import execute_tool_node, should_continue
    
    workflow = StateGraph(AgentState)

    workflow.add_node("planning", functools.partial(planning_node, llm_service=llm_service, terminal_ui=terminal_ui))
    workflow.add_node("research", functools.partial(research_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))
    workflow.add_node("synthesis", functools.partial(synthesis_node, llm_service=llm_service, terminal_ui=terminal_ui))
    
    workflow.add_node("call_model", functools.partial(call_deep_model_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))
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
