"""
SessionPool — Motor central de sesiones del servidor KogniTerm.

Mantiene una sesión de agente por `session_id`, la inicializa
al primer uso y la reutiliza indefinidamente (agente siempre despierto).
Cada sesión tiene su propio historial, cola de eventos y estado de agente.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import uuid

import os
from datetime import datetime
from io import StringIO
from typing import Any, AsyncIterator, Callable, Dict, Optional
import contextvars
import contextlib

session_cwd_var = contextvars.ContextVar("session_cwd", default=None)

_original_getcwd = os.getcwd
_original_chdir = os.chdir

def custom_getcwd():
    cwd = session_cwd_var.get()
    if cwd is not None:
        return cwd
    return _original_getcwd()

def custom_chdir(path):
    if session_cwd_var.get() is not None:
        session_cwd_var.set(os.path.abspath(path))
    else:
        _original_chdir(path)

os.getcwd = custom_getcwd
os.chdir = custom_chdir

@contextlib.contextmanager
def session_context(cwd, llm_service=None, history_manager=None, workspace_context=None, vector_db_manager=None):
    """Context manager for isolating session workspace and context."""
    cwd = os.path.abspath(cwd)
    cwd_token = session_cwd_var.set(cwd)
    tokens = []
    if llm_service:
        llm_service._use_context_vars = True
        tokens.append((llm_service._context_current_workspace_dir, llm_service._context_current_workspace_dir.set(cwd)))
        tokens.append((llm_service._context_history_file_path, llm_service._context_history_file_path.set(os.path.join(cwd, ".kogniterm", "history.json"))))
        if history_manager:
            tokens.append((llm_service._context_history_manager, llm_service._context_history_manager.set(history_manager)))
        if workspace_context:
            tokens.append((llm_service._context_workspace_context, llm_service._context_workspace_context.set(workspace_context)))
        if vector_db_manager:
            tokens.append((llm_service._context_vector_db_manager, llm_service._context_vector_db_manager.set(vector_db_manager)))
    try:
        yield
    finally:
        session_cwd_var.reset(cwd_token)
        for var, token in tokens:
            var.reset(token)

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from kogniterm.core.agent_state import AgentState
from kogniterm.core.llm_service import LLMService
from kogniterm.core.thread_manager import ThreadManager
from kogniterm.core.agent_interaction import AgentInteractionRegistry
from kogniterm.ui.terminal_ui import TerminalUI
from rich.console import Console

logger = logging.getLogger("kogniterm.server.session_pool")


def clean_thinking_text(text: str) -> str:
    import re

    # Remove ANSI codes
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)

    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip top, bottom, or middle box boundaries
        if "─" in stripped or "╭" in stripped or "╰" in stripped:
            continue

        line_content = line.strip()
        # Remove vertical borders at the start or end of the line
        line_content = re.sub(r"^[│┃]", "", line_content)
        line_content = re.sub(r"[│┃]$", "", line_content)

        line_content = line_content.strip()
        if line_content:
            cleaned_lines.append(line_content)

    return "\n".join(cleaned_lines)


def extract_thinking_and_response(renderable: Any) -> tuple[str, str]:
    from rich.padding import Padding
    from rich.console import Group
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.text import Text

    thinking = ""
    response = ""

    def recurse(r):
        nonlocal thinking, response
        if isinstance(r, Padding):
            recurse(r.renderable)
        elif isinstance(r, Group):
            for sub_r in r.renderables:
                recurse(sub_r)
        elif isinstance(r, Panel):
            title = str(r.title or "").lower()
            is_thinking_panel = "pensando" in title or "thinking" in title

            p_content = r.renderable
            content_str = ""
            if isinstance(p_content, Markdown):
                content_str = p_content.markup
            elif isinstance(p_content, Text):
                content_str = p_content.plain
            elif isinstance(p_content, str):
                content_str = p_content
            else:
                try:
                    if isinstance(p_content, (Group, Padding)):
                        recurse(p_content)
                        return
                    from rich.console import Console
                    from io import StringIO

                    buf = StringIO()
                    c = Console(
                        file=buf, force_terminal=False, no_color=True, width=120
                    )
                    c.print(p_content)
                    content_str = buf.getvalue().strip()
                except Exception:
                    content_str = str(p_content)

            if is_thinking_panel:
                thinking += "\n" + content_str
            else:
                display_title = f"### {r.title}\n" if r.title else ""
                response += "\n" + display_title + content_str
        elif isinstance(r, Markdown):
            response += "\n" + r.markup
        elif isinstance(r, Text):
            plain = r.plain
            if plain.strip():
                response += "\n" + plain
        elif isinstance(r, str):
            if r.strip():
                response += "\n" + r
        else:
            try:
                from rich.console import Console
                from io import StringIO

                buf = StringIO()
                c = Console(file=buf, force_terminal=False, no_color=True, width=120)
                c.print(r)
                val = buf.getvalue().strip()
                if val:
                    response += "\n" + val
            except Exception:
                val = str(r).strip()
                if val:
                    response += "\n" + val

    recurse(renderable)
    return thinking.strip(), response.strip()


# ── Adaptador de UI para el servidor ──────────────────────────────────────────


class ServerUI(TerminalUI):
    """
    Adaptador sin pantalla: captura todos los eventos del agente y los pone
    en una asyncio.Queue por sesión para ser enviados via WebSocket / SSE.

    Nota: El agente corre en un hilo worker (executor), por lo que este
    adaptador debe ser thread-safe.  Usamos asyncio.Queue con
    `call_soon_threadsafe` para pasar eventos al loop del servidor.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, session_id: str):
        super().__init__(
            console=Console(force_terminal=False, no_color=True, width=120)
        )
        self._loop = loop
        self.session_id = session_id
        # Sistema de Broadcast: Múltiples colas activas
        self._queues = []
        self._queues_lock = threading.Lock()
        # Cola legacy para compatibilidad
        self._async_queue: asyncio.Queue = asyncio.Queue()
        self.is_tui = True  # El agente usa rutas de "rich output"
        self.telegram_adapters = []
        # Sistemas de aprobación de herramientas (thread-safe)
        self._pending_approvals = {}  # {request_id: (threading.Event, bool)}
        self._pending_approvals_async = {}  # {request_id: (asyncio.Event, bool)}
        self._pending_lock = threading.Lock()

    def add_telegram_adapter(self, adapter):
        self.telegram_adapters.append(adapter)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _push(self, event_type: str, data: Any, agent_id: str = None) -> None:
        """Envía un evento desde cualquier hilo al loop asyncio del servidor.

        Si se provee agent_id, se incluye en el evento para que la TUI pueda
        enrutar el output al panel/pestaña del subagente correspondiente.
        """
        event = {"type": event_type, "data": data, "ts": datetime.utcnow().isoformat()}
        if agent_id:
            event["agent_id"] = agent_id
        try:
            # Broadcast a todas las colas activas
            with self._queues_lock:
                for q in self._queues:
                    self._loop.call_soon_threadsafe(q.put_nowait, event)

            # Backwards compatibility: push a la cola legacy
            self._loop.call_soon_threadsafe(self._async_queue.put_nowait, event)

            # Broadcast a Telegram si es un mensaje de texto (solo agente principal)
            if (
                not agent_id
                and event_type in ["message", "stream"]
                and self.telegram_adapters
            ):
                text = data if isinstance(data, str) else data.get("text", "")
                if text:
                    for adapter in self.telegram_adapters:
                        asyncio.run_coroutine_threadsafe(
                            adapter.send_message(text), self._loop
                        )
        except Exception as exc:
            logger.warning(
                f"[{self.session_id}] No se pudo enviar evento {event_type}: {exc}"
            )

    def _render_rich(self, renderable: Any) -> str:
        """Convierte un renderable de Rich a texto con formato ANSI."""
        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120, no_color=False)
        c.print(renderable)
        return buf.getvalue()

    # ── TerminalUI overrides ───────────────────────────────────────────────────

    def print_stream(self, text: str, agent_id: str = None) -> None:
        logger.info(f"[{self.session_id}] ServerUI.print_stream: {text[:50]}...")
        self._push("chunk", {"content": text}, agent_id=agent_id)
        self._push("stream", text, agent_id=agent_id)

    def update_live(self, renderable: Any, agent_id: str = None) -> None:
        try:
            # Check for special tuples first
            if isinstance(renderable, tuple) and len(renderable) >= 2:
                if renderable[0] == "__SPINNER__":
                    self._push(
                        "live_update",
                        {"special_type": "spinner", "text": renderable[1]},
                        agent_id=agent_id,
                    )
                    return
                elif renderable[0] == "__TERMINAL__":
                    tool = renderable[1]
                    output = renderable[2] if len(renderable) > 2 else ""
                    command = renderable[3] if len(renderable) > 3 else tool
                    self._push(
                        "live_update",
                        {
                            "special_type": "terminal",
                            "tool": tool,
                            "output": output,
                            "command": command,
                        },
                        agent_id=agent_id,
                    )
                    return

            thinking, response = extract_thinking_and_response(renderable)

            if thinking:
                thinking = clean_thinking_text(thinking)

            self._push(
                "live_update",
                {"thinking": thinking, "response": response},
                agent_id=agent_id,
            )
        except Exception as exc:
            logger.warning(f"Error al extraer estructuradamente: {exc}")
            try:
                buf = StringIO()
                c = Console(file=buf, force_terminal=False, no_color=True, width=120)
                c.print(renderable)
                plain_text = buf.getvalue()
                cleaned = clean_thinking_text(plain_text)
                self._push(
                    "live_update",
                    {"thinking": cleaned, "response": ""},
                    agent_id=agent_id,
                )
            except Exception as e2:
                logger.error(f"Fallback rendering failed: {e2}")
                self._push(
                    "live_update", {"thinking": "", "response": ""}, agent_id=agent_id
                )

    def stop_live(self, agent_id: str = None, **kwargs) -> None:
        self._push("live_stop", {}, agent_id=agent_id)

    def print_message(
        self, message: str, style: str = "", agent_id: str = None, **kwargs
    ) -> None:
        logger.info(f"[{self.session_id}] ServerUI.print_message: {message[:50]}...")
        self._push("chunk", {"content": message}, agent_id=agent_id)
        self._push("message", {"text": message}, agent_id=agent_id)

    def show_agent_panel(self, agent_id: str, title: str = "") -> None:
        """Notifica a la TUI que debe mostrar/activar el panel de un subagente."""
        self._push(
            "agent_panel_show", {"agent_id": agent_id, "title": title or agent_id}
        )

    def hide_agent_panels(self) -> None:
        """Notifica a la TUI que los paneles paralelos deben ocultarse."""
        self._push("agent_panel_hide", {})

    def print_warning_box(self, message: str, title: str = "Advertencia") -> None:
        logger.info(
            f"[{self.session_id}] ServerUI.print_warning_box: {message[:50]}..."
        )
        from kogniterm.ui.terminal_ui import create_warning_box

        warning_panel = create_warning_box(message, title)
        ansi_text = self._render_rich(warning_panel)
        self._push("chunk", {"content": ansi_text})
        self._push("message", {"text": ansi_text})

    def print_error_box(self, message: str, title: str = "Error") -> None:
        logger.info(f"[{self.session_id}] ServerUI.print_error_box: {message[:50]}...")
        from kogniterm.ui.terminal_ui import create_error_box

        error_panel = create_error_box(message, title)
        ansi_text = self._render_rich(error_panel)
        self._push("chunk", {"content": ansi_text})
        self._push("message", {"text": ansi_text})

    def print_tool_notification(
        self, tool_name: str, bajada: str = "", skill_name: str = "", **kwargs
    ) -> None:
        agent_id = kwargs.get("panel_id") or kwargs.get("agent_id")
        self._push(
            "tool_call",
            {"name": tool_name, "description": bajada, "skill": skill_name},
            agent_id=agent_id,
        )

    def update_terminal_output(
        self, tool_name: str, output: str, tool_call_id: Optional[str] = None, **kwargs
    ) -> None:
        logger.info(f"[{self.session_id}] ServerUI.update_terminal_output: {tool_name}")
        agent_id = kwargs.get("panel_id") or kwargs.get("agent_id")
        self._push(
            "terminal_output",
            {"content": output, "tool": tool_name, "tool_call_id": tool_call_id},
            agent_id=agent_id,
        )

    def set_terminal_cursor(self, active: bool, executor=None):
        logger.info(f"[{self.session_id}] ServerUI.set_terminal_cursor: {active}")
        self._push("set_terminal_cursor", {"active": active})

    def update_tool_display(
        self, tool_name: str, output: str, tool_call_id: Optional[str] = None, **kwargs
    ) -> None:
        logger.info(f"[{self.session_id}] ServerUI.update_tool_display: {tool_name}")
        agent_id = kwargs.get("panel_id") or kwargs.get("agent_id")
        self._push(
            "tool_result",
            {"content": output, "tool": tool_name, "tool_call_id": tool_call_id},
            agent_id=agent_id,
        )

    def update_task_tracker(self, agent_plans: dict) -> None:
        self._push("task_tracker", agent_plans)

    async def ask_approval_async(
        self, message: str, title: str = "Aprobación Requerida", **kwargs
    ) -> bool:
        """Emite un evento de aprobación y espera la respuesta del canal de forma asíncrona."""
        request_id = str(uuid.uuid4())
        event = asyncio.Event()

        with self._pending_lock:
            self._pending_approvals_async[request_id] = (event, False)

        self._push(
            "approval_required",
            {
                "id": request_id,
                "message": message,
                "title": title,
                "diff_content": kwargs.get("diff_content", ""),
                "file_path": kwargs.get("file_path", ""),
            },
        )

        logger.info(
            f"[{self.session_id}] Esperando aprobación asíncrona para {request_id}..."
        )
        await event.wait()

        with self._pending_lock:
            _, approved = self._pending_approvals_async.pop(request_id, (None, False))

        logger.info(
            f"[{self.session_id}] Aprobación asíncrona {request_id} decidida: {approved}"
        )
        return approved

    def ask_approval_sync(
        self, message: str, title: str = "Aprobación Requerida", **kwargs
    ) -> bool:
        """Emite un evento de aprobación y bloquea el hilo del worker esperando la respuesta."""
        request_id = str(uuid.uuid4())
        event = threading.Event()

        with self._pending_lock:
            self._pending_approvals[request_id] = (event, False)

        self._push(
            "approval_required",
            {
                "id": request_id,
                "message": message,
                "title": title,
                "diff_content": kwargs.get("diff_content", ""),
                "file_path": kwargs.get("file_path", ""),
            },
        )

        logger.info(
            f"[{self.session_id}] Esperando aprobación síncrona para {request_id}..."
        )
        # Bloquear el hilo worker
        event.wait()

        with self._pending_lock:
            _, approved = self._pending_approvals.pop(request_id, (None, False))

        logger.info(
            f"[{self.session_id}] Aprobación síncrona {request_id} decidida: {approved}"
        )
        return approved

    def handle_approval_response(self, request_id: str, approved: bool) -> None:
        """Recibe la respuesta de aprobación de la TUI o canal y despierta al thread o coroutina."""
        logger.info(f"[{self.session_id}] handle_approval_response llamado para request_id={request_id}, approved={approved}")
        with self._pending_lock:
            # 1. Despertar thread worker síncrono si está bloqueado
            if request_id in self._pending_approvals:
                logger.info(f"[{self.session_id}] Encontrado request_id={request_id} en _pending_approvals (síncrono). Despertando thread.")
                event, _ = self._pending_approvals[request_id]
                self._pending_approvals[request_id] = (event, approved)
                event.set()
                return

            # 2. Despertar coroutinas asíncronas
            if request_id in self._pending_approvals_async:
                logger.info(f"[{self.session_id}] Encontrado request_id={request_id} en _pending_approvals_async (asíncrono). Despertando coroutina.")
                event, _ = self._pending_approvals_async[request_id]
                self._pending_approvals_async[request_id] = (event, approved)
                # Como handle_approval_response puede ser llamado desde el loop o un thread,
                # usamos call_soon_threadsafe para setear el asyncio.Event de forma segura.
                self._loop.call_soon_threadsafe(event.set)
                return
                
        logger.warning(f"[{self.session_id}] Advertencia: request_id={request_id} no se encontró en las aprobaciones pendientes de esta sesión.")

    # ── Consumer API ───────────────────────────────────────────────────────────

    async def events(self) -> AsyncIterator[dict]:
        """Generador asíncrono: yield de eventos registrando una cola de broadcast por consumidor."""
        q = asyncio.Queue()
        with self._queues_lock:
            self._queues.append(q)
        try:
            while True:
                event = await q.get()
                yield event
                q.task_done()
        finally:
            with self._queues_lock:
                if q in self._queues:
                    self._queues.remove(q)


