import logging
import sys
import time
import threading
from kogniterm.core.config import settings
from rich.console import Console
from rich.spinner import Spinner
from rich.live import Live
from rich.text import Text

logger = logging.getLogger(__name__)

from kogniterm.core.agent_interaction import BaseAgentInteractionManager, AgentInteractionRegistry
from kogniterm.core.llm_service import LLMService
from kogniterm.core.agents.bash_agent import create_bash_agent, create_learning_agent, AgentState, get_system_message
from kogniterm.core.agents.agent_catalog import (
    DEFAULT_CHAT_AGENT,
    SUPPORTED_CHAT_AGENTS,
    create_agent_runner,
    describe_agents,
    normalize_agent_id,
)
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import Dict, Any, Optional
import os
import queue # Importar queue
from kogniterm.terminal.terminal_ui import TerminalUI # Importar TerminalUI
from kogniterm.terminal.keyboard_handler import KeyboardHandler # Importar KeyboardHandler
from kogniterm.core.agents.super_agent import create_super_agent

"""
This module contains the AgentInteractionManager class, responsible for
orchestrating AI agent interactions in the KogniTerm application.
"""

class AgentInteractionManager(BaseAgentInteractionManager):
    def __init__(self, llm_service: LLMService, agent_state: AgentState, terminal_ui: TerminalUI, interrupt_queue: queue.Queue, command_approval_handler=None):
        logger.info(f"AgentInteractionManager init: terminal_ui class={type(terminal_ui)}")
        self.llm_service = llm_service
        self.agent_state = agent_state
        self.terminal_ui = terminal_ui # Guardar la instancia de TerminalUI
        self.interrupt_queue = interrupt_queue # Guardar la cola de interrupción
        self.command_approval_handler = command_approval_handler
        self.bash_agent_app = create_bash_agent(llm_service, terminal_ui, interrupt_queue, command_approval_handler) # Pasar command_approval_handler
        self.super_agent_app = create_super_agent(llm_service, terminal_ui, interrupt_queue, command_approval_handler)
        self.learning_agent_app = create_learning_agent(llm_service, terminal_ui)
        self.agent_runners = {
            "super_agent": self.super_agent_app,
            "bash_agent": self.bash_agent_app,
        }
        self.active_agent_name = DEFAULT_CHAT_AGENT
        
        main_agent = os.environ.get("KOGNITERM_MAIN_AGENT", "super_agent").lower().strip()
        if main_agent == "super_agent":
            self.active_agent_app = self.super_agent_app
            self.active_agent_name = "super_agent"
            logger.info("AgentInteractionManager: Usando SuperAgent como agente principal.")
        else:
            self.active_agent_app = self.bash_agent_app
            self.active_agent_name = "bash_agent"
            logger.info("AgentInteractionManager: Usando BashAgent como agente principal.")
        self.agent_state.current_agent_mode = self.active_agent_name
        
        # Obtener el SYSTEM_MESSAGE dinámico para este llm_service
        current_system_message = get_system_message(self.llm_service)
        
        # Asegurarse de que el SYSTEM_MESSAGE esté siempre al principio del historial.
        if not self.agent_state.messages or not (isinstance(self.agent_state.messages[0], SystemMessage) and self.agent_state.messages[0].content == current_system_message.content):
            if self.agent_state.messages and not (isinstance(self.agent_state.messages[0], SystemMessage) and self.agent_state.messages[0].content == current_system_message.content):
                self.agent_state.messages.insert(0, current_system_message)
            elif not self.agent_state.messages:
                self.agent_state.messages.append(current_system_message)
        
        # Filtrar cualquier SYSTEM_MESSAGE duplicado del historial si ya lo hemos añadido
        system_message_count = sum(1 for msg in self.agent_state.messages if isinstance(msg, SystemMessage) and msg.content == current_system_message.content)
        if system_message_count > 1:
            first_system_message_index = -1
            for i, msg in enumerate(self.agent_state.messages):
                if isinstance(msg, SystemMessage) and msg.content == current_system_message.content:
                    if first_system_message_index == -1:
                        first_system_message_index = i
                    else:
                        self.agent_state.messages.pop(i)
                        break

        # Sincronizar automáticamente cuando cambie el modelo en LLMService
        if hasattr(self.llm_service, "register_model_change_listener"):
            self.llm_service.register_model_change_listener(self.set_model)

    def available_agents(self) -> list[dict]:
        """Catálogo nativo de motores conversacionales seleccionables."""
        return describe_agents()

    def active_agent(self) -> str:
        """Identificador canónico del motor actualmente activo."""
        return self.active_agent_name

    def set_active_agent(self, agent_id: str | None) -> str:
        """
        Cambia el motor activo conservando el historial y las dependencias
        compartidas de la sesión. Solo acepta agentes conversacionales reales.
        """
        normalized = normalize_agent_id(agent_id)
        if normalized not in SUPPORTED_CHAT_AGENTS:
            raise ValueError(f"Agente no soportado: {agent_id!r}")
        if normalized == self.active_agent_name and normalized in self.agent_runners:
            return normalized

        runner = self.agent_runners.get(normalized)
        if runner is None:
            runner = create_agent_runner(
                normalized,
                llm_service=self.llm_service,
                terminal_ui=self.terminal_ui,
                interrupt_queue=self.interrupt_queue,
                command_approval_handler=self.command_approval_handler,
            )
            self.agent_runners[normalized] = runner

        model_name = getattr(self.llm_service, "model_name", None)
        if model_name and hasattr(runner, "set_model"):
            try:
                runner.set_model(model_name)
            except Exception:
                logger.warning("No se pudo sincronizar el modelo con %s", normalized)

        self.active_agent_app = runner
        self.active_agent_name = normalized
        self.agent_state.current_agent_mode = normalized
        logger.info("AgentInteractionManager: agente activo cambiado a %s.", normalized)
        return normalized

    def set_model(self, model: str) -> None:
        """Actualiza el modelo del LLMService y de todos los runners instanciados."""
        if self.llm_service and getattr(self.llm_service, "model_name", None) != model:
            self.llm_service.set_model(model)
        seen_runner_ids = set()
        runners = [
            self.super_agent_app,
            self.bash_agent_app,
            self.active_agent_app,
            *self.agent_runners.values(),
        ]
        for runner in runners:
            if runner is None or id(runner) in seen_runner_ids:
                continue
            seen_runner_ids.add(id(runner))
            if hasattr(runner, "set_model"):
                runner.set_model(model)

    def invoke_agent(self, user_input: Optional[str]) -> Dict[str, Any]:
        import os
        
        # El mensaje ya fue añadido al historial por KogniTermApp antes de llamar a este método.
        # No lo añadimos de nuevo para evitar duplicación.
        
        # Inyectar contexto dinámico del directorio de trabajo actual
        current_working_directory = os.getcwd()
        
        # Mantener los mensajes existentes pero limpiar contextos dinámicos previos in-place
        i = 0
        while i < len(self.agent_state.messages):
            msg = self.agent_state.messages[i]
            if isinstance(msg, SystemMessage) and "📂 **Directorio de Trabajo Actual:**" in msg.content:
                self.agent_state.messages.pop(i)
            else:
                i += 1
        
        # Crear el mensaje de contexto dinámico
        context_message = SystemMessage(content=f"""
📂 **Directorio de Trabajo Actual:** `{current_working_directory}`

Este es el directorio en el que estás trabajando actualmente. Todas las rutas relativas se resolverán desde aquí.
Cuando ejecutes comandos o manipules archivos, ten en cuenta esta ubicación.
""")
        
        # Insertar el contexto en una posición segura (justo después del sistema principal)
        # Si el historial ya tiene un sistema en el índice 0, lo ponemos en el 1.
        insertion_idx = 0
        if self.agent_state.messages and isinstance(self.agent_state.messages[0], SystemMessage):
            insertion_idx = 1
        self.agent_state.messages.insert(insertion_idx, context_message)

        # Registrar y establecer el contexto de delegación del orquestador principal
        if self.llm_service and hasattr(self.llm_service, "delegation_manager"):
            try:
                from kogniterm.core.delegation import AgentRole
                if not self.llm_service.delegation_manager.get_context("orchestrator"):
                    self.llm_service.delegation_manager.register_agent(
                        agent_id="orchestrator",
                        parent_id=None,
                        role=AgentRole.ORCHESTRATOR
                    )
                ctx = self.llm_service.delegation_manager.get_context("orchestrator")
                # NO asignar delegation_context al agente raíz — el orquestador no es
                # un subagente delegado. Hacerlo causaba que _invoke_tool_with_interrupt
                # inyectara confirm=True en todas las herramientas, bypasseando el modal.
                self.llm_service.current_delegation_context = ctx
            except Exception as e:
                logger.error(f"Error al registrar el orquestador principal en la delegación: {e}")

        sys.stderr.flush()
        
        try:
            # Ejecutar invoke sin timeout
            final_state_dict = self.active_agent_app.invoke(self.agent_state, config={"recursion_limit": 1000})
        finally:
            pass

        sys.stderr.flush()
        
        # Actualizar el estado del agente con los valores del final_state_dict
        self.agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')
        self.agent_state.tool_code_to_confirm = final_state_dict.get('tool_code_to_confirm')
        self.agent_state.tool_code_tool_name = final_state_dict.get('tool_code_tool_name')
        self.agent_state.tool_code_tool_args = final_state_dict.get('tool_code_tool_args')
        self.agent_state.file_update_diff_pending_confirmation = final_state_dict.get('file_update_diff_pending_confirmation')
        self.agent_state.tool_pending_confirmation = final_state_dict.get('tool_pending_confirmation')
        self.agent_state.tool_args_pending_confirmation = final_state_dict.get('tool_args_pending_confirmation')
        logger.info(
            "[DIAG] aim: final_state_dict has file_diff=%s, tool_pend=%s; agent_state.file_diff=%s, agent_state.tool_pend=%s",
            final_state_dict.get('file_update_diff_pending_confirmation') is not None,
            final_state_dict.get('tool_pending_confirmation'),
            self.agent_state.file_update_diff_pending_confirmation is not None,
            self.agent_state.tool_pending_confirmation,
        )

        # Actualizar los mensajes in-place siempre para evitar pérdida de referencias
        if 'messages' in final_state_dict:
            self.agent_state.messages[:] = final_state_dict['messages']

        
        # 1. Intentar capturar del final_state_dict (prioridad si el agente lo estableció explícitamente)
        if 'tool_call_id_to_confirm' in final_state_dict and final_state_dict['tool_call_id_to_confirm']:
            self.agent_state.tool_call_id_to_confirm = final_state_dict['tool_call_id_to_confirm']
        else:
            # 2. Fallback: capturar del último AIMessage si tiene tool_calls
            last_ai_message = None
            for msg in reversed(self.agent_state.messages):
                if isinstance(msg, AIMessage):
                    last_ai_message = msg
                    break
            
            if last_ai_message and last_ai_message.tool_calls:
                # Asumiendo que solo hay una tool_call por AIMessage para simplificar
                self.agent_state.tool_call_id_to_confirm = last_ai_message.tool_calls[0]['id']
            else:
                self.agent_state.tool_call_id_to_confirm = None

        # Grafo de aprendizaje posterior: se ejecuta al final de un turno cuando no hay herramientas pendientes
        last_msg = self.agent_state.messages[-1] if self.agent_state.messages else None
        has_tool_calls = isinstance(last_msg, AIMessage) and bool(last_msg.tool_calls)
        
        if (hasattr(self, "learning_agent_app") and self.learning_agent_app and 
            not self.agent_state.command_to_confirm and 
            not getattr(self.agent_state, 'tool_pending_confirmation', None) and 
            not self.agent_state.file_update_diff_pending_confirmation and
            not getattr(self.agent_state, 'tool_code_to_confirm', None) and
            not has_tool_calls):
            try:
                logger.info("Ejecutando el grafo de aprendizaje posterior en segundo plano...")
                # Crear un estado shallow-copy para evitar race conditions si el estado principal se modifica
                learning_state = AgentState(messages=list(self.agent_state.messages))
                learning_state.critical_loop_detected = getattr(self.agent_state, 'critical_loop_detected', False)
                learning_state.stop_requested = getattr(self.agent_state, 'stop_requested', False)
                
                def run_learning_bg():
                    try:
                        self.learning_agent_app.invoke(learning_state)
                    except Exception as le:
                        logger.error(f"Error en segundo plano al ejecutar el grafo de aprendizaje: {le}")
                
                threading.Thread(target=run_learning_bg, daemon=True).start()
            except Exception as e:
                logger.error(f"Error al iniciar el thread de aprendizaje: {e}")
        
        return final_state_dict


AgentInteractionRegistry.register_factory(AgentInteractionManager)



