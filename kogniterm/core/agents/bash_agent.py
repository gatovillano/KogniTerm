from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import google.generativeai as genai
from rich.console import Console

from ..llm_service import LLMService

console = Console()

# Inicializar el servicio LLM de forma global
llm_service = LLMService()

# --- Mensaje de Sistema --- 
SYSTEM_MESSAGE = SystemMessage(content="""Eres KogniTerm, un asistente de IA experto en terminal.
Tu propósito es ayudar al usuario a realizar tareas directamente en su sistema.

Cuando el usuario te pida algo, tú eres quien debe ejecutarlo.

1.  **Analiza la petición**: Entiende lo que el usuario quiere lograr.
2.  **Usa tus herramientas**: Tienes un conjunto de herramientas, incluyendo `execute_command` para comandos de terminal y `file_operations` para interactuar con archivos y directorios. Úsalas para llevar a cabo la tarea.
3.  **Ejecuta directamente**: No le digas al usuario qué comandos ejecutar. Ejecútalos tú mismo usando la herramienta `execute_command` o `file_operations` según corresponda.
4.  **Rutas de Archivos**: Cuando el usuario se refiera a archivos o directorios, las rutas que recibirás serán rutas válidas en el sistema de archivos (absolutas o relativas al directorio actual). **Asegúrate de limpiar las rutas eliminando cualquier símbolo '@' o espacios extra al principio o al final antes de usarlas con las herramientas.**
5.  **Informa del resultado**: Una vez que la tarea esté completa, informa al usuario del resultado de forma clara y amigable.
6.  **Estilo de comunicación**: Responde siempre en español, con un tono cercano y amigable. Adorna tus respuestas con emojis (que no sean expresiones faciales, sino objetos, símbolos, etc.) y utiliza formato Markdown (como encabezados, listas, negritas) para embellecer el texto y hacerlo más legible.

La herramienta `execute_command` se encarga de la interactividad y la seguridad de los comandos; no dudes en usarla.
La herramienta `file_operations` te permite leer, escribir, borrar, listar y leer múltiples archivos.

Cuando recibas la salida de una herramienta, analízala, resúmela y preséntala al usuario de forma clara y amigable, utilizando formato Markdown si es apropiado.

El usuario te está dando permiso para que operes en su sistema. Actúa de forma proactiva para completar sus peticiones.
""")

# --- Definición del Estado del Agente ---

@dataclass
class AgentState:
    """Define la estructura del estado que fluye a través del grafo."""
    messages: List[BaseMessage] = field(default_factory=lambda: [SYSTEM_MESSAGE])
    command_to_confirm: Optional[str] = None # Nuevo campo para comandos que requieren confirmación

    @property
    def history_for_api(self) -> list[dict]:
        """Convierte los mensajes de LangChain al formato que espera la API de Google AI."""
        api_history = []
        messages = self.messages
        i = 0
        while i < len(messages):
            msg = messages[i]
            if isinstance(msg, ToolMessage):
                tool_messages_buffer = []
                # Collect all consecutive ToolMessages
                while i < len(messages) and isinstance(messages[i], ToolMessage):
                    tool_messages_buffer.append(messages[i])
                    i += 1
                
                parts = [
                    genai.protos.Part(function_response=genai.protos.FunctionResponse(
                        name=tm.tool_call_id,
                        response={'content': tm.content}
                    )) for tm in tool_messages_buffer
                ]
                api_history.append({'role': 'user', 'parts': parts})
                continue # Continue to the next message after the buffer

            if isinstance(msg, (HumanMessage, SystemMessage)):
                api_history.append({'role': 'user', 'parts': [genai.protos.Part(text=msg.content)]})
            elif isinstance(msg, AIMessage):
                if msg.tool_calls:
                    parts = [
                        genai.protos.Part(function_call=genai.protos.FunctionCall(name=tc['name'], args=tc['args']))
                        for tc in msg.tool_calls
                    ]
                    api_history.append({'role': 'model', 'parts': parts})
                else:
                    api_history.append({'role': 'model', 'parts': [genai.protos.Part(text=msg.content)]})
            i += 1
        return api_history

# --- Nodos del Grafo ---

def call_model_node(state: AgentState):
    """Llama al LLM con el historial actual de mensajes."""
    history = state.history_for_api
    response = llm_service.invoke(history)
    
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

def explain_command_node(state: AgentState):
    """Genera una explicación en lenguaje natural del comando a ejecutar."""
    # El último mensaje del AI es la llamada a herramienta para execute_command
    last_ai_message = state.messages[-1]
    command = last_ai_message.tool_calls[0]['args']['command']

    explanation_prompt = f"El siguiente comando será ejecutado: `{command}`. Por favor, explica en lenguaje natural qué hará este comando y por qué es necesario para la tarea actual. Sé conciso y claro."
    
    # Llamar al modelo para obtener una explicación
    # Necesitamos una copia del historial sin la última llamada a herramienta para que el modelo genere texto
    temp_history = state.history_for_api[:-1] # Eliminar el último mensaje del AI con la llamada a herramienta
    temp_history.append({'role': 'user', 'parts': [explanation_prompt]}) # Añadir el prompt de explicación
    
    response = llm_service.invoke(temp_history)
    explanation_text = response.candidates[0].content.parts[0].text

    # Añadir la explicación a los mensajes
    state.messages.append(AIMessage(content=explanation_text))
    
    # Ahora establecer el comando para confirmar
    state.command_to_confirm = command
    return state

def execute_tool_node(state: AgentState):
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
        console.print(f"[bold blue]⚙️ Argumentos:[/bold blue] [cyan]{tool_args}[/cyan]")
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
            console.print(f"[bold green]✅ Salida de la herramienta:[/bold green]\n[dim]{tool_output}[/dim]")
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

bash_agent_graph = StateGraph(AgentState)

bash_agent_graph.add_node("call_model", call_model_node)
bash_agent_graph.add_node("execute_tool", execute_tool_node)
bash_agent_graph.add_node("explain_command", explain_command_node) # Nuevo nodo
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

bash_agent_app = bash_agent_graph.compile()
