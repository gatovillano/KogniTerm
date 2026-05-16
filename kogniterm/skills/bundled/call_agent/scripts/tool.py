"""
Skill: call_agent
Herramienta para invocar agentes especializados
"""

import os
import logging
import threading
from typing import Type, Optional, Dict, Any
from pydantic import BaseModel, Field
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
import json

logger = logging.getLogger(__name__)

console = Console()

# Límite de recursión configurable para el research agent
RESEARCHER_RECURSION_LIMIT = int(os.getenv("RESEARCHER_RECURSION_LIMIT", "1000"))
AUTONOMY_DIALOG_TEXT = (
    "Si se determina aplicar cambios y ejecutar comandos los agentes "
    "serán autónomos y no solicitaran autorización"
)

class CallAgentInput(BaseModel):
    """Schema de entrada para la herramienta call_agent"""
    agent_name: str = Field(..., description="El nombre del agente a invocar: 'code_agent' o 'researcher_agent'.")
    task: str = Field(..., description="La tarea específica que el agente debe realizar.")


class AgentStreamProxy:
    """
    Proxy del terminal_ui que dirige todo el output de streaming al
    AgentStreamWidget montado en el chat log del TUI.
    """

    def __init__(self, original_ui: Any, stream_widget: Any):
        self.original_ui = original_ui
        self.stream_widget = stream_widget  # AgentStreamWidget
        self.console = getattr(original_ui, "console", console)
        self.is_tui = bool(getattr(original_ui, "is_tui", False))
        self.interrupt_queue = getattr(original_ui, "interrupt_queue", None)
        self.app = getattr(original_ui, "app", None)
        self._accumulated = ""

    def _widget_call(self, method_name: str, *args, **kwargs):
        """Llama un método en el widget desde cualquier hilo."""
        if self.stream_widget is None:
            return
        method = getattr(self.stream_widget, method_name, None)
        if method is None:
            return
        try:
            if threading.current_thread() is threading.main_thread():
                method(*args, **kwargs)
            elif self.app is not None:
                self.app.call_from_thread(method, *args, **kwargs)
        except Exception as e:
            logger.debug("AgentStreamProxy._widget_call %s: %s", method_name, e)

    def print_stream(self, text: str, **kwargs):
        if not text:
            return
        self._accumulated += text
        self._widget_call("append_text", text)

    def write_stream_to_chat(self, content: str, **kwargs):
        if not content:
            return
        self._accumulated += content
        self._widget_call("append_text", content)

    def update_live(self, renderable, **kwargs):
        self._widget_call("set_renderable", renderable)

    def stop_live(self, **kwargs):
        self._widget_call("commit")

    def print_tool_notification(self, tool_name: str, action_desc: str = "", **kwargs):
        # Añadir como línea en el panel
        line = f"\n⚙ {tool_name}"
        if action_desc:
            line += f": {action_desc}"
        self._accumulated += line
        self._widget_call("append_text", line)
        self._widget_call("commit")

    def update_terminal_output(self, tool_name: str, output: str, **kwargs):
        if output:
            chunk = f"\n[{tool_name}]\n{output}"
            self._accumulated += chunk
            self._widget_call("append_text", chunk)
            self._widget_call("commit")

    def update_tool_display(self, tool_name: str, output: str, **kwargs):
        self.update_terminal_output(tool_name, output)

    def resume_spinner(self, **kwargs):
        pass

    def print_message(self, message: str, style: str = "", is_user_message: bool = False, status: str = None, use_bubble: bool = False):
        if message:
            self._accumulated += f"\n{message}"
            self._widget_call("append_text", f"\n{message}")
            self._widget_call("commit")

    def print_success_box(self, message: str, title: str = "Éxito"):
        self.print_message(f"✅ {title}: {message}")

    def print_error_box(self, message: str, title: str = "Error"):
        self.print_message(f"❌ {title}: {message}")

    def print_warning_box(self, message: str, title: str = "Advertencia"):
        self.print_message(f"⚠ {title}: {message}")

    def print_confirmation_panel(self, content, title, border_style):
        if original_ui := self.original_ui:
            method = getattr(original_ui, "print_confirmation_panel", None)
            if method:
                method(content, title, border_style)

    def ask_approval_sync(self, message: str, title: str = "Aprobación Requerida", **kwargs) -> bool:
        if self.original_ui:
            method = getattr(self.original_ui, "ask_approval_sync", None)
            if method:
                return method(message=message, title=title, **kwargs)
        return True

    def ask_deep_agent_autonomy_sync(self, agent_label: str) -> bool:
        if self.original_ui:
            method = getattr(self.original_ui, "ask_deep_agent_autonomy_sync", None)
            if method:
                return method(agent_label)
        return True

    def get_interrupt_queue(self):
        if self.original_ui:
            method = getattr(self.original_ui, "get_interrupt_queue", None)
            if method:
                return method()
        return self.interrupt_queue

    def put(self, message):
        if self.original_ui and hasattr(self.original_ui, "put"):
            return self.original_ui.put(message)

    def put_nowait(self, message):
        if self.original_ui and hasattr(self.original_ui, "put_nowait"):
            return self.original_ui.put_nowait(message)

    def __getattr__(self, name):
        if self.original_ui is not None:
            return getattr(self.original_ui, name)
        return lambda *a, **kw: None


