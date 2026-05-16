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
from datetime import datetime
from io import StringIO
from typing import Any, AsyncIterator, Callable, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from kogniterm.core.agent_state import AgentState
from kogniterm.core.llm_service import LLMService
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

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _push(self, event_type: str, data: Any) -> None:
        """Envía un evento desde cualquier hilo al loop asyncio del servidor."""
        event = {"type": event_type, "data": data, "ts": datetime.utcnow().isoformat()}
        try:
            self._loop.call_soon_threadsafe(self._async_queue.put_nowait, event)
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
        self._push("stream", text)

    def update_live(self, renderable: Any) -> None:
        self._push("live_update", self._render_rich(renderable))

    def stop_live(self, **kwargs) -> None:
        self._push("live_stop", {})

    def print_message(self, message: str, style: str = "", **kwargs) -> None:
        self._push("message", {"text": message, "style": style})

    def print_tool_notification(self, tool_name: str, bajada: str = "", skill_name: str = "", **kwargs) -> None:
        self._push("tool_start", {"tool": tool_name, "description": bajada, "skill": skill_name})

    def update_terminal_output(self, tool_name: str, output: str, **kwargs) -> None:
        self._push("tool_output", {"tool": tool_name, "output": output})

    def update_task_tracker(self, agent_plans: dict) -> None:
        self._push("task_tracker", agent_plans)

    async def ask_approval_async(self, message: str, title: str = "Aprobación Requerida", **kwargs) -> bool:
        """Emite un evento de aprobación y espera la respuesta del canal."""
        request_id = str(uuid.uuid4())
        self._push("approval_required", {"id": request_id, "message": message, "title": title})
        # TODO: esperar respuesta vía canal de respuesta (por ahora deniega por seguridad)
        logger.warning(f"[{self.session_id}] Aprobación requerida sin canal de respuesta — denegando.")
        return False

    def ask_approval_sync(self, message: str, title: str = "Aprobación Requerida", **kwargs) -> bool:
        self._push("approval_required", {"message": message, "title": title})
        return False

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

    def __init__(self, session_id: str, llm_service: LLMService, loop: asyncio.AbstractEventLoop):
        self.session_id = session_id
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()

        # UI adapter (sin pantalla)
        self.ui = ServerUI(loop=loop, session_id=session_id)

        # Estado del agente
        self.agent_state = AgentState()

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
            self.ui._push("user_message", {"text": message})

            # Añadir el mensaje humano al historial
            self.agent_state.add_message(HumanMessage(content=message))

            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(executor, self.manager.invoke_agent, message)
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
        # Executor para correr el agente (hilo dedicado por tarea)
        from concurrent.futures import ThreadPoolExecutor
        self._executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="kt-agent")

    def initialize(self, llm_service: LLMService, loop: asyncio.AbstractEventLoop) -> None:
        """Debe llamarse en el lifespan de la app, una sola vez."""
        self._llm_service = llm_service
        self._loop = loop
        logger.info("SessionPool inicializado con LLMService.")

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
