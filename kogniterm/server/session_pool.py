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

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from kogniterm.core.agent_state import AgentState
from kogniterm.core.llm_service import LLMService
from kogniterm.core.session_manager import SessionManager
from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager
from kogniterm.terminal.terminal_ui import TerminalUI
from rich.console import Console

logger = logging.getLogger("kogniterm.server.session_pool")


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
        super().__init__(console=Console(force_terminal=False, no_color=True, width=120))
        self._loop = loop
        self.session_id = session_id
        # Cola asyncio — los consumidores (WS / SSE) la leen desde el loop principal
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

    def _push(self, event_type: str, data: Any) -> None:
        """Envía un evento desde cualquier hilo al loop asyncio del servidor."""
        event = {"type": event_type, "data": data, "ts": datetime.utcnow().isoformat()}
        try:
            self._loop.call_soon_threadsafe(self._async_queue.put_nowait, event)
            
            # Broadcast a Telegram si es un mensaje de texto
            if event_type in ["message", "stream"] and self.telegram_adapters:
                text = data if isinstance(data, str) else data.get("text", "")
                if text:
                    for adapter in self.telegram_adapters:
                        # Usamos run_coroutine_threadsafe para enviar desde fuera del loop
                        asyncio.run_coroutine_threadsafe(adapter.send_message(text), self._loop)
        except Exception as exc:
            logger.warning(f"[{self.session_id}] No se pudo enviar evento {event_type}: {exc}")

    def _render_rich(self, renderable: Any) -> str:
        """Convierte un renderable de Rich a texto plano / ANSI."""
        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120, no_color=True)
        c.print(renderable)
        return buf.getvalue()

    # ── TerminalUI overrides ───────────────────────────────────────────────────

    def print_stream(self, text: str) -> None:
        logger.info(f"[{self.session_id}] ServerUI.print_stream: {text[:50]}...")
        # Desktop expects 'chunk' type with 'content' key, Core expects 'stream' type with text data
        self._push("chunk", {"content": text})
        self._push("stream", text)

    def update_live(self, renderable: Any) -> None:
        rich_content = self._render_rich(renderable)
        self._push("live_update", rich_content)
        # Compatibility with desktop 'reasoning' if applicable (optional)

    def stop_live(self, **kwargs) -> None:
        self._push("live_stop", {})

    def print_message(self, message: str, style: str = "", **kwargs) -> None:
        logger.info(f"[{self.session_id}] ServerUI.print_message: {message[:50]}...")
        self._push("chunk", {"content": message})
        self._push("message", {"text": message})

    def print_tool_notification(self, tool_name: str, bajada: str = "", skill_name: str = "", **kwargs) -> None:
        self._push("tool_call", {"name": tool_name, "description": bajada, "skill": skill_name})

    def update_terminal_output(self, tool_name: str, output: str, tool_call_id: Optional[str] = None, **kwargs) -> None:
        logger.info(f"[{self.session_id}] ServerUI.update_terminal_output: {tool_name}")
        self._push("tool_result", {"content": output, "tool": tool_name, "tool_call_id": tool_call_id})

    def update_task_tracker(self, agent_plans: dict) -> None:
        self._push("task_tracker", agent_plans)

    async def ask_approval_async(self, message: str, title: str = "Aprobación Requerida", **kwargs) -> bool:
        """Emite un evento de aprobación y espera la respuesta del canal de forma asíncrona."""
        request_id = str(uuid.uuid4())
        event = asyncio.Event()
        
        with self._pending_lock:
            self._pending_approvals_async[request_id] = (event, False)
            
        self._push("approval_required", {
            "id": request_id,
            "message": message,
            "title": title,
            "diff_content": kwargs.get("diff_content", ""),
            "file_path": kwargs.get("file_path", "")
        })
        
        logger.info(f"[{self.session_id}] Esperando aprobación asíncrona para {request_id}...")
        await event.wait()
        
        with self._pending_lock:
            _, approved = self._pending_approvals_async.pop(request_id, (None, False))
            
        logger.info(f"[{self.session_id}] Aprobación asíncrona {request_id} decidida: {approved}")
        return approved

    def ask_approval_sync(self, message: str, title: str = "Aprobación Requerida", **kwargs) -> bool:
        """Emite un evento de aprobación y bloquea el hilo del worker esperando la respuesta."""
        request_id = str(uuid.uuid4())
        event = threading.Event()
        
        with self._pending_lock:
            self._pending_approvals[request_id] = (event, False)
            
        self._push("approval_required", {
            "id": request_id,
            "message": message,
            "title": title,
            "diff_content": kwargs.get("diff_content", ""),
            "file_path": kwargs.get("file_path", "")
        })
        
        logger.info(f"[{self.session_id}] Esperando aprobación síncrona para {request_id}...")
        # Bloquear el hilo worker
        event.wait()
        
        with self._pending_lock:
            _, approved = self._pending_approvals.pop(request_id, (None, False))
            
        logger.info(f"[{self.session_id}] Aprobación síncrona {request_id} decidida: {approved}")
        return approved

    def handle_approval_response(self, request_id: str, approved: bool) -> None:
        """Recibe la respuesta de aprobación de la TUI o canal y despierta al thread o coroutina."""
        with self._pending_lock:
            # 1. Despertar thread worker síncrono si está bloqueado
            if request_id in self._pending_approvals:
                event, _ = self._pending_approvals[request_id]
                self._pending_approvals[request_id] = (event, approved)
                event.set()
                return

            # 2. Despertar coroutinas asíncronas
            if request_id in self._pending_approvals_async:
                event, _ = self._pending_approvals_async[request_id]
                self._pending_approvals_async[request_id] = (event, approved)
                # Como handle_approval_response puede ser llamado desde el loop o un thread,
                # usamos call_soon_threadsafe para setear el asyncio.Event de forma segura.
                self._loop.call_soon_threadsafe(event.set)

    # ── Consumer API ───────────────────────────────────────────────────────────

    async def events(self) -> AsyncIterator[dict]:
        """Generador asíncrono: yield de eventos mientras la sesión está activa."""
        while True:
            event = await self._async_queue.get()
            yield event
            self._async_queue.task_done()


