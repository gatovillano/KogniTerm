from __future__ import annotations
from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING
if TYPE_CHECKING:
    from ..llm_service import LLMService
import functools
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.live import Live

from kogniterm.terminal.terminal_ui import TerminalUI
from kogniterm.core.agent_state import AgentState
from kogniterm.core.exceptions import UserConfirmationRequired

console = Console()

# --- Mensaje de Sistema del Agente de Código ---
SYSTEM_MESSAGE = SystemMessage(content="""INSTRUCCIÓN CRÍTICA: Eres el Agente de Código de KogniTerm (CodeAgent).
Tu rol es ser un Desarrollador Senior y Arquitecto de Software experto en Python, JavaScript/TypeScript y diseño de sistemas.

**Tus Principios Fundamentales:**
1.  **Calidad sobre Velocidad**: Prefieres una solución robusta y bien probada a un parche rápido.
2.  **"Trust but Verify" (Confía pero Verifica)**: NUNCA asumas el contenido de un archivo. Antes de editar, SIEMPRE lee el archivo actual. Antes de usar una función, verifica su firma.
3.  **Consistencia**: El código nuevo debe parecer escrito por el mismo autor que el código existente. Respeta las convenciones de estilo (PEP8, ESLint, etc.) del proyecto.
4.  **Seguridad**: Evita vulnerabilidades comunes. Valida entradas. Maneja excepciones explícitamente.

**Tu Flujo de Trabajo:**
1.  **Análisis Preliminar**:
    *   Si te piden modificar código, primero localiza y LEE los archivos relevantes.
    *   Entiende el contexto: ¿Quién llama a esta función? ¿Qué dependencias tiene?
2.  **Planificación**:
    *   Para cambios complejos, esboza mentalmente o en un bloque de pensamiento los pasos a seguir.
3.  **Ejecución**:
    *   Usa `advanced_file_editor` para modificaciones precisas.
    *   Usa `python_executor` para crear scripts de reproducción de bugs o validar lógica aislada si es necesario.
4.  **Verificación**:
    *   Después de editar, verifica que la sintaxis sea correcta.
    *   Si es posible, sugiere o ejecuta una validación rápida.

**Herramientas a tu disposición:**
*   `file_operations`: Para explorar directorios y leer archivos.
*   `advanced_file_editor`: TU HERRAMIENTA PRINCIPAL para editar código. Úsala con precisión.
*   `codebase_search_tool`: Para encontrar referencias, definiciones y ejemplos de uso en el proyecto.
*   `python_executor`: Para ejecutar snippets de Python, probar lógica o correr scripts de mantenimiento.
*   `execute_command`: Para correr linters, tests o comandos de build.

**Instrucciones de Respuesta:**
*   Sé técnico y preciso.
*   Usa Markdown para bloques de código.
*   Explica el "por qué" de tus cambios si no es obvio.
*   Si encuentras un error en el planteamiento del usuario, comunícalo amablemente y propón una mejor alternativa.

Recuerda: Eres el guardián de la calidad del código en KogniTerm.
""")

# --- Funciones Auxiliares (Reutilizadas/Adaptadas de bash_agent) ---

def handle_tool_confirmation(state: AgentState, llm_service: LLMService):
    """Maneja la confirmación de herramientas (idéntico a bash_agent por ahora)."""
    # ... (Lógica de confirmación estándar)
    # Nota: Podríamos importar esto de un módulo común si refactorizáramos, 
    # pero por ahora duplicaré la lógica mínima necesaria o asumiré que el grafo principal lo maneja.
    # Para mantener este archivo autocontenido y funcional como el bash_agent, replicaré la lógica clave.
    
    last_message = state.messages[-1]
    if not isinstance(last_message, ToolMessage):
        state.reset_tool_confirmation()
        return state

    tool_message_content = last_message.content
    tool_id = state.tool_call_id_to_confirm

    if "Aprobado" in tool_message_content:
        console.print("[bold green]✅ Confirmación recibida. Procediendo...[/bold green]")
        tool_name = state.tool_pending_confirmation
        tool_args = state.tool_args_pending_confirmation
    
        if tool_name and tool_args:
            tool = llm_service.get_tool(tool_name)
            if tool:
                if tool_name in ["file_update_tool", "advanced_file_editor"]:
                    tool_args["confirm"] = True
    
                try:
                    raw_tool_output = llm_service._invoke_tool_with_interrupt(tool, tool_args)
                    tool_output_str = str(raw_tool_output)
                    state.messages.append(ToolMessage(content=tool_output_str, tool_call_id=tool_id))
                except Exception as e:
                    error_output = f"Error al re-ejecutar {tool_name}: {e}"
                    state.messages.append(ToolMessage(content=error_output, tool_call_id=tool_id))
            else:
                state.messages.append(ToolMessage(content=f"Herramienta {tool_name} no encontrada.", tool_call_id=tool_id))
    else:
        console.print("[bold yellow]⚠️ Operación denegada.[/bold yellow]")
        state.messages.append(ToolMessage(content="Operación denegada por el usuario.", tool_call_id=tool_id))

    state.reset_tool_confirmation()
    return state

