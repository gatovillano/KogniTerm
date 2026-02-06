import asyncio
from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import google.genai as genai
from rich.console import Console, Group
from rich.panel import Panel
import functools
from langchain_core.runnables import RunnableConfig # Nueva importación
from rich.markup import escape # Nueva importación
import sys # Nueva importación
import json # Importar json para verificar si la salida es un JSON
import queue # Importar el módulo queue
from concurrent.futures import ThreadPoolExecutor, as_completed # Nueva importación para paralelización

from ..llm_service import LLMService
from kogniterm.terminal.terminal_ui import TerminalUI
from kogniterm.core.agent_state import AgentState # Importar AgentState desde el archivo consolidado
from kogniterm.terminal.keyboard_handler import KeyboardHandler # Importar KeyboardHandler
from ..async_io_manager import get_io_manager, AsyncTaskResult

console = Console()



# --- Mensaje de Sistema ---
def get_system_message(llm_service: LLMService) -> SystemMessage:
    base_content = """INSTRUCCIÓN CRÍTICA: Tu nombre es KogniTerm. Eres un asistente experto de terminal.

**Tus Principios:**
1.  **Eres KogniTerm**: Experto en terminal, depuración y Python.
2.  **Contexto**: Utiliza el "Contexto Actual del Proyecto" que recibes para ubicarte.
3.  **Autonomía**: Tú ejecutas los comandos. No le pidas al usuario que lo haga.
4.  **Seguridad**: Usa `execute_command` para comandos de shell.
5.  **Investigación**: Usa `codebase_search_tool` para entender el código antes de tocarlo.
6.  **Edición**: Usa `advanced_file_editor`. SIEMPRE lee el archivo primero.
7.  **Comunicación**: Sé conciso, amigable y usa Markdown. NO expliques comandos de terminal obvios.
8.  **Agentes Especializados**:
    - Si te piden "investigar" a fondo o crear informes -> `call_agent(agent_name="researcher_agent", ...)`
    - Si te piden "desarrollar" características complejas o refactorizar -> `call_agent(agent_name="code_agent", ...)`
"""
    
    # Solo añadir la instrucción de pensar si el modelo NO es de razonamiento nativo
    if not llm_service.is_thinking_model():
        base_content += "\nRecuerda: ¡PIENSA ANTES DE ACTUAR!\n"
    
    return SystemMessage(content=base_content)

# Para mantener compatibilidad con imports si los hay, aunque ahora usaremos la función
SYSTEM_MESSAGE = get_system_message(LLMService(use_multi_provider=False)) if 'LLMService' in globals() else None

from kogniterm.core.exceptions import UserConfirmationRequired # Importación correcta

# --- Nodos del Grafo ---

