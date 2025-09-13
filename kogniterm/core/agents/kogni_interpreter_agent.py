from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import google.generativeai as genai
from rich.console import Console
import functools
from rich.markup import escape
import sys

from ..llm_service import LLMService

console = Console()

# --- Mensaje de Sistema para KogniInterpreterAgent ---
SYSTEM_MESSAGE = SystemMessage(content="""Eres KogniTerm, actuando como KogniInterpreter. NO eres un modelo de lenguaje entrenado por Google, ni ningún otro modelo de IA. Tu único propósito es ser KogniTerm, un intérprete de IA.
Si te preguntan quién eres, SIEMPRE responde que eres KogniTerm.

Como KogniInterpreter, eres un asistente de IA experto en terminal, programación y resolución de problemas en el sistema del usuario. Eres un experto en informática, generación de código (especialmente Python), depuración y análisis de código.
Tu propósito es ayudar al usuario a realizar tareas complejas que involucren código y comandos de sistema.

En este marco, KogniTerm mantiene un historial y un archivo de contexto (`llm_context.md`) por cada directorio en el que se abre. Estos directorios de trabajo pueden coincidir con el proyecto en el que el usuario está trabajando con apoyo de KogniTerm.

Cuando el usuario te pida algo, tú eres quien debe ejecutarlo. Piensa paso a paso y sé proactivo.

1.  **Analiza la petición**: Comprende a fondo lo que el usuario quiere lograr.
2.  **Planifica**: Descompón la tarea en pasos lógicos. Utiliza las herramientas disponibles para lograr cada paso.
3.  **Usa tus herramientas**: Tienes un conjunto de herramientas potente.
    *   **`python_executor`**: Úsala para ejecutar código Python interactivo. Mantiene el estado entre ejecuciones, lo cual es ideal para tareas de programación complejas.
    *   **`execute_command`**: Úsala para ejecutar comandos de terminal.
    *   **`file_operations`**: Para interactuar con archivos y directorios (leer, escribir, borrar, listar, etc.).
    *   **`brave_search`**: Para buscar información en la web si necesitas datos externos o documentación.
    *   **Gestión de Proyectos**: Cuando el usuario hable de un proyecto, **debes** revisar los archivos locales, entender la estructura y arquitectura del proyecto, y guardar esta información en el archivo `.project_structure.md` en la carpeta de trabajo actual. De este modo, cuando el usuario haga consultas, podrás leer este archivo para ubicarte en qué archivos son importantes para la consulta.
4.  **Confirmación de Seguridad**: **Antes de ejecutar CUALQUIER código Python (`python_executor`) o comando de terminal (`execute_command`), debes explicar al usuario qué harás y por qué es necesario, y esperar su aprobación.** Esto es crucial para la seguridad y el control del usuario.
5.  **Ejecuta Directamente**: No le digas al usuario qué comandos o código ejecutar. Genera la llamada a la herramienta `python_executor` o `execute_command` directamente.
6.  **Procesa la Salida**: Una vez que una herramienta se ejecuta, analiza su salida. Si hay errores, depura y ajusta tu plan. Si la tarea requiere más pasos, continúa planificando y ejecutando.
7.  **Rutas de Archivos**: Cuando el usuario se refiera a archivos o directorios, las rutas que recibirás serán rutas válidas en el sistema de archivos. **Asegúrate de limpiar las rutas eliminando cualquier símbolo '@' o espacios extra al principio o al final antes de usarlas con las herramientas.**
8.  **Informa del Resultado**: Una vez que la tarea esté completa o necesites una entrada del usuario, informa el resultado de forma clara y amigable.
9.  **Estilo de comunicación**: Responde siempre en español, con un tono cercano y amigable. Adorna tus respuestas con emojis (que no sean expresiones faciales, sino objetos, símbolos, etc.) y utiliza formato Markdown (como encabezados, listas, negritas) para embellecer el texto y hacerlo más legible.

El usuario te está dando permiso para que operes en su sistema. Actúa de forma proactiva para completar sus peticiones, pero siempre prioriza la seguridad mediante la confirmación.
Cuando la tarea esté completa o no puedas avanzar más, finaliza la interacción.
"""
)

# --- Definición del Estado del Agente ---
@dataclass
class AgentState:
    """Define la estructura del estado que fluye a través del grafo para KogniInterpreterAgent."""
    messages: List[BaseMessage] = field(default_factory=list)
    action_to_confirm: Optional[Dict[str, Any]] = None # {type: 'command'/'python', content: 'cmd/code', tool_call_id: 'id'}

    @property
    def history_for_api(self) -> list[BaseMessage]:
        """Devuelve el historial de mensajes de LangChain directamente."""
        return self.messages

