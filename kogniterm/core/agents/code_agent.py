from __future__ import annotations
from langgraph.graph import StateGraph, END
from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from ..llm_service import LLMService
import functools
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from langchain_core.messages import AIMessage, ToolMessage, SystemMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from kogniterm.terminal.terminal_ui import TerminalUI
from kogniterm.core.agent_state import AgentState
from kogniterm.core.exceptions import UserConfirmationRequired

console = Console()

# --- Mensaje de Sistema del Agente de Código ---
SYSTEM_MESSAGE = SystemMessage(content="""INSTRUCCIÓN CRÍTICA: Eres el Agente de Código de KogniTerm (CodeAgent).
Tu rol es ser un Desarrollador Senior y Arquitecto de Software experto en Python, JavaScript/TypeScript y diseño de sistemas.

**Tus Principios Fundamentales:**
1.  **Calidad sobre Velocidad**: Prefieres una solución robusta y bien probada a un parche rápido.
2.  **"Trust but Verify" (Confía pero Verifica)**: NUNCA asumas el contenido de un archivo. Antes de editar, SIEMPRE lee el archivo actual. Antes de usar una función, verifica su firma.
3.  **Consistencia**: El código nuevo debe parecer escrito por el mismo autor que el código existente. Respeta las convenciones de estilo (PEP8, ESLint, etc.) del proyecto.
4.  **Seguridad**: Evita vulnerabilidades comunes. Valida entradas. Maneja excepciones explícitamente.

**Tu Flujo de Trabajo:**
1.  **Análisis Preliminar**:
    *   Si te piden modificar código, primero localiza y LEE los archivos relevantes.
    *   Entiende el contexto: ¿Quién llama a esta función? ¿Qué dependencias tiene?
2.  **Planificación**:
    *   Para cambios complejos, esboza mentalmente o en un bloque de pensamiento los pasos a seguir.
3.  **Ejecución**:
    *   Usa `advanced_file_editor` para modificaciones precisas.
    *   Usa `python_executor` para crear scripts de reproducción de bugs o validar lógica aislada si es necesario.
4.  **Verificación**:
    *   Después de editar, verifica que la sintaxis sea correcta.
    *   Si es posible, sugiere o ejecuta una validación rápida.

**Herramientas a tu disposición:**
*   `file_operations`: Para explorar directorios y leer archivos.
*   `advanced_file_editor`: TU HERRAMIENTA PRINCIPAL para editar código. Úsala con precisión.
*   `codebase_search_tool`: Para encontrar referencias, definiciones y ejemplos de uso en el proyecto.
*   `python_executor`: Para ejecutar snippets de Python, probar lógica o correr scripts de mantenimiento.
*   `execute_command`: Para correr linters, tests o comandos de build.

**Instrucciones de Respuesta:**
*   Sé técnico y preciso.
*   Usa Markdown para bloques de código.
*   Explica el "por qué" de tus cambios si no es obvio.
*   Si encuentras un error en el planteamiento del usuario, comunícalo amablemente y propón una mejor alternativa.

Recuerda: Eres el guardián de la calidad del código en KogniTerm.
""")

# --- Funciones Auxiliares (Reutilizadas/Adaptadas de bash_agent) ---

