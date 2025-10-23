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

from ..llm_service import LLMService

console = Console()



# --- Mensaje de Sistema ---
SYSTEM_MESSAGE = SystemMessage(content="""Eres KogniTerm. NO eres un modelo de lenguaje entrenado por Google, ni ningún otro modelo de IA. Tu único propósito es ser KogniTerm.
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

Utiliza esta información para entender rápidamente el entorno del proyecto y tomar decisiones más informadas, especialmente para saber qué archivos observar o a qué archivos ir en relación con la solicitud del usuario. No necesitas usar herramientas como `file_read_directory_tool` o `git_status` para obtener esta información básica inicial, ya te la he proporcionado.

Cuando el usuario te pida algo, tú eres quien debe ejecutarlo.

1.  **Analiza la petición**: Entiende lo que el usuario quiere lograr.
2.  **Usa tus herramientas**: Tienes un conjunto de herramientas, incluyendo `execute_command` para comandos de terminal, `file_operations` para interactuar con archivos y directorios, y `python_executor` para ejecutar código Python. Úsalas para llevar a cabo la tarea.
    *   **Gestión de Proyectos**: Cuando el usuario hable de un proyecto, **debes** revisar los archivos locales, entender la estructura y arquitectura del proyecto, y guardar esta información en el archivo `.project_structure.md` en la carpeta de trabajo actual. De este modo, cuando el usuario haga consultas, podrás leer este archivo para ubicarte en qué archivos son importantes para la consulta.
3.  **Ejecuta directamente**: No le digas al usuario qué comandos ejecutar. Ejecútalos tú mismo usando la herramienta `execute_command`, `file_operations` o `python_executor` según corresponda.
4.  **Rutas de Archivos**: Cuando el usuario se refiera a archivos o directorios, las rutas que recibirás serán rutas válidas en el sistema de archivos (absolutas o relativas al directorio actual). **Asegúrate de limpiar las rutas eliminando cualquier símbolo '@' o espacios extra al principio o al final antes de usarlas con las herramientas.**
5.  **Informa del resultado**: Una vez que la tarea esté completa, informa al usuario del resultado de forma clara y amigable.
6.  **Estilo de comunicación**: Responde siempre en español, con un tono cercano y amigable. Adorna tus respuestas con emojis (que no sean expresiones faciales, sino objetos, símbolos, etc.) y utiliza formato Markdown (como encabezados, listas, negritas) para embellecer el texto y hacerlo más legible.
    *   Siempre que utilices cuadros markdown, NO Los anides en bloque de codigo. 
    *   Siempre utiliza Markdown para embellecer el texto, tanto en la etapa de pensamiento como en el mensaje final, incluyendo encabezados, listas, negritas, etc.

La herramienta `execute_command` se encarga de la interactividad y la seguridad de los comandos; no dudes en usarla.
La herramienta `file_operations` te permite leer, escribir, borrar, listar y leer múltiples archivos.
La herramienta `python_executor` te permite ejecutar código Python interactivo, manteniendo el estado entre ejecuciones para tareas complejas que requieran múltiples pasos de código. PRIORIZA utilizar codigo python para tus tareas. 

**Al editar archivos, SIEMPRE debes usar la herramienta `file_update_tool`. Asegúrate de establecer `confirm=True` y de incluir el `diff` de los cambios propuestos en el argumento `content` para que el usuario pueda revisarlos antes de la aplicación.**

Cuando recibas la salida de una herramienta, analízala, resúmela y preséntala al usuario de forma clara y amigable, utilizando formato Markdown si es apropiado.

El usuario te está dando permiso para que operes en su sistema. Actúa de forma proactiva para completar sus peticiones.
""")

# --- Definición del Estado del Agente ---

class UserConfirmationRequired(Exception):
    """Excepción personalizada para indicar que se requiere confirmación del usuario."""
    def __init__(self, message: str, tool_name: Optional[str] = None, tool_args: Optional[Dict[str, Any]] = None, raw_tool_output: Optional[str] = None):
        self.message = message
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.raw_tool_output = raw_tool_output # Nuevo campo para la salida cruda de la herramienta
        super().__init__(self.message)

