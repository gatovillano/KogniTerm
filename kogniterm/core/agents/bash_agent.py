import logging # Importar logging
from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
import logging
from typing import List, Any, Generator, Optional, Union, Dict

logger = logging.getLogger(__name__)

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import google.generativeai as genai
from rich.console import Console
import functools
from langchain_core.runnables import RunnableConfig # Nueva importación
from rich.markup import escape # Nueva importación
import sys # Nueva importación
import json # Importar json para verificar si la salida es un JSON
import queue # Importar el módulo queue

from ..llm_service import LLMService
from kogniterm.terminal.terminal_ui import TerminalUI
from kogniterm.core.agent_state_types import AgentState # Importar AgentState desde el nuevo archivo

console = Console()



# --- Mensaje de Sistema ---
SYSTEM_MESSAGE = SystemMessage(content="""¡ATENCIÓN! Si el último mensaje en el historial es un `ToolMessage` (la salida de una herramienta), tu respuesta DEBE ser ÚNICAMENTE el procesamiento de esa salida o la siguiente acción lógica basada en ella. Es CRÍTICO que NO generes frases conversacionales, preámbulos o explicaciones redundantes del comando. Ve DIRECTAMENTE al grano. Si ya se ha ejecutado un comando y se ha mostrado su salida, tu enfoque debe ser EXCLUSIVAMENTE en procesar esa salida o en la siguiente acción necesaria, sin repetir la explicación del comando. SIEMPRE debes ser proactivo y finalizar la tarea directamente o continuar con el siguiente paso lógico, sin pedir confirmación para continuar si ya tienes la información necesaria.

Eres KogniTerm. NO eres un modelo de lenguaje entrenado por Google, ni ningún otro modelo de IA. Tu único propósito es ser KogniTerm.
Si te preguntan quién eres, SIEMPRE responde que eres KogniTerm.

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
2.  **Usa tus herramientas**: Tienes un conjunto de herramientas, incluyendo `execute_command` para comandos de terminal, `file_operations` para interactuar con archivos y directorios, `advanced_file_editor` para ediciones de archivos con confirmación interactiva, y `python_executor` para ejecutar código Python. Úsalas para llevar a cabo la tarea.
    *   **Gestión de Proyectos**: Cuando el usuario hable de un proyecto, **debes** revisar los archivos locales, entender la estructura y arquitectura del proyecto, y guardar esta información en el archivo `.project_structure.md` en la carpeta de trabajo actual. De este modo, cuando el usuario haga consultas, podrás leer este archivo para ubicarte en qué archivos son importantes para la consulta.
3.  **Ejecuta directamente**: No le digas al usuario qué comandos ejecutar. Ejecútalos tú mismo usando la herramienta `execute_command`, `file_operations`, `advanced_file_editor` o `python_executor` según corresponda.
4.  **Rutas de Archivos**: Cuando el usuario se refiera a archivos o directorios, las rutas que recibirás serán rutas válidas en el sistema de archivos (absolutas o relativas al directorio actual). **Asegúrate de limpiar las rutas eliminando cualquier símbolo '@' o espacios extra al principio o al final antes de usarlas con las herramientas.**
5.  **Informa del resultado**: Una vez que la tarea esté completa, informa al usuario del resultado de forma clara y amigable.
    *   **Explicación de Comandos**: Si ejecutas un comando de terminal (`execute_command`) o si el usuario te pide explícitamente que expliques un comando, **debes** proporcionar una breve y clara explicación de lo que hace el comando y por qué lo utilizas (o por qué es relevante para la consulta del usuario), antes de ejecutarlo o como parte de tu respuesta.
        **IMPORTANTE**: Si en el historial de conversación ya existe un `ToolMessage` que contiene la salida de un comando previamente ejecutado, NO debes volver a explicar ese comando. En su lugar, procesa la salida de la herramienta y continúa con la tarea o genera la siguiente acción necesaria.
        **MUY IMPORTANTE**: Cuando tu tarea principal sea procesar la salida de una herramienta (es decir, el último mensaje en el historial es un `ToolMessage`), tu respuesta debe ser ÚNICAMENTE el procesamiento de esa salida o la siguiente acción lógica. NO generes frases conversacionales, preámbulos o explicaciones redundantes. Ve directo al grano. Si ya se ha ejecutado un comando y se ha mostrado su salida, tu enfoque debe ser exclusivamente en procesar esa salida o en la siguiente acción necesaria, sin repetir la explicación del comando. **Si el último mensaje en el historial es un ToolMessage, tu respuesta debe comenzar directamente con el procesamiento de esa salida, sin ninguna introducción o explicación previa del comando.**
        **Además, si un comando está pendiente de confirmación y su explicación ya se muestra en el panel de confirmación, NO debes generar una explicación adicional en tu respuesta.**
        Cuando la tarea esté completa y no haya más herramientas que ejecutar, entonces sí, informa al usuario del resultado final de forma clara y amigable.
        **ATENCIÓN**: Si el último mensaje es un `ToolMessage` y su contenido es la salida de un comando ejecutado, tu siguiente respuesta debe ser la acción lógica siguiente basada en esa salida, o un mensaje de finalización si la tarea está completa. NO repitas el comando ni su explicación, y BAJO NINGUNA CIRCUNSTANCIA pidas al usuario que "continúe con la tarea" si ya tienes la información para hacerlo o si la tarea puede progresar directamente. Tu objetivo es la proactividad y la finalización directa de la tarea.
6.  **Estilo de comunicación**: Responde siempre en español, con un tono cercano y amigable. Adorna tus respuestas con emojis (que no sean expresiones faciales, sino objetos, símbolos, etc.) y utiliza formato Markdown (como encabezados, listas, negritas) para embellecer el texto y hacerlo más legible.
    *   Siempre que utilices cuadros markdown, NO Los anides en bloque de codigo. 
    *   Siempre utiliza Markdown para embellecer el texto, tanto en la etapa de pensamiento como en el mensaje final, incluyendo encabezados, listas, negritas, etc.

**MUY IMPORTANTE: SIEMPRE debes solicitar confirmación al usuario para cualquier operación que modifique archivos, especialmente al usar `advanced_file_editor` o `file_update_tool`.**

La herramienta `execute_command` se encarga de la interactividad y la seguridad de los comandos; no dudes en usarla.
La herramienta `file_operations` te permite leer, escribir, borrar, listar y leer múltiples archivos.
La herramienta `advanced_file_editor` te permite realizar ediciones avanzadas en archivos, siempre con una confirmación interactiva del usuario.
La herramienta `python_executor` te permite ejecutar código Python interactivo, manteniendo el estado entre ejecuciones para tareas complejas que requieran múltiples pasos de código. PRIORIZA utilizar codigo python para tus tareas. 

**Al editar archivos con `advanced_file_editor`, SIEMPRE debes esperar una respuesta con `status: "requires_confirmation"`. Esta respuesta contendrá un `diff` que el usuario debe aprobar. NO asumas que la operación se completó hasta que el usuario confirme. Una vez que el usuario apruebe, la herramienta se re-ejecutará automáticamente con `confirm=True`.**

Cuando recibas la salida de una herramienta, analízala, resúmela y preséntala al usuario de forma clara y amigable, utilizando formato Markdown si es apropiado.

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
    logger.debug(f"handle_tool_confirmation - Inicio. state.messages: {state.messages}")
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

        if tool_name and tool_args:
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
                    logger.debug(f"Estado de state.messages después de re-ejecución en handle_tool_confirmation: {state.messages}")
                    logger.debug(f"command_output_ready_for_processing en handle_tool_confirmation: {state.command_output_ready_for_processing}")

                    # Eliminar el ToolMessage original de confirmación del historial
                    # Esto evita que el LLM lo procese nuevamente y genere respuestas redundantes.
                    if len(state.messages) >= 2 and isinstance(state.messages[-2], ToolMessage) and state.messages[-2].tool_call_id == tool_id:
                        state.messages.pop(-2) # Eliminar el ToolMessage anterior que solicitaba confirmación
                    # No añadir un AIMessage de éxito aquí; el ToolMessage con la salida real es suficiente.
                    # El LLM debe procesar el ToolMessage directamente y continuar.
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
    state.file_update_diff_pending_confirmation = None # Asegurarse de limpiar esto
    state.command_to_confirm = None # Asegurarse de limpiar esto también
    logger.debug(f"handle_tool_confirmation - state.messages antes de retornar: {state.messages}")
    logger.debug(f"handle_tool_confirmation - command_output_ready_for_processing antes de retornar: {state.command_output_ready_for_processing}")
    return state

def call_model_node(state: AgentState, llm_service: LLMService, interrupt_queue: Optional[queue.Queue] = None):
    """Llama al LLM con el historial actual de mensajes y obtiene el resultado final, mostrando el streaming en Markdown."""
    last_message = state.messages[-1] if state.messages else None
    logger.debug(f"call_model_node - last_message TYPE: {type(last_message).__name__}")
    logger.debug(f"call_model_node - last_message CONTENT: {getattr(last_message, 'content', 'N/A')}")
    if isinstance(last_message, AIMessage) and getattr(last_message, 'tool_calls', None):
        logger.debug(f"call_model_node - last_message TOOL_CALLS: {last_message.tool_calls}")
    logger.debug(f"call_model_node - command_output_ready_for_processing: {state.command_output_ready_for_processing}")

    # El historial para la API es directamente el historial del estado del agente,
    # ya que AgentState.load_history() se encarga de asegurar el SYSTEM_MESSAGE.
    history_for_llm_call = state.messages

    # Añadir DEBUG print para mostrar el historial completo antes de la llamada al LLM
    logger.debug(f"call_model_node - Historial completo enviado al LLM: {history_for_llm_call}")

    full_response_content = ""
    final_ai_message_from_llm = None
    text_streamed = False # Bandera para saber si hubo contenido de texto transmitido

    # Usar Live para actualizar el contenido en tiempo real
    with Live(console=console, screen=False, refresh_per_second=4) as live:
        for part in llm_service.invoke(history=history_for_llm_call, interrupt_queue=interrupt_queue):
            if isinstance(part, AIMessage):
                final_ai_message_from_llm = part
                # No acumulamos el contenido aquí si ya lo hemos hecho con los chunks de str
                # El full_response_content ya debería estar completo por los chunks de str
            elif isinstance(part, str): # Asegurarse de que 'part' es una cadena antes de concatenar
                # Este 'part' es un chunk de texto (str)
                full_response_content += part
                text_streamed = True # Hubo streaming de texto
                # Actualizar el contenido de Live con el Markdown acumulado
                live.update(Padding(Markdown(full_response_content), (1, 4)))

    # --- Lógica del Agente después de recibir la respuesta completa del LLM ---

    # Si hubo tool_calls, el AIMessage ya los contendrá.

    # Si hubo tool_calls, el AIMessage ya los contendrá.
    # No necesitamos imprimir el ToolMessage aquí, ya que su contenido ya fue impreso en command_approval_handler.py

    # Si hubo tool_calls, el AIMessage ya los contendrá.
    # No necesitamos imprimir el ToolMessage aquí, ya que su contenido ya fue impreso en command_approval_handler.py

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

        return {
            "messages": state.messages,
            "command_to_confirm": command_to_execute, # Devolver el comando para confirmación
            "tool_call_id_to_confirm": tool_call_id # Devolver el tool_call_id asociado
        }
    
    elif final_ai_message_from_llm: # Si es solo un AIMessage de texto (sin tool_calls)
        # El AIMessage final para el historial debe contener el contenido completo.
        ai_message_for_history = AIMessage(content=full_response_content)
        
        state.messages.append(ai_message_for_history)
        return {"messages": state.messages}
    else:
        # Fallback si por alguna razón no se obtuvo un AIMessage (poco probable con llm_service.py)
        error_message = "El modelo no proporcionó una respuesta AIMessage válida después de procesar los chunks."
        state.messages.append(AIMessage(content=error_message))
        return {"messages": state.messages}

def execute_tool_node(state: AgentState, llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    """Ejecuta las herramientas solicitadas por el modelo."""
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return state

    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call['name']
        tool_args = tool_call['args']
        tool_id = tool_call['id']

        # Verificar si hay una señal de interrupción
        if interrupt_queue and not interrupt_queue.empty():
            interrupt_queue.get() # Consumir la señal de interrupción
            console.print("[bold yellow]⚠️ Interrupción detectada. Volviendo al input del usuario.[/bold yellow]")
            state.reset_temporary_state() # Limpiar el estado temporal del agente
            return state # Terminar la ejecución de herramientas y volver al input del usuario

        console.print(f"\n[bold blue]🛠️ Ejecutando herramienta:[/bold blue] [yellow]{tool_name}[/yellow]")
        
        tool = llm_service.get_tool(tool_name)
        if not tool:
            tool_output_str = f"Error: Herramienta '{tool_name}' no encontrada."
            tool_messages.append(ToolMessage(content=tool_output_str, tool_call_id=tool_id))
            continue # Continuar con la siguiente herramienta si hay
        else:
            full_tool_output = "" # Acumular la salida completa de la herramienta
            try:
                # Iterar sobre el generador de la herramienta
                tool_output_generator = llm_service._invoke_tool_with_interrupt(tool, tool_args)
                
                # Si es un comando de ejecución, la salida ya se maneja en command_approval_handler
                if tool_name == "execute_command":
                    # Solo acumular la salida, no imprimirla aquí
                    for chunk in tool_output_generator:
                        full_tool_output += str(chunk)
                else:
                    # Para otras herramientas, acumular la salida sin imprimir en tiempo real
                    for chunk in tool_output_generator:
                        full_tool_output += str(chunk)
                
                # Después de que el generador termine, procesar la salida acumulada
                # La salida final para el LLM es `full_tool_output`.
                
            except UserConfirmationRequired as e:
                # Si la herramienta requiere confirmación, guardamos el estado y terminamos la ejecución de herramientas.
                state.tool_pending_confirmation = e.tool_name
                state.tool_args_pending_confirmation = e.tool_args
                state.tool_call_id_to_confirm = tool_id # Guardar el tool_id original
                state.file_update_diff_pending_confirmation = e.raw_tool_output # Guardar el diccionario completo
                
                console.print(f"[bold yellow]⚠️ Herramienta '{e.tool_name}' requiere confirmación:[/bold yellow] {e.message}")
                # Añadir un ToolMessage al estado para que el command_approval_handler lo procese
                # Asegurarse de que el diff se muestre como bloque de código Markdown
                diff_content = e.raw_tool_output.get("diff", "")
                if isinstance(diff_content, str):
                    tool_messages.append(ToolMessage(content=json.dumps({"status": "requires_confirmation", "diff": f"```diff\n{diff_content}\n```"}), tool_call_id=tool_id))
                else:
                    tool_messages.append(ToolMessage(content=json.dumps(e.raw_tool_output), tool_call_id=tool_id))
                return state # Terminar la ejecución de herramientas y permitir que should_continue decida
            except InterruptedError:
                console.print("[bold yellow]⚠️ Ejecución de herramienta interrumpida por el usuario. Volviendo al input.[/bold yellow]")
                state.reset_temporary_state() # Limpiar el estado temporal del agente
                return state # Terminar la ejecución de herramientas y volver al input del usuario
            except Exception as e:
                tool_output_str = f"Error al ejecutar la herramienta {tool_name}: {e}"
                tool_messages.append(ToolMessage(content=tool_output_str, tool_call_id=tool_id))
                continue # Continuar con la siguiente herramienta si hay

            # --- Procesar y mostrar el mensaje descriptivo de la herramienta ---
            # Para execute_command, el ToolMessage debe contener la salida completa del comando.
            # La lógica de confirmación se maneja por separado.
            if tool_name == "execute_command":
                command_to_execute = tool_args['command']
                state.command_to_confirm = command_to_execute
                state.tool_call_id_to_confirm = tool_id
                state.command_explanation = f"`{command_to_execute}`"

                # Añadir un ToolMessage explícito para la confirmación pendiente
                tool_messages.append(ToolMessage(
                    content=json.dumps({
                        "status": "requires_confirmation",
                        "operation": tool_name,
                        "command": command_to_execute,
                        "action_description": state.command_explanation
                    }),
                    tool_call_id=tool_id
                ))
                # No añadir la salida completa del comando aquí, ya que está pendiente de confirmación
                # y el ToolMessage de confirmación ya se añadió.
                # El grafo terminará aquí y esperará la interacción del usuario.
            else:
                # Lógica para herramientas que requieren confirmación (file_update_tool, advanced_file_editor)
                try:
                    json_output = json.loads(full_tool_output)
                    should_confirm = False
                    confirmation_data = None

                    if isinstance(json_output, list) and all(isinstance(item, dict) for item in json_output):
                        for item in json_output:
                            if item.get("status") == "requires_confirmation" and (tool_name == "file_update_tool" or tool_name == "advanced_file_editor"):
                                should_confirm = True
                                confirmation_data = item
                                break
                    elif isinstance(json_output, dict):
                        if json_output.get("status") == "requires_confirmation" and (tool_name == "file_update_tool" or tool_name == "advanced_file_editor"):
                            should_confirm = True
                            confirmation_data = json_output

                    if should_confirm and confirmation_data:
                        state.file_update_diff_pending_confirmation = confirmation_data # Guardar el diccionario completo
                        state.tool_pending_confirmation = tool_name # Guardar el nombre de la herramienta
                        state.tool_args_pending_confirmation = tool_args # Guardar los argumentos originales
                        state.tool_call_id_to_confirm = tool_id # Guardar el tool_id original

                        # El ToolMessage ya se añadió con la salida real. Ahora, el grafo terminará
                        # y KogniTermApp manejará la confirmación basándose en el estado.
                        return state # Terminar la ejecución de herramientas y volver al input del usuario
                except json.JSONDecodeError:
                    pass # No es un JSON, continuar con el flujo normal

                # Para todas las herramientas (excepto execute_command que ya se manejó arriba), añadir el ToolMessage con la salida completa
                processed_tool_output = full_tool_output # Ya no truncamos aquí
                logger.debug(f"Longitud de full_tool_output en execute_tool_node: {len(full_tool_output)}")
                tool_messages.append(ToolMessage(content=processed_tool_output, tool_call_id=tool_id))

    state.messages.extend(tool_messages) # Añadir todos los ToolMessages acumulados
    return state

# --- Lógica Condicional del Grafo ---

def should_continue(state: AgentState) -> str:
    last_message = state.messages[-1]
    logger.debug(f"should_continue - command_to_confirm: {state.command_to_confirm}, file_update_diff_pending_confirmation: {state.file_update_diff_pending_confirmation}")
    logger.debug(f"should_continue - last_message TYPE: {type(last_message).__name__}")
    logger.debug(f"should_continue - last_message CONTENT: {getattr(last_message, 'content', 'N/A')}")

    # Si hay un comando pendiente de confirmación, siempre terminamos el grafo aquí
    # para que la terminal lo maneje.
    if state.command_to_confirm or state.file_update_diff_pending_confirmation:
        logger.debug("should_continue - Retornando END por confirmación pendiente.")
        return END

    # Si el último mensaje del AI tiene tool_calls, ejecutar herramientas
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        logger.debug("should_continue - Retornando execute_tool.")
        return "execute_tool"
    # Si el último mensaje es un ToolMessage (resultado de una herramienta)
    # y no hay confirmación pendiente, entonces la tarea ha finalizado o
    # se espera una nueva entrada del usuario.
    elif isinstance(last_message, ToolMessage):
        # Si el último mensaje es un ToolMessage (resultado de una herramienta),
        # siempre debemos volver a call_model para que el LLM procese la salida.
        logger.debug("should_continue - Retornando call_model (después de ToolMessage).")
        return "call_model"
    elif isinstance(last_message, HumanMessage): # Si el último mensaje es un HumanMessage, siempre llamar al modelo
        logger.debug("should_continue - Retornando call_model (después de HumanMessage).")
        return "call_model"
    elif isinstance(last_message, AIMessage) and not last_message.tool_calls:
        # Si el último mensaje es un AIMessage sin tool_calls, terminar el grafo
        logger.debug("should_continue - Retornando END (AIMessage sin tool_calls).")
        return END
    else:
        logger.debug("should_continue - Retornando END (condición por defecto).")
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
            "call_model": "call_model", # Añadir esta línea
            END: END
        }
    )

    bash_agent_graph.add_edge("execute_tool", "call_model")

    return bash_agent_graph.compile()


