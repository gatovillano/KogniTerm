"""
Skill: call_agents_parallel
Herramienta para invocar a DeepCoder y DeepResearcher en paralelo
"""
import os
import logging
import threading
from typing import Any
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()

RESEARCHER_RECURSION_LIMIT = int(os.getenv("RESEARCHER_RECURSION_LIMIT", "1000"))
AUTONOMY_DIALOG_TEXT = (
    "Si se determina aplicar cambios y ejecutar comandos los agentes "
    "serán autónomos y no solicitaran autorización"
)


def _request_autonomous_execution(agent_label: str, terminal_ui: Any = None) -> bool:
    """Solicita consentimiento para arrancar agentes profundos en modo autónomo."""
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

    En LOCAL mode (TUI directa sin WS) accede directamente a los widgets Textual.
    En SERVER mode (TUI conectada via WS) enruta via _push() con agent_id para
    que los eventos lleguen al panel correcto a través del WebSocket.
    """
    def __init__(self, original_ui, panel_id):
        self.original_ui = original_ui
        self.panel_id = panel_id
        self.console = getattr(original_ui, "console", console)
        self.is_tui = bool(getattr(original_ui, "is_tui", False))
        self.interrupt_queue = getattr(original_ui, "interrupt_queue", None)
        self.app = getattr(original_ui, "app", original_ui)
        self._accumulated_text = ""
        self._last_update_time = 0
        self._update_interval = 0.05  # 50ms (20 FPS max)

    @property
    def _is_server_mode(self) -> bool:
        """True cuando original_ui es un ServerUI (modo WS), no una TUI Textual."""
        return hasattr(self.original_ui, '_push') and not hasattr(self.original_ui, 'query_one')

    def _safe_call_app(self, method_name, *args, **kwargs):
        try:
            # Forzar panel_id en todos los casos
            kwargs["panel_id"] = self.panel_id
            
            if hasattr(self.original_ui, method_name):
                method = getattr(self.original_ui, method_name)
                return method(*args, **kwargs)
            if hasattr(self.app, method_name):
                method = getattr(self.app, method_name)
                return method(*args, **kwargs)
        except Exception:
            logger.exception("ParallelPanelUI: error calling %s", method_name)
        return None

    def _get_tui_panel(self):
        """Retorna el widget ChatLogWidget del panel en modo TUI local."""
        try:
            # Primero intentar obtenerlo como atributo directo de la app (más rápido y seguro)
            if hasattr(self.app, self.panel_id):
                return getattr(self.app, self.panel_id)
            if hasattr(self.app, 'query_one'):
                return self.app.query_one(f"#{self.panel_id}")
        except Exception as e:
            logger.exception("ParallelPanelUI: Error querying panel %s: %s", self.panel_id, e)
        return None

    def update_live(self, renderable, **kwargs):
        """Update the panel with the given renderable."""
        if self._is_server_mode:
            # En modo servidor enviamos como live_update con agent_id
            if isinstance(renderable, str):
                self.original_ui._push("live_update", {"thinking": "", "response": renderable}, agent_id=self.panel_id)
            elif isinstance(renderable, tuple):
                self.original_ui._push("live_update", {"thinking": "", "response": str(renderable)}, agent_id=self.panel_id)
            else:
                try:
                    from io import StringIO
                    from rich.console import Console as RichConsole
                    buf = StringIO()
                    c = RichConsole(file=buf, force_terminal=False, no_color=True, width=120)
                    c.print(renderable)
                    self.original_ui._push("live_update", {"thinking": "", "response": buf.getvalue()}, agent_id=self.panel_id)
                except Exception:
                    pass
            return

        # Modo TUI local: acceso directo al widget
        def _update():
            try:
                panel = self._get_tui_panel()
                if panel is None:
                    logger.warning("ParallelPanelUI: Panel %s not found in TUI application", self.panel_id)
                    return
                if hasattr(panel, "write_stream"):
                    panel.write_stream(renderable)
                elif hasattr(panel, "update"):
                    panel.update(renderable)
                if hasattr(panel, "scroll_end"):
                    panel.scroll_end(animate=False)
            except Exception as e:
                logger.exception("ParallelPanelUI: Error during panel %s _update: %s", self.panel_id, e)
        
        if threading.current_thread() is threading.main_thread():
            _update()
        else:
            try:
                self.app.call_from_thread(_update)
            except Exception as e:
                logger.exception("ParallelPanelUI: Error scheduling call_from_thread: %s", e)

    def stop_live(self, *args, **kwargs):
        """Called by the agent when a node finishes streaming."""
        if self._is_server_mode:
            self.original_ui._push("live_stop", {}, agent_id=self.panel_id)
            self._accumulated_text = ""
            return

        # Modo TUI local
        def _stop():
            try:
                panel = self._get_tui_panel()
                if panel and hasattr(panel, "stop_stream"):
                    panel.stop_stream()
            except Exception:
                pass
        
        if threading.current_thread() is threading.main_thread():
            _stop()
        else:
            try:
                self.app.call_from_thread(_stop)
            except Exception:
                pass
        self._accumulated_text = ""

    def write_stream_to_chat(self, *args, **kwargs):
        return self._safe_call_app("write_stream_to_chat", *args, **kwargs)

    def print_stream(self, text: str):
        if not text:
            return
        logger.info(f"ParallelPanelUI.print_stream: received text chunk for {self.panel_id}: {repr(text[:30])}")
        self._accumulated_text += text

        if self._is_server_mode:
            # En modo servidor: enviar como evento stream con agent_id
            self.original_ui._push("stream", text, agent_id=self.panel_id)
            return

        # Modo TUI local: actualizar el panel directamente
        return self.update_live(self._accumulated_text)

    def print_message(self, message: str, style: str = "", is_user_message: bool = False, status: str = None, use_bubble: bool = False):
        if self._is_server_mode:
            self.original_ui._push("message", {"text": message}, agent_id=self.panel_id)
            return
        return self._call_forward(
            "print_message",
            message,
            style,
            is_user_message,
            status,
            use_bubble,
        )

    def update_terminal_output(self, tool_name: str, output: str, command: str = "", **kwargs):
        if not output:
            return
        if self._is_server_mode:
            # Acumular y enviar como live_update
            msg = f"\n**$ {command or tool_name}**\n```\n{output}\n```"
            self._accumulated_text += msg
            self.original_ui._push("live_update", {"thinking": "", "response": self._accumulated_text}, agent_id=self.panel_id)
            return
        # Acumular la salida de la herramienta en el historial del panel
        msg = f"\n\n**$ {command or tool_name}**\n```bash\n{output}\n```\n"
        self._accumulated_text += msg
        return self.update_live(self._accumulated_text)

    def update_tool_display(self, *args, **kwargs):
        return self.update_terminal_output(*args, **kwargs)

    def print_tool_notification(self, tool_name: str, action_desc: str = "", skill_name: str = "", **kwargs):
        if self._is_server_mode:
            self.original_ui._push("tool_call", {"name": tool_name, "description": action_desc, "skill": skill_name}, agent_id=self.panel_id)
            return
        # Acumular la notificación en el historial
        msg = f"\n**⚙ {skill_name or tool_name}**"
        if action_desc:
            msg += f": *{action_desc}*"
        self._accumulated_text += msg + "\n"
        return self.update_live(self._accumulated_text)

    def _call_forward(self, method_name: str, *args, **kwargs):
        """Delegar al original_ui en modo TUI local."""
        if self.original_ui is None:
            return None
        if hasattr(self.original_ui, method_name):
            target = self.original_ui
        elif hasattr(self.app, method_name):
            target = self.app
        else:
            return None
        method = getattr(target, method_name)
        try:
            import inspect
            sig = inspect.signature(method)
            call_kwargs = dict(kwargs)
            if "panel_id" not in call_kwargs:
                call_kwargs["panel_id"] = self.panel_id
            
            # Si el método acepta **kwargs (VAR_KEYWORD), pasamos todos los argumentos
            has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
            if has_var_keyword:
                accepted = call_kwargs
            else:
                accepted = {k: v for k, v in call_kwargs.items() if k in sig.parameters}
            return method(*args, **accepted)
        except Exception:
            try:
                return method(*args, **kwargs)
            except Exception:
                return None

    def put(self, message):
        if self.original_ui is not None and hasattr(self.original_ui, 'put'):
            return self.original_ui.put(message)

    def put_nowait(self, message):
        if self.original_ui is not None and hasattr(self.original_ui, 'put_nowait'):
            return self.original_ui.put_nowait(message)

    def __getattr__(self, name):
        if self.original_ui is None:
            return lambda *args, **kwargs: None
        return getattr(self.original_ui, name)

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

    coder_authorized = _request_autonomous_execution("DeepCoder", terminal_ui)
    researcher_authorized = _request_autonomous_execution("DeepResearcher", terminal_ui)

    if not coder_authorized and not researcher_authorized:
        return "Ejecución paralela cancelada por el usuario."
    
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

    # Activar layout de paneles paralelos
    is_server_mode = hasattr(terminal_ui, '_push') and not hasattr(terminal_ui, 'query_one')

    if is_server_mode:
        # Modo WS: notificar a la TUI via eventos WebSocket
        try:
            terminal_ui.show_agent_panel("live_display_coder", "DeepCoder")
            terminal_ui.show_agent_panel("live_display_researcher", "DeepResearcher")
        except Exception as e:
            logger.warning("No se pudieron emitir agent_panel_show events: %s", e)
    elif terminal_ui and getattr(terminal_ui, "is_tui", False):
        # Modo TUI local: activar paneles directamente
        try:
            target_app = _resolve_tui_app(terminal_ui)
            if target_app is None:
                raise RuntimeError("No se pudo resolver la app TUI")
            
            def _activate_panels():
                """Se ejecuta en el hilo principal de Textual."""
                try:
                    # Mostrar el contenedor de paneles paralelos (TabbedContent)
                    target_app.query_one("#bottom_container").display = True
                    container = target_app.query_one("#parallel_agents_container")
                    container.display = True
                    try:
                        target_app.query_one("#tracker_container").add_class("parallel-mode")
                        target_app.query_one("#tracker_container").display = True
                    except Exception:
                        pass

                    # NOTA: NO ocultamos #input_container ni StatusFooter
                    # El usuario debe poder continuar interactuando con el agente principal

                    # Inicializar pestañas con mensajes de bienvenida
                    try:
                        coder_panel = target_app.query_one("#live_display_coder")
                        if hasattr(coder_panel, "write_stream"):
                            coder_panel.write_stream("[bold cyan]⚡ DeepCoder iniciando...[/bold cyan]")
                        coder_panel.border_title = "DeepCoder"
                    except Exception:
                        pass
                    try:
                        researcher_panel = target_app.query_one("#live_display_researcher")
                        if hasattr(researcher_panel, "write_stream"):
                            researcher_panel.write_stream("[bold magenta]🔍 DeepResearcher iniciando...[/bold magenta]")
                        researcher_panel.border_title = "DeepResearcher"
                    except Exception:
                        pass

                    # Ocultar paneles normales (solo los de thinking/tool, no el input)
                    try:
                        target_app.query_one("#live_display").display = False
                    except Exception:
                        pass
                    try:
                        target_app.query_one("#tool_display").display = False
                    except Exception:
                        pass
                    
                    target_app.refresh(layout=True)
                except Exception as e:
                    logger.warning("Error activando paneles: %s", e)
            
            if threading.current_thread() is threading.main_thread():
                _activate_panels()
            else:
                target_app.call_from_thread(_activate_panels)
            
            logger.info("Esperando estabilización de TUI...")
            import time
            time.sleep(0.5)
        except Exception as e:
            logger.error("Error activando paneles paralelos: %s", e)
    
    # Crear UIs con panel_id para enrutamiento correcto
    ui_coder = ParallelPanelUI(terminal_ui, "live_display_coder")
    ui_researcher = ParallelPanelUI(terminal_ui, "live_display_researcher")
    
    logger.debug("Creando agentes...")
    try:
        # Forzar refresco de skills para asegurar que task_tracker sea detectado
        if llm_service and hasattr(llm_service, 'skill_manager'):
            logger.info("Refrescando skills para detectar task_tracker...")
            llm_service.skill_manager.refresh_skills(force=True)

        # Resetear task_tracker antes de cada sesión paralela
        try:
            tracker = llm_service.get_tool("task_tracker") if llm_service else None
            if tracker and hasattr(tracker, "invoke"):
                tracker.invoke(action="init", plan=[])  # Limpiar estado previo
                logger.info("task_tracker reseteado para nueva sesión paralela")
            else:
                logger.error("No se pudo obtener la herramienta task_tracker")
        except Exception as _te:
            logger.warning("No se pudo resetear task_tracker: %s", _te)

        agent_coder = create_deep_coder(llm_service, ui_coder, interrupt_queue) if coder_authorized else None
        agent_researcher = create_deep_researcher(llm_service, ui_researcher, interrupt_queue) if researcher_authorized else None

        from langchain_core.messages import HumanMessage as _HumanMessage

        def run_coder():
            """Ejecuta el agente coder y retorna su resultado final."""
            if not coder_authorized:
                return "DeepCoder cancelado por el usuario antes de iniciar el modo autónomo."
            try:
                logger.info("run_coder: iniciando ejecución")
                task_message = (
                    f"{task_coder}\n\n"
                    "---\n"
                    "⚠️⚠️⚠️ **PROTOCOLO OBLIGATORIO: task_tracker** ⚠️⚠️⚠️\n"
                    "Tu PRIMERÍSIMA acción en el primer turno DEBE ser inicializar el "
                    "task_tracker con tu plan de ejecución descompuesto:\n"
                    "  task_tracker(action=\"init\", agent_name=\"Coder\", plan=[\"paso 1\", \"paso 2\", ...])\n"
                    "Luego, a medida que avanzas, marca cada paso como 'in-progress' y luego como 'done' al completarlo. No hacerlo es considerado un fallo crítico."
                )
                initial_state = {
                    "messages": [_HumanMessage(content=task_message)],
                    "autonomous_approvals": True,
                }
                final_state = agent_coder.invoke(
                    initial_state,
                    config={"recursion_limit": 1000},
                )
                msgs = final_state.get("messages", [])
                last = msgs[-1].content if msgs else "Sin respuesta"
                logger.info("run_coder: finalizado")
                return last
            except Exception as e:
                logger.exception("run_coder: error: %s", e)
                return f"Error en DeepCoder: {e}"

        def run_researcher():
            """Ejecuta el agente researcher y retorna su resultado final."""
            if not researcher_authorized:
                return "DeepResearcher cancelado por el usuario antes de iniciar el modo autónomo."
            try:
                logger.info("run_researcher: iniciando ejecución")
                task_message = (
                    f"{task_researcher}\n\n"
                    "---\n"
                    "⚠️⚠️⚠️ **PROTOCOLO OBLIGATORIO: task_tracker** ⚠️⚠️⚠️\n"
                    "Tu PRIMERÍSIMA acción en el primer turno DEBE ser inicializar el "
                    "task_tracker con tu plan de investigación descompuesto en sub-preguntas:\n"
                    "  task_tracker(action=\"init\", agent_name=\"Researcher\", plan=[\"sub-pregunta 1\", \"sub-pregunta 2\", ..., \"Síntesis final\"])\n"
                    "Luego, a medida que avanzas, marca cada sub-pregunta como 'in-progress' y luego como 'done' al completarla. No hacerlo es considerado un fallo crítico."
                )
                initial_state = {
                    "messages": [_HumanMessage(content=task_message)],
                    "autonomous_approvals": True,
                }
                final_state = agent_researcher.invoke(
                    initial_state,
                    config={"recursion_limit": RESEARCHER_RECURSION_LIMIT},
                )
                msgs = final_state.get("messages", [])
                last = msgs[-1].content if msgs else "Sin respuesta"
                logger.info("run_researcher: finalizado")
                return last
            except Exception as e:
                logger.exception("run_researcher: error: %s", e)
                return f"Error en DeepResearcher: {e}"

        # Iniciar hilos
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f_coder = executor.submit(run_coder)
            f_res = executor.submit(run_researcher)
            
            # Esperar resultados de forma individual y segura
            results = {}
            for future, name in [(f_coder, "Coder"), (f_res, "Researcher")]:
                try:
                    results[name] = future.result(timeout=600)
                except Exception as e:
                    logger.exception(f"Excepción en el hilo del agente {name}: {e}")
                    results[name] = f"Error crítico en {name}: {e}"
        
        result_coder = results["Coder"]
        result_res = results["Researcher"]

        # Imprimir resumen en el log principal para que no se pierda la información si los paneles se cierran
        if terminal_ui:
            terminal_ui.print_message(f"🏁 **Misión Paralela Finalizada**\n\n**DeepCoder:**\n{result_coder}\n\n**DeepResearcher:**\n{result_res}")

    except Exception as e:
        logger.exception("Error general en call_agents_parallel: %s", e)
        return f"Error en ejecución paralela: {e}"
    finally:
        # Consolidar: mover contenido de los paneles al chat log y ocultarlos
        try:
            if is_server_mode:
                # Modo WS: notificar a la TUI via evento para ocultar paneles
                try:
                    terminal_ui.hide_agent_panels()
                except Exception as e:
                    logger.warning("No se pudo emitir agent_panel_hide: %s", e)
            else:
                target_app = _resolve_tui_app(terminal_ui)
                if target_app:
                    if hasattr(target_app, 'consolidate_parallel_panels'):
                        target_app.consolidate_parallel_panels()
                    else:
                        def _deactivate_panels():
                            try:
                                container = target_app.query_one("#parallel_agents_container")
                                container.display = False
                                try:
                                    target_app.query_one("#tracker_container").remove_class("parallel-mode")
                                except Exception:
                                    pass
                                try:
                                    target_app.query_one("#live_display").display = True
                                except Exception:
                                    pass
                                try:
                                    target_app.query_one("#tool_display").display = True
                                except Exception:
                                    pass
                                # Restaurar input y footer (aunque no los hayamos ocultado, por si acaso)
                                try:
                                    target_app.query_one("#input_container").display = True
                                except Exception:
                                    pass
                                try:
                                    target_app.query_one("StatusFooter").display = True
                                except Exception:
                                    pass
                                target_app.refresh(layout=True)
                            except Exception:
                                pass
                        
                        if threading.current_thread() is threading.main_thread():
                            _deactivate_panels()
                        else:
                            import time
                            time.sleep(2)
                            target_app.call_from_thread(_deactivate_panels)
        except Exception as e:
            logger.error(f"Error consolidando paneles paralelos: {e}")
        
    return f"<coder_analysis>\n{result_coder}\n</coder_analysis>\n\n<researcher_analysis>\n{result_res}\n</researcher_analysis>"

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