from rich.live import Live # Importar Live
from rich.markdown import Markdown # Importar Markdown
from rich.padding import Padding # Nueva importación
from rich.status import Status # ¡Nueva importación!
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

    # Asumimos que el ToolMessage de confirmación tiene un formato específico
    # ej. "Confirmación de usuario: Aprobado para 'escribir en el archivo ...'".
    if "Aprobado" in tool_message_content:
        console.print("[bold green]✅ Confirmación de usuario recibida: Aprobado.[/bold green]")
        tool_name = state.tool_pending_confirmation
        tool_args = state.tool_args_pending_confirmation
    
        if tool_name == "plan_creation_tool":
            if "Aprobado" in tool_message_content:
                success_message = f"El plan '{tool_args.get('plan_title', 'generado')}' fue aprobado por el usuario. El agente puede proceder con la ejecución de los pasos."
                state.messages.append(AIMessage(content=success_message))
                console.print(f"[green]✨ {success_message}[/green]")
            else:
                denied_message = f"El plan '{tool_args.get('plan_title', 'generado')}' fue denegado por el usuario. El agente debe revisar la estrategia."
                state.messages.append(AIMessage(content=denied_message))
                console.print(f"[yellow]⚠️ {denied_message}[/yellow]")
        elif tool_name and tool_args:
            console.print(f"[bold blue]🛠️ Re-ejecutando herramienta '{tool_name}' tras aprobación:[/bold blue]")
    
            tool = llm_service.get_tool(tool_name)
            if tool:
                # Si es file_update_tool o advanced_file_editor_tool, añadir el parámetro confirm=True
                if tool_name == "file_update_tool" or tool_name == "advanced_file_editor":
                    tool_args["confirm"] = True
                    # Si el contenido original se pasó como parte de tool_args,
                    # debemos asegurarnos de que el 'content' que se pasa para la re-ejecución
                    # sea el contenido final que el usuario aprobó (que debería estar en tool_args).
                    # No necesitamos el diff aquí, solo el contenido final.
                    # El diff ya se mostró al usuario para la confirmación.
                    # Si el content es None, significa que el LLM no lo proporcionó, lo cual es un error.
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
                    state.reset_temporary_state() # Limpiar el estado temporal del agente
                    return state # Terminar la ejecución de herramientas y volver al input del usuario
                except Exception as e:
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

    state.reset_tool_confirmation() # Limpiar el estado de confirmación
    state.tool_call_id_to_confirm = None # Limpiar también el tool_call_id guardado
    return state