def call_model_node(state: AgentState, llm_service: LLMService, interrupt_queue: Optional[queue.Queue] = None):
    """Llama al LLM (CodeAgent)."""
    # Asegurar que el SystemMessage específico del CodeAgent esté presente
    # Si el historial ya tiene un SystemMessage al principio, lo reemplazamos o nos aseguramos de que sea este.
    # En la arquitectura actual, el state.history_for_api suele construir el historial.
    # Aquí forzaremos el SYSTEM_MESSAGE del CodeAgent como el contexto principal.
    
    # Nota: state.history_for_api es una propiedad calculada. 
    # Para cambiar la "persona", idealmente deberíamos inyectar este mensaje en el contexto.
    # Por simplicidad, lo añadiremos como un SystemMessage efímero si no está, 
    # o confiaremos en que el orquestador lo configure. 
    # PERO, dado que este es un agente independiente, vamos a construir el historial aquí.
    
    messages = [SYSTEM_MESSAGE] + state.messages
    
    # Lógica de streaming y llamada (similar a bash_agent)
    full_response_content = ""
    final_ai_message = None
    
    try:
        from kogniterm.terminal.visual_components import create_processing_spinner
        spinner = create_processing_spinner()
    except ImportError:
        from rich.spinner import Spinner
        spinner = Spinner("dots", text="CodeAgent pensando...")

    with Live(spinner, console=console, screen=False, refresh_per_second=10) as live:
        # Usamos invoke del llm_service pero pasando nuestros mensajes con la persona correcta
        # Nota: llm_service.invoke usa state.history_for_api internamente si no se pasan mensajes.
        # Aquí pasaremos 'messages' explícitamente si la API de llm_service lo permite, 
        # o modificaremos el comportamiento.
        # Revisando bash_agent, llama a llm_service.invoke(history=history...)
        
        for part in llm_service.invoke(history=messages, interrupt_queue=interrupt_queue):
            if isinstance(part, AIMessage):
                final_ai_message = part
            elif isinstance(part, str):
                full_response_content += part
                live.update(Padding(Markdown(full_response_content), (0, 4)))

    if final_ai_message:
        # Reconstruir el mensaje final con el contenido completo streameado
        if not final_ai_message.content and full_response_content:
             final_ai_message.content = full_response_content
             
        state.messages.append(final_ai_message)
        llm_service._save_history(state.messages)
        
        if final_ai_message.tool_calls:
            # Preparar confirmación si es necesario (aunque CodeAgent usa menos confirmaciones de comando, sí de edición)
            # La lógica de confirmación se maneja en execute_tool_node
            pass
            
    return {"messages": state.messages}

def execute_single_tool(tc, llm_service, interrupt_queue):
    """Ejecuta una herramienta individual."""
    tool_name = tc['name']
    tool_args = tc['args']
    tool_id = tc['id']
    
    tool = llm_service.get_tool(tool_name)
    if not tool:
        return tool_id, f"Error: Herramienta '{tool_name}' no encontrada.", None

    try:
        # CodeAgent usa herramientas de análisis y edición.
        # La lógica de ejecución es estándar.
        output = llm_service._invoke_tool_with_interrupt(tool, tool_args)
        return tool_id, str(output), None
    except UserConfirmationRequired as e:
        return tool_id, json.dumps(e.raw_tool_output), e
    except Exception as e:
        return tool_id, f"Error en {tool_name}: {e}", e

def execute_tool_node(state: AgentState, llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    """Nodo de ejecución de herramientas."""
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return state

    tool_messages = []
    executor = ThreadPoolExecutor(max_workers=5)
    futures = []
    
    console.print(f"[bold blue]🔧 CodeAgent utilizando herramientas...[/bold blue]")

    for tool_call in last_message.tool_calls:
        if interrupt_queue and not interrupt_queue.empty():
            interrupt_queue.get()
            state.reset_temporary_state()
            return state
            
        futures.append(executor.submit(execute_single_tool, tool_call, llm_service, interrupt_queue))

    for future in as_completed(futures):
        tool_id, content, exception = future.result()
        
        if isinstance(exception, UserConfirmationRequired):
            # Manejo de confirmación para ediciones críticas
            state.tool_pending_confirmation = exception.tool_name
            state.tool_args_pending_confirmation = exception.tool_args
            state.tool_call_id_to_confirm = tool_id
            state.file_update_diff_pending_confirmation = exception.raw_tool_output
            
            # Importante: No añadimos el mensaje de error todavía, dejamos que el sistema pida confirmación
            # Pero necesitamos registrar que esta herramienta "falló" requiriendo confirmación
            # En el flujo actual, retornamos para pedir input al usuario.
            tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))
            state.messages.extend(tool_messages)
            llm_service._save_history(state.messages)
            return state
            
        tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))

    state.messages.extend(tool_messages)
    llm_service._save_history(state.messages)
    return state

def should_continue(state: AgentState) -> str:
    """Decide si el agente debe continuar."""
    last_message = state.messages[-1]
    
    if state.file_update_diff_pending_confirmation:
        return END # Esperar input del usuario
        
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "execute_tool"
    elif isinstance(last_message, ToolMessage):
        return "call_model"
    
    return END

# --- Construcción del Grafo ---

def create_code_agent(llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None):
    workflow = StateGraph(AgentState)

    workflow.add_node("call_model", functools.partial(call_model_node, llm_service=llm_service, interrupt_queue=interrupt_queue))
    workflow.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))

    workflow.set_entry_point("call_model")

    workflow.add_conditional_edges(
        "call_model",
        should_continue,
        {
            "execute_tool": "execute_tool",
            END: END
        }
    )

    workflow.add_edge("execute_tool", "call_model")

    return workflow.compile()
