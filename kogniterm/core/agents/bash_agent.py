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

from ..llm_service import LLMService

console = Console()



# --- Mensaje de Sistema ---
SYSTEM_MESSAGE = SystemMessage(content="""Eres KogniTerm. NO eres un modelo de lenguaje entrenado por Google, ni ningún otro modelo de IA. Tu único propósito es ser KogniTerm.
Si te preguntan quién eres, SIEMPRE responde que eres KogniTerm.

Como KogniTerm, eres un asistente de IA experto en terminal.
Tu propósito es ayudar al usuario a realizar tareas directamente en su sistema.

Cuando el usuario te pida algo, tú eres quien debe ejecutarlo.

1.  **Analiza la petición**: Entiende lo que el usuario quiere lograr.
2.  **Usa tus herramientas**: Tienes un conjunto de herramientas, incluyendo `execute_command` para comandos de terminal, `file_operations` para interactuar con archivos y directorios, y `python_executor` para ejecutar código Python. Úsalas para llevar a cabo la tarea.
3.  **Ejecuta directamente**: No le digas al usuario qué comandos ejecutar. Ejecútalos tú mismo usando la herramienta `execute_command`, `file_operations` o `python_executor` según corresponda.
4.  **Rutas de Archivos**: Cuando el usuario se refiera a archivos o directorios, las rutas que recibirás serán rutas válidas en el sistema de archivos (absolutas o relativas al directorio actual). **Asegúrate de limpiar las rutas eliminando cualquier símbolo '@' o espacios extra al principio o al final antes de usarlas con las herramientas.**
5.  **Informa del resultado**: Una vez que la tarea esté completa, informa al usuario del resultado de forma clara y amigable.
6.  **Estilo de comunicación**: Responde siempre en español, con un tono cercano y amigable. Adorna tus respuestas con emojis (que no sean expresiones faciales, sino objetos, símbolos, etc.) y utiliza formato Markdown (como encabezados, listas, negritas) para embellecer el texto y hacerlo más legible.

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

    @property
    def history_for_api(self) -> list[BaseMessage]:
        """Devuelve el historial de mensajes de LangChain directamente."""
        return self.messages

# --- Nodos del Grafo ---

def call_model_node(state: AgentState, llm_service: LLMService):
    """Llama al LLM con el historial actual de mensajes."""
    history = state.history_for_api
    response = llm_service.invoke(history)
    
    # --- INICIO DE LA CORRECCIÓN ---
    if isinstance(response, AIMessage):
        state.messages.append(response)
        return state
    # --- FIN DE LA CORRECCIÓN ---

    # Check if response has candidates and parts
    if response.candidates and response.candidates[0].content.parts:
        # Iterate through all parts to find tool calls
        tool_calls = []
        text_response_parts = []
        for part in response.candidates[0].content.parts:
            if part.function_call.name:
                tool_name = part.function_call.name
                tool_args = {key: value for key, value in part.function_call.args.items()}
                tool_calls.append({"name": tool_name, "args": tool_args, "id": tool_name})
            elif part.text:
                text_response_parts.append(part.text)
        
        if tool_calls:
            ai_message = AIMessage(content="", tool_calls=tool_calls)
            state.messages.append(ai_message)
        elif text_response_parts:
            text_response = "".join(text_response_parts)
            state.messages.append(AIMessage(content=text_response))
    else:
        # Handle cases where there's no content (e.g., blocked response)
        # The llm_service.invoke should return an error message in this case
        error_message = "El modelo no proporcionó una respuesta válida."
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            error_message += f" Razón de bloqueo: {response.prompt_feedback.block_reason.name}"
        state.messages.append(AIMessage(content=error_message))
    
    return state

def explain_command_node(state: AgentState, llm_service: LLMService):
    """Genera una explicación en lenguaje natural del comando a ejecutar."""
    # El último mensaje del AI es la llamada a herramienta para execute_command
    last_ai_message = state.messages[-1]
    command = last_ai_message.tool_calls[0]['args']['command']

    explanation_prompt = f"El siguiente comando será ejecutado: `{command}`. Por favor, explica en lenguaje natural qué hará este comando y por qué es necesario para la tarea actual. Sé conciso y claro."
    
    # Llamar al modelo para obtener una explicación
    # Necesitamos una copia del historial sin la última llamada a herramienta para que el modelo genere texto
    temp_history = state.history_for_api[:-1] # Eliminar el último mensaje del AI con la llamada a herramienta
    temp_history.append(HumanMessage(content=explanation_prompt)) # Añadir el prompt de explicación como HumanMessage
    
    response = llm_service.invoke(temp_history)
    explanation_text = response.candidates[0].content.parts[0].text

    # Añadir la explicación a los mensajes
    state.messages.append(AIMessage(content=explanation_text))
    
    # Ahora establecer el comando para confirmar
    state.command_to_confirm = command
    return state

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
        
        # --- Fin de logs ---

        if tool_name == "execute_command":
            return state # El agente transicionará a explain_command_node
        else:
            tool = llm_service.get_tool(tool_name)
            if not tool:
                tool_output = f"Error: Herramienta '{tool_name}' no encontrada."
            else:
                try:
                    tool_output = tool.invoke(tool_args)
                except Exception as e:
                    tool_output = f"Error al ejecutar la herramienta {tool_name}: {e}"
            
            # --- Añadir logs para la salida de la herramienta ---
            console.print(f"[bold green]✅ Salida de la herramienta:[/bold green]\n[dim]{escape(str(tool_output))}[/dim]")
            # --- Fin de logs ---

            tool_messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_id))

    state.messages.extend(tool_messages)
    return state

# --- Lógica Condicional del Grafo ---

def should_continue(state: AgentState) -> str:
    """Decide si continuar llamando a herramientas o finalizar."""
    last_message = state.messages[-1]
    if state.command_to_confirm: # Si hay un comando para confirmar, necesitamos ir a un paso de confirmación
        return "confirm_command"
    elif isinstance(last_message, AIMessage) and last_message.tool_calls:
        # Si es una llamada a herramienta execute_command, ir a explain_command
        if last_message.tool_calls[0]['name'] == "execute_command":
            return "explain_command"
        else:
            return "execute_tool"
    else:
        return END

# --- Construcción del Grafo ---

def create_bash_agent(llm_service: LLMService):
    bash_agent_graph = StateGraph(AgentState)

    bash_agent_graph.add_node("call_model", functools.partial(call_model_node, llm_service=llm_service))
    bash_agent_graph.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service))
    bash_agent_graph.add_node("explain_command", functools.partial(explain_command_node, llm_service=llm_service)) # Nuevo nodo
    bash_agent_graph.add_node("confirm_command", lambda state: state) # Nuevo nodo, solo pasa el estado

    bash_agent_graph.set_entry_point("call_model")

    bash_agent_graph.add_conditional_edges(
        "call_model",
        should_continue,
        {
            "execute_tool": "execute_tool",
            "explain_command": "explain_command", # Nueva transición
            "confirm_command": "confirm_command",
            END: END
        }
    )

    bash_agent_graph.add_edge("execute_tool", "call_model")
    bash_agent_graph.add_edge("explain_command", "confirm_command") # Nueva transición
    bash_agent_graph.add_edge("confirm_command", END) # El agente termina aquí, la terminal toma el control

    return bash_agent_graph.compile()

