import time
import queue
import logging
import contextlib
from typing import Optional, List, Dict, Any, Union
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.padding import Padding

# Kogniterm imports
from ..agent_state import AgentState
from ..llm_service import LLMService
# We can't import terminal_ui directly due to circular dependencies, we'll pass it as arg

logger = logging.getLogger(__name__)

class BaseAgentNode:
    """
    Clase base para nodos de agentes que comparten la lógica de llamada al modelo,
    renderizado en tiempo real y detección de bucles.
    """
    
    @staticmethod
    def get_system_message(llm_service: LLMService, custom_prompt: str) -> SystemMessage:
        return SystemMessage(content=custom_prompt)

    @classmethod
    def call_model(
        cls, 
        state: AgentState, 
        llm_service: LLMService, 
        system_prompt: str,
        terminal_ui: Optional[Any] = None, 
        interrupt_queue: Optional[queue.Queue] = None
    ) -> Dict[str, Any]:
        """
        Llama al modelo de lenguaje con streaming y renderizado unificado.
        """
        state.stop_requested = False
        console = terminal_ui.console if terminal_ui else Console()
        call_model_t0 = time.perf_counter()
        
        # 1. Detección de Bucles
        logger.info("[LOG_DEBUG] BaseAgentNode.call_model INICIANDO")
        if cls._detect_critical_loop(state, console):
            logger.warning("[LOG_DEBUG] Bucle crítico detectado en call_model")
            return {
                "messages": state.messages,
                "command_to_confirm": None,
                "tool_call_id_to_confirm": None,
                "critical_loop_detected": True
            }

        # 2. Preparar Historial
        history = [cls.get_system_message(llm_service, system_prompt)] + state.messages
        logger.info(f"[LOG_DEBUG] Historial preparado (mensajes: {len(history)})")
        
        # 3. Estado de Streaming
        streaming_state = {
            "full_response": "",

            "full_thinking": "",
            "final_ai_message": None,
            "text_streamed": False,
            "last_update": 0,
            "update_throttle": 0.05
        }

        # 4. Iniciar Keyboard Handler (CLI)
        is_tui = getattr(terminal_ui, "is_tui", False)
        kh = None
        if not is_tui:
            try:
                from .bash_agent import KeyboardHandler # Reciclar por ahora
                kh = KeyboardHandler(interrupt_queue)
                kh.start()
            except ImportError: pass

        try:
            # 5. Contexto de Renderizado (Live / TUI)
            with cls._get_live_context(terminal_ui, is_tui, console) as live:
                if terminal_ui:
                    terminal_ui.print_status("Pensando...", spinner_style="dots")

                # Instrumentación fina para detectar bloqueos antes del primer chunk.
                logger.info("[LOG_DEBUG] Iniciando llm_service.invoke (creando generador)")
                invoke_loop_t0 = time.perf_counter()
                response_stream = llm_service.invoke(
                    history=history,
                    interrupt_queue=interrupt_queue,
                )
                logger.info(
                    "[LOG_DEBUG] Generador creado en %.3fs, iniciando iteración",
                    time.perf_counter() - invoke_loop_t0,
                )
                first_chunk_logged = False
                
                # Bucle de Streaming
                for part in response_stream:
                    if not first_chunk_logged:
                        first_chunk_logged = True
                        logger.info(
                            "[LOG_DEBUG] Primer chunk recibido tras %.3fs desde inicio de iteración",
                            time.perf_counter() - invoke_loop_t0,
                        )
                    cls._process_chunk(part, streaming_state, terminal_ui, is_tui, live)
                    
                    # Interrupción
                    if (interrupt_queue and not interrupt_queue.empty()) or llm_service.stop_generation_flag:
                        logger.info("Interrupción detectada.")
                        break

                # Consolidación final
                cls._finalize_display(streaming_state, terminal_ui, is_tui)

        finally:
            if kh: kh.stop()

        # 6. Procesar Resultado Final
        logger.info(
            "[LOG_DEBUG] BaseAgentNode.call_model finalizado en %.3fs",
            time.perf_counter() - call_model_t0,
        )
        return cls._build_node_output(state, streaming_state, llm_service)

    @staticmethod
    def _detect_critical_loop(state: AgentState, console: Console) -> bool:
        if len(state.tool_call_history) >= 4:
            last_calls = list(state.tool_call_history)[-4:]
            if all(tc['name'] == last_calls[0]['name'] and tc['args_hash'] == last_calls[0]['args_hash'] for tc in last_calls):
                console.print("[bold red]🚨 BUCLE CRÍTICO DETECTADO![/bold red]")
                state.add_message(AIMessage(content="He detectado un bucle infinito. Deteniendo."))
                state.critical_loop_detected = True
                state.clear_tool_call_history()
                return True
        return False

    @staticmethod
    @contextlib.contextmanager
    def _get_live_context(terminal_ui, is_tui, console):
        if not is_tui:
            from rich.spinner import Spinner
            spinner = Spinner("dots", text=Text("🤖 Procesando...", style="cyan"))
            with Live(spinner, console=console, screen=False, refresh_per_second=10) as live:
                yield live
        else:
            @contextlib.contextmanager
            def dummy(): yield type('D', (), {'update': lambda s, x: None})()
            with dummy() as d: yield d

    @classmethod
    def _process_chunk(cls, part, s_state, terminal_ui, is_tui, live):
        if isinstance(part, AIMessage):
            s_state["final_ai_message"] = part
            # Actualizar full_response si el mensaje final tiene contenido y no hubo stream previo
            if part.content and not s_state["full_response"]:
                s_state["full_response"] = part.content
                if is_tui and terminal_ui:
                    terminal_ui.print_stream(str(part.content))
                    s_state["text_streamed"] = True
        elif isinstance(part, str):
            if part.startswith("__THINKING__:") or part.startswith("THINKING:"):
                prefix = "__THINKING__:" if part.startswith("__THINKING__:") else "THINKING:"
                s_state["full_thinking"] += part[len(prefix):]
            else:
                s_state["full_response"] += part
                s_state["text_streamed"] = True
                if is_tui and terminal_ui:
                    terminal_ui.print_stream(part)
            
            # Throttle UI update
            now = time.time()
            if now - s_state["last_update"] > s_state["update_throttle"]:
                cls._update_display(s_state, terminal_ui, is_tui, live)
                s_state["last_update"] = now

    @staticmethod
    def _update_display(s_state, terminal_ui, is_tui, live):
        renderables = []
        if s_state["full_thinking"]:
            from kogniterm.terminal.themes import ColorPalette
            # Render de 'pensamiento' simplificado en TUI para evitar paneles/bordes
            if is_tui:
                # Usar Text plano con estilo dim para evitar bordes y tablas que rompan el layout
                thinking_text = Text(s_state["full_thinking"], style=f"dim {ColorPalette.TEXT_DIM}")
                renderables.append(thinking_text)
            else:
                # En modo CLI clásico seguimos mostrando un Panel con Markdown
                renderables.append(Panel(
                    Markdown(s_state["full_thinking"]), 
                    title=f"[{ColorPalette.TEXT_DIM}]Pensando...[/{ColorPalette.TEXT_DIM}]", 
                    border_style=ColorPalette.TEXT_DIM,
                    style=ColorPalette.TEXT_DIM,
                    padding=(0, 4),
                    expand=True
                ))
            if s_state["full_response"]:
                renderables.append(Text("")) # Margen inferior respecto al mensaje final
        if s_state["full_response"]:
            renderables.append(Markdown(s_state["full_response"]))
        
        group = Group(*renderables)
        if is_tui and terminal_ui:
            # En TUI el contenido principal ya se envía por print_stream por chunk.
            # Solo actualizamos el panel live para razonamiento si existe.
            if s_state["full_thinking"]:
                terminal_ui.update_live(group)
        elif live:
            live.update(Padding(group, (0, 0)) if renderables else Text("🤖 Procesando..."))

    @staticmethod
    def _finalize_display(s_state, terminal_ui, is_tui):
        if is_tui and terminal_ui:
            # Asegurar una última actualización con el contenido final completo
            BaseAgentNode._update_display(s_state, terminal_ui, is_tui, None)
            
            if s_state["text_streamed"] or s_state["full_thinking"] or s_state["full_response"]:
                terminal_ui.stop_live()
            else:
                try: terminal_ui.app.hide_live_display()
                except: pass

    @staticmethod
    def _build_node_output(state: AgentState, s_state, llm_service: LLMService) -> Dict[str, Any]:
        msg = s_state["final_ai_message"]
        if not msg:
            content = s_state["full_response"] or "Respuesta vacía."
            msg = AIMessage(content=content)
            
        state.add_message(msg)
        llm_service._save_history(state.messages)
        
        # Detectar comandos para confirmación (Shell)
        command = None
        tool_id = None
        if msg.tool_calls:
            tool_id = msg.tool_calls[0]['id']
            for tc in msg.tool_calls:
                if tc['name'] in ['execute_command', 'run_command']:
                    command = tc['args'].get('command')
                    break
        
        return {
            "messages": state.messages,
            "command_to_confirm": command,
            "tool_call_id_to_confirm": tool_id
        }