# ── Sesión individual ──────────────────────────────────────────────────────────


class AgentSession:
    """
    Una sesión de agente persistente para un `session_id` dado.
    El agente se inicializa una vez y permanece "despierto" entre mensajes.
    """

    def __init__(
        self,
        session_id: str,
        llm_service: LLMService,
        loop: asyncio.AbstractEventLoop,
        thread_manager: Optional[ThreadManager] = None,
        workspace_dir: Optional[str] = None,
    ):
        self.session_id = session_id
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.llm_service = llm_service

        # Determinar el workspace_dir correcto
        self.workspace_dir = workspace_dir or (thread_manager.workspace_dir if thread_manager else os.getcwd())
        self.workspace_dir = os.path.abspath(self.workspace_dir)

        # Configurar thread_manager específico de este workspace
        from kogniterm.core.thread_manager import ThreadManager
        self.thread_manager = ThreadManager(workspace_dir=self.workspace_dir)

        # Inicializar vector_db_manager para la sesión
        from kogniterm.core.context.vector_db_manager import VectorDBManager
        try:
            self.vector_db_manager = VectorDBManager(project_path=self.workspace_dir)
        except Exception:
            self.vector_db_manager = None

        # Inicializar history_manager para la sesión
        from kogniterm.core.history_manager import HistoryManager
        history_file_path = os.path.join(self.workspace_dir, ".kogniterm", "history.json")
        self.history_manager = HistoryManager(
            history_file_path=history_file_path,
            max_history_messages=llm_service.max_history_messages,
            max_history_chars=llm_service.max_history_chars,
            tokenizer=llm_service.tokenizer,
            auto_save_interval=llm_service.auto_save_interval
        )

        # Inicializar workspace_context para la sesión
        from kogniterm.core.context.workspace_context import WorkspaceContext
        self.workspace_context = WorkspaceContext(root_dir=self.workspace_dir)

        # UI adapter (sin pantalla)
        self.ui = ServerUI(loop=loop, session_id=session_id)

        # Inyectar terminal_ui en el LLMService y SkillManager para que
        # skills como task_tracker puedan acceder al canal de eventos.
        llm_service.terminal_ui = self.ui
        if hasattr(llm_service, "skill_manager") and llm_service.skill_manager:
            llm_service.skill_manager.terminal_ui = self.ui
            # Inyectar retroactivamente en los módulos de herramientas cargadas
            import sys

            try:
                for tool in llm_service.skill_manager.get_tools():
                    module_name = getattr(tool, "__module__", None)
                    if module_name:
                        module = sys.modules.get(module_name)
                        if module:
                            if hasattr(module, "_terminal_ui"):
                                setattr(module, "_terminal_ui", self.ui)
                            if hasattr(module, "_llm_service"):
                                setattr(module, "_llm_service", llm_service)
                            # También inyectar como atributo de la función/herramienta si lo requiere
                            if hasattr(tool, "terminal_ui"):
                                setattr(tool, "terminal_ui", self.ui)
                            if hasattr(tool, "llm_service"):
                                setattr(tool, "llm_service", llm_service)
            except Exception as e:
                logger.error(
                    f"[Session:{session_id}] Error inyectando dependencias en herramientas: {e}"
                )

        # Cargar historial si existe
        initial_messages = []
        if self.thread_manager:
            loaded_history = self.thread_manager.load_thread_messages(session_id)
            if loaded_history:
                logger.info(
                    f"[Session:{session_id}] Historial cargado ({len(loaded_history)} mensajes)."
                )
                initial_messages = loaded_history
            else:
                self.thread_manager.create_thread(thread_id=session_id)

        # Estado del agente
        self.agent_state = AgentState(messages=initial_messages)

        # Cola de interrupción (para Ctrl+C desde el canal)
        self.interrupt_queue: queue.Queue = queue.Queue()

        # Cola de mensajes pendientes cuando el agente está ocupado
        self._pending_messages: list = []

        # Inicializar CommandExecutor y CommandApprovalHandler para el servidor
        from kogniterm.core.command_executor import CommandExecutor
        from kogniterm.terminal.command_approval_handler import CommandApprovalHandler

        self.command_executor = CommandExecutor()
        self.command_executor.workspace_directory = self.workspace_dir
        self.command_executor.terminal_ui = self.ui

        try:
            self.command_approval_handler = CommandApprovalHandler(
                llm_service,
                self.command_executor,
                None,
                self.ui,
                self.agent_state,
                llm_service.get_tool("file_update") if llm_service else None,
                llm_service.get_tool("advanced_file_editor") if llm_service else None,
                llm_service.get_tool("file_operations") if llm_service else None,
            )
        except Exception as e:
            logger.error(
                f"[Session:{self.session_id}] Error al inicializar CommandApprovalHandler: {e}"
            )
            self.command_approval_handler = None

        # Gestor de interacción (crea el grafo LangGraph)
        self.manager = AgentInteractionRegistry.create(
            llm_service=llm_service,
            agent_state=self.agent_state,
            terminal_ui=self.ui,
            interrupt_queue=self.interrupt_queue,
            command_approval_handler=self.command_approval_handler,
        )

        # Lock para serializar invocaciones del agente por sesión
        self._agent_lock = asyncio.Lock()

        # Bandera de sesión activa
        self.is_running = False

        # Si es una sesión nueva, guardarla para que sea persistente desde el inicio
        if self.thread_manager and not initial_messages:
            self.thread_manager.save_thread_messages(
                self.session_id, self.agent_state.messages
            )

        logger.info(f"[Session:{session_id}] Inicializada.")

    def update_workspace_dir(self, workspace_dir: str) -> None:
        """Actualiza dinámicamente el workspace_dir para esta sesión."""
        if not workspace_dir:
            return
        workspace_dir = os.path.abspath(workspace_dir)
        if self.workspace_dir == workspace_dir:
            return

        logger.info(f"[Session:{self.session_id}] Actualizando workspace_dir de {self.workspace_dir} a {workspace_dir}")
        self.workspace_dir = workspace_dir

        # Actualizar thread manager
        from kogniterm.core.thread_manager import ThreadManager
        self.thread_manager = ThreadManager(workspace_dir=workspace_dir)

        # Actualizar vector_db_manager para la sesión
        from kogniterm.core.context.vector_db_manager import VectorDBManager
        try:
            self.vector_db_manager = VectorDBManager(project_path=workspace_dir)
        except Exception:
            self.vector_db_manager = None

        # Actualizar history_manager para la sesión
        from kogniterm.core.history_manager import HistoryManager
        history_file_path = os.path.join(workspace_dir, ".kogniterm", "history.json")
        self.history_manager = HistoryManager(
            history_file_path=history_file_path,
            max_history_messages=self.llm_service.max_history_messages,
            max_history_chars=self.llm_service.max_history_chars,
            tokenizer=self.llm_service.tokenizer,
            auto_save_interval=self.llm_service.auto_save_interval
        )

        # Actualizar workspace_context para la sesión
        from kogniterm.core.context.workspace_context import WorkspaceContext
        self.workspace_context = WorkspaceContext(root_dir=workspace_dir)

        # Actualizar command_executor
        if hasattr(self, "command_executor") and self.command_executor:
            self.command_executor.workspace_directory = workspace_dir

    def interrupt(self) -> None:
        """Interrumpe la ejecución actual del agente en esta sesión."""
        logger.info(f"[Session:{self.session_id}] Interrupción solicitada.")
        self.interrupt_queue.put_nowait(True)
        if self.llm_service:
            self.llm_service.stop_generation_flag = True

    def _drain_pending_messages(self) -> list:
        """Extrae y retorna todos los mensajes pendientes en cola."""
        messages = list(self._pending_messages)
        self._pending_messages.clear()
        return messages

    def write_terminal_input(self, text: str) -> None:
        """Escribe la entrada del usuario en la PTY del CommandExecutor del servidor."""
        if hasattr(self, "command_executor") and self.command_executor:
            self.command_executor.write_input(text)

    async def send(self, message: str, executor) -> None:
        """
        Envía un mensaje al agente y lo ejecuta en un hilo worker.
        Los eventos se emiten en tiempo real a `self.ui._async_queue`.
        """
        async with self._agent_lock:
            self.last_activity = datetime.utcnow()
            if self.is_running:
                self._pending_messages.append(message)
                self.interrupt()
                return

            self.is_running = True

            # 1. Manejo de Meta-comandos en el Servidor
            processed = False
            msg_lower = message.lower().strip()

            if msg_lower in ("%reset", "/reset"):
                self.agent_state.reset()
                if self.thread_manager:
                    self.thread_manager.save_thread_messages(self.session_id, [])
                self.ui.print_message("Sesión reiniciada correctamente.", style="green")
                processed = True
            elif msg_lower in ("%index", "/index"):
                self.ui.print_message(
                    "Iniciando re-indexación del workspace...", style="cyan"
                )
                from kogniterm.server.app import run_indexing_task

                asyncio.create_task(run_indexing_task(self.session_id))
                processed = True
            elif msg_lower in ("%undo", "/undo"):
                if len(self.agent_state.messages) >= 2:
                    self.agent_state.messages.pop()  # AI
                    self.agent_state.messages.pop()  # Human
                    if self.thread_manager:
                        self.thread_manager.save_thread_messages(
                            self.session_id, self.agent_state.messages
                        )
                    self.ui.print_message(
                        "Última interacción eliminada.", style="yellow"
                    )
                else:
                    self.ui.print_message("No hay nada que deshacer.", style="red")
                processed = True
            elif msg_lower.startswith(("/resume", "%resume")):
                parts = message.split()
                if len(parts) > 1:
                    target_session = parts[1]
                    loaded = (
                        self.thread_manager.load_thread_messages(target_session)
                        if self.thread_manager
                        else None
                    )
                    self.ui.print_message(
                        f"Reanudando desde hilo: {target_session}", style="blue"
                    )
                    if loaded:
                        self.agent_state.messages[:] = loaded
                        self.ui.print_message(
                            f"Hilo '{target_session}' cargado correctamente.",
                            style="green",
                        )
                    else:
                        self.ui.print_message(
                            f"No se pudo cargar el hilo '{target_session}'.",
                            style="red",
                        )
                    processed = True
                else:
                    sessions = (
                        self.thread_manager.list_threads()
                        if self.thread_manager
                        else []
                    )
                    if sessions:
                        session_list = "\n".join(
                            [f"- {s['id']} : {s.get('title', '')}" for s in sessions]
                        )
                        self.ui.print_message(
                            f"Hilos disponibles:\n{session_list}\n\nUsa '/resume <id>' para cargar uno.",
                            style="blue",
                        )
                    else:
                        self.ui.print_message("No hay hilos guardados.", style="yellow")
                    processed = True

            if processed:
                self.ui._push("done", {"session_id": self.session_id})
                self.is_running = False
                return

            # 2. Flujo normal de agente
            self.ui._push("user_message", {"text": message})
            self.agent_state.add_message(HumanMessage(content=message))

            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(executor, self._run_agent_loop, message)
                # Guardar después de cada interacción exitosa
                if self.thread_manager:
                    self.thread_manager.save_thread_messages(
                        self.session_id, self.agent_state.messages
                    )

                    # Autónombrado de hilo
                    asyncio.create_task(self._try_generate_title())

                self.ui._push("done", {"session_id": self.session_id})
            except Exception as exc:
                logger.error(
                    f"[Session:{self.session_id}] Error al invocar agente: {exc}"
                )
                self.ui._push("error", {"message": str(exc)})
            finally:
                self.is_running = False

    def _run_agent_loop(self, user_input: Optional[str]) -> None:
        """
        Ejecuta el bucle de interacción del agente de forma síncrona en el hilo worker,
        procesando confirmaciones de comandos y de skills de la misma manera que la TUI local.
        """
        with session_context(
            cwd=self.workspace_dir,
            llm_service=self.llm_service,
            history_manager=self.history_manager,
            workspace_context=self.workspace_context,
            vector_db_manager=self.vector_db_manager
        ):
            old_cwd = os.getcwd()
            try:
                # Cambiar al workspace_dir de la sesión
                if hasattr(self, "workspace_dir") and self.workspace_dir and os.path.exists(self.workspace_dir):
                    try:
                        os.chdir(self.workspace_dir)
                    except Exception as e:
                        logger.error(f"[Session:{self.session_id}] Error al cambiar de directorio a {self.workspace_dir}: {e}")

                # Actualizar dinámicamente el workspace en el llm_service de la sesión
                if self.llm_service and hasattr(self.llm_service, "update_workspace"):
                    try:
                        self.llm_service.update_workspace(self.workspace_dir)
                    except Exception as e:
                        logger.error(f"[Session:{self.session_id}] Error al actualizar el workspace en el LLMService: {e}")

                is_first_iteration = True
                while True:
                    pending = self._drain_pending_messages()
                    if pending:
                        user_input = pending.pop(0)
                        self.ui._push("user_message", {"text": user_input})
                        self.agent_state.add_message(HumanMessage(content=user_input))
                    elif is_first_iteration and not user_input:
                        break

                    is_first_iteration = False

                    # 1. Invocar al agente
                    final_state = self.manager.invoke_agent(user_input)

                    self.agent_state.messages = final_state.get(
                        "messages", self.agent_state.messages
                    )
                    self.agent_state.command_to_confirm = final_state.get(
                        "command_to_confirm"
                    )

                    # Caso A: Comando de terminal (Bash)
                    if self.agent_state.command_to_confirm:
                        command = self.agent_state.command_to_confirm

                        # Bloquear el hilo worker hasta que el usuario decida (TUI/WebSocket)
                        approved = self.ui.ask_approval_sync(
                            message=f"¿Ejecutar comando: {command}?",
                            title="Confirmación de Comando",
                            diff_content=command,
                            file_path="bash",
                        )

                        if command and self.command_approval_handler:
                            self.command_approval_handler.handle_command_approval(
                                command_to_execute=command, auto_approve=approved
                            )

                        # Limpiar estado de confirmación tras procesar
                        self.agent_state.command_to_confirm = None
                        self.agent_state.tool_call_id_to_confirm = None

                        if not approved:
                            self.ui.print_warning_box("Comando cancelado por el usuario.")

                        user_input = None
                        continue  # Volver al inicio del bucle para que el agente procese el resultado

                    # Caso B: Confirmación de Skill (file_operations, advanced_file_editor, etc.)
                    elif (
                        getattr(self.agent_state, "tool_pending_confirmation", None)
                        or self.agent_state.file_update_diff_pending_confirmation
                    ):
                        tool_name = self.agent_state.tool_pending_confirmation
                        diff_info = self.agent_state.file_update_diff_pending_confirmation

                        message = "Confirmación de herramienta requerida."
                        diff_content = None
                        file_path = None

                        if isinstance(diff_info, dict):
                            message = diff_info.get(
                                "action_description", diff_info.get("message", message)
                            )
                            diff_content = diff_info.get("diff")
                            file_path = diff_info.get("path")
                        elif isinstance(diff_info, str):
                            diff_content = diff_info

                        approved = self.ui.ask_approval_sync(
                            message=message,
                            title=f"Confirmación: {tool_name}",
                            diff_content=diff_content,
                            file_path=file_path,
                        )

                        if self.command_approval_handler:
                            self.command_approval_handler.handle_command_approval(
                                command_to_execute="",  # No es un comando bash
                                raw_tool_output=diff_info
                                if isinstance(diff_info, dict)
                                else {
                                    "status": "requires_confirmation",
                                    "diff": diff_content,
                                    "path": file_path,
                                    "operation": tool_name,
                                },
                                auto_approve=approved,
                                tool_name=tool_name,
                                original_tool_args=self.agent_state.tool_args_pending_confirmation,
                            )

                        # Limpiar estado de confirmación
                        self.agent_state.reset_tool_confirmation()
                        self.agent_state.tool_call_id_to_confirm = None

                        if not approved:
                            self.ui.print_warning_box("Acción cancelada por el usuario.")

                        user_input = None
                        continue  # Volver al inicio del bucle

                    # Sin confirmaciones pendientes: salir del loop
                    break
            except Exception as e:
                logger.error(
                    f"[Session:{self.session_id}] Error crítico en _run_agent_loop: {e}",
                    exc_info=True,
                )
                raise e
            finally:
                try:
                    os.chdir(old_cwd)
                except Exception:
                    pass

    @property
    def message_count(self) -> int:
        return len(
            [m for m in self.agent_state.messages if isinstance(m, HumanMessage)]
        )

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "message_count": self.message_count,
            "is_running": self.is_running,
        }

    async def _try_generate_title(self):
        """Intenta generar un título en background y notifica al cliente si se generó."""
        if self.thread_manager and self.llm_service:
            new_title = await self.thread_manager.generate_title_if_needed(
                self.session_id, self.agent_state.messages, self.llm_service
            )
            if new_title:
                self.ui._push(
                    "thread_title_updated",
                    {"thread_id": self.session_id, "title": new_title},
                )