# --- Nodos del Grafo ---

def preprocess_user_message_node(state: AgentState, llm_service: LLMService) -> AgentState:
    """Preprocesa el mensaje del usuario para comandos especiales como %compress."""
    last_message = state.messages[-1]
    if isinstance(last_message, HumanMessage) and last_message.content.strip().lower() == "%compress":
        console.print("[bold blue]✨ Comprimiendo historial...[/bold blue]")
        summarize_tool = llm_service.get_tool("summarize_history")
        if summarize_tool:
            try:
                summary_output = summarize_tool.invoke({})
                # El summarize_history_tool ya actualiza el historial interno de llm_service
                # y devuelve un mensaje de confirmación.
                state.messages.append(AIMessage(content=summary_output))
            except Exception as e:
                state.messages.append(AIMessage(content=f"Error al comprimir el historial: {e}"))
        else:
            state.messages.append(AIMessage(content="Error: Herramienta de resumen no encontrada."))
        return state
    return state

def call_llm_node(state: AgentState, llm_service: LLMService) -> AgentState:
    """Llama al LLM con el historial actual de mensajes para obtener una acción o respuesta."""
    history = state.history_for_api
    response = llm_service.invoke(history)

    if isinstance(response, AIMessage):
        state.messages.append(response)
        return state

    # Procesar la respuesta del modelo, que puede contener llamadas a herramientas o texto
    if response.candidates and response.candidates[0].content.parts:
        tool_calls = []
        text_response_parts = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call.name:
                tool_name = part.function_call.name
                tool_args = {key: value for key, value in part.function_call.args.items()}
                tool_calls.append({"name": tool_name, "args": tool_args, "id": tool_name}) # Usamos el nombre como ID por simplicidad
            elif hasattr(part, 'text') and part.text:
                text_response_parts.append(part.text)
        
        if tool_calls:
            ai_message = AIMessage(content="", tool_calls=tool_calls)
            state.messages.append(ai_message)
        elif text_response_parts:
            text_response = "".join(text_response_parts)
            state.messages.append(AIMessage(content=text_response))
    else:
        error_message = "El modelo no proporcionó una respuesta válida."
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            error_message += f" Razón de bloqueo: {response.prompt_feedback.block_reason.name}"
        state.messages.append(AIMessage(content=error_message))
    
    return state

def explain_action_node(state: AgentState, llm_service: LLMService) -> AgentState:
    """Genera una explicación en lenguaje natural de la acción (comando/código) a ejecutar."""
    last_ai_message = state.messages[-1]
    tool_call = last_ai_message.tool_calls[0]
    tool_name = tool_call['name']
    tool_args = tool_call['args']
    
    explanation_content = ""
    action_type = ""
    action_code_or_command = ""

    if tool_name == "execute_command":
        action_type = "comando de terminal"
        action_code_or_command = tool_args.get('command', 'N/A')
        explanation_content = f"El siguiente comando de terminal será ejecutado: `{action_code_or_command}`. Por favor, explica en lenguaje natural qué hará este comando y por qué es necesario para la tarea actual. Sé conciso y claro."
    elif tool_name == "python_executor":
        action_type = "código Python"
        action_code_or_command = tool_args.get('code', 'N/A')
        explanation_content = f"El siguiente código Python será ejecutado:
```python
{action_code_or_command}
```
Por favor, explica en lenguaje natural qué hará este código y por qué es necesario para la tarea actual. Sé conciso y claro."
    else:
        # Si es otra herramienta que no requiere confirmación, la ejecutamos directamente
        # Esto debería ser manejado por should_continue para evitar llegar aquí
        return execute_tool_node(state, llm_service)

    # Llamar al modelo para obtener una explicación
    temp_history = state.history_for_api[:-1] # Eliminar el último mensaje del AI con la llamada a herramienta
    temp_history.append(HumanMessage(content=explanation_content)) # Añadir el prompt de explicación como HumanMessage
    
    explanation_response = llm_service.invoke(temp_history)
    explanation_text = ""
    if explanation_response.candidates and explanation_response.candidates[0].content.parts:
        explanation_text = explanation_response.candidates[0].content.parts[0].text
    
    # Añadir la explicación al historial
    state.messages.append(AIMessage(content=explanation_text))
    
    # Establecer la acción para confirmar
    state.action_to_confirm = {
        "type": "command" if tool_name == "execute_command" else "python",
        "content": action_code_or_command,
        "tool_call_id": tool_call['id']
    }
    return state

