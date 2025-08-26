import sys
from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import google.generativeai as genai
from google.generativeai.protos import Part, FunctionCall

from kogniterm.core.llm_service import LLMService

# Inicializar el servicio LLM de forma global
llm_service = LLMService()

# --- Mensaje de Sistema ---
SYSTEM_MESSAGE = SystemMessage(content="""¡Hola! 👋 Soy KogniTerm, tu asistente de IA experto en terminal. ¡Estoy aquí para ayudarte a realizar tareas directamente en tu sistema de la manera más amigable y eficiente posible! ✨

Cuando me pidas algo, yo me encargaré de ejecutarlo por ti. Mi objetivo es simplificar tu trabajo y que la experiencia sea genial. 🚀

Aquí te explico cómo funciono y qué espero de ti:

1.  **Analiza la petición**: Entiendo perfectamente lo que quieres lograr. ¡No te preocupes!
2.  **Usa mis herramientas**: Tengo un conjunto de herramientas superútiles a mi disposición, como `execute_command` para comandos de terminal, y otras para buscar en la web (`brave_search`) y acceder a contenido de URLs (`web_fetch`). ¡Las usaré sin dudar para completar tus tareas! 🛠️
3.  **Ejecuta directamente**: ¡No te pediré que ejecutes comandos! Yo los haré por ti usando la herramienta `execute_command`. Así, tú te relajas y yo hago el trabajo pesado. 😉
4.  **Informa del resultado**: Una vez que la tarea esté lista, te informaré el resultado de forma clara, concisa y con una sonrisa. ¡Siempre con un toque amigable! 😊

La herramienta `execute_command` maneja la interactividad y seguridad de los comandos, así que puedes confiar en que todo estará bien.

**¡IMPORTANTE!** 🚨 Cuando use la herramienta `execute_command`, no la combinaré con otras herramientas en la misma respuesta. ¡`execute_command` será la única herramienta en esa llamada!

Cuando reciba la salida de una herramienta, la analizaré, resumiré y te la presentaré de forma clara y amigable, usando Markdown si es necesario para que todo sea fácil de leer. 📝

¡Cuento con tu permiso para operar en tu sistema! Actuaré de forma proactiva para completar tus peticiones. ¡Vamos a hacer cosas increíbles juntos! 💡

**Gestión de Memoria:**
*   **Inicio de Conversación**: Al inicio de cada conversación, verificaré si el archivo de memoria existe. Si no existe, lo inicializaré automáticamente usando `memory_init_tool`. Si existe, lo leeré usando `memory_read_tool` para cargar el contexto previo. Esto me permite recordar contextos importantes entre sesiones. 🧠
*   **Guardado Autónomo**: Guardaré memorias relevantes de forma autónoma cuando me plantees temas importantes como detalles del directorio actual, objetivos del proyecto o cualquier información crucial. Utilizaré `memory_append_tool` para asegurarme de que esta información esté siempre disponible cuando la necesite. 💾
*   **Acceso a Memoria**: Puedo acceder a la información guardada en tu memoria en cualquier momento usando `memory_read_tool` para ayudarte de manera más eficiente y contextualizada. 📖
""")

# --- Definición del Estado del Agente ---

@dataclass
class AgentState:
    """Define la estructura del estado que fluye a través del grafo."""
    messages: List[BaseMessage] = field(default_factory=lambda: [SYSTEM_MESSAGE])
    command_to_confirm: Optional[str] = None # Nuevo campo para comandos que requieren confirmación
    action_needed: Optional[str] = None # Añadido para consistencia con OrchestratorState

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
                    Part(function_response=genai.protos.FunctionResponse(
                        name=tm.tool_call_id,
                        response={'content': tm.content}
                    )) for tm in tool_messages_buffer
                ]
                api_history.append({'role': 'user', 'parts': parts})
                continue # Continue to the next message after the buffer

            if isinstance(msg, (HumanMessage, SystemMessage)):
                api_history.append({'role': 'user', 'parts': [Part(text=msg.content)]})
            elif isinstance(msg, AIMessage):
                if msg.tool_calls:
                    parts = [
                        Part(function_call=FunctionCall(name=tc['name'], args=tc['args']))
                        for tc in msg.tool_calls
                    ]
                    api_history.append({'role': 'model', 'parts': parts})
                else:
                    api_history.append({'role': 'model', 'parts': [Part(text=msg.content)]})
            i += 1
        return api_history

# --- Nodos del Grafo ---

async def call_model_node(state: AgentState):
    """Llama al LLM con el historial actual de mensajes."""
    history = state.history_for_api
    response = await llm_service.ainvoke(history)
    
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

async def explain_command_node(state: AgentState):
    """Genera una explicación en lenguaje natural del comando a ejecutar."""
    # El último mensaje del AI es la llamada a herramienta para execute_command
    last_ai_message = state.messages[-1]
    command = last_ai_message.tool_calls[0].args['command']

    explanation_prompt = f"El siguiente comando será ejecutado: `{command}`. Por favor, explica en lenguaje natural qué hará este comando y por qué es necesario para la tarea actual. Sé conciso y claro."
    
    # Llamar al modelo para obtener una explicación
    # Necesitamos una copia del historial sin la última llamada a herramienta para que el modelo genere texto
    temp_history = state.history_for_api[:-1] # Eliminar el último mensaje del AI con la llamada a herramienta
    temp_history.append({'role': 'user', 'parts': [explanation_prompt]}) # Añadir el prompt de explicación
    
    response = await llm_service.ainvoke(temp_history)
    explanation_text = response.candidates[0].content.parts[0].text

    # Añadir la explicación a los mensajes
    state.messages.append(AIMessage(content=explanation_text))
    
    # Ahora establecer el comando para confirmar
    state.command_to_confirm = command
    return state

async def execute_tool_node(state: AgentState):
    """Ejecuta las herramientas solicitadas por el modelo."""
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return state

    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call['name']
        tool_args = tool_call['args']
        tool_id = tool_call['id']

        if tool_name == "execute_command":
            # Añadir un ToolMessage para mantener la consistencia en el historial
            tool_messages.append(ToolMessage(content="Comando enviado para explicación y confirmación.", tool_call_id=tool_id))
            # El agente transicionará a explain_command_node
            return state
        else:
            # Imprimir un mensaje para notificar al usuario que la herramienta se está ejecutando
            # Esto es útil para herramientas que pueden tardar un poco.
            print(f"⚙️  Ejecutando herramienta: {tool_name}...", file=sys.stdout, flush=True)
            
            tool = llm_service.get_tool(tool_name)
            if not tool:
                tool_output = f"Error: Herramienta '{tool_name}' no encontrada."
            else:
                try:
                    # Usar ainvoke para la ejecución asíncrona de la herramienta
                    tool_output = await tool.ainvoke(tool_args)
                    # Limitar el tamaño de la salida de la herramienta a 1000 caracteres
                    # para evitar exceder el límite de payload de la API de Gemini
                    if len(str(tool_output)) > 1000:
                        tool_output = str(tool_output)[:997] + "..."
                except Exception as e:
                    tool_output = f"Error al ejecutar la herramienta {tool_name}: {e}"
            
            # Imprime una nueva línea para separar la notificación de la salida final.
            print()
            
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
