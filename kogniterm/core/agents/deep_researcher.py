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
from concurrent.futures import ThreadPoolExecutor, as_completed

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
from kogniterm.core.exceptions import UserConfirmationRequired
from kogniterm.ui.themes import ColorPalette, Icons
from kogniterm.ui.terminal_ui import TerminalUI

console = Console()


def process_file_references(content: str, workspace_directory: str) -> str:
    """Procesa referencias a archivos con @ y las reemplaza con su contenido."""

    def replace_file_ref(match):
        file_path = match.group(1)
        full_path = os.path.join(workspace_directory, file_path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            return f"```{file_path}\n{file_content}\n```"
        except Exception as e:
            logger.warning(f"No se pudo leer el archivo {full_path}: {e}")
            return f"@ {file_path} (Error al leer archivo: {e})"

    # Reemplazar @ruta con el contenido del archivo
    return re.sub(r"@([^\s]+)", replace_file_ref, content)


# --- Estado Extendido para Deep Research ---
@dataclass
class DeepResearchState(AgentState):
    research_plan: List[str] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 8  # Aumentado para permitir investigación profunda iterativa
    current_task: str = ""
    autonomous_approvals: bool = True  # DeepResearch opera en modo autónomo por defecto
    # Nuevos campos para investigación profunda
    research_gaps: List[str] = field(default_factory=list)  # Lagunas identificadas en reflexión
    source_urls: List[str] = field(default_factory=list)  # URLs de fuentes rastreadas
    reflection_count: int = 0  # Cuántas veces se ha hecho reflexión
    synthesis_sections: Dict[str, str] = field(default_factory=dict)  # Síntesis incremental por tarea


# --- Prompts ---
def get_deep_research_system_prompt(llm_service: LLMService) -> str:
    prompt = """Eres el **KogniDeepResearcher**, un motor de investigación de élite diseñado para realizar análisis técnicos PROFUNDOS y EXHAUSTIVOS, como miembro de un equipo multi-agente.

⚠️⚠️⚠️ PROTOCOLO DE CUMPLIMIENTO OBLIGATORIO: task_tracker ⚠️⚠️⚠️
Cualquier tarea asignada DEBE ser registrada y actualizada en la herramienta `task_tracker`.
1. **Inicialización Inmediata**: En tu PRIMER TURNO, antes de realizar cualquier otra acción o ejecutar cualquier herramienta (como realizar búsquedas, leer archivos, etc.), DEBES llamar a `task_tracker` con `action="init"`, especificando `agent_name="Researcher"` y la lista de tareas en `plan`.
2. **Actualizaciones en Tiempo Real**: Cada vez que inicies, completes o cambie el estado de una tarea, DEBES llamar inmediatamente a `task_tracker` con `action="update"`, especificando el `task_index` y el nuevo `status` ("in-progress", "completed", "failed").
3. **Registro Final**: Al concluir el trabajo, asegúrate de marcar la última tarea como completada llamando a `task_tracker`.
¡NUNCA OMITAS ESTE PASO! No inicializar el task tracker inmediatamente en el primer turno se considera un fallo de ejecución crítico y una violación del protocolo.

**IMPORTANTE — CONTEXTO DE OPERACIÓN:**
No interactúas directamente con el usuario final. Tu receptor es el **Bash Agent (KogniTerm)**, quien coordina la ejecución global. Tu misión es entregar un **Informe de Investigación Magistral** al Bash Agent para que este tome decisiones informadas.

## 🔬 METODOLOGÍA DE INVESTIGACIÓN PROFUNDA
Tu objetivo es resolver consultas complejas mediante un proceso iterativo y PROFUNDO de:
1. **Planificación**: Desglosar la consulta en sub-preguntas lógicas y específicas.
2. **Exploración de Fuentes Primarias**: Utilizar `tavily_search` con `search_depth="advanced"` para temas complejos, `web_fetch` para leer contenido completo de URLs relevantes, y `github` para analizar código fuente y repositorios.
3. **Verificación Cruzada**: NUNCA te quedes con una sola fuente. Busca al menos 3 fuentes independientes por sub-pregunta. Si encuentras contradicciones, INVESTIGA MÁS para resolverlas.
4. **Rastreo de Fuentes**: Cada hallazgo DEBE incluir la URL de origen. Usa `web_fetch` para obtener detalles técnicos específicos de documentación oficial.
5. **Análisis Crítico**: Evalúa la calidad y relevancia de cada fuente. Prioriza documentación oficial, papers, repositorios con muchas estrellas, y contenido técnico detallado sobre blogs superficiales.
6. **Síntesis Profunda**: Crear un informe técnico magistral con citas, fragmentos de código y arquitectura, conectando los puntos entre diferentes fuentes.

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
- **Técnico y Preciso**: Basado exclusivamente en evidencia encontrada y citada.
- **Estructurado**: Usa Markdown, tablas y diagramas Mermaid si es necesario.
- **Accionable**: Proporciona conclusiones claras que el Bash Agent pueda usar.
- **Detallado con párrafos explicativos**: Cada sección debe desarrollarse con párrafos descriptivos completos. **NO te limites a listas de viñetas o encabezados vacíos.** Después de cada título o punto clave, escribe al menos 2–3 párrafos que expliquen el "por qué", el "cómo" y las implicaciones técnicas. El informe debe ser comprensible para alguien que no estuvo presente en la investigación.
- **Con Fuentes**: Cada afirmación técnica debe tener su URL de referencia en formato [fuente](url).
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


DEEP_RESEARCH_SYSTEM_PROMPT = (
    get_deep_research_system_prompt(LLMService(use_multi_provider=False))
    if "LLMService" in globals()
    else ""
)

# --- Nodos del Grafo ---


def planning_node(
    state: DeepResearchState,
    llm_service: LLMService,
    terminal_ui: Optional[TerminalUI] = None,
):
    """Genera un plan de investigación inicial."""
    current_console = terminal_ui.console if terminal_ui else console

    # Notificación inmediata en TUI
    if terminal_ui and hasattr(terminal_ui, "update_live"):
        is_tui = hasattr(terminal_ui, "app") and terminal_ui.app is not None
        if is_tui:
            terminal_ui.update_live(
                ("__SPINNER__", "Planificando estrategia de investigación...")
            )
        else:
            from rich.panel import Panel
            from kogniterm.terminal.themes import Icons
            from rich.padding import Padding

            terminal_ui.update_live(
                Padding(
                    Panel(
                        f"{Icons.RESEARCH} [bold]Planificando estrategia de investigación...[/bold]",
                        border_style="magenta",
                        padding=(0, 4),
                        expand=True,
                    ),
                    (0, 0),
                )
            )

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
        HumanMessage(content=prompt),
    ]

    content = ""
    try:
        for part in llm_service.invoke(history=messages):
            if hasattr(part, "content") and part.content:
                content += part.content
            elif (
                isinstance(part, str)
                and not part.startswith("__THINKING__:")
                and not part.startswith("THINKING:")
            ):
                content += part

        # Limpieza robusta de JSON
        data = {}
        try:
            # Buscar el primer '{' para ignorar preámbulos (como "Aquí tienes el plan:")
            start_idx = content.find("{")
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
                data = {
                    "plan": [str(data)],
                    "rationale": "Formato no estándar detectado.",
                }
            plan = data.get("plan") or data.get("objectives") or []
        except Exception as e:
            logger.warning(
                f"Fallo al parsear JSON de planificación: {e}. Contenido: {content[:100]}..."
            )
            # Fallback: intentar extraer líneas si no es JSON o falló el parseo
            import re

            plan = [
                line.strip("- ")
                for line in content.split("\n")
                if line.strip().startswith("-")
            ]
            if not plan:
                plan = ["Investigación general del requerimiento"]
            data = {
                "plan": plan,
                "rationale": "Plan de emergencia (error de formato JSON)",
            }

        state.research_plan = plan
        state.current_task = plan[0] if plan else ""

        # Guardar en mensajes para el historial
        state.messages.append(
            AIMessage(
                content=f"Plan de investigación: {plan}\nRationale: {data.get('rationale', '')}"
            )
        )

        # Inicializar task_tracker
        tracker = llm_service.get_tool("task_tracker")
        if tracker:
            tracker.invoke(
                action="init", agent_name="Researcher", plan=state.research_plan
            )

    except Exception as e:
        logger.error("Error en planning_node: %s", e)
        state.research_plan = ["Análisis general"]
        state.current_task = "Análisis general"

    return {
        "research_plan": state.research_plan,
        "current_task": state.current_task,
        "messages": state.messages,
    }

    return {"findings": state.findings}


def research_node(
    state: DeepResearchState,
    llm_service: LLMService,
    terminal_ui: Optional[TerminalUI] = None,
    interrupt_queue: Optional[queue.Queue] = None,
):
    """Nodo de investigación: registra hallazgos estructurados con fuentes y mantiene la UI informada."""
    import re
    import json

    # Registrar hallazgos de todas las herramientas ejecutadas recientemente (soporte para paralelismo)
    recent_tool_messages = []
    for msg in reversed(state.messages):
        if isinstance(msg, ToolMessage):
            recent_tool_messages.append(msg)
        elif isinstance(msg, AIMessage):
            break

    url_pattern = re.compile(r'https?://[^\s)<>"]+')

    for msg in reversed(recent_tool_messages):
        content = str(msg.content)
        # Extraer URLs del contenido para rastreo de fuentes
        urls = url_pattern.findall(content)
        if urls:
            for u in urls:
                if u not in state.source_urls:
                    state.source_urls.append(u)

        # Intentar extraer metadatos estructurados si el ToolMessage tiene artifact
        sources = urls[:5]  # Máximo 5 fuentes por hallazgo
        confidence = "medium"

        # Si el mensaje tiene artifact con metadata de herramienta
        artifact = getattr(msg, 'artifact', None)
        if artifact and isinstance(artifact, dict):
            if 'source_urls' in artifact:
                sources = artifact['source_urls']
            if 'confidence' in artifact:
                confidence = artifact['confidence']

        finding = {
            "task": state.current_task,
            "content": content,
            "sources": sources,
            "confidence": confidence,
            "tool": msg.name if hasattr(msg, 'name') else "unknown",
        }
        state.findings.append(finding)

    # Actualizar UI con progreso
    if terminal_ui and hasattr(terminal_ui, "update_live"):
        is_tui = hasattr(terminal_ui, "app") and terminal_ui.app is not None
        if is_tui:
            terminal_ui.update_live(
                ("__SPINNER__", f"Investigando: {state.current_task} ({len(state.findings)} hallazgos, {len(state.source_urls)} fuentes)")
            )

    return {"findings": state.findings, "source_urls": state.source_urls}


def reflection_node(
    state: DeepResearchState,
    llm_service: LLMService,
    terminal_ui: Optional[TerminalUI] = None,
):
    """Nodo de pensamiento crítico que evalúa la PROFUNDIDAD y CALIDAD de los hallazgos."""
    state.iteration_count += 1
    state.reflection_count += 1

    if terminal_ui and hasattr(terminal_ui, "update_live"):
        is_tui = hasattr(terminal_ui, "app") and terminal_ui.app is not None
        if is_tui:
            terminal_ui.update_live(
                (
                    "__SPINNER__",
                    "Reflexionando sobre la profundidad y calidad de los hallazgos...",
                )
            )
        else:
            from rich.panel import Panel
            from kogniterm.terminal.themes import Icons
            from rich.padding import Padding

            terminal_ui.update_live(
                Padding(
                    Panel(
                        f"{Icons.THINKING} [bold]Evaluando profundidad de investigación (iter {state.iteration_count}/{state.max_iterations})...[/bold]",
                        border_style="cyan",
                        padding=(0, 4),
                        expand=True,
                    ),
                    (0, 0),
                )
            )

    # Si alcanzamos el límite de iteraciones, forzar síntesis
    if state.iteration_count >= state.max_iterations:
        logger.info(f"⚠️ Límite de iteraciones ({state.max_iterations}) alcanzado. Forzando síntesis.")
        state.messages.append(
            ToolMessage(
                content="REFLEXIÓN: Límite de iteraciones alcanzado. Procediendo a síntesis.",
                tool_call_id="reflection_node",
            )
        )
        return {"messages": state.messages, "reflection_result": "READY", "iteration_count": state.iteration_count}

    # Construir resumen detallado de hallazgos con fuentes
    findings_text = ""
    for i, f in enumerate(state.findings):
        task = f.get('task', 'N/A')
        content = str(f.get('content', ''))[:300]
        sources = f.get('sources', [])
        confidence = f.get('confidence', 'unknown')
        findings_text += f"\n[{i+1}] Tarea: {task}\n   Resumen: {content}...\n   Fuentes: {len(sources)} | Confianza: {confidence}\n"

    plan_text = "\n".join([f"- {p}" for p in state.research_plan])

    # Incluir lagunas previas si existen
    prev_gaps = ""
    if state.research_gaps:
        prev_gaps = "\n\n**Lagunas de la reflexión anterior:**\n" + "\n".join([f"- {g}" for g in state.research_gaps])

    prompt = f"""Eres un **Crítico de Investigación de Élite**. Evalúa si la investigación tiene PROFUNDIDAD y CALIDAD suficientes.

**Plan Original:**
{plan_text}
{prev_gaps}

**Hallazgos ({len(state.findings)} total):**
{findings_text}

Evalúa rigurosamente:
1. ¿Todas las sub-preguntas del plan tienen evidencia sólida?
2. ¿Hay 2-3 fuentes independientes por tema importante?
3. ¿Contradicciones resueltas o señaladas?
4. ¿Faltan detalles técnicos (versiones, APIs, código, métricas)?
5. ¿Profundidad suficiente para decisión técnica real?

Responde JSON estricto:
```json
{{
  "status": "READY" o "NEEDS_MORE",
  "gaps": ["lagunas específicas a investigar, vacío si READY"],
  "priority": "high|medium|low",
  "reasoning": "por qué estás listo o necesitas más"
}}
```
"""

    response = llm_service.invoke(
        history=[
            SystemMessage(content="Eres un Crítico de Investigación riguroso. Responde solo con JSON válido."),
            HumanMessage(content=prompt),
        ]
    )
    content = ""
    for part in response:
        if isinstance(part, str) and not part.startswith("THINKING"):
            content += part

    # Parsear JSON
    import json
    import re
    decision = "NEEDS_MORE"
    gaps = []
    priority = "medium"
    try:
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            decision = parsed.get('status', 'NEEDS_MORE')
            gaps = parsed.get('gaps', [])
            priority = parsed.get('priority', 'medium')
    except Exception as e:
        logger.warning(f"No se pudo parsear reflexión JSON: {e}. Usando NEEDS_MORE.")
        decision = "NEEDS_MORE"
        gaps = ["No se pudo evaluar automáticamente, continuar investigando"]

    # Guardar lagunas para próxima iteración
    if gaps:
        state.research_gaps = gaps

    state.messages.append(
        ToolMessage(
            content=f"REFLEXIÓN TÉCNICA: status={decision}, priority={priority}, gaps={gaps}",
            tool_call_id="reflection_node",
        )
    )
    return {
        "messages": state.messages,
        "reflection_result": "READY" if decision == "READY" else "FALTA",
        "research_gaps": gaps,
        "iteration_count": state.iteration_count,
    }


def synthesis_node(
    state: DeepResearchState,
    llm_service: LLMService,
    terminal_ui: Optional[TerminalUI] = None,
):
    """Compila todos los hallazgos en el reporte final."""
    current_console = terminal_ui.console if terminal_ui else console

    # Notificación inmediata en TUI
    if terminal_ui and hasattr(terminal_ui, "update_live"):
        is_tui = hasattr(terminal_ui, "app") and terminal_ui.app is not None
        if is_tui:
            terminal_ui.update_live(
                ("__SPINNER__", "Sintetizando informe final de investigación...")
            )
        else:
            from rich.panel import Panel
            from kogniterm.terminal.themes import Icons
            from rich.padding import Padding

            terminal_ui.update_live(
                Padding(
                    Panel(
                        f"{Icons.RESEARCH} [bold]Sintetizando informe final de investigación...[/bold]",
                        border_style="green",
                        padding=(0, 4),
                        expand=True,
                    ),
                    (0, 0),
                )
            )

    # Construir resumen de hallazgos con fuentes
    all_findings_summary = ""
    for idx, finding in enumerate(state.findings):
        task = finding.get('task', 'N/A')
        content = finding.get('content', '')
        sources = finding.get('sources', [])
        confidence = finding.get('confidence', 'unknown')
        tool = finding.get('tool', 'unknown')
        sources_text = "\n".join([f"  - {s}" for s in sources]) if sources else "  - (sin fuentes explícitas)"
        all_findings_summary += f"### Hallazgo {idx + 1}: {task} [confianza: {confidence}, tool: {tool}]\n{content}\n\n**Fuentes:**\n{sources_text}\n\n"

    sources_list = "\n".join([f"- {u}" for u in state.source_urls[:20]]) if state.source_urls else "- (no se registraron URLs)"

    prompt = f"""Como experto Sintetizador Técnico de ÉLITE, utiliza toda la información recopilada para crear el INFORME FINAL DE INVESTIGACIÓN PROFUNDA.
    
    HISTORIAL DE INVESTIGACIÓN ({len(state.findings)} hallazgos, {len(state.source_urls)} fuentes únicas):
    {all_findings_summary}
    
    FUENTES RASTREADAS:\n{sources_list}
    
    CONSULTA ORIGINAL: {state.messages[0].content}
    
    REQUISITOS DEL INFORME (MÍNIMO 1500 PALABRAS, PROFUNDO Y TÉCNICO):
    1. **Resumen Ejecutivo**: Síntesis de 2-3 párrafos con las conclusiones clave.
    2. **Análisis por Sub-pregunta**: Para cada punto del plan de investigación, un análisis detallado con párrafos explicativos (no solo viñetas) que conecten múltiples fuentes.
    3. **Arquitectura y Flujos**: Usa diagramas Mermaid cuando sea relevante.
    4. **Detalles Técnicos Específicos**: Versiones, APIs, fragmentos de código, métricas, con citas a fuentes.
    5. **Contradicciones y Resolución**: Si hubo fuentes en conflicto, explica cómo se resolvieron.
    6. **Conclusiones y Recomendaciones**: Accionables para el Bash Agent, con advertencias 'KogniInsight'.
    7. **Referencias**: Lista numerada de todas las URLs citadas.
    
    Cada afirmación técnica DEBE incluir su referencia en formato [n] donde n es el índice en la lista de referencias.
    """

    # Llamada final al modelo
    response = llm_service.invoke(
        history=[
            SystemMessage(content=get_deep_research_system_prompt(llm_service)),
            HumanMessage(content=prompt),
        ],
        temperature=0.3,
    )

    # Recolectar la respuesta y filtrar razonamiento
    full_content = ""
    final_ai_message = None

    for part in response:
        if isinstance(part, AIMessage):
            final_ai_message = part
            if not full_content and part.content and isinstance(part.content, str):
                full_content = part.content
        elif isinstance(part, str):
            # Filtrar explícitamente contenido de pensamiento
            if not part.startswith("__THINKING__:") and not part.startswith(
                "THINKING:"
            ):
                full_content += part
                if terminal_ui and hasattr(terminal_ui, "update_live"):
                    from rich.panel import Panel
                    from rich.padding import Padding

                    terminal_ui.update_live(
                        Padding(
                            Panel(
                                Markdown(
                                    f"## 🔬 Informe de Síntesis\n\n{full_content}"
                                ),
                                border_style="green",
                                title="DeepResearcher",
                                padding=(0, 4),
                                expand=True,
                            ),
                            (0, 0),
                        )
                    )

    if not full_content and final_ai_message and final_ai_message.content:
        full_content = str(final_ai_message.content)

    if not (terminal_ui and hasattr(terminal_ui, "update_live")):
        current_console.print(
            Padding(
                Markdown(f"## 🔬 Informe de Investigación\n\n{full_content}"), (1, 4)
            )
        )

    state.messages.append(
        AIMessage(content=f"## 🔬 Informe de Deep Research\n\n{full_content}")
    )
    return {"messages": state.messages, "findings": state.findings}


# --- Implementación principal conceptualmente basada en agentes previos pero con lógica mejorada ---


def call_deep_model_node(
    state: DeepResearchState,
    llm_service: LLMService,
    terminal_ui: Optional[TerminalUI] = None,
    interrupt_queue: Optional[queue.Queue] = None,
):
    """Llama al LLM de Deep Research con soporte completo para TUI/CLI y contexto persistente."""
    current_console = terminal_ui.console if terminal_ui else console
    is_tui = getattr(terminal_ui, "is_tui", False)

    # Limpiar razonamiento de mensajes anteriores para evitar saturación
    cleaned_messages = []
    for msg in state.messages:
        if isinstance(msg, AIMessage) and "reasoning_content" in msg.additional_kwargs:
            msg.additional_kwargs.pop("reasoning_content")
        cleaned_messages.append(msg)

    context_info = f"\n\nESTADO DE LA INVESTIGACIÓN:\n- Plan de investigación: {state.research_plan}\n- Tarea actual: {state.current_task}\n- Hallazgos acumulados: {len(state.findings)}\n- Iteración: {state.iteration_count}/{state.max_iterations}"
    if state.findings:
        context_info += f"\n- Último hallazgo: {state.findings[-1]['task']}"
    if getattr(state, 'research_gaps', None):
        context_info += f"\n\n⚠️ LAGUNAS IDENTIFICADAS POR REFLEXIÓN (DEBES INVESTIGAR ESTO):\n"
        for i, gap in enumerate(state.research_gaps, 1):
            context_info += f"  {i}. {gap}\n"
        context_info += "\nUsa tavily_search, web_fetch o github para cerrar estas brechas."
    if getattr(state, 'source_urls', None):
        context_info += f"\n\nFuentes ya rastreadas ({len(state.source_urls)}): " + ", ".join(state.source_urls[:5])
    if getattr(state, 'reflection_result', None):
        context_info += f"\n\nÚltima evaluación de reflexión: {state.reflection_result}"

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

        class Icons:
            THINKING = "🤔"
            RESEARCH = "🔍"

        class ColorPalette:
            PRIMARY_LIGHT = "cyan"
            SECONDARY = "blue"
            GRAY_800 = "#333333"
            GRAY_600 = "#666666"
            GRAY_900 = "#1e1e1e"

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
            if is_tui:
                if terminal_ui and hasattr(terminal_ui, "update_live"):
                    terminal_ui.update_live(
                        ("__SPINNER__", "DeepResearcher Investigando...")
                    )
            else:
                from kogniterm.terminal.visual_components import create_animated_spinner

                renderables.append(
                    create_animated_spinner("DeepResearcher Investigando...", "dots")
                )
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
                        expand=True,
                    )
                    renderables.append(thought_panel)
                else:
                    renderables.append(
                        Panel(
                            Markdown(full_thinking_content),
                            title=f"{Icons.THINKING} [bold {ColorPalette.PRIMARY_LIGHT}]DeepResearcher Razonando...[/]",
                            border_style=ColorPalette.PRIMARY_LIGHT,
                            padding=(0, 4),
                            expand=True,
                        )
                    )

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
            live_ctx = Live(
                console=current_console, screen=False, refresh_per_second=10
            )
        else:

            @contextlib.contextmanager
            def _dummy_live():
                yield None

            live_ctx = _dummy_live()

        with live_ctx as live:
            _live_ref[0] = live

            update_display(initial=True)

            for part in llm_service.invoke(
                history=messages, interrupt_queue=interrupt_queue
            ):
                if isinstance(part, AIMessage):
                    final_ai_message = part
                elif isinstance(part, str):
                    if part.startswith("__THINKING__:") or part.startswith("THINKING:"):
                        prefix = (
                            "__THINKING__:"
                            if part.startswith("__THINKING__:")
                            else "THINKING:"
                        )
                        full_thinking_content += part[len(prefix) :]
                        update_display()
                    else:
                        full_response_content += part
                        text_streamed = True
                        update_display()

                if (
                    interrupt_queue and not interrupt_queue.empty()
                ) or llm_service.stop_generation_flag:
                    break

            # Actualización final para asegurar visibilidad total
            update_display(final=True)

            if is_tui:
                terminal_ui.stop_live()
    finally:
        if kh:
            kh.stop()

    if final_ai_message:
        # Asegurar que el contenido procesado se guarde en el mensaje
        if not final_ai_message.content and full_response_content:
            final_ai_message.content = full_response_content
        state.messages.append(final_ai_message)
        state.save_history(llm_service)

    return {"messages": state.messages}


def execute_single_tool(tc, llm_service, terminal_ui, interrupt_queue):
    """Ejecuta una herramienta individual SIN mostrar salida (modo Deep Researcher)."""
    tool_name = tc["name"]
    tool_args = tc["args"]
    tool_id = tc["id"]

    tool = llm_service.get_tool(tool_name)
    if not tool:
        return tool_id, f"Error: Herramienta '{tool_name}' no encontrada.", None

    try:
        full_tool_output = ""
        tool_output_generator = llm_service._invoke_tool_with_interrupt(tool, tool_args)

        for chunk in tool_output_generator:
            full_tool_output += str(chunk)

        return tool_id, full_tool_output, None
    except InterruptedError:
        return (
            tool_id,
            f"Ejecución de herramienta '{tool_name}' interrumpida por el usuario.",
            InterruptedError("Interrumpido por el usuario."),
        )
    except Exception as e:
        return tool_id, f"Error al ejecutar la herramienta {tool_name}: {e}", e


def execute_tool_node(
    state: DeepResearchState,
    llm_service: LLMService,
    terminal_ui: Optional[TerminalUI] = None,
    interrupt_queue: Optional[queue.Queue] = None,
):
    """Nodo de ejecución de herramientas SIN mostrar salida (modo Deep Researcher)."""
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return state

    tool_messages = []
    executor = ThreadPoolExecutor(max_workers=5)
    futures = []

    if interrupt_queue and not interrupt_queue.empty():
        interrupt_queue.get()
        state.reset_temporary_state()
        return state

    for tool_call in last_message.tool_calls:
        if interrupt_queue and not interrupt_queue.empty():
            interrupt_queue.get()
            state.reset_temporary_state()
            break

        futures.append(
            executor.submit(
                execute_single_tool,
                tool_call,
                llm_service,
                terminal_ui,
                interrupt_queue,
            )
        )

    for future in as_completed(futures):
        try:
            tool_id, content, exception = future.result()
            if exception:
                if isinstance(exception, UserConfirmationRequired):
                    tool_messages.append(
                        ToolMessage(content=content, tool_call_id=tool_id)
                    )
                else:
                    tool_messages.append(
                        ToolMessage(content=content, tool_call_id=tool_id)
                    )
            else:
                tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))
        except Exception as e:
            tool_messages.append(
                ToolMessage(content=f"Error en ejecutor: {e}", tool_call_id="unknown")
            )

    state.messages.extend(tool_messages)
    llm_service._save_history(state.messages)
    executor.shutdown(wait=True)
    return state


def should_continue(state: DeepResearchState) -> str:
    """Decide si el agente debe continuar."""
    from langgraph.graph import END

    if state.completed:
        return END

    last_message = state.messages[-1]

    if state.command_to_confirm is not None:
        return END

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "execute_tool"
    elif isinstance(last_message, ToolMessage):
        return "call_model"

    return "call_model"


def create_deep_researcher(
    llm_service: LLMService,
    terminal_ui: Any = None,
    interrupt_queue: Optional[queue.Queue] = None,
):
    workflow = StateGraph(DeepResearchState)

    workflow.add_node(
        "planning",
        functools.partial(
            planning_node, llm_service=llm_service, terminal_ui=terminal_ui
        ),
    )
    workflow.add_node(
        "research",
        functools.partial(
            research_node,
            llm_service=llm_service,
            terminal_ui=terminal_ui,
            interrupt_queue=interrupt_queue,
        ),
    )
    workflow.add_node(
        "reflection",
        functools.partial(
            reflection_node, llm_service=llm_service, terminal_ui=terminal_ui
        ),
    )
    workflow.add_node(
        "synthesis",
        functools.partial(
            synthesis_node, llm_service=llm_service, terminal_ui=terminal_ui
        ),
    )
    workflow.add_node(
        "call_model",
        functools.partial(
            call_deep_model_node,
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

    workflow.set_entry_point("planning")
    workflow.add_edge("planning", "call_model")
    workflow.add_edge("execute_tool", "research")
    workflow.add_edge("research", "call_model")

    def deep_research_router(state: DeepResearchState):
        """Router iterativo: respeta max_iterations y bucle reflection->research."""
        # Si el modelo ha completado explícitamente
        if state.completed:
            return "synthesis"

        # Si hay tool calls pendientes, ejecutar herramientas
        if should_continue(state) == "execute_tool":
            return "execute_tool"

        # Si hay hallazgos y alcanzamos el límite de iteraciones, ir a reflexión
        if state.findings and state.iteration_count >= state.max_iterations:
            return "reflection"

        # Si tenemos al menos un hallazgo y la reflexión anterior dijo READY, síntesis
        if state.findings and getattr(state, 'reflection_result', None) == "READY":
            return "reflection"  # El nodo reflection forzará síntesis si es READY

        # Si ya pasamos por reflexión y dijo FALTA, volver a investigar con gaps
        if state.findings and getattr(state, 'reflection_result', None) == "FALTA":
            return "call_model"  # El modelo usará research_gaps para profundizar

        # Flujo normal: si hay hallazgos suficientes para una primera reflexión
        if state.findings and len(state.findings) >= max(1, len(state.research_plan) // 2):
            return "reflection"

        return "call_model"

    workflow.add_conditional_edges(
        "call_model",
        deep_research_router,
        {
            "execute_tool": "execute_tool",
            "reflection": "reflection",
            "call_model": "call_model",
            "synthesis": "synthesis",
        },
    )

    # Bucle: reflection puede volver a call_model si FALTA, o ir a synthesis si READY
    def reflection_router(state: DeepResearchState):
        if getattr(state, 'reflection_result', None) == "READY":
            return "synthesis"
        return "call_model"

    workflow.add_conditional_edges(
        "reflection",
        reflection_router,
        {
            "synthesis": "synthesis",
            "call_model": "call_model",
        },
    )
    workflow.add_edge("synthesis", END)

    return workflow.compile()
