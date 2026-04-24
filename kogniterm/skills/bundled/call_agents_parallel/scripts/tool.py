"""
Skill: call_agents_parallel
Herramienta para invocar a DeepCoder y DeepResearcher en paralelo
"""
import os
import logging
from typing import Any
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()

RESEARCHER_RECURSION_LIMIT = int(os.getenv("RESEARCHER_RECURSION_LIMIT", "100"))

class TerminalUIProxy:
    def __init__(self, original_ui, panel_id):
        self.original_ui = original_ui
        self.panel_id = panel_id
        # Use the original UI's console (e.g., TextualTerminalUI.DummyConsole)
        # so live/stream contexts target the TUI panels instead of stdout.
        self.console = getattr(original_ui, "console", console)
        self.is_tui = bool(getattr(original_ui, "is_tui", False))
        self.interrupt_queue = getattr(original_ui, "interrupt_queue", None)

    def _call_forward(self, method_name: str, *args, **kwargs):
        """Forward a UI call to the original UI, injecting panel_id when supported.

        Adds debug logging and a fallback to try calling the same method on
        `original_ui.app` (Textual app) when the primary call fails.
        """
        if self.original_ui is None:
            logger.debug("TerminalUIProxy: no original_ui to forward %s", method_name)
            return None

        # Prefer the attribute on the original UI
        if hasattr(self.original_ui, method_name):
            target = self.original_ui
        # Fallback: sometimes the textual App is wrapped in `.app`
        elif hasattr(self.original_ui, "app") and hasattr(self.original_ui.app, method_name):
            target = self.original_ui.app
        else:
            logger.debug("TerminalUIProxy: neither original_ui nor original_ui.app expose %s", method_name)
            return None

        method = getattr(target, method_name)
        try:
            import inspect
            sig = inspect.signature(method)
            call_kwargs = dict(kwargs)
            if "panel_id" in sig.parameters and "panel_id" not in call_kwargs:
                call_kwargs["panel_id"] = self.panel_id

            # Filtrar kwargs no soportados por la firma para evitar TypeError.
            accepted = {k: v for k, v in call_kwargs.items() if k in sig.parameters}
            logger.debug("TerminalUIProxy: calling %s on %s args=%s kwargs=%s", method_name, type(target).__name__, args, accepted)
            return method(*args, **accepted)
        except Exception as exc:
            logger.exception("TerminalUIProxy: error calling %s on %s: %s", method_name, type(target).__name__, exc)
            # Last-ditch attempt: call without signature filtering
            try:
                return method(*args, **kwargs)
            except Exception:
                logger.exception("TerminalUIProxy: final fallback failed for %s", method_name)
                return None
        
    def __getattr__(self, name):
        # Delegate attribute access to the original UI when possible.
        # __getattr__ is only called when the normal attribute lookup fails,
        # so this safely proxies missing attributes to the wrapped UI.
        if self.original_ui is None:
            return lambda *args, **kwargs: None
        return getattr(self.original_ui, name)
        
    def print_stream(self, text: str):
        return self._call_forward("print_stream", text)
        
    def write_stream_to_chat(self, content: str):
        return self._call_forward("write_stream_to_chat", content)
        
    def update_live(self, renderable):
        return self._call_forward("update_live", renderable)
        
    def print_message(self, message: str, style: str = "", is_user_message: bool = False, status: str = None, use_bubble: bool = False):
        return self._call_forward(
            "print_message",
            message,
            style,
            is_user_message,
            status,
            use_bubble,
        )

    def print_tool_notification(self, tool_name: str, action_desc: str = ""):
        return self._call_forward("print_tool_notification", tool_name, action_desc)

    def print_success_box(self, message: str, title: str = "Éxito"):
        return self._call_forward("print_success_box", message, title)
        
    def print_error_box(self, message: str, title: str = "Error"):
        return self._call_forward("print_error_box", message, title)

    def print_warning_box(self, message: str, title: str = "Advertencia"):
        return self._call_forward("print_warning_box", message, title)
        
    def update_terminal_output(self, tool_name: str, output: str, command: str = "", show_cursor: bool = None):
        return self._call_forward(
            "update_terminal_output",
            tool_name,
            output,
            command,
            show_cursor=show_cursor,
        )

    def update_tool_display(self, tool_name: str, output: str, command: str = "", max_lines: int | None = None):
        return self._call_forward(
            "update_tool_display",
            tool_name,
            output,
            command,
            max_lines=max_lines,
        )
        
    def stop_live(self):
        return self._call_forward("stop_live")
    
    def put(self, message):
        if self.original_ui is not None and hasattr(self.original_ui, 'put'):
            return self.original_ui.put(message)
        logger.warning(f"TerminalUIProxy: put() no disponible en original_ui")

    def put_nowait(self, message):
        if self.original_ui is not None and hasattr(self.original_ui, 'put_nowait'):
            return self.original_ui.put_nowait(message)
        logger.warning(f"TerminalUIProxy: put_nowait() no disponible en original_ui")


