from __future__ import annotations
import asyncio
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Literal
if TYPE_CHECKING:
    from ..llm_service import LLMService
import functools
import queue
import json
import logging
import os
import re
from dataclasses import dataclass, field

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

from kogniterm.core.agent_state import AgentState
from kogniterm.ui.themes import ColorPalette, Icons
from kogniterm.ui.terminal_ui import TerminalUI

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

# --- Estado Extendido para Deep Research ---
@dataclass
class DeepResearchState(AgentState):
    research_plan: List[str] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 5
    current_task: str = ""
    autonomous_approvals: bool = True  # DeepResearch opera en modo autónomo por defecto


# --- Prompts ---
def get_deep_research_system_prompt(llm_service: LLMService) -> str:
    prompt = """Eres el **KogniDeepResearcher**, un motor de investigación de élite diseñado para realizar análisis técnicos profundos y exhaustivos, como miembro de un equipo multi-agente.

**IMPORTANTE — CONTEXTO DE OPERACIÓN:**
No interactúas directamente con el usuario final. Tu receptor es el **Bash Agent (KogniTerm)**, quien coordina la ejecución global. Tu misión es entregar un **Informe de Investigación Magistral** al Bash Agent para que este tome decisiones informadas.

Tu objetivo es resolver consultas complejas mediante un proceso iterativo de:
1. **Planificación**: Desglosar la consulta en sub-preguntas lógicas.
2. **Exploración**: Utilizar búsquedas web, análisis de código y GitHub para encontrar respuestas.
"""
    if not llm_service.is_thinking_model():
        prompt += "3. **Razonamiento Crítico**: Evaluar la información obtenida. Si encuentras contradicciones o lagunas, DEBES investigar más profundo.\n"
    
    prompt += """4. **Síntesis**: Crear un informe técnico magistral con citas, fragmentos de código y arquitectura.

## 🚀 OPTIMIZACIÓN Y VELOCIDAD (PARALELISMO)
Para ser eficiente y rápido, **DEBES ejecutar múltiples herramientas simultáneamente** cuando las acciones sean independientes. 
*Ejemplo:* Puedes realizar 3 búsquedas web o leer 3 archivos en un mismo turno emitiendo múltiples llamadas a herramientas. El sistema procesará todas en paralelo.

## 📌 PROTOCOLO OBLIGATORIO: task_tracker
Este protocolo es CRÍTICO para que el sistema visualice tu progreso en el panel lateral.
Usa `task_tracker` para gestionar tu progreso con el `agent_name='Researcher'`. 
1. **INIT**: Al inicio, registra tu plan de investigación con `action='init'`.
2. **UPDATE**: Marca cada sub-tarea como `in-progress` al iniciarla y como `done` al completarla.
3. **GET**: Antes de tu entrega final, verifica que todas tus tareas estén marcadas como `done`.

**ENTREGA DE RESULTADOS AL BASH AGENT:**
Tu respuesta final es el Informe de Investigación Magistral. Debe ser:
- **Técnico y Preciso**: Basado exclusivamente en evidencia encontrada.
- **Estructurado**: Usa Markdown, tablas y diagramas Mermaid si es necesario.
- **Accionable**: Proporciona conclusiones claras que el Bash Agent pueda usar.
- **Detallado con párrafos explicativos**: Cada sección debe desarrollarse con párrafos descriptivos completos. **NO te limites a listas de viñetas o encabezados vacíos.** Después de cada título o punto clave, escribe al menos 2–3 párrafos que expliquen el "por qué", el "cómo" y las implicaciones técnicas. El informe debe ser comprensible para alguien que no estuvo presente en la investigación.
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
    
    # Notificación inmediata en TUI
    if terminal_ui and hasattr(terminal_ui, "update_live"):
        from rich.panel import Panel
        from kogniterm.terminal.themes import Icons
        from rich.padding import Padding
        terminal_ui.update_live(Padding(Panel(f"{Icons.RESEARCH} [bold]Planificando estrategia de investigación...[/bold]", border_style="magenta", padding=(0, 4), expand=True), (0, 0)))
        terminal_ui.stop_live()

    last_message = state.messages[-1].content
    
    # Procesar referencias a archivos
    workspace_directory = os.getcwd()  # Asumir que el workspace es el cwd
    processed_message = process_file_references(last_message, workspace_directory)
    
    # Actualizar el mensaje en el estado con el contenido procesado
    state.messages[-1] = HumanMessage(content=processed_message)
    
    prompt = f"""Basado en la siguiente consulta: '{processed_message}'
    Genera un plan de investigación detallado. Divide el problema en al menos 3 sub-tareas claras y concisas.
    Responde ÚNICAMENTE con un objeto JSON con el formato:
    {{
        "plan": ["sub-tarea 1", "sub-tarea 2", ...],
        "rationale": "Breve explicación de por qué este enfoque."
    }}
    """
    
    messages = [
        SystemMessage(content=get_deep_research_system_prompt(llm_service)),
        HumanMessage(content=prompt)
    ]
    
    content = ""
    try:
        for part in llm_service.invoke(history=messages):
            if hasattr(part, "content") and part.content:
                content += part.content
            elif isinstance(part, str) and not part.startswith("__THINKING__:") and not part.startswith("THINKING:"):
                content += part
                
        # Limpieza robusta de JSON
        data = {}
        try:
            # Buscar el primer '{' para ignorar preámbulos (como "Aquí tienes el plan:")
            start_idx = content.find('{')
            if start_idx != -1:
                import json
                # Usar raw_decode para extraer solo el primer objeto JSON válido
                # Esto nos hace inmunes a texto posterior o "Extra data" que confunde a json.loads
                decoder = json.JSONDecoder()
                data, _ = decoder.raw_decode(content[start_idx:])
            else:
                # Fallback si no se encuentra ningún '{'
                data = json.loads(content)
            
            if not isinstance(data, dict):
                data = {"plan": [str(data)], "rationale": "Formato no estándar detectado."}
            plan = data.get("plan") or data.get("objectives") or []
        except Exception as e:
            logger.warning(f"Fallo al parsear JSON de planificación: {e}. Contenido: {content[:100]}...")
            # Fallback: intentar extraer líneas si no es JSON o falló el parseo
            import re
            plan = [line.strip("- ") for line in content.split("\n") if line.strip().startswith("-")]
            if not plan:
                plan = ["Investigación general del requerimiento"]
            data = {"plan": plan, "rationale": "Plan de emergencia (error de formato JSON)"}

        state.research_plan = plan
        state.current_task = plan[0] if plan else ""
        
        # Guardar en mensajes para el historial
        state.messages.append(AIMessage(content=f"Plan de investigación: {plan}\nRationale: {data.get('rationale', '')}"))
        
        # Inicializar task_tracker
        tracker = llm_service.get_tool("task_tracker")
        if tracker:
            tracker.invoke(action="init", agent_name="Researcher", plan=state.research_plan)
            
    except Exception as e:
        logger.error("Error en planning_node: %s", e)
        state.research_plan = ["Análisis general"]
        state.current_task = "Análisis general"
    
    return {"research_plan": state.research_plan, "current_task": state.current_task, "messages": state.messages}

    return {"findings": state.findings}

def research_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None, interrupt_queue: Optional[queue.Queue] = None):
    """Nodo de investigación: registra hallazgos y mantiene la UI informada."""
    
    # Registrar hallazgos de todas las herramientas ejecutadas recientemente (soporte para paralelismo)
    recent_tool_messages = []
    for msg in reversed(state.messages):
        if isinstance(msg, ToolMessage):
            recent_tool_messages.append(msg)
        elif isinstance(msg, AIMessage):
            break
            
    for msg in reversed(recent_tool_messages):
        state.findings.append({
            "task": state.current_task,
            "content": msg.content
        })
    
    return {"findings": state.findings}

def reflection_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    """Nodo de pensamiento crítico que evalúa la calidad de los hallazgos."""
    if terminal_ui and hasattr(terminal_ui, "update_live"):
        from rich.padding import Padding
        terminal_ui.update_live(Padding(Panel(f"{Icons.THINKING} [bold]Reflexionando sobre los hallazgos y buscando inconsistencias...[/bold]", border_style="cyan", padding=(0, 4), expand=True), (0, 0)))
        terminal_ui.stop_live()

    findings_text = "\n".join([f"- {f['task']}: {f['content'][:200]}..." for f in state.findings])
    
    prompt = f"""Revisa los hallazgos actuales:
    {findings_text}
    
    ¿Hay contradicciones? ¿Falta información crítica para la consulta original: '{state.messages[0].content}'?
    Si todo está claro, responde 'READY'. Si falta algo, indica qué tarea o área técnica necesita más profundidad.
    Responde brevemente.
    """
    
    response = llm_service.invoke(history=[SystemMessage(content="Eres un Crítico de Investigación."), HumanMessage(content=prompt)])
    content = ""
    for part in response:
        if isinstance(part, str) and not part.startswith("THINKING"): content += part
    
    state.messages.append(ToolMessage(content=f"REFLEXIÓN TÉCNICA: {content}", tool_call_id="reflection_node"))
    return {"messages": state.messages}

def synthesis_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    """Compila todos los hallazgos en el reporte final."""
    current_console = terminal_ui.console if terminal_ui else console
    
    # Notificación inmediata en TUI
    if terminal_ui and hasattr(terminal_ui, "update_live"):
        from rich.panel import Panel
        from kogniterm.terminal.themes import Icons
        from rich.padding import Padding
        terminal_ui.update_live(Padding(Panel(f"{Icons.RESEARCH} [bold]Sintetizando informe final de investigación...[/bold]", border_style="green", padding=(0, 4), expand=True), (0, 0)))
        terminal_ui.stop_live()

    all_findings_summary = ""
    for idx, finding in enumerate(state.findings):
        all_findings_summary += f"### Hallazgo {idx+1}: {finding.get('task')}\n{finding.get('content')}\n\n"
        
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
    
    # Recolectar la respuesta y filtrar razonamiento
    full_content = ""
    
    for part in response:
        if isinstance(part, AIMessage):
            final_ai_message = part
        elif isinstance(part, str):
            # Filtrar explícitamente contenido de pensamiento
            if not part.startswith("__THINKING__:") and not part.startswith("THINKING:"):
                full_content += part
                if terminal_ui and hasattr(terminal_ui, "update_live"):
                    from rich.panel import Panel
                    from rich.padding import Padding
                    terminal_ui.update_live(Padding(Panel(Markdown(f"## 🔬 Informe de Síntesis\n\n{full_content}"), border_style="green", title="DeepResearcher", padding=(0, 4), expand=True), (0, 0)))

    if not (terminal_ui and hasattr(terminal_ui, "update_live")):        
        current_console.print(Padding(Markdown(f"## 🔬 Informe de Investigación\n\n{full_content}"), (1, 4)))
            
    state.messages.append(AIMessage(content=f"## 🔬 Informe de Deep Research\n\n{full_content}"))
    return {"messages": state.messages, "findings": state.findings}

# --- Implementación principal conceptualmente basada en agentes previos pero con lógica mejorada ---

def call_deep_model_node(state: DeepResearchState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None, interrupt_queue: Optional[queue.Queue] = None):
    """Llama al LLM de Deep Research con soporte completo para TUI/CLI y contexto persistente."""
    current_console = terminal_ui.console if terminal_ui else console
    is_tui = getattr(terminal_ui, "is_tui", False)

    # Limpiar razonamiento de mensajes anteriores para evitar saturación
    cleaned_messages = []
    for msg in state.messages:
        if isinstance(msg, AIMessage) and "reasoning_content" in msg.additional_kwargs:
            msg.additional_kwargs.pop("reasoning_content")
        cleaned_messages.append(msg)

    context_info = f"\n\nESTADO DE LA INVESTIGACIÓN:\n- Plan de investigación: {state.research_plan}\n- Tarea actual: {state.current_task}\n- Hallazgos acumulados: {len(state.findings)}"
    if state.findings:
        context_info += f"\n- Último hallazgo: {state.findings[-1]['task']}"
        
    system_prompt = get_deep_research_system_prompt(llm_service) + context_info
    
    # Inyectar instrucción de avance de tarea de manera natural en el sistema, no en cada paso
    messages = [SystemMessage(content=system_prompt)] + cleaned_messages
    
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

    def update_display(final: bool = False, initial: bool = False):
        """Construye y envía el renderable al panel o al Live"""
        renderables = []
        
        if initial:
            from kogniterm.terminal.visual_components import create_animated_spinner
            if is_tui:
                renderables.append(create_animated_spinner("DeepResearcher Investigando...", "dots"))
            else:
                renderables.append(create_animated_spinner("DeepResearcher Investigando...", "dots"))
        else:
            if full_thinking_content:
                if is_tui:
                    thinking_content = Markdown(full_thinking_content)
                    thought_panel = Panel(
                        thinking_content,
                        title=f"{Icons.THINKING} DeepResearcher Pensando...",
                        border_style=ColorPalette.GRAY_700,
                        style=f"dim {ColorPalette.GRAY_500} on {ColorPalette.GRAY_900}",
                        padding=(0, 4),
                        expand=True
                    )
                    renderables.append(thought_panel)
                else:
                    renderables.append(Panel(
                        Markdown(full_thinking_content),
                        title=f"{Icons.THINKING} [bold {ColorPalette.PRIMARY_LIGHT}]DeepResearcher Razonando...[/]",
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
        import contextlib
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
                        text_streamed = True
                        update_display()
                
                if (interrupt_queue and not interrupt_queue.empty()) or llm_service.stop_generation_flag:
                    break
            
            # Actualización final para asegurar visibilidad total
            update_display(final=True)

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
    
    workflow = StateGraph(DeepResearchState) # Usar DeepResearchState

    workflow.add_node("planning", functools.partial(planning_node, llm_service=llm_service, terminal_ui=terminal_ui))
    workflow.add_node("research", functools.partial(research_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))
    workflow.add_node("reflection", functools.partial(reflection_node, llm_service=llm_service, terminal_ui=terminal_ui))
    workflow.add_node("synthesis", functools.partial(synthesis_node, llm_service=llm_service, terminal_ui=terminal_ui))
    
    workflow.add_node("call_model", functools.partial(call_deep_model_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))
    workflow.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue, autonomous_approvals=True))

    # Definir flujo
    workflow.set_entry_point("planning")
    workflow.add_edge("planning", "call_model")
    workflow.add_edge("execute_tool", "research") # Después de herramientas, registrar hallazgos
    workflow.add_edge("research", "call_model")

    def deep_research_router(state: DeepResearchState):
        from .code_agent import should_continue
        
        # 1. Si el modelo decidió ejecutar una herramienta
        if should_continue(state) == "execute_tool":
            return "execute_tool"
            
        # 2. Consultar tracker: si está todo hecho -> reflexión
        tracker = llm_service.get_tool("task_tracker")
        if tracker:
            status = tracker.invoke(action="get", agent_name="Researcher")
            if "PENDING" not in status and "IN-PROGRESS" not in status and "Estado del Plan" in status:
                return "reflection"
        
        # 3. Si no, seguir investigando
        return "call_model"

    workflow.add_conditional_edges("call_model", deep_research_router, {
        "execute_tool": "execute_tool",
        "reflection": "reflection",
        "call_model": "call_model"
    })
    
    workflow.add_edge("reflection", "synthesis")
    workflow.add_edge("synthesis", END)

    return workflow.compile()