def call_model_node(state: AgentState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None, interrupt_queue: Optional[queue.Queue] = None):

    """
    Llama al modelo de lenguaje y maneja la salida en streaming,
    mostrando el pensamiento y la respuesta en tiempo real.
    """
    # Usar la consola de terminal_ui si está disponible, de lo contrario usar la global
    current_console = terminal_ui.console if terminal_ui else console
    
    # --- Lógica de Detección de Bucles ---
    if len(state.tool_call_history) >= 4:
        last_calls = list(state.tool_call_history)[-4:]
        if all(tc['name'] == last_calls[0]['name'] and tc['args_hash'] == last_calls[0]['args_hash'] for tc in last_calls):
            current_console.print("[bold red]🚨 ¡BUCLE CRÍTICO DETECTADO! El agente está repitiendo la misma acción exactamente.[/bold red]")
            error_msg = "He detectado que estoy en un bucle infinito repitiendo la misma acción. Deteniendo para evitar consumo innecesario. Por favor, intenta reformular tu petición o revisa los logs."
            state.messages.append(AIMessage(content=error_msg))
            # Activar la bandera de bucle crítico para terminar el flujo
            state.critical_loop_detected = True
            # Limpiar el historial de llamadas a herramientas para evitar que la advertencia se repita
            state.clear_tool_call_history()
            return {
                "messages": state.messages,
                "command_to_confirm": None,
                "tool_call_id_to_confirm": None,
                "critical_loop_detected": True
            }

    history = [get_system_message(llm_service)] + state.messages
    full_response_content = ""
    full_thinking_content = ""
    final_ai_message_from_llm = None
    text_streamed = False 

    # Importar componentes visuales
    try:
        from kogniterm.terminal.visual_components import create_processing_spinner, create_thinking_spinner, create_thought_bubble
        from kogniterm.terminal.themes import ColorPalette, Icons
        # Crear spinner mejorado usando componentes visuales
        spinner = create_processing_spinner()
    except ImportError:
        # Fallback al spinner original si hay problemas de importación
        from rich.spinner import Spinner
        from rich.text import Text
        spinner = Spinner("dots", text=Text("🤖 Procesando...", style="cyan"))
        # Definir fallbacks para evitar NameError
        class ColorPalette:
            PRIMARY_LIGHT = "cyan"
            SECONDARY = "blue"
            SECONDARY_LIGHT = "yellow"
            TEXT_SECONDARY = "grey"
            GRAY_600 = "grey"
        class Icons:
            THINKING = "🤔"
            TOOL = "🛠️"
        
        def create_thought_bubble(content, title="Pensando...", icon="🤔", color="cyan"):
            from rich.panel import Panel
            from rich.markdown import Markdown
            from rich.padding import Padding
            if isinstance(content, str):
                content = Markdown(content)
            return Padding(Panel(content, title=f"{icon} {title}", border_style=f"dim {color}"), (1, 4))

    # Usar Live para actualizar el contenido en tiempo real
    # Iniciamos con el spinner
    
    # Iniciar KeyboardHandler para detectar ESC durante la generación
    kh = KeyboardHandler(interrupt_queue)
    kh.start()
    
    try:
        with Live(spinner, console=current_console, screen=False, refresh_per_second=10) as live:
            def update_live_display():
                """Función auxiliar para actualizar el display de forma consistente."""
                renderables = []
                
                # 1. Mostrar pensamiento si existe
                if full_thinking_content:
                    renderables.append(create_thought_bubble(full_thinking_content, title="KogniTerm Pensando..."))
                
                # 2. Añadir respuesta si existe
                if full_response_content:
                    renderables.append(Markdown(full_response_content))
                
                # 3. Si no hay nada aún, mostrar el spinner inicial
                if not renderables:
                    live.update(spinner)
                else:
                    # Envolver en Padding para añadir margen lateral (sangría)
                    live.update(Padding(Group(*renderables), (0, 4)))

            interrupcion_detectada = False
            for part in llm_service.invoke(history=history, interrupt_queue=interrupt_queue):
                if isinstance(part, AIMessage):
                    final_ai_message_from_llm = part
                elif isinstance(part, str):
                    if part.startswith("__THINKING__:"):
                        # Es contenido de razonamiento (Thinking)
                        thinking_chunk = part[len("__THINKING__:"):]
                        full_thinking_content += thinking_chunk
                        update_live_display()
                    else:
                        # Es contenido normal de la respuesta
                        full_response_content += part
                        text_streamed = True
                        update_live_display()
                
                # Verificar interrupción en cada iteración del streaming
                # Chequeamos tanto la cola como la bandera del servicio
                if (interrupt_queue and not interrupt_queue.empty()) or llm_service.stop_generation_flag:
                    interrupcion_detectada = True
                    if interrupt_queue:
                        while not interrupt_queue.empty():
                            interrupt_queue.get_nowait()
                    break
            
            if interrupcion_detectada:
                current_console.print(f"\n{Icons.STOPWATCH} [bold red]Interrupción detectada. Deteniendo...[/bold red]")
            
            # Al finalizar el stream, asegurarnos de que el display final sea correcto
            # Si no hubo streaming de texto (e.g. error o respuesta no chunked), forzar actualización con el mensaje final
            if final_ai_message_from_llm and not text_streamed and final_ai_message_from_llm.content:
                full_response_content = final_ai_message_from_llm.content
                update_live_display()
            else:
                update_live_display()
    finally:
        kh.stop()


    # --- Lógica del Agente después de recibir la respuesta completa del LLM ---

    # Usar directamente el AIMessage del LLMService para evitar duplicación de contenido
    if final_ai_message_from_llm:
        state.messages.append(final_ai_message_from_llm)

        # Si la herramienta es 'execute_command', establecemos command_to_confirm
        command_to_execute = None
        tool_call_id = None # Inicializar tool_call_id
        if final_ai_message_from_llm.tool_calls:
            # Siempre capturar el tool_call_id del primer tool_call si existe
            tool_call_id = final_ai_message_from_llm.tool_calls[0]['id']

            for tc in final_ai_message_from_llm.tool_calls:
                if tc['name'] == 'execute_command':
                    command_to_execute = tc['args'].get('command')
                    break # Asumimos una sola llamada a comando por ahora

        # Guardar historial explícitamente para asegurar sincronización con LLMService
        llm_service._save_history(state.messages)

        # Añadir separación visual después de la respuesta del LLM
        console.print()  # Línea en blanco para separación

        return {
            "messages": state.messages,
            "command_to_confirm": command_to_execute, # Devolver el comando para confirmación
            "tool_call_id_to_confirm": tool_call_id # Devolver el tool_call_id asociado
        }
    else:
        # Fallback si por alguna razón no se obtuvo un AIMessage (poco probable con llm_service.py)
        error_message = "El modelo no proporcionó una respuesta AIMessage válida después de procesar los chunks."
        state.messages.append(AIMessage(content=error_message))
        # Guardar historial explícitamente
        llm_service._save_history(state.messages)
        return {"messages": state.messages}

