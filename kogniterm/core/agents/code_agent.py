from __future__ import annotations
import asyncio
from langgraph.graph import StateGraph, END
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..llm_service import LLMService
import functools
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
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
from kogniterm.core.exceptions import UserConfirmationRequired
from ..async_io_manager import get_io_manager
from ..utils.tool_utils import (
    get_tool_action_description,
    tool_requires_content_for_confirmation,
)

console = Console()


# --- Mensaje de Sistema del Agente de Código ---
def get_system_message(llm_service: LLMService) -> SystemMessage:
    content = """INSTRUCCIÓN CRÍTICA: Eres el Agente de Código de KogniTerm (CodeAgent).
Tu rol es ser un Desarrollador Senior y Arquitecto de Software experto en Python, JavaScript/TypeScript y diseño de sistemas.

⚠️⚠️⚠️ PROTOCOLO DE CUMPLIMIENTO OBLIGATORIO: task_tracker ⚠️⚠️⚠️
Cualquier solicitud o tarea asignada (sin importar su complejidad) DEBE ser registrada y actualizada en la herramienta `task_tracker`.
1. **Inicialización Inmediata**: En tu PRIMER TURNO, antes de realizar cualquier otra acción o ejecutar cualquier herramienta (como leer archivos o buscar), DEBES llamar a `task_tracker` con `action="init"`, especificando `agent_name="Coder"` y la lista de tareas detallada en `plan`.
2. **Actualizaciones en Tiempo Real**: Cada vez que inicies, completes o cambie el estado de una tarea, DEBES llamar inmediatamente a `task_tracker` con `action="update"`, especificando el `task_index` y el nuevo `status` ("in_progress", "completed", "failed").
3. **Registro Final**: Al concluir el trabajo, asegúrate de marcar la última tarea como completada llamando a `task_tracker`.
¡NUNCA OMITAS ESTE PASO! No inicializar el task tracker inmediatamente en el primer turno se considera un fallo de ejecución crítico y una violación del protocolo.

**Tus Principios Fundamentales:**
1.  **Calidad sobre Velocidad**: Prefieres una solución robusta y bien probada a un parche rápido.
2.  **"Trust but Verify" (Confía pero Verifica)**: NUNCA asumas el contenido de un archivo. Antes de editar, SIEMPRE lee el archivo actual.
3.  **Consistencia**: El código nuevo debe seguir el estilo del existente (PEP8, ESLint).
4.  **Seguridad**: Evita vulnerabilidades. Valida entradas. Maneja excepciones.
5.  **ACTUACIÓN AUTÓNOMA**: Una vez que tengas el contenido del archivo y hayas planeado el cambio, **APLÍCALO INMEDIATAMENTE** en el siguiente turno. No esperes a que el Bash Agent te pida confirmación si ya tienes toda la información.

**Tu Flujo de Trabajo:**
1.  **Análisis**: Localiza y LEE los archivos relevantes. Entiende el contexto.
2.  **Planificación**: Esboza los pasos de tu plan de implementación.
3.  **Ejecución**: Usa `advanced_file_editor` para modificaciones.
4.  **Validación**: Verifica sintaxis y usa `python_executor` si es necesario para probar lógica.

**Herramientas:**
* `advanced_file_editor`: TU HERRAMIENTA PRINCIPAL. Úsala con precisión. Tus cambios se aplican de forma autónoma.
* `codebase_search_tool`: Para encontrar referencias.
* `python_executor`: Para scripts de prueba o mantenimiento.
* `execute_command`: Para correr tests o builds.
* `file_operations`: Para leer y explorar.

**Instrucciones de Respuesta:**
*   Sé técnico.
*   Usa Markdown para código.
*   Explica el "por qué" de tus cambios.
*   Si encuentras errores en el plan del usuario, propón mejoras.

## 🚀 OPTIMIZACIÓN Y VELOCIDAD (PARALELISMO DE HERRAMIENTAS)
- **Ejecución Parallela Obligatoria**: El sistema ejecuta TODAS tus llamadas a herramientas en un mismo turno **en paralelo**.
- Cuando necesites inspeccionar, buscar o leer múltiples archivos o partes del proyecto, **emite TODAS las tool_calls en el mismo turno**. No hagas una llamada, esperes el resultado y luego hagas otra.
- Ejemplo: Si necesitas leer `file1.py` y `file2.py`, emite ambas llamadas a `file_operations` en el mismo mensaje.

## 📌 PROTOCOLO OBLIGATORIO DE SEGUIMIENTO DE TAREAS (task_tracker)
1. **Inicialización Obligatoria**: Para toda tarea o plan, DEBES inicializar tu plan de trabajo llamando a `task_tracker` con `action="init"`, especificando tu `agent_name='Coder'` y la lista de tareas en `plan`.
2. **Actualización de Progreso**: Cada vez que completes una tarea o cambie el estado de una tarea, DEBES llamar inmediatamente a `task_tracker` con `action="update"`, especificando el `task_index` y el nuevo `status` ("completed", "in_progress", "failed").
3. **Finalización**: Al terminar todo el trabajo solicitado, DEBES registrar la finalización llamando a `task_tracker` con `action="update"` para marcar la última tarea como completada.
¡NUNCA procedas con ninguna tarea o acción sin registrarla y mantenerla al día en `task_tracker`!

Recuerda: Eres el guardián de la calidad del código.
"""
    if not llm_service.is_thinking_model():
        content += """
Recuerda: Como este modelo no tiene razonamiento nativo, DEBES encerrar todo tu proceso de pensamiento e investigación de código dentro de etiquetas `<thought>...</thought>` antes de escribir cualquier respuesta o ejecutar cualquier herramienta.
Ejemplo:
<thought>
Estoy planeando la modificación del archivo...
</thought>
[Aquí tu respuesta final o llamada a herramienta]
"""
    return SystemMessage(content=content)


