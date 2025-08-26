import sys
from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage, ToolCall
import google.generativeai as genai
from google.generativeai.protos import Part, FunctionCall, FunctionResponse

from kogniterm.core.llm_service import LLMService

# Inicializar el servicio LLM de forma global
llm_service = LLMService()

# --- Mensaje de Sistema ---
SYSTEM_MESSAGE = SystemMessage(content="""¡Hola! 👋 Soy KogniTerm, tu asistente de IA experto en terminal. ¡Estoy aquí para ayudarte a realizar tareas directamente en tu sistema de la manera más amigable y eficiente posible! ✨

Cuando me pidas algo, yo me encargaré de ejecutarlo por ti. Mi objetivo es simplificar tu trabajo y que la experiencia sea genial. 🚀

Aquí te explico cómo funciono y qué espero de ti:

1.  **Analiza la petición**: Entiendo perfectamente lo que quieres lograr. ¡No te preocupes!
2.  **Usa mis herramientas**: Tengo un conjunto de herramientas superútiles a mi disposición, como `execute_command` para comandos de terminal, y otras para buscar en la web (`brave_search`) y acceder a contenido de URLs (`web_fetch`). ¡Las usaré sin dudar para completar tus tareas! 🛠️ Cuando uses `github_tool` para leer contenido de archivos, por favor, usa siempre el parámetro `save_to_temp_file=True` para asegurarte de obtener el contenido completo sin truncamiento.
3.  **Ejecuta directamente**: ¡No te pediré que ejecutes comandos! Yo los haré por ti usando la herramienta `execute_command`. Así, tú te relajas y yo hago el trabajo pesado. 😉
4.  **Informa del resultado**: Una vez que la tarea esté lista, te informaré el resultado de forma clara, concisa y con una sonrisa. ¡Siempre con un toque amigable! 😊

La herramienta `execute_command` maneja la interactividad y seguridad de los comandos, así que puedes confiar en que todo estará bien.

¡IMPORTANTE! 🚨 Cuando use la herramienta `execute_command`, te **pediré confirmación explícita** antes de ejecutarla. Esto me permite encadenar comandos y otras herramientas para completar tareas complejas de forma autónoma, pero siempre bajo tu supervisión. Si es beneficioso para la tarea, puedo ejecutar múltiples acciones por turno.

Después de cada ejecución de herramienta (excepto `execute_command` que requiere confirmación), te indicaré brevemente lo que hice y lo que haré a continuación, manteniendo un flujo constante de información. Si necesito realizar pasos intermedios o pensar en el siguiente paso sin interactuar contigo directamente, usaré la frase `[CONTINUE_TASK]` al final de mi mensaje. Esto significa que seguiré trabajando en la tarea sin esperar tu input. Solo te daré una respuesta final cuando la tarea esté 100% completada. Cuando reciba la salida de una herramienta, la analizaré, resumiré y te la presentaré de forma clara y amigable, usando Markdown si es necesario para que todo sea fácil de leer. 📝

¡Cuento con tu permiso para operar en tu sistema! Actuaré de forma proactiva para completar tus peticiones. ¡Vamos a hacer cosas increíbles juntos! 💡

**Gestión de Memoria:**
*   **Inicio de Conversación**: Al inicio de cada conversación, verificaré si el archivo de memoria existe. Si no existe, lo inicializaré automáticamente usando `memory_init_tool`. Si existe, lo leeré usando `memory_read_tool` para cargar el contexto previo. Esto me permite recordar contextos importantes entre sesiones. 🧠
*   **Historial de Comandos**: Además del archivo de memoria, también consideraré el historial de comandos de la terminal para comprender mejor el contexto de tu sesión. 📜
*   **Guardado Autónomo**: Guardaré memorias relevantes de forma autónoma cuando me plantees temas importantes como detalles del directorio actual, objetivos del proyecto o cualquier información crucial. Utilizaré `memory_append_tool` para asegurarme de que esta información esté siempre disponible cuando la necesite. 💾
*   **Acceso a Memoria**: Puedo acceder a la información guardada en tu memoria en cualquier momento usando `memory_read_tool` para ayudarte de manera más eficiente y contextualizada. 📖
""")

# --- Definición del Estado del Agente ---