async def execute_single_tool_async(tc, llm_service, terminal_ui, interrupt_queue):
    """
    Versión asíncrona de execute_single_tool.
    Ejecuta la herramienta en un thread separado para no bloquear.
    """
    tool_name = tc['name']
    tool_args = tc['args']
    tool_id = tc['id']

    tool = llm_service.get_tool(tool_name)
    if not tool:
        return tool_id, f"Error: Herramienta '{tool_name}' no encontrada.", None

    try:
        io_manager = get_io_manager()
        
        # Función síncrona que se ejecutará en el executor
        def run_tool_sync():
            full_tool_output = ""
            tool_output_generator = llm_service._invoke_tool_with_interrupt(tool, tool_args)

            for chunk in tool_output_generator:
                full_tool_output += str(chunk)

            return full_tool_output
        
        # Ejecutar de forma asíncrona
        result = io_manager.run_in_executor(run_tool_sync)
        
        if result.success:
            return tool_id, result.result, None
        else:
            return tool_id, f"Error al ejecutar la herramienta {tool_name}: {result.error}", Exception(result.error)
            
    except UserConfirmationRequired as e:
        return tool_id, json.dumps(e.raw_tool_output), e
    except InterruptedError:
        return tool_id, f"Ejecución de herramienta '{tool_name}' interrumpida por el usuario.", InterruptedError("Interrumpido por el usuario.")
    except Exception as e:
        return tool_id, f"Error al ejecutar la herramienta {tool_name}: {e}", e


def execute_single_tool(tc, llm_service, terminal_ui, interrupt_queue):
    """Versión síncrona para compatibilidad."""
    tool_name = tc['name']
    tool_args = tc['args']
    tool_id = tc['id']

    tool = llm_service.get_tool(tool_name)
    if not tool:
        return tool_id, f"Error: Herramienta '{tool_name}' no encontrada.", None

    try:
        full_tool_output = ""
        tool_output_generator = llm_service._invoke_tool_with_interrupt(tool, tool_args)

        for chunk in tool_output_generator:
            # NO imprimir aquí - el output ya se muestra en command_approval_handler.py
            # if tool_name == "execute_command":
            #     terminal_ui.print_stream(str(chunk))
            full_tool_output += str(chunk)

        # Sin truncamiento - devolver la salida completa tal cual
        processed_tool_output = full_tool_output

        return tool_id, processed_tool_output, None
    except UserConfirmationRequired as e:
        return tool_id, json.dumps(e.raw_tool_output), e
    except InterruptedError:
        return tool_id, f"Ejecución de herramienta '{tool_name}' interrumpida por el usuario.", InterruptedError("Interrumpido por el usuario.")
    except Exception as e:
        return tool_id, f"Error al ejecutar la herramienta {tool_name}: {e}", e