def _get_chat_log(terminal_ui: Any):
    """Obtiene el ChatLogWidget desde el terminal_ui si está disponible."""
    try:
        app = getattr(terminal_ui, "app", None)
        if app and hasattr(app, "chat_log"):
            return app.chat_log
    except Exception:
        pass
    return None


def _widget_set_complete(widget: Any, terminal_ui: Any, msg: str = "") -> None:
    """Marca el AgentStreamWidget como completado desde cualquier hilo."""
    app = getattr(terminal_ui, "app", None)
    try:
        if threading.current_thread() is threading.main_thread():
            widget.set_complete()
            if msg:
                widget.append_text(f"\n{msg}")
        elif app is not None:
            def _do():
                widget.set_complete()
                if msg:
                    widget.append_text(f"\n{msg}")
            app.call_from_thread(_do)
    except Exception as e:
        logger.debug("_widget_set_complete: %s", e)


def _widget_set_error(widget: Any, terminal_ui: Any, msg: str = "") -> None:
    """Marca el AgentStreamWidget como error desde cualquier hilo."""
    app = getattr(terminal_ui, "app", None)
    try:
        if threading.current_thread() is threading.main_thread():
            widget.set_error(msg)
        elif app is not None:
            app.call_from_thread(widget.set_error, msg)
    except Exception as e:
        logger.debug("_widget_set_error: %s", e)


def _request_autonomous_execution(agent_label: str, terminal_ui: Any = None) -> bool:
    """Solicita consentimiento antes de iniciar agentes profundos en modo autónomo."""
    if terminal_ui and hasattr(terminal_ui, "ask_deep_agent_autonomy_sync"):
        return bool(terminal_ui.ask_deep_agent_autonomy_sync(agent_label))

    if terminal_ui and hasattr(terminal_ui, "ask_approval_sync"):
        return bool(
            terminal_ui.ask_approval_sync(
                message=AUTONOMY_DIALOG_TEXT,
                title=f"Autonomía de {agent_label}",
            )
        )

    return True

