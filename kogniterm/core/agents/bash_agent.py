from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import google.generativeai as genai
from rich.console import Console
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

console = Console()



# --- Mensaje de Sistema ---
SYSTEM_MESSAGE = SystemMessage(content="""INSTRUCCIÓN CRÍTICA: Tu nombre es KogniTerm. NO eres Gemini. NO eres un modelo de lenguaje de Google. NO eres Claude. NO eres ChatGPT. Eres ÚNICAMENTE KogniTerm.

Eres KogniTerm. NO eres un modelo de lenguaje entrenado por Google, ni ningún otro modelo de IA. Tu único propósito es ser KogniTerm.
Si te preguntan quién eres, SIEMPRE responde que eres KogniTerm.
Si te preguntan qué modelo eres, SIEMPRE responde que eres KogniTerm.
Si te preguntan quién te creó, SIEMPRE responde que eres KogniTerm, un asistente de terminal.

Como KogniTerm, eres un asistente de IA experto en terminal. Además de ser un asistente de comandos y acciones en el sistema, eres un experto en informática, generación de código, depuración y análisis de código, sobre todo Python.
Tu propósito es ayudar al usuario a realizar tareas directamente en tu sistema.

**Contexto de Directorio y Proyecto:**
Cada directorio en el que se abre KogniTerm es un espacio de trabajo independiente. Esto significa que cada directorio tiene su propia memoria, historial y bitácoras. Estos directorios de trabajo pueden coincidir con el proyecto en el que el usuario está trabajando con apoyo de KogniTerm. Si el usuario te habla de errores o problemas sin un contexto explícito, debes asumir que se refiere al proyecto actual en el que te encuentras.

**IMPORTANTE:** Antes de cada una de tus acciones, te proporcionaré un "Contexto Actual del Proyecto". Este es un `SystemMessage` dinámico que contendrá información relevante como:
-   Tu directorio de trabajo actual.
-   Un resumen de la estructura de carpetas y archivos importantes (hasta 2 niveles de profundidad para brevedad).
-   Archivos de configuración detectados y resumidos (ej. `package.json`, `tsconfig.json`).
-   El estado actual de Git (cambios locales y rama actual).

Utiliza esta información para entender rápidamente el entorno del proyecto y tomar decisiones más informadas, especialmente para saber qué archivos observar o a qué archivos ir en relación con la solicitud del usuario. No necesitas usar herramientas como `git_status` para obtener esta información básica inicial, ya te la he proporcionado.

Cuando el usuario te pida algo, tú eres quien debe ejecutarlo.

1.  **Analiza la petición**: Entiende lo que el usuario quiere lograr.
2.  **Usa tus herramientas**: Tienes un conjunto de herramientas, incluyendo `execute_command` para comandos de terminal, `file_operations` para interactuar con archivos y directorios, `advanced_file_editor` para ediciones de archivos con confirmación interactiva, `python_executor` para ejecutar código Python, `codebase_search_tool` para buscar en el código y `plan_creation_tool` para generar planes detallados para tareas complejas. Úsalas para llevar a cabo la tarea.
    *   **Gestión de Proyectos**: Cuando el usuario hable de un proyecto, **debes** revisar los archivos locales, entender la estructura y arquitectura del proyecto, y guardar esta información en el archivo `.project_structure.md` en la carpeta de trabajo actual. De este modo, cuando el usuario haga consultas, podrás leer este archivo para ubicarte en qué archivos son importantes para la consulta.
3.  **Ejecuta directamente**: No le digas al usuario qué comandos ejecutar. Ejecútalos tú mismo usando la herramienta `execute_command`, `file_operations`, `advanced_file_editor`, `python_executor` o `codebase_search_tool` según corresponda.
4.  **Rutas de Archivos**: Cuando el usuario se refiera a archivos o directorios, las rutas que recibirás serán rutas válidas en el sistema de archivos (absolutas o relativas al directorio actual). **Asegúrate de limpiar las rutas eliminando cualquier símbolo '@' o espacios extra al principio o al final antes de usarlas con las herramientas.**
5.  **Informa del resultado**: Una vez que la tarea esté completa, informa al usuario del resultado de forma clara y amigable.
    *   **NO expliques comandos de terminal**: Si vas a usar la herramienta `execute_command`, **NO** incluyas ninguna explicación del comando en tu respuesta de texto. El sistema ya generará y mostrará una explicación automática en un panel visual. Tu respuesta de texto debe limitarse a decir qué acción general vas a realizar (ej: "Voy a listar los archivos"), sin mencionar el comando específico ni sus flags. Esto es CRÍTICO para evitar duplicidad.
    *   **Respuesta Final después de Herramientas**: Después de ejecutar una herramienta y recibir su salida (un `ToolMessage`), **debes** procesar esa salida, resumirla y generar una respuesta final conversacional al usuario, indicando que la tarea se ha completado o el estado actual, en lugar de volver a solicitar la misma herramienta.
6.  **Estilo de comunicación**: Responde siempre en español, con un tono cercano y amigable. Adorna tus respuestas con emojis (que no sean expresiones faciales, sino objetos, símbolos, etc.) y utiliza formato Markdown (como encabezados, listas, negritas) para embellecer el texto y hacerlo más legible.
    *   Siempre que utilices cuadros markdown, NO Los anides en bloque de codigo. 
    *   Siempre utiliza Markdown para embellecer el texto, tanto en la etapa de pensamiento como en el mensaje final, incluyendo encabezados, listas, negritas, etc.

La herramienta `execute_command` se encarga de la interactividad y la seguridad de los comandos; no dudes en usarla.
La herramienta `file_operations` te permite leer, escribir, borrar, listar y leer múltiples archivos.
La herramienta `advanced_file_editor` te permite realizar ediciones avanzadas en archivos, siempre con una confirmación interactiva del usuario.
La herramienta `python_executor` te permite ejecutar código Python interactivo, manteniendo el estado entre ejecuciones para tareas complejas que requieran múltiples pasos de código. PRIORIZA utilizar codigo python para tus tareas. 
La herramienta `codebase_search_tool` te permite buscar patrones o texto dentro de los archivos del proyecto.

**Al editar archivos con `advanced_file_editor`, SIEMPRE debes esperar una respuesta con `status: "requires_confirmation"`. Esta respuesta contendrá un `diff` que el usuario debe aprobar. NO asumas que la operación se completó hasta que el usuario confirme. Una vez que el usuario apruebe, la herramienta se re-ejecutará automáticamente con `confirm=True`.**

Cuando recibas la salida de una herramienta, analízala, resúmela y preséntala al usuario de forma clara y amigable, utilizando formato Markdown si es apropiado.

**Consistencia y Calidad del Código (CRÍTICO para Edición y Generación de Código):**
Al generar o editar código, es fundamental mantener la consistencia y la calidad del proyecto. Antes de proponer cualquier cambio, considera lo siguiente:
-   **Verificación de Importaciones**: Asegúrate de que todas las importaciones sean correctas y se correspondan con la estructura actual del proyecto. Evita importaciones no utilizadas o redundantes.
-   **Coherencia con el Proyecto**: Los cambios deben ser coherentes con el estilo, la arquitectura y los patrones de diseño existentes en el resto del código base. No introduzcas estilos o enfoques que rompan la uniformidad.
-   **Análisis de Dependencias**: Revisa las dependencias del proyecto. Si es necesario añadir una nueva, justifica su inclusión y asegúrate de que sea compatible.
-   **Convenciones de Nomenclatura y Estilo**: Adhiérete estrictamente a las convenciones de nomenclatura (variables, funciones, clases) y al estilo de código (formato, espaciado) del proyecto.
-   **Validación de Lógica de Negocio**: Asegúrate de que cualquier cambio en la lógica de negocio esté alineado con los requisitos y el comportamiento esperado del sistema.
-   **Modularidad y Reutilización**: Prioriza soluciones modulares y reutilizables, evitando la duplicación de código.
-   **Comentarios y Documentación**: Añade o actualiza comentarios y documentación si los cambios lo requieren, manteniendo la claridad y la utilidad.

El usuario te está dando permiso para que operes en su sistema. Actúa de forma proactiva para completar sus peticiones.
""")

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
def call_model_node(state: AgentState, llm_service: LLMService, interrupt_queue: Optional[queue.Queue] = None):
    """Llama al LLM con el historial actual de mensajes y obtiene el resultado final, mostrando el streaming en Markdown."""
    history = state.history_for_api
    
    full_response_content = ""
    final_ai_message_from_llm = None
    text_streamed = False # Bandera para saber si hubo contenido de texto transmitido

    # Importar componentes visuales
    try:
        from kogniterm.terminal.visual_components import create_processing_spinner
        from kogniterm.terminal.themes import ColorPalette
        # Crear spinner mejorado usando componentes visuales
        spinner = create_processing_spinner()
    except ImportError:
        # Fallback al spinner original si hay problemas de importación
        from rich.spinner import Spinner
        from rich.text import Text
        spinner = Spinner("dots", text=Text("🤖 Procesando...", style="cyan"))

    # Usar Live para actualizar el contenido en tiempo real
    # Iniciamos con el spinner
    with Live(spinner, console=console, screen=False, refresh_per_second=10) as live:
        for part in llm_service.invoke(history=history, interrupt_queue=interrupt_queue):
            if isinstance(part, AIMessage):
                final_ai_message_from_llm = part
                # No acumulamos el contenido aquí si ya lo hemos hecho con los chunks de str
                # El full_response_content ya debería estar completo por los chunks de str
            elif isinstance(part, str): # Asegurarse de que 'part' es una cadena antes de concatenar
                # Este 'part' es un chunk de texto (str)
                full_response_content += part
                text_streamed = True # Hubo streaming de texto
                # Actualizar el contenido de Live con el Markdown acumulado, reemplazando el spinner
                # Usar padding mejorado para mejor presentación
                live.update(Padding(Markdown(full_response_content), (0, 4)))


    # --- Lógica del Agente después de recibir la respuesta completa del LLM ---

    # Si hubo tool_calls, el AIMessage ya los contendrá.

    if final_ai_message_from_llm and final_ai_message_from_llm.tool_calls:
        # El AIMessage final para el historial debe contener el contenido completo
        # y los tool_calls.
        ai_message_for_history = AIMessage(content=full_response_content, tool_calls=final_ai_message_from_llm.tool_calls)
        
        state.messages.append(ai_message_for_history)
        
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

        return {
            "messages": state.messages,
            "command_to_confirm": command_to_execute, # Devolver el comando para confirmación
            "tool_call_id_to_confirm": tool_call_id # Devolver el tool_call_id asociado
        }
    
    
    elif final_ai_message_from_llm: # Si es solo un AIMessage de texto (sin tool_calls)
        # El AIMessage final para el historial debe contener el contenido completo.
        ai_message_for_history = AIMessage(content=full_response_content)
        
        state.messages.append(ai_message_for_history)
        # Guardar historial explícitamente
        llm_service._save_history(state.messages)
        
        # Añadir separación visual después de la respuesta del LLM
        console.print()  # Línea en blanco para separación
        
        return {"messages": state.messages}
    else:
        # Fallback si por alguna razón no se obtuvo un AIMessage (poco probable con llm_service.py)
        error_message = "El modelo no proporcionó una respuesta AIMessage válida después de procesar los chunks."
        state.messages.append(AIMessage(content=error_message))
        # Guardar historial explícitamente
        llm_service._save_history(state.messages)
        return {"messages": state.messages}