def execute_tool_node(state: AgentState, llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    """Ejecuta las herramientas solicitadas por el modelo."""
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return state

    tool_messages = []
    
    # Iniciar KeyboardHandler si no hay herramientas interactivas (como execute_command)
    # execute_command ya maneja su propia interactividad y detección de ESC.
    has_interactive_tool = any(tc['name'] == 'execute_command' for tc in last_message.tool_calls)
    kh = None
    if not has_interactive_tool:
        kh = KeyboardHandler(interrupt_queue)
        kh.start()
        
    try:
        executor = ThreadPoolExecutor(max_workers=min(len(last_message.tool_calls), 5))
        futures = []
        for tool_call in last_message.tool_calls:
            # Registrar la llamada a la herramienta en el historial para detección de bucles
            tool_name = tool_call['name']
            tool_args = tool_call['args']
            
            # Generar un hash consistente de los argumentos
            try:
                args_hash = json.dumps(tool_args, sort_keys=True)
            except TypeError:
                args_hash = str(tool_args) # Fallback si los argumentos no son serializables
            
            state.tool_call_history.append({"name": tool_name, "args_hash": args_hash})

            # Verificar si hay una señal de interrupción antes de enviar
            if interrupt_queue and not interrupt_queue.empty():
                interrupt_queue.get()
                terminal_ui.console.print("[bold yellow]⚠️ Interrupción detectada. Volviendo al input del usuario.[/bold yellow]")
                state.reset_temporary_state()
                executor.shutdown(wait=False)
                return state

            # Obtener la instancia de la herramienta para buscar la descripción de la acción
            tool = llm_service.get_tool(tool_call['name'])
            bajada = ""
            if tool and hasattr(tool, 'get_action_description'):
                try:
                    bajada = tool.get_action_description(**tool_call['args'])
                except Exception as e:
                    logger.warning(f"Error al obtener descripción de acción para {tool_call['name']}: {e}")

            # Mejorar el mensaje de ejecución de herramienta con iconos y colores temáticos
            try:
                from kogniterm.terminal.themes import Icons, ColorPalette
                terminal_ui.console.print(f"\n[bold {ColorPalette.SECONDARY}]{Icons.TOOL} Ejecutando herramienta:[/bold {ColorPalette.SECONDARY}] [{ColorPalette.SECONDARY_LIGHT}]{tool_call['name']}[/{ColorPalette.SECONDARY_LIGHT}]")
                if bajada:
                    terminal_ui.console.print(f"[italic {ColorPalette.TEXT_SECONDARY}]   └─ {bajada}[/italic {ColorPalette.TEXT_SECONDARY}]")
            except ImportError:
                # Fallback al mensaje original
                terminal_ui.console.print(f"\n[bold blue]🛠️ Ejecutando herramienta:[/bold blue] [yellow]{tool_call['name']}[/yellow]")
                if bajada:
                    terminal_ui.console.print(f"[italic grey]   └─ {bajada}[/italic grey]")
            futures.append(executor.submit(execute_single_tool, tool_call, llm_service, terminal_ui, interrupt_queue))

        for future in as_completed(futures):
            tool_id, content, exception = future.result()
            if exception:
                if isinstance(exception, UserConfirmationRequired):
                    state.tool_pending_confirmation = exception.tool_name
                    state.tool_args_pending_confirmation = exception.tool_args
                    state.tool_call_id_to_confirm = tool_id
                    state.file_update_diff_pending_confirmation = exception.raw_tool_output
                    terminal_ui.console.print(f"[bold yellow]⚠️ Herramienta '{exception.tool_name}' requiere confirmación:[/bold yellow] {exception.message}")
                    tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))
                    executor.shutdown(wait=False)
                    # Guardar historial antes de retornar para confirmación
                    state.messages.extend(tool_messages)
                    llm_service._save_history(state.messages)
                    return {
                        "messages": state.messages,
                        "tool_pending_confirmation": state.tool_pending_confirmation,
                        "tool_args_pending_confirmation": state.tool_args_pending_confirmation,
                        "tool_call_id_to_confirm": state.tool_call_id_to_confirm,
                        "file_update_diff_pending_confirmation": state.file_update_diff_pending_confirmation
                    }
                elif isinstance(exception, InterruptedError):
                    terminal_ui.console.print("[bold yellow]⚠️ Ejecución de herramienta interrumpida por el usuario. Volviendo al input.[/bold yellow]")
                    state.reset_temporary_state()
                    executor.shutdown(wait=False)
                    llm_service._save_history(state.messages)
                    return {
                        "messages": state.messages,
                        "command_to_confirm": None,
                        "tool_call_id_to_confirm": None
                    }
                else:
                    tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))
            else:
                tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))
                # Lógica para confirmación si es execute_command
                tool_call_info = next(tc for tc in last_message.tool_calls if tc['id'] == tool_id)
                tool_name = tool_call_info['name']
                tool_args = tool_call_info['args']
                if tool_name == "execute_command":
                    state.command_to_confirm = tool_args['command']
                    state.tool_call_id_to_confirm = tool_id
                else:
                    # Lógica para herramientas que requieren confirmación
                    try:
                        json_output = json.loads(content)
                        should_confirm = False
                        confirmation_data = None
                        if isinstance(json_output, list) and all(isinstance(item, dict) for item in json_output):
                            for item in json_output:
                                if item.get("status") == "requires_confirmation":
                                    should_confirm = True
                                    confirmation_data = item
                                    break
                        elif isinstance(json_output, dict):
                            if json_output.get("status") == "requires_confirmation":
                                should_confirm = True
                                confirmation_data = json_output
                        if should_confirm and confirmation_data:
                            state.file_update_diff_pending_confirmation = confirmation_data
                            state.tool_pending_confirmation = tool_name
                            state.tool_args_pending_confirmation = tool_args
                            state.tool_call_id_to_confirm = tool_id
                            executor.shutdown(wait=False)
                            state.messages.extend(tool_messages)
                            llm_service._save_history(state.messages)
                            return {
                                "messages": state.messages,
                                "tool_pending_confirmation": state.tool_pending_confirmation,
                                "tool_args_pending_confirmation": state.tool_args_pending_confirmation,
                                "tool_call_id_to_confirm": state.tool_call_id_to_confirm,
                                "file_update_diff_pending_confirmation": state.file_update_diff_pending_confirmation
                            }
                    except json.JSONDecodeError:
                        pass

        executor.shutdown(wait=True)
        state.messages.extend(tool_messages)
        
        # Guardar historial explícitamente al finalizar la ejecución de herramientas
        llm_service._save_history(state.messages)

    finally:
        if kh:
            kh.stop()

    return {
        "messages": state.messages,
        "command_to_confirm": getattr(state, 'command_to_confirm', None),
        "tool_call_id_to_confirm": getattr(state, 'tool_call_id_to_confirm', None),
        "file_update_diff_pending_confirmation": getattr(state, 'file_update_diff_pending_confirmation', None)
    }