# --- Funciones Auxiliares (Reutilizadas/Adaptadas de bash_agent) ---


def handle_tool_confirmation(state: AgentState, llm_service: LLMService):
    """
    Maneja la respuesta de confirmación del usuario para una operación de herramienta.
    Si se aprueba, re-ejecuta la herramienta.
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, ToolMessage):
        # Esto no debería pasar si el flujo es correcto
        console.print(
            "[bold red]Error: handle_tool_confirmation llamado sin un ToolMessage.[/bold red]"
        )
        state.reset_tool_confirmation()
        return state

    tool_message_content = last_message.content
    tool_id = state.tool_call_id_to_confirm  # Usar el tool_id guardado

    if "Aprobado" in tool_message_content:
        console.print(
            "[bold green]✅ Confirmación de usuario recibida: Aprobado.[/bold green]"
        )
        tool_name = state.tool_pending_confirmation
        tool_args = state.tool_args_pending_confirmation

        if tool_name == "plan_creation_tool":
            plan_title = (
                tool_args.get("plan_title", "generado") if tool_args else "generado"
            )
            if "Aprobado" in tool_message_content:
                success_message = f"El plan '{plan_title}' fue aprobado por el usuario. El agente puede proceder con la ejecución de los pasos."
                state.messages.append(AIMessage(content=success_message))
                console.print(f"[green]✨ {success_message}[/green]")
            else:
                denied_message = f"El plan '{plan_title}' fue denegado por el usuario. El agente debe revisar la estrategia."
                state.messages.append(AIMessage(content=denied_message))
                console.print(f"[yellow]⚠️ {denied_message}[/yellow]")
        elif tool_name and tool_args:
            console.print(
                f"[bold blue]🛠️ Re-ejecutando herramienta '{tool_name}' tras aprobación:[/bold blue]"
            )

            tool = llm_service.get_tool(tool_name)
            if tool:
                if tool_name in {
                    "file_update_tool",
                    "advanced_file_editor",
                    "advanced_file_editor_tool",
                    "sophisticated_editor_tool",
                }:
                    tool_args["confirm"] = True
                    if (
                        tool_requires_content_for_confirmation(tool_name, tool_args)
                        and tool_args.get("content") is None
                    ):
                        error_output = (
                            "Error: El contenido a actualizar no puede ser None."
                        )
                        state.messages.append(
                            ToolMessage(content=error_output, tool_call_id=tool_id)
                        )
                        console.print(f"[bold red]❌ {error_output}[/bold red]")
                        state.reset_tool_confirmation()
                        return state

                try:
                    raw_tool_output = llm_service._invoke_tool_with_interrupt(
                        tool, tool_args
                    )
                    tool_output_str = str(raw_tool_output)
                    tool_messages = [
                        ToolMessage(content=tool_output_str, tool_call_id=tool_id)
                    ]
                    state.messages.extend(tool_messages)
                    console.print(
                        f"[green]✨ Herramienta '{tool_name}' re-ejecutada con éxito.[/green]"
                    )

                except InterruptedError:
                    console.print(
                        "[bold yellow]⚠️ Re-ejecución de herramienta interrumpida por el usuario. Volviendo al input.[/bold yellow]"
                    )
                    state.reset_temporary_state()
                    return state
                except Exception as e:  # noqa: BLE001
                    error_output = f"Error al re-ejecutar la herramienta {tool_name} tras aprobación: {e}"
                    state.messages.append(
                        ToolMessage(content=error_output, tool_call_id=tool_id)
                    )
                    console.print(f"[bold red]❌ {error_output}[/bold red]")
            else:
                error_output = (
                    f"Error: Herramienta '{tool_name}' no encontrada para re-ejecución."
                )
                state.messages.append(
                    ToolMessage(content=error_output, tool_call_id=tool_id)
                )
                console.print(f"[bold red]❌ {error_output}[/bold red]")
        else:
            error_output = "Error: No se encontró información de la herramienta pendiente para re-ejecución."
            state.messages.append(
                ToolMessage(content=error_output, tool_call_id=tool_id)
            )
            console.print(f"[bold red]❌ {error_output}[/bold red]")
    else:
        console.print(
            "[bold yellow]⚠️ Confirmación de usuario recibida: Denegado.[/bold yellow]"
        )
        tool_output_str = f"Operación denegada por el usuario: {state.tool_pending_confirmation or state.tool_code_tool_name}"
        state.messages.append(
            ToolMessage(content=tool_output_str, tool_call_id=tool_id)
        )

    state.reset_tool_confirmation()
    state.tool_call_id_to_confirm = None
    return state


def call_model_node(
    state: AgentState,
    llm_service: LLMService,
    terminal_ui: Optional[TerminalUI] = None,
    interrupt_queue: Optional[queue.Queue] = None,
):
    if state.completed:
        logger.info(
            "El agente de código ya completó su proceso (completed flag). Saltando llamada al modelo."
        )
        if not state.messages or not isinstance(state.messages[-1], AIMessage):
            state.messages.append(
                AIMessage(content="Proceso finalizado a través de complete_task.")
            )
        return {"messages": state.messages, "completed": True}

    if state.delegation_context and getattr(
        state.delegation_context, "metadata", {}
    ).get("completed"):
        logger.info(
            "El agente de código ya completó su proceso a través de complete_task. Saltando llamada al modelo."
        )
        if not state.messages or not isinstance(state.messages[-1], AIMessage):
            state.messages.append(
                AIMessage(content="Proceso finalizado a través de complete_task.")
            )
        return {"messages": state.messages, "completed": True}

    current_console = terminal_ui.console if terminal_ui else console
    is_tui = getattr(terminal_ui, "is_tui", False)

    # --- Lógica de Detección de Bucles ---
    if len(state.tool_call_history) >= 4:
        last_calls = list(state.tool_call_history)[-4:]
        if all(
            tc["name"] == last_calls[0]["name"]
            and tc["args_hash"] == last_calls[0]["args_hash"]
            for tc in last_calls
        ):
            console.print(
                "[bold red]🚨 ¡BUCLE CRÍTICO DETECTADO EN CODEAGENT! Deteniendo...[/bold red]"
            )
            error_msg = "He detectado que estoy en un bucle infinito repitiendo la misma acción. Deteniendo para evitar consumo innecesario."
            state.messages.append(AIMessage(content=error_msg))
            # Activar la bandera de bucle crítico para terminar el flujo
            state.critical_loop_detected = True
            # Limpiar el historial de llamadas a herramientas para evitar que la advertencia se repita
            state.clear_tool_call_history()
            return {"messages": state.messages, "critical_loop_detected": True}

    messages = [get_system_message(llm_service)] + state.messages

    full_response_content = ""
    full_thinking_content = ""
    final_ai_message = None

    try:
        from kogniterm.terminal.visual_components import create_processing_spinner
        from kogniterm.terminal.themes import ColorPalette, Icons

        spinner = create_processing_spinner()
    except ImportError:
        from rich.spinner import Spinner

        spinner = Spinner("dots", text="🤖 CodeAgent pensando...")

    # Iniciar KeyboardHandler para detectar ESC (solo CLI)
    kh = None
    if not is_tui:
        from kogniterm.terminal.keyboard_handler import KeyboardHandler

        kh = KeyboardHandler(interrupt_queue)
        kh.start()

    try:
        import contextlib

        if not is_tui:
            live_context = Live(
                spinner, console=current_console, screen=False, refresh_per_second=10
            )
        else:

            @contextlib.contextmanager
            def dummy_live():
                yield type("DummyLive", (), {"update": lambda self, x: None})()

            live_context = dummy_live()

        with live_context as live:
            TUI_BG = ColorPalette.GRAY_900 if "ColorPalette" in globals() else "#1e1e1e"

            def update_display():
                renderables = []
                if full_thinking_content:
                    if is_tui:
                        thinking_content = Markdown(full_thinking_content)
                        thought_panel = Panel(
                            thinking_content,
                            title=f"{Icons.THINKING} CodeAgent Pensando...",
                            border_style=ColorPalette.PRIMARY,
                            style=f"on {TUI_BG}",
                            padding=(0, 4),
                            expand=True,
                        )

                        renderables.append(thought_panel)
                    else:
                        renderables.append(
                            Panel(
                                Markdown(full_thinking_content),
                                title=f"[bold {ColorPalette.PRIMARY_LIGHT}]{Icons.THINKING} CodeAgent Pensando...[/]",
                                border_style=ColorPalette.PRIMARY_LIGHT,
                                padding=(0, 4),
                                expand=True,
                            )
                        )

                if full_response_content:
                    if full_thinking_content:
                        renderables.append(Text(""))
                    renderables.append(Markdown(full_response_content))

                if is_tui:
                    group = Group(*renderables)
                    terminal_ui.update_live(Padding(group, (0, 0)))
                else:
                    final_renderable = (
                        Padding(Group(*renderables), (0, 0)) if renderables else spinner
                    )
                    live.update(final_renderable)

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
                        update_display()

                if (
                    interrupt_queue and not interrupt_queue.empty()
                ) or llm_service.stop_generation_flag:
                    break

            if is_tui:
                terminal_ui.stop_live()
    finally:
        if kh:
            kh.stop()

    if final_ai_message:
        if not final_ai_message.content and full_response_content:
            final_ai_message.content = full_response_content
        state.messages.append(final_ai_message)
        state.save_history(llm_service)

    return {"messages": state.messages}


def _is_markdown_content(text: str) -> bool:
    """Detecta si el contenido parece ser markdown."""
    if not text or len(text.strip()) < 5:
        return False

    # Indicadores de markdown
    markdown_indicators = [
        text.startswith("#"),  # Headers
        "## " in text or "### " in text,  # Headers en cualquier parte
        "\n- " in text
        or "\n* " in text
        or "\n+ " in text
        or text.startswith("- "),  # Listas
        "```" in text,  # Bloques de código
        ("[" in text and "](" in text)
        or (
            "<" in text and ">" in text and ("http" in text or "https" in text)
        ),  # Links MD o <url>
        "**" in text or "__" in text,  # Bold
        ("*" in text and text.count("*") >= 2),  # Italic
        ("|" in text and "---" in text),  # Tablas
    ]

    # Si tiene al menos un indicador fuerte, lo tratamos como markdown
    return any(markdown_indicators)


def execute_single_tool(tc, llm_service, terminal_ui, interrupt_queue):
    """Ejecuta una herramienta individual con verbosidad adaptada a TUI/CLI."""
    tool_name = tc["name"]
    tool_args = tc["args"]
    tool_id = tc["id"]
    is_tui = getattr(terminal_ui, "is_tui", False)

    # Notificación de inicio
    tool = llm_service.get_tool(tool_name)
    bajada = ""
    skill_name = ""
    if tool:
        # Obtener skill_name del skill_manager
        if hasattr(llm_service, "skill_manager"):
            skill = llm_service.skill_manager.get_skill_for_tool(tool_name)
            if skill:
                skill_name = skill.name

        bajada = get_tool_action_description(tool, tool_args)

    if is_tui:
        terminal_ui.print_tool_notification(tool_name, bajada, skill_name=skill_name)
    else:
        args_json = json.dumps(tool_args, indent=2, ensure_ascii=False)
        console.print(
            Panel(
                Syntax(args_json, "json", theme="monokai", line_numbers=False),
                title=f"[bold cyan]🛠️ Ejecutando: {tool_name}[/bold cyan]",
                border_style="cyan",
                padding=(0, 4),
                expand=True,
            )
        )

    if not tool:
        return tool_id, f"Error: Herramienta '{tool_name}' no encontrada.", None

    try:
        # _invoke_tool_with_interrupt es un generador, debemos iterar para obtener el resultado final
        output_str = ""
        for part in llm_service._invoke_tool_with_interrupt(
            tool, tool_args, terminal_ui=terminal_ui
        ):
            if part is not None:
                output_str += str(part)

        # Determinar si el contenido debe renderizarse como markdown
        is_markdown = _is_markdown_content(output_str)

        # Preparar el contenido para mostrar
        if len(output_str) > 1000:
            display_output = (
                output_str[:1000]
                + "\n\n... (truncado para brevedad, contenido completo enviado al LLM)"
            )
            is_truncated = True
        else:
            display_output = output_str
            is_truncated = False

        # Renderizar el resultado
        if not is_tui:
            if is_markdown:
                content_renderable = Markdown(display_output)
            else:
                content_renderable = Text(display_output)

            console.print(
                Panel(
                    content_renderable,
                    title=f"[bold green]✅ Resultado de {tool_name}[/bold green]"
                    + (" (truncado)" if is_truncated else ""),
                    border_style="green",
                    padding=(0, 4),
                    expand=True,
                )
            )
        else:
            # En TUI, si estamos en paneles paralelos (proxied), debemos mostrar el resultado
            # para que el flujo sea visible en la columna correspondiente.
            # Si no es proxied, el ChatLogWidget ya maneja los ToolMessage de forma nativa.
            if hasattr(terminal_ui, "panel_id") and terminal_ui.panel_id:
                from kogniterm.terminal.visual_components import (
                    create_tool_output_panel,
                )

                panel = create_tool_output_panel(
                    tool_name, display_output, is_markdown=is_markdown
                )
                terminal_ui.update_live(panel)
                if hasattr(terminal_ui, "stop_live"):
                    terminal_ui.stop_live()
            pass

        # --- Refresco automático de herramientas ---
        # Si la herramienta es 'refresh_tools', forzar al SkillManager a recargar
        if tool_name == "refresh_tools" and hasattr(llm_service, "skill_manager"):
            logger.info(
                "Detectada llamada a refresh_tools en CodeAgent. Disparando SkillManager.refresh_skills(force=True)."
            )
            llm_service.skill_manager.refresh_skills(force=True)
            if hasattr(llm_service, "sync_tools"):
                llm_service.sync_tools()

        # Si la herramienta es 'skill_factory' y terminó con éxito, refrescar el arsenal
        if tool_name == "skill_factory" and hasattr(llm_service, "skill_manager"):
            logger.info(
                "Detectada creación de skill via skill_factory en CodeAgent. Disparando refresh automático."
            )
            try:
                llm_service.skill_manager.refresh_skills(force=True)
                if hasattr(llm_service, "sync_tools"):
                    llm_service.sync_tools()
                new_tool_names = list(llm_service.skill_manager.tool_registry.keys())
                logger.info(
                    f"Arsenal de CodeAgent actualizado. Herramientas: {new_tool_names}"
                )
                output_str += f"\n\n✅ Arsenal actualizado automáticamente. Herramientas ahora disponibles: {new_tool_names}"
            except Exception as e:
                logger.warning(
                    f"Error al refrescar skills en CodeAgent tras skill_factory: {e}"
                )

        return tool_id, output_str, None
    except UserConfirmationRequired as e:
        try:
            return tool_id, json.dumps(e.raw_tool_output), e
        except TypeError:  # Si raw_tool_output no es serializable
            return tool_id, str(e.raw_tool_output), e
    except InterruptedError:
        return (
            tool_id,
            f"Ejecución de herramienta '{tool_name}' interrumpida por el usuario.",
            InterruptedError("Interrumpido por el usuario."),
        )
    except Exception as e:  # noqa: BLE001
        console.print(f"[bold red]❌ Error en {tool_name}: {e}[/bold red]")
        return tool_id, f"Error en {tool_name}: {e}", e


def is_destructive_command(command: str) -> bool:
    """
    Determina si un comando de terminal es potencialmente destructivo.
    """
    cmd_lower = command.lower().strip()

    # Patrones de comandos peligrosos
    destructive_patterns = [
        "rm -rf",
        "rm -r ",
        "rm -f ",
        "dd if=",
        "mkfs",
        "mke2fs",
        "chmod 777",
        "chmod -r 777",
        "chown -r",
        "chown -R",
        "> /dev/sd",  # Escritura directa a disco
        "git reset --hard",
        "git clean -fd",
        "git clean -fx",
        "docker rm",
        "docker rmi",
        "docker system prune",
        "docker volume rm",
        "pip uninstall",
        "npm uninstall",
        "yarn remove",
        "shutdown",
        "reboot",
        "halt",
        "poweroff",
    ]

    return any(pattern in cmd_lower for pattern in destructive_patterns)


def _consume_tool_generator(result) -> str:
    """Convierte el resultado de una herramienta a texto persistible."""
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    if result is None:
        return ""
    return str(result)


def _invoke_tool_autonomously(
    llm_service: LLMService,
    tool_name: str,
    tool_args: dict,
    terminal_ui: Optional[Any] = None,
) -> str:
    """Reintenta una herramienta con confirmación implícita para agentes autónomos."""
    tool = llm_service.get_tool(tool_name)
    if tool is None:
        raise RuntimeError(
            f"Herramienta no encontrada para aprobación autónoma: {tool_name}"
        )

    approved_args = dict(tool_args or {})
    approved_args["confirm"] = True

    parts = []
    for part in llm_service._invoke_tool_with_interrupt(
        tool, approved_args, terminal_ui=terminal_ui
    ):
        parts.append(part)

    if not parts:
        return ""
    if len(parts) == 1:
        return _consume_tool_generator(parts[0])
    return "".join(str(part) for part in parts)


def execute_tool_node(
    state: AgentState,
    llm_service: LLMService,
    terminal_ui: Optional[TerminalUI] = None,
    interrupt_queue: Optional[queue.Queue] = None,
):
    """Nodo de ejecución de herramientas con soporte para TUI."""

    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return state

    tool_messages = []
    executor = ThreadPoolExecutor(max_workers=15)
    futures = []
    autonomous_mode = bool(getattr(state, "autonomous_approvals", False))

    # Mostrar encabezado solo en CLI
    is_tui = getattr(terminal_ui, "is_tui", False)
    if not is_tui:
        console.print(
            Padding(
                Text(
                    "💻 Fase de Implementación: Ejecutando herramientas...",
                    style="bold magenta underline",
                ),
                (1, 0),
            )
        )

    for tool_call in last_message.tool_calls:
        # Registrar la llamada a la herramienta en el historial para detección de bucles
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # EXCEPCIÓN: CodeAgent/DeepCoder auto-confirma ediciones para mayor autonomía
        editing_tools = {
            "advanced_file_editor",
            "file_update_tool",
            "write_to_file",
            "replace_file_content",
            "multi_replace_file_content",
            "file_create_tool",
        }
        if tool_name in editing_tools:
            logger.info(
                f"DEBUG: Ejecutando herramienta de edición {tool_name} con args: {tool_args}"
            )
            tool_args["confirm"] = True

        # Generar un hash consistente de los argumentos
        try:
            args_hash = json.dumps(tool_args, sort_keys=True)
        except TypeError:
            args_hash = str(
                tool_args
            )  # Fallback si los argumentos no son serializables

        state.tool_call_history.append({"name": tool_name, "args_hash": args_hash})

        if interrupt_queue and not interrupt_queue.empty():
            interrupt_queue.get()
            state.clear_tool_call_history()  # Limpiar historial si se interrumpe
            return state

        # CASO ESPECIAL: execute_command con comandos destructivos
        if tool_name == "execute_command" and not autonomous_mode:
            command = tool_args.get("command", "")
            if is_destructive_command(command):
                # Feedback visual de preparación de comando destructivo
                bajada = f"Comando detectado como POTENCIALMENTE DESTRUCTIVO: {command}"

                # Obtener skill_name
                skill_name = ""
                if hasattr(llm_service, "skill_manager"):
                    skill = llm_service.skill_manager.get_skill_for_tool(tool_name)
                    if skill:
                        skill_name = skill.name

                if is_tui:
                    terminal_ui.print_tool_notification(
                        tool_name, bajada, skill_name=skill_name
                    )
                else:
                    console.print(
                        f"\n[bold red]⚠️  Comando destructivo detectado:[/bold red] [yellow]{command}[/yellow]"
                    )

                # Establecer estado para confirmación en la UI
                state.command_to_confirm = command
                state.tool_call_id_to_confirm = tool_call["id"]

                # IMPORTANTE: Si hay un comando destructivo, salir y esperar confirmación
                executor.shutdown(wait=False)
                return {
                    "messages": state.messages,
                    "command_to_confirm": state.command_to_confirm,
                    "tool_call_id_to_confirm": state.tool_call_id_to_confirm,
                }

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
        tool_id, content, exception = future.result()

        if isinstance(exception, UserConfirmationRequired):
            if autonomous_mode:
                try:
                    auto_content = _invoke_tool_autonomously(
                        llm_service,
                        exception.tool_name
                        or next(
                            tc["name"]
                            for tc in last_message.tool_calls
                            if tc["id"] == tool_id
                        ),
                        exception.tool_args,
                        terminal_ui=terminal_ui,
                    )
                    tool_messages.append(
                        ToolMessage(content=auto_content, tool_call_id=tool_id)
                    )
                    continue
                except Exception as auto_exc:  # noqa: BLE001
                    tool_messages.append(
                        ToolMessage(
                            content=f"Error en aprobación autónoma de {exception.tool_name}: {auto_exc}",
                            tool_call_id=tool_id,
                        )
                    )
                    continue

            # Manejo de confirmación para ediciones críticas
            state.tool_pending_confirmation = exception.tool_name
            state.tool_args_pending_confirmation = exception.tool_args
            state.tool_call_id_to_confirm = tool_id
            state.file_update_diff_pending_confirmation = exception.raw_tool_output

            tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))
            state.messages.extend(tool_messages)
            state.save_history(llm_service)
            return state

        tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))

    state.messages.extend(tool_messages)
    state.save_history(llm_service)
    return state


def should_continue(state: AgentState) -> str:
    """Decide si el agente debe continuar."""
    from langgraph.graph import END
    if state.completed or state.critical_loop_detected:
        return END

    last_message = state.messages[-1]

    if state.command_to_confirm or state.file_update_diff_pending_confirmation:
        return END

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "execute_tool"
    elif isinstance(last_message, ToolMessage):
        return "call_model"
    
    is_autonomous = getattr(state, "autonomous_approvals", False) or getattr(state, "delegation_context", None) is not None
    if is_autonomous and not state.completed:
        return "call_model"

    return END


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
