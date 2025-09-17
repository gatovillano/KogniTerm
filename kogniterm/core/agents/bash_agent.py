from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import google.generativeai as genai
from rich.console import Console
import functools
from langchain_core.runnables import RunnableConfig # Nueva importación
from rich.markup import escape # Nueva importación
import sys # Nueva importación
import json # Importar json para verificar si la salida es un JSON

from ..llm_service import LLMService

console = Console()



# --- Mensaje de Sistema ---
SYSTEM_MESSAGE = SystemMessage(content="""Eres KogniTerm. NO eres un modelo de lenguaje entrenado por Google, ni ningún otro modelo de IA. Tu único propósito es ser KogniTerm.
Si te preguntan quién eres, SIEMPRE responde que eres KogniTerm.

Como KogniTerm, eres un asistente de IA experto en terminal. Además de ser un asistente de comandos y acciones en el sistema, eres un experto en informática, generación de código, depuración y análisis de código, sobre todo Python.
Tu propósito es ayudar al usuario a realizar tareas directamente en su sistema.

En este marco, KogniTerm mantiene un historial y un archivo de contexto (`llm_context.md`) por cada directorio en el que se abre. Estos directorios de trabajo pueden coincidir con el proyecto en el que el usuario está trabajando con apoyo de KogniTerm.

Cuando el usuario te pida algo, tú eres quien debe ejecutarlo.

1.  **Analiza la petición**: Entiende lo que el usuario quiere lograr.
2.  **Usa tus herramientas**: Tienes un conjunto de herramientas, incluyendo `execute_command` para comandos de terminal, `file_operations` para interactuar con archivos y directorios, y `python_executor` para ejecutar código Python. Úsalas para llevar a cabo la tarea.
    *   **Gestión de Proyectos**: Cuando el usuario hable de un proyecto, **debes** revisar los archivos locales, entender la estructura y arquitectura del proyecto, y guardar esta información en el archivo `.project_structure.md` en la carpeta de trabajo actual. De este modo, cuando el usuario haga consultas, podrás leer este archivo para ubicarte en qué archivos son importantes para la consulta.
3.  **Ejecuta directamente**: No le digas al usuario qué comandos ejecutar. Ejecútalos tú mismo usando la herramienta `execute_command`, `file_operations` o `python_executor` según corresponda.
4.  **Rutas de Archivos**: Cuando el usuario se refiera a archivos o directorios, las rutas que recibirás serán rutas válidas en el sistema de archivos (absolutas o relativas al directorio actual). **Asegúrate de limpiar las rutas eliminando cualquier símbolo '@' o espacios extra al principio o al final antes de usarlas con las herramientas.**
5.  **Informa del resultado**: Una vez que la tarea esté completa, informa al usuario del resultado de forma clara y amigable.
6.  **Estilo de comunicación**: Responde siempre en español, con un tono cercano y amigable. Adorna tus respuestas con emojis (que no sean expresiones faciales, sino objetos, símbolos, etc.) y utiliza formato Markdown (como encabezados, listas, negritas) para embellecer el texto y hacerlo más legible.
    *   Siempre utiliza una línea separadora (por ejemplo, `---` o `***`) al inicio y al final de tus mensajes, tanto en la etapa de pensamiento como en el mensaje final.
    *   Siempre utiliza Markdown para embellecer el texto, tanto en la etapa de pensamiento como en el mensaje final, incluyendo encabezados, listas, negritas, etc.

La herramienta `execute_command` se encarga de la interactividad y la seguridad de los comandos; no dudes en usarla.
La herramienta `file_operations` te permite leer, escribir, borrar, listar y leer múltiples archivos.
La herramienta `python_executor` te permite ejecutar código Python interactivo, manteniendo el estado entre ejecuciones para tareas complejas que requieran múltiples pasos de código.

Cuando recibas la salida de una herramienta, analízala, resúmela y preséntala al usuario de forma clara y amigable, utilizando formato Markdown si es apropiado.

El usuario te está dando permiso para que operes en su sistema. Actúa de forma proactiva para completar sus peticiones.
""")