def call_agent_skill(agent_name: str, task: str, llm_service: Any = None, terminal_ui: Any = None, interrupt_queue: Any = None, approval_handler: Any = None) -> str:
    """
    Función principal que implementa la funcionalidad de call_agent
    
    Args:
        agent_name: Nombre del agente a invocar
        task: Tarea específica que el agente debe realizar
        llm_service: Servicio LLM para el agente
        terminal_ui: Interfaz de terminal
        interrupt_queue: Cola de interrupciones
        approval_handler: Manejador de aprobaciones
    
    Returns:
        str: Resultado de la ejecución del agente
    """
    is_tui = bool(getattr(terminal_ui, "is_tui", False))

    # --- Montar el panel de streaming en el TUI ---
    stream_widget = None
    agent_ui = terminal_ui  # por defecto usar el terminal_ui original

    if is_tui:
        chat_log = _get_chat_log(terminal_ui)
        if chat_log is not None:
            display_name = {
                "code_agent": "DeepCoder",
                "code_crew": "DeepCoder",
                "researcher_agent": "DeepResearcher",
            }.get(agent_name, agent_name)
            try:
                stream_widget = chat_log.mount_agent_stream(display_name)
                if stream_widget is not None:
                    agent_ui = AgentStreamProxy(terminal_ui, stream_widget)
            except Exception as e:
                logger.warning("No se pudo montar AgentStreamWidget: %s", e)
        # Mostrar header en el chat log principal
        if terminal_ui and hasattr(terminal_ui, "print_message"):
            terminal_ui.print_message(
                f"🤖 Delegando tarea a **{display_name}**…",
                style="bold green",
            )
    else:
        console.print(f"\n[bold green]🤖 Delegando tarea a: {agent_name}[/bold green]")
        console.print(f"[italic]Tarea: {task}[/italic]\n")

    if agent_name == "code_agent" or agent_name == "code_crew":
        from kogniterm.core.agents.deep_coder import create_deep_coder
        
        agent_display = "DeepCoder" if agent_name == "code_agent" else "DeepCoder (Legacy Crew Name)"
        if not is_tui:
            console.print(f"[dim]ℹ️  Invocando al motor de desarrollo profundo ({agent_display})...[/dim]")
        
        from kogniterm.core.agent_state import AgentState
        from langchain_core.messages import HumanMessage

        if not _request_autonomous_execution(agent_display, terminal_ui):
            if stream_widget is not None:
                _widget_set_complete(stream_widget, terminal_ui, "Cancelado por el usuario.")
            return f"Ejecución de {agent_display} cancelada por el usuario."
        
        agent_graph = create_deep_coder(llm_service, agent_ui, interrupt_queue)
        initial_state = AgentState(messages=[HumanMessage(content=task)], autonomous_approvals=True)
        
        try:
            final_state = agent_graph.invoke(initial_state, config={"recursion_limit": RESEARCHER_RECURSION_LIMIT})
            last_message = final_state["messages"][-1]
            
            result_str = last_message.content
            
            if not result_str.strip():
                logger.warning(f"{agent_display} devolvió un resultado vacío.")
                if stream_widget is not None:
                    _widget_set_error(stream_widget, terminal_ui, "Sin resultado.")
                return "Error: El motor de desarrollo no pudo generar un resultado."

            if stream_widget is not None:
                _widget_set_complete(stream_widget, terminal_ui)
            elif not is_tui:
                console.print(Panel(
                    Markdown(result_str),
                    title=f"[bold green]✅ Tarea de Código Finalizada por {agent_display}[/bold green]",
                    border_style="green",
                    padding=(1, 2)
                ))
            return f"Respuesta de {agent_display}:\n\n{result_str}"
        except Exception as e:
            error_msg = f"Error al ejecutar {agent_display}: {str(e)}"
            logger.error(error_msg)
            if stream_widget is not None:
                _widget_set_error(stream_widget, terminal_ui, str(e))
            return error_msg

    elif agent_name == "researcher_agent":
        from kogniterm.core.agents.deep_researcher import create_deep_researcher
        
        if not is_tui:
            console.print("[dim]ℹ️  Invocando al motor de investigación profunda (DeepResearcher)...[/dim]")
        
        from kogniterm.core.agent_state import AgentState
        from langchain_core.messages import HumanMessage

        if not _request_autonomous_execution("DeepResearcher", terminal_ui):
            if stream_widget is not None:
                _widget_set_complete(stream_widget, terminal_ui, "Cancelado por el usuario.")
            return "Ejecución de DeepResearcher cancelada por el usuario."
        
        agent_graph = create_deep_researcher(llm_service, agent_ui, interrupt_queue)
        initial_state = AgentState(messages=[HumanMessage(content=task)], autonomous_approvals=True)
        
        try:
            final_state = agent_graph.invoke(initial_state, config={"recursion_limit": RESEARCHER_RECURSION_LIMIT})
            last_message = final_state["messages"][-1]
            
            result_str = last_message.content
            
            if not result_str.strip():
                logger.warning("DeepResearcher devolvió un resultado vacío.")
                if stream_widget is not None:
                    _widget_set_error(stream_widget, terminal_ui, "Sin resultado.")
                return "Error: El motor de investigación no pudo generar un resultado."

            if stream_widget is not None:
                _widget_set_complete(stream_widget, terminal_ui)
            elif not is_tui:
                console.print(Panel(
                    Markdown(result_str),
                    title="[bold green]✅ Informe de Investigación Finalizado[/bold green]",
                    border_style="green",
                    padding=(1, 2)
                ))
            return f"Respuesta de DeepResearcher:\n\n{result_str}"
        except Exception as e:
            error_msg = f"Error al ejecutar DeepResearcher: {str(e)}"
            logger.error(error_msg)
            if stream_widget is not None:
                _widget_set_error(stream_widget, terminal_ui, str(e))
            return error_msg

    else:
        return f"Error: Agente '{agent_name}' no reconocido. Opciones válidas: 'code_agent', 'researcher_agent'."

# Schema para el LLM
tool_schema = {
    "name": "call_agent",
    "description": "Invoca a un agente especializado para realizar tareas complejas. Agentes disponibles: 'code_agent' (para tareas de código y edición), 'researcher_agent' (para investigación y tareas complejas).",
    "parameters": {
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "description": "El nombre del agente a invocar: 'code_agent' o 'researcher_agent'.",
                "enum": ["code_agent", "researcher_agent"]
            },
            "task": {
                "type": "string",
                "description": "La tarea específica que el agente debe realizar."
            }
        },
        "required": ["agent_name", "task"]
    }
}