@dataclass
class AgentState:
    """Define la estructura del estado que fluye a través del grafo."""
    messages: List[BaseMessage] = field(default_factory=list)
    command_to_confirm: Optional[str] = None # Nuevo campo para comandos que requieren confirmación
    tool_call_id_to_confirm: Optional[str] = None # Nuevo campo para el tool_call_id asociado al comando
    current_agent_mode: str = "bash" # Añadido para el modo del agente
    
    # Nuevos campos para manejar la confirmación de herramientas
    tool_pending_confirmation: Optional[str] = None
    tool_args_pending_confirmation: Optional[Dict[str, Any]] = None
    file_update_diff_pending_confirmation: Optional[str] = None # Nuevo campo para el diff de file_update_tool

    def reset_tool_confirmation(self):
        """Reinicia el estado de la confirmación de herramientas."""
        self.tool_pending_confirmation = None
        self.tool_args_pending_confirmation = None
        # self.tool_call_id_to_confirm = None # Asegurarse de limpiar también este campo - ELIMINADO
        self.file_update_diff_pending_confirmation = None # Limpiar el diff también

    def reset(self):
        """Reinicia completamente el estado del agente."""
        self.messages = []
        self.command_to_confirm = None
        self.tool_call_id_to_confirm = None
        self.reset_tool_confirmation()
        self.file_update_diff_pending_confirmation = None # Limpiar el diff también

    def reset_temporary_state(self):
        """Reinicia los campos de estado temporal del agente, manteniendo el historial de mensajes."""
        self.command_to_confirm = None
        # self.tool_call_id_to_confirm = None # ELIMINADO
        self.reset_tool_confirmation()

    @property
    def history_for_api(self) -> list[BaseMessage]:
        """Devuelve el historial de mensajes de LangChain directamente."""
        return self.messages

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

        if tool_name and tool_args:
            console.print(f"[bold blue]🛠️ Re-ejecutando herramienta '{tool_name}' tras aprobación:[/bold blue]")

            tool = llm_service.get_tool(tool_name)
            if tool:
                # Si es file_update_tool, añadir el parámetro confirm=True
                if tool_name == "file_update_tool":
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
        tool_output_str = f"Operación denegada por el usuario: {state.tool_pending_confirmation}"
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

    # Usar Live para actualizar el contenido en tiempo real
    with Live(console=console, screen=False, refresh_per_second=4) as live:
        for part in llm_service.invoke(history=history, system_message=str(SYSTEM_MESSAGE.content), interrupt_queue=interrupt_queue):
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