class ParallelPanelUI:
    """Concrete wrapper that forces calls to the TUI with an explicit panel_id.

    This avoids relying on signature inspection and guarantees that streaming
    and tool outputs target the intended parallel panel widgets.
    """
    def __init__(self, original_ui, panel_id):
        self.original_ui = original_ui
        self.panel_id = panel_id
        self.console = getattr(original_ui, "console", console)
        self.is_tui = bool(getattr(original_ui, "is_tui", False))
        self.interrupt_queue = getattr(original_ui, "interrupt_queue", None)
        self.app = getattr(original_ui, "app", original_ui)

    def _safe_call_app(self, method_name, *args, **kwargs):
        try:
            if hasattr(self.original_ui, method_name):
                method = getattr(self.original_ui, method_name)
                return method(*args, **{**kwargs, "panel_id": self.panel_id})
            if hasattr(self.app, method_name):
                method = getattr(self.app, method_name)
                return method(*args, **{**kwargs, "panel_id": self.panel_id})
        except Exception:
            logger.exception("ParallelPanelUI: error calling %s", method_name)
        return None

    def update_live(self, renderable):
        return self._safe_call_app("update_live", renderable)

    def write_stream_to_chat(self, content: str):
        return self._safe_call_app("write_stream_to_chat", content)

    def print_stream(self, text: str):
        return self._safe_call_app("print_stream", text)

    def update_terminal_output(self, tool_name: str, output: str, command: str = "", show_cursor: bool = None):
        return self._safe_call_app("update_terminal_output", tool_name, output, command, show_cursor=show_cursor)

    def update_tool_display(self, tool_name: str, output: str, command: str = "", max_lines: int | None = None):
        return self._safe_call_app("update_tool_display", tool_name, output, command, max_lines=max_lines)

    def print_tool_notification(self, tool_name: str, action_desc: str = ""):
        return self._safe_call_app("print_tool_notification", tool_name, action_desc)

    def stop_live(self):
        return self._safe_call_app("stop_live")

    def put(self, message):
        if self.original_ui is not None and hasattr(self.original_ui, 'put'):
            return self.original_ui.put(message)

    def put_nowait(self, message):
        if self.original_ui is not None and hasattr(self.original_ui, 'put_nowait'):
            return self.original_ui.put_nowait(message)