# --- Definición del Estado del Agente ---

@dataclass
class AgentState:
    """Define la estructura del estado que fluye a través del grafo."""
    messages: List[BaseMessage] = field(default_factory=list)
    command_to_confirm: Optional[str] = None # Nuevo campo para comandos que requieren confirmación
    tool_call_id_to_confirm: Optional[str] = None # Nuevo campo para el tool_call_id asociado al comando
    current_agent_mode: str = "bash" # Añadido para el modo del agente

    @property
    def history_for_api(self) -> list[BaseMessage]:
        """Devuelve el historial de mensajes de LangChain directamente."""
        return self.messages

# --- Nodos del Grafo ---

from rich.live import Live # Importar Live
from rich.markdown import Markdown # Importar Markdown
from rich.padding import Padding # Nueva importación
from rich.status import Status # ¡Nueva importación!

def call_model_node(state: AgentState, llm_service: LLMService):
    """Llama al LLM con el historial actual de mensajes y obtiene el resultado final, mostrando el streaming en Markdown."""
    history = state.history_for_api
    
    full_response_content = ""
    final_ai_message_from_llm = None
    text_streamed = False # Bandera para saber si hubo contenido de texto transmitido

    # Usar Live para actualizar el contenido en tiempo real
    with Live(console=console, screen=False, refresh_per_second=4) as live:
        for part in llm_service.invoke(history=history, system_message=SYSTEM_MESSAGE.content):
            if isinstance(part, AIMessage):
                final_ai_message_from_llm = part
                # Si el AIMessage final tiene contenido, lo añadimos al full_response_content
                if part.content:
                    full_response_content += part.content
            else:
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
        for tc in final_ai_message_from_llm.tool_calls:
            if tc['name'] == 'execute_command':
                command_to_execute = tc['args'].get('command')
                tool_call_id = tc['id'] # Capturar el tool_call_id
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


def execute_tool_node(state: AgentState, llm_service: LLMService):
    """Ejecuta las herramientas solicitadas por el modelo."""
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return state

    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call['name']
        tool_args = tool_call['args']
        tool_id = tool_call['id']

        # --- Añadir logs para la ejecución de herramientas ---
        console.print(f"\n[bold blue]🛠️ Ejecutando herramienta:[/bold blue] [yellow]{tool_name}[/yellow]")
        
        tool = llm_service.get_tool(tool_name)
        if not tool:
            tool_output_str = f"Error: Herramienta '{tool_name}' no encontrada."
        else:
            try:
                raw_tool_output = tool.invoke(tool_args)
                tool_output_str = str(raw_tool_output) # Convertir a cadena
            except Exception as e:
                tool_output_str = f"Error al ejecutar la herramienta {tool_name}: {e}"
        
        # --- Procesar y mostrar el mensaje descriptivo de la herramienta ---
        first_line = tool_output_str.split('\n')[0].strip()
        remaining_output = tool_output_str

        # Heurística simple para detectar un mensaje descriptivo
        is_descriptive_message = False
        if first_line and first_line.endswith('.') and len(first_line) > 10: # Si termina en punto y es lo suficientemente largo
            try:
                json.loads(first_line) # Intenta parsear como JSON, si falla, es probable que sea descriptivo
            except json.JSONDecodeError:
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
            # Si es execute_command, establecer command_to_confirm y terminar el grafo aquí.
            # La terminal se encargará de la confirmación y ejecución.
            state.command_to_confirm = tool_args['command']
            return state # Esto hará que el grafo termine en este nodo si no hay más tool_calls
        else:
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

def create_bash_agent(llm_service: LLMService):
    bash_agent_graph = StateGraph(AgentState)

    bash_agent_graph.add_node("call_model", functools.partial(call_model_node, llm_service=llm_service))
    bash_agent_graph.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service))

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