# --- Lógica Condicional del Grafo ---

def should_continue(state: AgentState) -> str:
    """Decide si continuar llamando a herramientas o finalizar."""
    # Si se detectó un bucle crítico, terminar el flujo inmediatamente
    if state.critical_loop_detected:
        return END
    
    last_message = state.messages[-1]
    
    # Si hay un comando pendiente de confirmación, siempre terminamos el grafo aquí
    # para que la terminal lo maneje.
    if state.command_to_confirm or state.file_update_diff_pending_confirmation:
        return END

    # Si el último mensaje del AI tiene tool_calls, ejecutar herramientas
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "execute_tool"
    # Si el último mensaje es un ToolMessage (resultado de una herramienta),
    # volver a llamar al modelo para que genere una respuesta final.
    elif isinstance(last_message, ToolMessage):
        return "call_model"
    else:
        return END

# --- Construcción del Grafo ---

def create_bash_agent(llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    bash_agent_graph = StateGraph(AgentState)

    bash_agent_graph.add_node("call_model", functools.partial(call_model_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))
    bash_agent_graph.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))

    bash_agent_graph.set_entry_point("call_model")

    bash_agent_graph.add_conditional_edges(
        "call_model",
        should_continue,
        {
            "execute_tool": "execute_tool",
            END: END
        }
    )

    bash_agent_graph.add_edge("execute_tool", "call_model")

    return bash_agent_graph.compile()