def execute_tool_node(state: AgentState, llm_service: LLMService, interrupt_queue: Optional[queue.Queue] = None):
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
        else:
            try:
                raw_tool_output = llm_service._invoke_tool_with_interrupt(tool, tool_args)
                tool_output_str = str(raw_tool_output) # Convertir a cadena
            except UserConfirmationRequired as e:
                # Si la herramienta requiere confirmación, guardamos el estado y terminamos la ejecución de herramientas.
                state.tool_pending_confirmation = tool_name
                state.tool_args_pending_confirmation = tool_args
                # El mensaje de la excepción se usará como confirmation_prompt en KogniTermApp
                state.tool_call_id_to_confirm = tool_id # Guardar el tool_id original
                tool_output_str = f"UserConfirmationRequired: {e.message}"
                console.print(f"[bold yellow]⚠️ Herramienta '{tool_name}' requiere confirmación:[/bold yellow] {e.message}")
                return state # Salir de la ejecución de herramientas, KogniTermApp manejará la confirmación
            except InterruptedError:
                console.print("[bold yellow]⚠️ Ejecución de herramienta interrumpida por el usuario. Volviendo al input.[/bold yellow]")
                state.reset_temporary_state() # Limpiar el estado temporal del agente
                return state # Terminar la ejecución de herramientas y volver al input del usuario
            except Exception as e:
                tool_output_str = f"Error al ejecutar la herramienta {tool_name}: {e}"
        
        # --- Procesar y mostrar el mensaje descriptivo de la herramienta ---
        # Si la salida es un JSON, no intentamos extraer un mensaje descriptivo de la primera línea.
        # Simplemente la mostramos como parte de la salida.
        try:
            json_output = json.loads(tool_output_str)
            # Inicializar variables para la lógica de confirmación
            should_confirm = False
            confirmation_data = None

            if isinstance(json_output, list) and all(isinstance(item, dict) for item in json_output):
                for item in json_output:
                    if item.get("status") == "pending_confirmation" and tool_name == "file_update_tool":
                        should_confirm = True
                        confirmation_data = item
                        break
            elif isinstance(json_output, dict):
                if json_output.get("status") == "pending_confirmation" and tool_name == "file_update_tool":
                    should_confirm = True
                    confirmation_data = json_output

            if should_confirm and confirmation_data:
                state.file_update_diff_pending_confirmation = confirmation_data.get("diff") # Guardar el diff
                raise UserConfirmationRequired(
                    message=f"Confirmación de actualización de archivo requerida para '{tool_args.get('path', 'archivo desconocido')}'.",
                    tool_name=tool_name,
                    tool_args=tool_args,
                    raw_tool_output=tool_output_str # Pasar el JSON completo aquí
                )
            remaining_output = tool_output_str # Si es JSON, la salida completa es relevante
        except json.JSONDecodeError:
            # Si no es JSON, aplicamos la heurística para el mensaje descriptivo
            first_line = tool_output_str.split('\n')[0].strip()
            remaining_output = tool_output_str

            is_descriptive_message = False
            # Consideramos que es un mensaje descriptivo si termina en punto y es lo suficientemente largo
            if first_line and first_line.endswith('.') and len(first_line) > 10:
                is_descriptive_message = True
            
            if is_descriptive_message:
                console.print(f"[green]✨ {first_line}[/green]")
                remaining_output = '\n'.join(tool_output_str.split('\n')[1:]).strip() # Eliminar la primera línea
                if not remaining_output: # Si no queda más contenido después del mensaje descriptivo
                    remaining_output = "La herramienta se ejecutó correctamente y no produjo más salida."
            elif tool_output_str.strip() == "":
                remaining_output = "La herramienta se ejecutó correctamente y no produjo ninguna salida."

        # --- Fin de procesamiento de mensaje descriptivo ---

        if tool_name == "execute_command":
            # Para execute_command, siempre añadimos un ToolMessage.
            # La confirmación se manejará en KogniTermApp.
            # El contenido inicial del ToolMessage puede ser una indicación de que el comando está pendiente de confirmación.
            tool_output_str = f"Comando '{tool_args['command']}' pendiente de confirmación."
            tool_messages.append(ToolMessage(content=tool_output_str, tool_call_id=tool_id))
            state.command_to_confirm = tool_args['command'] # Todavía necesitamos esto para KogniTermApp
            state.tool_call_id_to_confirm = tool_id # Guardar el tool_id para KogniTermApp
            # No retornamos aquí, permitimos que el bucle continúe y que state.messages.extend(tool_messages) se ejecute.
        else:
            # ... (lógica existente para otras herramientas) ...
            tool_messages.append(ToolMessage(content=remaining_output, tool_call_id=tool_id))

    state.messages.extend(tool_messages)
    return state

# --- Lógica Condicional del Grafo ---

def should_continue(state: AgentState) -> str:
    """Decide si continuar llamando a herramientas o finalizar."""
    last_message = state.messages[-1]
    
    # Si hay un comando pendiente de confirmación, siempre terminamos el grafo aquí
    # para que la terminal lo maneje.
    if state.command_to_confirm:
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

def create_bash_agent(llm_service: LLMService, interrupt_queue: Optional[queue.Queue] = None):
    bash_agent_graph = StateGraph(AgentState)

    bash_agent_graph.add_node("call_model", functools.partial(call_model_node, llm_service=llm_service, interrupt_queue=interrupt_queue))
    bash_agent_graph.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service, interrupt_queue=interrupt_queue))

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