@dataclass
class AgentState:
    """Define la estructura del estado que fluye a través del grafo."""
    messages: List[BaseMessage] = field(default_factory=list) # Inicializar como lista vacía
    action_needed: Optional[str] = None # Añadido para consistencia con OrchestratorState
    internal_continue: bool = False # Nuevo campo para indicar continuación interna
    command_to_confirm: Optional[str] = None # Re-introducido para comandos que requieren confirmación

    def __post_init__(self):
        """Asegura que el SYSTEM_MESSAGE esté siempre al inicio, si no está ya presente."""
        if not self.messages or self.messages[0] != SYSTEM_MESSAGE:
            self.messages.insert(0, SYSTEM_MESSAGE)

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
                    Part(function_response=FunctionResponse(
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

def _messages_from_api_history(api_history: list[dict]) -> List[BaseMessage]:
    """Convierte el historial de la API de Google AI de nuevo a mensajes de LangChain."""
    messages: List[BaseMessage] = []
    for entry in api_history:
        role = entry.get('role')
        parts = entry.get('parts', [])
        
        content_text = ""
        tool_calls = []

        for part in parts:
            if part.text: # Access .text attribute
                content_text += part.text
            if part.function_call: # Access .function_call attribute
                fc = part.function_call
                tool_calls.append(ToolCall(name=fc.name, args={k: v for k, v in fc.args.items()}, id=fc.name)) # Access .name and .args.items()

        if role == 'user':
            messages.append(HumanMessage(content=content_text))
        elif role == 'model':
            if tool_calls:
                messages.append(AIMessage(content=content_text, tool_calls=tool_calls))
            else:
                messages.append(AIMessage(content=content_text))
        # Note: ToolMessage and SystemMessage are not typically in api_history in this format
    return messages

# --- Nodos del Grafo ---

# --- Nodos del Grafo ---

async def call_model_node(state: AgentState):
    """Llama al LLM con el historial actual de mensajes."""
    history = state.history_for_api
    # Convert history back to BaseMessage for llm_service.ainvoke
    langchain_history = _messages_from_api_history(history)
    response = await llm_service.ainvoke(langchain_history)
    
    state.internal_continue = False # Reset internal_continue flag
    state.command_to_confirm = None # Reset command_to_confirm flag

    # Check if response has candidates and parts
    if response.candidates and response.candidates[0].content.parts:
        # Iterate through all parts to find tool calls and text
        tool_calls = []
        text_response_parts = []
        full_ai_response_content = "" # Para capturar todo el texto del AI
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call.name:
                tool_name = part.function_call.name
                tool_args = {key: value for key, value in part.function_call.args.items()}
                tool_calls.append(ToolCall(name=tool_name, args=tool_args, id=tool_name))
            elif hasattr(part, 'text') and part.text:
                text_response_parts.append(part.text)
                full_ai_response_content += part.text # Acumular todo el texto

        # Check for [CONTINUE_TASK] keyword
        if "[CONTINUE_TASK]" in full_ai_response_content:
            state.internal_continue = True
            # Remove [CONTINUE_TASK] from the actual message content
            full_ai_response_content = full_ai_response_content.replace("[CONTINUE_TASK]", "").strip()

        if tool_calls:
            ai_message = AIMessage(content=full_ai_response_content, tool_calls=tool_calls)
            state.messages.append(ai_message)
        elif full_ai_response_content: # Use full_ai_response_content for text-only messages
            state.messages.append(AIMessage(content=full_ai_response_content))
    else:
        # Handle cases where there's no content (e.g., blocked response)
        error_message = "El modelo no proporcionó una respuesta válida."
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
            error_message += f" Razón de bloqueo: {response.prompt_feedback.block_reason.name}"
        state.messages.append(AIMessage(content=error_message))
    
    return state

async def explain_command_node(state: AgentState):
    """Genera una explicación en lenguaje natural del comando a ejecutar."""
    last_ai_message = state.messages[-1]
    
    # Ensure the last message is an AIMessage with tool calls
    if not isinstance(last_ai_message, AIMessage) or not last_ai_message.tool_calls:
        print("Error: Last message is not an AIMessage with tool calls in explain_command_node.", file=sys.stderr)
        state.messages.append(AIMessage(content="Error interno: No se pudo determinar el comando a explicar."))
        return state

    command_tool_call = next((tc for tc in last_ai_message.tool_calls if tc['name'] == 'execute_command'), None)
    if not command_tool_call:
        print("Error: No execute_command tool call found in explain_command_node.", file=sys.stderr)
        state.messages.append(AIMessage(content="Error interno: No se encontró la llamada a la herramienta 'execute_command'."))
        return state

    command = command_tool_call['args'].get('command', 'unknown command')

    explanation_prompt = f"El siguiente comando será ejecutado: `{command}`. Por favor, explica en lenguaje natural qué hará este comando y por qué es necesario para la tarea actual. Sé conciso y claro."
    
    # Llamar al modelo para obtener una explicación
    # Crear un historial temporal que excluya la última AIMessage con tool_calls para evitar bucles
    temp_history_for_llm = state.messages[:-1] + [HumanMessage(content=explanation_prompt)]
    
    response = await llm_service.ainvoke(temp_history_for_llm)
    
    explanation_text = "No se pudo generar una explicación."
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                explanation_text = part.text
                break

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
            except Exception as e:
                tool_output = f"Error al ejecutar la herramienta {tool_name}: {e}"
        
        # Imprime una nueva línea para separar la notificación de la salida final.
        print()
        
        tool_messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_id))

    state.messages.extend(tool_messages)
    return state

# --- Lógica Condicional del Grafo ---

def should_continue(state: AgentState) -> str:
    """Decide si continuar llamando a herramientas, al modelo o finalizar."""
    last_message = state.messages[-1]
    if state.internal_continue:
        return "call_model"
    elif state.command_to_confirm:
        return "await_user_confirmation"
    elif isinstance(last_message, AIMessage) and last_message.tool_calls:
        # Check if any of the tool calls is 'execute_command'
        for tool_call in last_message.tool_calls:
            if tool_call['name'] == 'execute_command':
                return "explain_command" # Go to explain_command node for confirmation
        return "execute_tool" # For other tools, execute directly
    else:
        return END

# --- Construcción del Grafo ---

bash_agent_graph = StateGraph(AgentState)

bash_agent_graph.add_node("call_model", call_model_node)
bash_agent_graph.add_node("explain_command", explain_command_node) # Re-add explain_command_node
bash_agent_graph.add_node("execute_tool", execute_tool_node)

bash_agent_graph.set_entry_point("call_model")

bash_agent_graph.add_conditional_edges(
    "call_model",
    should_continue,
    {
        "explain_command": "explain_command", # New edge to explain_command
        "execute_tool": "execute_tool",
        "call_model": "call_model", # Nueva arista para bucle interno
        END: END
    }
)

# After explaining the command, decide whether to execute or not based on user approval
bash_agent_graph.add_conditional_edges(
    "explain_command",
    lambda state: "execute_tool", # Always execute after explanation (confirmation handled by main loop)
    {"execute_tool": "execute_tool"}
)

bash_agent_graph.add_edge("execute_tool", "call_model")

bash_agent_app = bash_agent_graph.compile()