# ── Pool global de sesiones ───────────────────────────────────────────────────


class SessionPool:
    """
    Registro global de todas las sesiones activas del servidor.
    Thread-safe para creación/obtención de sesiones.
    """

    def __init__(self):
        self._sessions: Dict[str, AgentSession] = {}
        self._lock = threading.Lock()
        self._llm_service: Optional[LLMService] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread_manager: Optional[ThreadManager] = None
        # Executor para correr el agente (hilo dedicado por tarea)
        from concurrent.futures import ThreadPoolExecutor

        self._executor = ThreadPoolExecutor(
            max_workers=20, thread_name_prefix="kt-agent"
        )
        self._ready_event: Optional[asyncio.Event] = None

    @property
    def ready_event(self) -> asyncio.Event:
        if self._ready_event is None:
            self._ready_event = asyncio.Event()
        return self._ready_event

    async def wait_until_ready(self) -> None:
        """Espera de forma no bloqueante a que el pool esté inicializado."""
        if self._llm_service and self._loop:
            return
        await self.ready_event.wait()

    def initialize(
        self, llm_service: LLMService, loop: asyncio.AbstractEventLoop
    ) -> None:
        """Debe llamarse en el lifespan de la app, una sola vez."""
        self._llm_service = llm_service
        self._loop = loop
        self._thread_manager = ThreadManager(workspace_dir=os.getcwd())
        logger.info("SessionPool inicializado con LLMService y ThreadManager.")

        # Seteamos el ready_event de forma segura en el event loop
        def set_event():
            self.ready_event.set()

        loop.call_soon_threadsafe(set_event)

    def get_or_create(self, session_id: str, workspace_dir: Optional[str] = None) -> AgentSession:
        """Obtiene una sesión existente o crea una nueva (thread-safe)."""
        with self._lock:
            if session_id not in self._sessions:
                if not self._llm_service or not self._loop:
                    raise RuntimeError(
                        "SessionPool no inicializado. Llama a initialize() primero."
                    )
                self._sessions[session_id] = AgentSession(
                    session_id=session_id,
                    llm_service=self._llm_service,
                    loop=self._loop,
                    thread_manager=self._thread_manager,
                    workspace_dir=workspace_dir,
                )
            else:
                session = self._sessions[session_id]
                if workspace_dir and session.workspace_dir != workspace_dir:
                    session.update_workspace_dir(workspace_dir)
            return self._sessions[session_id]

    def get(self, session_id: str) -> Optional[AgentSession]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"Sesión {session_id} eliminada.")
                return True
        return False

    def list_all(self) -> list:
        with self._lock:
            return [s.to_dict() for s in self._sessions.values()]

    def new_session_id(self) -> str:
        return str(uuid.uuid4())


# Instancia global (singleton)
pool = SessionPool()