# ── Sesión individual ──────────────────────────────────────────────────────────


class AgentSession:
    """
    Una sesión de agente persistente para un `session_id` dado.
    El agente se inicializa una vez y permanece "despierto" entre mensajes.
    """

    def __init__(self, session_id: str, llm_service: LLMService, loop: asyncio.AbstractEventLoop, session_manager: Optional[SessionManager] = None):
        self.session_id = session_id
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.session_manager = session_manager

        # UI adapter (sin pantalla)
        self.ui = ServerUI(loop=loop, session_id=session_id)

        # Cargar historial si existe
        initial_messages = []
        if self.session_manager:
            loaded_history = self.session_manager.load_session(session_id)
            if loaded_history:
                logger.info(f"[Session:{session_id}] Historial cargado ({len(loaded_history)} mensajes).")
                initial_messages = loaded_history

        # Estado del agente
        self.agent_state = AgentState(messages=initial_messages)

        # Cola de interrupción (para Ctrl+C desde el canal)
        self.interrupt_queue: queue.Queue = queue.Queue()

        # Gestor de interacción (crea el grafo LangGraph)
        self.manager = AgentInteractionManager(
            llm_service=llm_service,
            agent_state=self.agent_state,
            terminal_ui=self.ui,
            interrupt_queue=self.interrupt_queue,
        )

        # Lock para serializar invocaciones del agente por sesión
        self._agent_lock = asyncio.Lock()

        # Bandera de sesión activa
        self.is_running = False

        # Si es una sesión nueva, guardarla para que sea persistente desde el inicio
        if self.session_manager and not initial_messages:
            self.session_manager.save_session(self.session_id, self.agent_state.messages)

        logger.info(f"[Session:{session_id}] Inicializada.")

    def interrupt(self) -> None:
        """Interrumpe la ejecución actual del agente en esta sesión."""
        self.interrupt_queue.put_nowait(True)

    async def send(self, message: str, executor) -> None:
        """
        Envía un mensaje al agente y lo ejecuta en un hilo worker.
        Los eventos se emiten en tiempo real a `self.ui._async_queue`.
        """
        async with self._agent_lock:
            self.last_activity = datetime.utcnow()
            self.is_running = True
            
            # 1. Manejo de Meta-comandos en el Servidor
            processed = False
            msg_lower = message.lower().strip()
            
            if msg_lower in ("%reset", "/reset"):
                self.agent_state.reset()
                if self.session_manager:
                    self.session_manager.save_session(self.session_id, [])
                self.ui.print_message("Sesión reiniciada correctamente.", style="green")
                processed = True
            elif msg_lower in ("%index", "/index"):
                self.ui.print_message("Iniciando re-indexación del workspace...", style="cyan")
                from kogniterm.server.app import run_indexing_task
                asyncio.create_task(run_indexing_task(self.session_id))
                processed = True
            elif msg_lower in ("%undo", "/undo"):
                if len(self.agent_state.messages) >= 2:
                    self.agent_state.messages.pop() # AI
                    self.agent_state.messages.pop() # Human
                    if self.session_manager:
                        self.session_manager.save_session(self.session_id, self.agent_state.messages)
                    self.ui.print_message("Última interacción eliminada.", style="yellow")
                else:
                    self.ui.print_message("No hay nada que deshacer.", style="red")
                processed = True
            elif msg_lower.startswith(("/resume", "%resume")):
                # /resume [session_name]
                parts = message.split()
                if len(parts) > 1:
                    target_session = parts[1]
                    loaded = self.session_manager.load_session(target_session)
                    # ... (resto de lógica de resume)
                    self.ui.print_message(f"Reanudando desde sesión: {target_session}", style="blue")
                    if loaded:
                        self.agent_state.messages[:] = loaded
                        self.ui.print_message(f"Sesión '{target_session}' cargada correctamente.", style="green")
                    else:
                        self.ui.print_message(f"No se pudo cargar la sesión '{target_session}'.", style="red")
                    processed = True
                else:
                    # Listar sesiones disponibles
                    sessions = self.session_manager.list_sessions()
                    if sessions:
                        session_list = "\n".join([f"- {s['name']} ({s['modified']})" for s in sessions])
                        self.ui.print_message(f"Sesiones disponibles:\n{session_list}\n\nUsa '/resume <nombre>' para cargar una.", style="blue")
                    else:
                        self.ui.print_message("No hay sesiones guardadas.", style="yellow")
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
                await loop.run_in_executor(executor, self.manager.invoke_agent, message)
                # Guardar después de cada interacción exitosa
                if self.session_manager:
                    self.session_manager.save_session(self.session_id, self.agent_state.messages)
                self.ui._push("done", {"session_id": self.session_id})
            except Exception as exc:
                logger.error(f"[Session:{self.session_id}] Error al invocar agente: {exc}")
                self.ui._push("error", {"message": str(exc)})
            finally:
                self.is_running = False

    @property
    def message_count(self) -> int:
        return len([m for m in self.agent_state.messages if isinstance(m, HumanMessage)])

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "message_count": self.message_count,
            "is_running": self.is_running,
        }


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
        self._session_manager: Optional[SessionManager] = None
        # Executor para correr el agente (hilo dedicado por tarea)
        from concurrent.futures import ThreadPoolExecutor
        self._executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="kt-agent")
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

    def initialize(self, llm_service: LLMService, loop: asyncio.AbstractEventLoop) -> None:
        """Debe llamarse en el lifespan de la app, una sola vez."""
        self._llm_service = llm_service
        self._loop = loop
        # Usar el directorio de trabajo actual para el SessionManager
        self._session_manager = SessionManager(workspace_dir=os.getcwd())
        logger.info("SessionPool inicializado con LLMService y SessionManager.")
        
        # Seteamos el ready_event de forma segura en el event loop
        def set_event():
            self.ready_event.set()
        loop.call_soon_threadsafe(set_event)

    def get_or_create(self, session_id: str) -> AgentSession:
        """Obtiene una sesión existente o crea una nueva (thread-safe)."""
        with self._lock:
            if session_id not in self._sessions:
                if not self._llm_service or not self._loop:
                    raise RuntimeError("SessionPool no inicializado. Llama a initialize() primero.")
                self._sessions[session_id] = AgentSession(
                    session_id=session_id,
                    llm_service=self._llm_service,
                    loop=self._loop,
                    session_manager=self._session_manager
                )
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