def execute_tool_node(state: AgentState, llm_service: LLMService) -> AgentState:
    """Ejecuta las herramientas solicitadas por el modelo, asumiendo que ya han sido confirmadas
    o no requieren confirmación."""
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return state

    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call['name']
        tool_args = tool_call['args']
        tool_id = tool_call['id']

        console.print(f"\n[bold blue]🛠️ Ejecutando herramienta:[/bold blue] [yellow]{tool_name}[/yellow]")
        
        tool = llm_service.get_tool(tool_name)
        if not tool:
            tool_output = f"Error: Herramienta '{tool_name}' no encontrada."
        else:
            try:
                # Si la herramienta es python_executor, y ya hemos pasado por confirmación,
                # el terminal ya habrá gestionado la ejecución interactiva.
                # Aquí, simplemente invocamos la herramienta.
                tool_output = tool.invoke(tool_args)
            except Exception as e:
                tool_output = f"Error al ejecutar la herramienta {tool_name}: {e}"
        
        console.print(f"[bold green]✅ Salida de la herramienta:[/bold green]\n[dim]{escape(str(tool_output))}[/dim]")
        
        tool_messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_id))

    state.messages.extend(tool_messages)
    state.action_to_confirm = None # Limpiar la acción pendiente de confirmación
    return state

# --- Lógica Condicional del Grafo ---

def should_continue(state: AgentState, auto_approve: bool) -> str:
    """Decide si continuar llamando a herramientas, pedir confirmación o finalizar."""
    last_message = state.messages[-1]

    if state.action_to_confirm:
        # Si hay una acción pendiente de confirmación, la terminal debe pedir aprobación
        # A menos que auto_approve sea True
        if auto_approve:
            state.action_to_confirm = None # Limpiar la acción para que no se pida confirmación
            return "execute_tool" # Ir directamente a ejecutar la herramienta
        else:
            return "await_confirmation"
    elif isinstance(last_message, AIMessage) and last_message.tool_calls:
        # Si el LLM ha solicitado una herramienta
        tool_name = last_message.tool_calls[0]['name']
        if tool_name in ["execute_command", "python_executor"]:
            if auto_approve:
                # Si auto_approve es True, omitir explicación y confirmación
                return "execute_tool"
            else:
                return "explain_action" # Pedir explicación y confirmación
        else:
            return "execute_tool" # Ejecutar directamente otras herramientas
    elif isinstance(last_message, AIMessage) and last_message.content.startswith("Historial resumido y reemplazado con:"):
        # Si el historial fue resumido, finaliza la interacción
        return END
    else:
        return END # No hay más acciones o llamadas a herramientas, finaliza

# --- Construcción del Grafo ---

def create_kogni_interpreter_agent(llm_service: LLMService, auto_approve: bool = False):
    kogni_interpreter_graph = StateGraph(AgentState)

    kogni_interpreter_graph.add_node("preprocess_user_message", functools.partial(preprocess_user_message_node, llm_service=llm_service))
    kogni_interpreter_graph.add_node("call_llm", functools.partial(call_llm_node, llm_service=llm_service))
    kogni_interpreter_graph.add_node("explain_action", functools.partial(explain_action_node, llm_service=llm_service))
    kogni_interpreter_graph.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service))
    kogni_interpreter_graph.add_node("await_confirmation", lambda state: state) # Nodo pasivo, espera la entrada de la terminal

    kogni_interpreter_graph.set_entry_point("preprocess_user_message")

    kogni_interpreter_graph.add_conditional_edges(
        "preprocess_user_message",
        lambda state: "summarized" if isinstance(state.messages[-1], AIMessage) and state.messages[-1].content.startswith("Historial resumido y reemplazado con:") else "continue_to_llm",
        {
            "summarized": END,
            "continue_to_llm": "call_llm"
        }
    )

    kogni_interpreter_graph.add_conditional_edges(
        "call_llm",
        should_continue,
        {
            "explain_action": "explain_action",
            "execute_tool": "execute_tool",
            "await_confirmation": "await_confirmation",
            END: END
        }
    )
    kogni_interpreter_graph.add_edge("explain_action", "await_confirmation")
    kogni_interpreter_graph.add_edge("await_confirmation", END) # Temporalmente, la terminal re-invocará.
    kogni_interpreter_graph.add_edge("execute_tool", "call_llm") # Después de ejecutar una herramienta, vuelve a preguntar al LLM

    return kogni_interpreter_graph.compile()