def call_agents_parallel(task_coder: str, task_researcher: str, llm_service: Any = None, terminal_ui: Any = None, interrupt_queue: Any = None, approval_handler: Any = None) -> str:
    """Invoca ambos agentes en paralelo"""
    from kogniterm.core.agents.deep_coder import create_deep_coder
    from kogniterm.core.agents.deep_researcher import create_deep_researcher
    from kogniterm.core.agent_state import AgentState
    from langchain_core.messages import HumanMessage
    import concurrent.futures

    console.print("\n[bold green]Iniciando agentes en PARALELO[/bold green]")

    # Resolver terminal_ui / interrupt_queue desde llm_service si no fueron inyectados.
    import queue as _queue
    if terminal_ui is None and llm_service is not None:
        terminal_ui = getattr(llm_service, "terminal_ui", None)
    if interrupt_queue is None and llm_service is not None:
        interrupt_queue = getattr(llm_service, "interrupt_queue", None)
    # Garantizar un objeto queue válido para evitar KeyboardHandler con None
    if interrupt_queue is None:
        interrupt_queue = _queue.Queue()

    logger.debug("call_agents_parallel: terminal_ui=%s interrupt_queue_set=%s", type(terminal_ui).__name__ if terminal_ui else None, bool(interrupt_queue))
    
    def _resolve_tui_app(ui_obj: Any):
        """Obtiene la instancia App de Textual desde un posible wrapper."""
        current = ui_obj
        visited = set()
        for _ in range(4):
            if current is None:
                return None
            marker = id(current)
            if marker in visited:
                break
            visited.add(marker)
            if hasattr(current, "query_one") and hasattr(current, "call_from_thread"):
                return current
            if hasattr(current, "app"):
                current = getattr(current, "app")
                continue
            break
        return None

    # Activar layout de dos columnas para paneles paralelos
    if terminal_ui and getattr(terminal_ui, "is_tui", False):
        try:
            target_app = _resolve_tui_app(terminal_ui)
            if target_app is None:
                raise RuntimeError("No se pudo resolver la app TUI")
            
            # Forzar activación de paneles desde el hilo principal de Textual
            def _activate_panels():
                # Primero asegurar que el contenedor padre bottom_container sea visible
                # ya que tiene display:none en CSS y los hijos no se muestran sin él
                try:
                    bottom_container = target_app.query_one("#bottom_container")
                    bottom_container.display = True
                    logger.debug("bottom_container display=True")
                except Exception as e:
                    logger.warning("No se pudo hacer visible bottom_container: %s", e)

                container = target_app.query_one("#parallel_agents_container")
                container.display = True
                
                # Activar paneles individuales
                target_app.live_display_coder.display = True
                target_app.live_display_researcher.display = True
                
                # Ocultar panel único y tool display para dar espacio
                target_app.live_display.display = False
                target_app.tool_display.display = False
            
            import threading
            if threading.current_thread() is threading.main_thread():
                _activate_panels()
            else:
                target_app.call_from_thread(_activate_panels)
            logger.info("Paneles duales activados correctamente")
        except Exception as e:
            logger.error("Error activando paneles paralelos: %s", e)
    
    # Use a concrete wrapper that forces the `panel_id` to ensure outputs
    # are rendered in the two-column parallel panels.
    ui_coder = ParallelPanelUI(terminal_ui, "live_display_coder")
    ui_researcher = ParallelPanelUI(terminal_ui, "live_display_researcher")
    
    # Esperar 0.3 segundos para que la UI renderice los paneles antes de iniciar agentes
    import time
    time.sleep(0.3)
    
    agent_coder = create_deep_coder(llm_service, ui_coder, interrupt_queue)
    agent_researcher = create_deep_researcher(llm_service, ui_researcher, interrupt_queue)
    
    def run_coder():
        state = AgentState(messages=[HumanMessage(content=task_coder)])
        try:
            res = agent_coder.invoke(state, config={"recursion_limit": RESEARCHER_RECURSION_LIMIT})
            return f"RESULTADO DEEP CODER:\n{res['messages'][-1].content}"
        except Exception as e:
            return f"Error en Deep Coder: {e}"

    def run_researcher():
        state = AgentState(messages=[HumanMessage(content=task_researcher)])
        try:
            res = agent_researcher.invoke(state, config={"recursion_limit": RESEARCHER_RECURSION_LIMIT})
            return f"RESULTADO DEEP RESEARCHER:\n{res['messages'][-1].content}"
        except Exception as e:
            return f"Error en Deep Researcher: {e}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f_coder = executor.submit(run_coder)
        f_res = executor.submit(run_researcher)
        
        result_coder = f_coder.result()
        result_res = f_res.result()

    # Consolidar: mover contenido de los paneles al chat log y ocultarlos
    try:
        target_app = _resolve_tui_app(terminal_ui)
        if target_app is None:
            raise RuntimeError("No se pudo resolver la app TUI")
        
        # Primero desactivar los listeners de teclado antes de eliminar paneles
        import asyncio
        if hasattr(target_app, '_keyboard_handler'):
            target_app._keyboard_handler = None
            
        if hasattr(target_app, 'consolidate_parallel_panels'):
            target_app.consolidate_parallel_panels()
        else:
            def _deactivate_panels():
                container = target_app.query_one("#parallel_agents_container")
                container.display = False
                target_app.live_display_coder.display = False
                target_app.live_display_researcher.display = False
                target_app.live_display.display = True
                target_app.tool_display.display = True
                target_app.live_display_coder.update("")
                target_app.live_display_researcher.update("")
            import threading
            if threading.current_thread() is threading.main_thread():
                _deactivate_panels()
            else:
                target_app.call_from_thread(_deactivate_panels)
            
    except Exception as e:
        logger.error(f"Error consolidando paneles paralelos: {e}")
        
    return f"{result_coder}\n\n{'='*40}\n\n{result_res}"

tool_schema = {
    "name": "call_agents_parallel",
    "description": "Invoca a DeepCoder y DeepResearcher simultáneamente para acelerar el procesamiento paralelo de tareas complementarias.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_coder": {
                "type": "string",
                "description": "La tarea específica que debe realizar el DeepCoder (desarrollo, edición de código, refactorización)."
            },
            "task_researcher": {
                "type": "string",
                "description": "La tarea específica que debe realizar el DeepResearcher (investigación, análisis de archivos, diseño)."
            }
        },
        "required": ["task_coder", "task_researcher"]
    }
}