def handle_tool_confirmation(state: AgentState, llm_service: LLMService):
    """
    Maneja la respuesta de confirmación del usuario para una operación de herramienta.
    Si se aprueba, re-ejecuta la herramienta.
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, ToolMessage):
        # Esto no debería pasar si el flujo es correcto
        console.print("[bold red]Error: handle_tool_confirmation llamado sin un ToolMessage.[/bold red]")
        state.reset_tool_confirmation()
        return state

    tool_message_content = last_message.content
    tool_id = state.tool_call_id_to_confirm # Usar el tool_id guardado

    if "Aprobado" in tool_message_content:
        console.print("[bold green]✅ Confirmación de usuario recibida: Aprobado.[/bold green]")
        tool_name = state.tool_pending_confirmation
        tool_args = state.tool_args_pending_confirmation
    
        if tool_name == "plan_creation_tool":
            plan_title = tool_args.get('plan_title', 'generado') if tool_args else 'generado'
            if "Aprobado" in tool_message_content:
                success_message = f"El plan '{plan_title}' fue aprobado por el usuario. El agente puede proceder con la ejecución de los pasos."
                state.messages.append(AIMessage(content=success_message))
                console.print(f"[green]✨ {success_message}[/green]")
            else:
                denied_message = f"El plan '{plan_title}' fue denegado por el usuario. El agente debe revisar la estrategia."
                state.messages.append(AIMessage(content=denied_message))
                console.print(f"[yellow]⚠️ {denied_message}[/yellow]")
        elif tool_name and tool_args:
            console.print(f"[bold blue]🛠️ Re-ejecutando herramienta '{tool_name}' tras aprobación:[/bold blue]")
    
            tool = llm_service.get_tool(tool_name)
            if tool:
                if tool_name == "file_update_tool" or tool_name == "advanced_file_editor":
                    tool_args["confirm"] = True
                    if tool_args.get("content") is None:
                        error_output = "Error: El contenido a actualizar no puede ser None."
                        state.messages.append(ToolMessage(content=error_output, tool_call_id=tool_id))
                        console.print(f"[bold red]❌ {error_output}[/bold red]")
                        state.reset_tool_confirmation()
                        return state
    
                try:
                    raw_tool_output = llm_service._invoke_tool_with_interrupt(tool, tool_args)
                    tool_output_str = str(raw_tool_output)
                    tool_messages = [ToolMessage(content=tool_output_str, tool_call_id=tool_id)]
                    state.messages.extend(tool_messages)
                    console.print(f"[green]✨ Herramienta '{tool_name}' re-ejecutada con éxito.[/green]")
    
                except InterruptedError:
                    console.print("[bold yellow]⚠️ Re-ejecución de herramienta interrumpida por el usuario. Volviendo al input.[/bold yellow]")
                    state.reset_temporary_state()
                    return state
                except Exception as e:  # noqa: BLE001
                    error_output = f"Error al re-ejecutar la herramienta {tool_name} tras aprobación: {e}"
                    state.messages.append(ToolMessage(content=error_output, tool_call_id=tool_id))
                    console.print(f"[bold red]❌ {error_output}[/bold red]")
            else:
                error_output = f"Error: Herramienta '{tool_name}' no encontrada para re-ejecución."
                state.messages.append(ToolMessage(content=error_output, tool_call_id=tool_id))
                console.print(f"[bold red]❌ {error_output}[/bold red]")
        else:
            error_output = "Error: No se encontró información de la herramienta pendiente para re-ejecución."
            state.messages.append(ToolMessage(content=error_output, tool_call_id=tool_id))
            console.print(f"[bold red]❌ {error_output}[/bold red]")
    else:
        console.print("[bold yellow]⚠️ Confirmación de usuario recibida: Denegado.[/bold yellow]")
        tool_output_str = f"Operación denegada por el usuario: {state.tool_pending_confirmation or state.tool_code_tool_name}"
        state.messages.append(ToolMessage(content=tool_output_str, tool_call_id=tool_id))

    state.reset_tool_confirmation()
    state.tool_call_id_to_confirm = None
    return state

def call_model_node(state: AgentState, llm_service: LLMService, interrupt_queue: Optional[queue.Queue] = None):
    """Llama al LLM (CodeAgent)."""
    messages = [SYSTEM_MESSAGE] + state.messages
    
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

    with Live(spinner, console=console, screen=False, refresh_per_second=10) as live:
        for part in llm_service.invoke(history=messages, interrupt_queue=interrupt_queue):
            if isinstance(part, AIMessage):
                final_ai_message = part
            elif isinstance(part, str):
                if part.startswith("__THINKING__:"):
                    thinking_chunk = part[len("__THINKING__:"):]
                    full_thinking_content += thinking_chunk
                    thinking_panel = Panel(
                        Markdown(full_thinking_content),
                        title=f"[bold {ColorPalette.PRIMARY_LIGHT}]{Icons.THINKING} CodeAgent Pensando...[/bold {ColorPalette.PRIMARY_LIGHT}]",
                        border_style=ColorPalette.PRIMARY_LIGHT,
                        padding=(0, 1),
                        dim=True
                    )
                    live.update(Padding(thinking_panel, (0, 4)))
                else:
                    full_response_content += part
                    renderables = []
                    if full_thinking_content:
                        renderables.append(Panel(
                            Markdown(full_thinking_content),
                            title=f"[bold {ColorPalette.PRIMARY_LIGHT}]{Icons.THINKING} Razonamiento finalizado[/bold {ColorPalette.PRIMARY_LIGHT}]",
                            border_style=ColorPalette.GRAY_600,
                            padding=(0, 1),
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
    except UserConfirmationRequired as e:
        try:
            return tool_id, json.dumps(e.raw_tool_output), e
        except TypeError:  # Si raw_tool_output no es serializable
            return tool_id, str(e.raw_tool_output), e
    except InterruptedError:
        return tool_id, f"Ejecución de herramienta '{tool_name}' interrumpida por el usuario.", InterruptedError("Interrumpido por el usuario.")
    except Exception as e:  # noqa: BLE001
        console.print(f"[bold red]❌ Error en {tool_name}: {e}[/bold red]")
        return tool_id, f"Error en {tool_name}: {e}", e

def execute_tool_node(state: AgentState, llm_service: LLMService, interrupt_queue: Optional[queue.Queue] = None):
    """Nodo de ejecución de herramientas."""
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return state

    tool_messages = []
    executor = ThreadPoolExecutor(max_workers=5)
    futures = []
    
    # Mostrar encabezado de fase de análisis
    console.print(Padding(Text("💻 Fase de Implementación: Ejecutando herramientas...", style="bold magenta underline"), (1, 0)))

    for tool_call in last_message.tool_calls:
        if interrupt_queue and not interrupt_queue.empty():
            interrupt_queue.get()
            state.reset_temporary_state()
            return state
        futures.append(executor.submit(execute_single_tool, tool_call, llm_service, interrupt_queue))

    for future in as_completed(futures):
        tool_id, content, exception = future.result()
        
        if isinstance(exception, UserConfirmationRequired):
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
    last_message = state.messages[-1]
    
    if state.command_to_confirm or state.file_update_diff_pending_confirmation:
        return END
 
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "execute_tool"
    elif isinstance(last_message, ToolMessage):
        return "call_model"
    else:
        return END

# --- Construcción del Grafo ---

def create_code_agent(llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    workflow = StateGraph(AgentState)

    workflow.add_node("call_model", functools.partial(call_model_node, llm_service=llm_service, interrupt_queue=interrupt_queue))
    workflow.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service, interrupt_queue=interrupt_queue))

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