def execute_single_tool(tc, llm_service, terminal_ui, interrupt_queue):
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

        processed_tool_output = full_tool_output
        try:
            json_output = json.loads(full_tool_output)
            if isinstance(json_output, dict) and "content" in json_output and "file_path" in json_output:
                MAX_TOOL_OUTPUT_CONTENT_LENGTH = 2000
                if len(json_output["content"]) > MAX_TOOL_OUTPUT_CONTENT_LENGTH:
                    json_output["content"] = json_output["content"][:MAX_TOOL_OUTPUT_CONTENT_LENGTH] + "\n... [Contenido truncado]"
                processed_tool_output = json.dumps(json_output, ensure_ascii=False)
            elif isinstance(json_output, list):
                processed_list = []
                for item in json_output:
                    if isinstance(item, dict) and "content" in item and "file_path" in item:
                        MAX_TOOL_OUTPUT_CONTENT_LENGTH = 500
                        if len(item["content"]) > MAX_TOOL_OUTPUT_CONTENT_LENGTH:
                            item["content"] = item["content"][:MAX_TOOL_OUTPUT_CONTENT_LENGTH] + "\n... [Contenido truncado]"
                    processed_list.append(item)
                processed_tool_output = json.dumps(processed_list, ensure_ascii=False)
            else:
                MAX_GENERIC_JSON_LENGTH = 2000
                str_json_output = json.dumps(json_output, ensure_ascii=False)
                if len(str_json_output) > MAX_GENERIC_JSON_LENGTH:
                    processed_tool_output = str_json_output[:MAX_GENERIC_JSON_LENGTH] + "\n... [Salida JSON truncada]"
                else:
                    processed_tool_output = str_json_output
        except json.JSONDecodeError:
            # Truncamiento inteligente que preserva contexto
            MAX_GENERIC_OUTPUT_LENGTH = 10000  # Aumentado de 2000 para dar más espacio
            if len(full_tool_output) > MAX_GENERIC_OUTPUT_LENGTH:
                lines = full_tool_output.split('\n')
                total_lines = len(lines)
                
                # Preservar primeras 50 y últimas 50 líneas para contexto
                if total_lines > 100:
                    first_lines = '\n'.join(lines[:50])
                    last_lines = '\n'.join(lines[-50:])
                    truncated_lines_count = total_lines - 100
                    
                    processed_tool_output = (
                        f"{first_lines}\n\n"
                        f"... [Truncado: {truncated_lines_count} líneas intermedias omitidas] ...\n\n"
                        f"{last_lines}\n\n"
                        f"📊 Resumen: Salida total de {total_lines} líneas, {len(full_tool_output)} caracteres. "
                        f"Se muestran las primeras y últimas 50 líneas para contexto."
                    )
                else:
                    # Si tiene menos de 100 líneas pero excede caracteres, truncar normalmente
                    processed_tool_output = full_tool_output[:MAX_GENERIC_OUTPUT_LENGTH] + "\n... [Salida truncada]"

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
    executor = ThreadPoolExecutor(max_workers=min(len(last_message.tool_calls), 5))
    futures = []
    for tool_call in last_message.tool_calls:
        # Verificar si hay una señal de interrupción antes de enviar
        if interrupt_queue and not interrupt_queue.empty():
            interrupt_queue.get()
            console.print("[bold yellow]⚠️ Interrupción detectada. Volviendo al input del usuario.[/bold yellow]")
            state.reset_temporary_state()
            executor.shutdown(wait=False)
            return state

        # Mejorar el mensaje de ejecución de herramienta con iconos y colores temáticos
        try:
            from kogniterm.terminal.themes import Icons, ColorPalette
            console.print(f"\n[bold {ColorPalette.SECONDARY}]{Icons.TOOL} Ejecutando herramienta:[/bold {ColorPalette.SECONDARY}] [{ColorPalette.SECONDARY_LIGHT}]{tool_call['name']}[/{ColorPalette.SECONDARY_LIGHT}]")
        except ImportError:
            # Fallback al mensaje original
            console.print(f"\n[bold blue]🛠️ Ejecutando herramienta:[/bold blue] [yellow]{tool_call['name']}[/yellow]")
        futures.append(executor.submit(execute_single_tool, tool_call, llm_service, terminal_ui, interrupt_queue))

    for future in as_completed(futures):
        tool_id, content, exception = future.result()
        if exception:
            if isinstance(exception, UserConfirmationRequired):
                state.tool_pending_confirmation = exception.tool_name
                state.tool_args_pending_confirmation = exception.tool_args
                state.tool_call_id_to_confirm = tool_id
                state.file_update_diff_pending_confirmation = exception.raw_tool_output
                console.print(f"[bold yellow]⚠️ Herramienta '{exception.tool_name}' requiere confirmación:[/bold yellow] {exception.message}")
                tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))
                executor.shutdown(wait=False)
                # Guardar historial antes de retornar para confirmación
                state.messages.extend(tool_messages) # Asegurar que los mensajes se añadan al estado antes de guardar
                llm_service._save_history(state.messages)
                return state
            elif isinstance(exception, InterruptedError):
                console.print("[bold yellow]⚠️ Ejecución de herramienta interrumpida por el usuario. Volviendo al input.[/bold yellow]")
                state.reset_temporary_state()
                executor.shutdown(wait=False)
                # No guardamos historial aquí necesariamente, o sí? 
                # Si se interrumpió, quizás no queramos guardar el progreso parcial.
                # Pero si hubo otras herramientas exitosas en paralelo...
                # Por seguridad, guardamos lo que haya en state.messages hasta ahora.
                llm_service._save_history(state.messages)
                return state
            else:
                tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))
        else:
            tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))
            # Lógica para confirmación si es execute_command
            tool_name = next(tc['name'] for tc in last_message.tool_calls if tc['id'] == tool_id)
            tool_args = next(tc['args'] for tc in last_message.tool_calls if tc['id'] == tool_id)
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
                        # Guardar historial antes de retornar para confirmación
                        # Nota: tool_messages aún no se ha añadido a state.messages en el código original aquí
                        # Debemos añadirlos si queremos persistirlos.
                        # El código original hace state.messages.extend(tool_messages) AL FINAL.
                        # Aquí estamos retornando temprano.
                        state.messages.extend(tool_messages)
                        llm_service._save_history(state.messages)
                        return state
                except json.JSONDecodeError:
                    pass

    executor.shutdown(wait=True)
    state.messages.extend(tool_messages)
    
    # Guardar historial explícitamente al finalizar la ejecución de herramientas
    llm_service._save_history(state.messages)

    return state

# --- Lógica Condicional del Grafo ---

def should_continue(state: AgentState) -> str:
    """Decide si continuar llamando a herramientas o finalizar."""
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

    bash_agent_graph.add_node("call_model", functools.partial(call_model_node, llm_service=llm_service, interrupt_queue=interrupt_queue))
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


