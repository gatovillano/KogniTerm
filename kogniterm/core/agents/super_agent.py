import asyncio
import json
import logging
import os
import queue
import threading
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from kogniterm.core.agent_state import AgentState
from kogniterm.core.ai_cli_bridge.llm_bridge import LLMBridge
from kogniterm.core.agents.bash_agent import (
    get_system_message,
    learning_node,
    verification_node,
)
from kogniterm.core.llm_service import LLMService
from kogniterm.core.utils.prompt_processor import process_prompt_references
from kogniterm.terminal.terminal_ui import TerminalUI

logger = logging.getLogger(__name__)


def _langchain_to_dict_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """Convierte una lista de mensajes LangChain a la estructura de diccionarios de LiteLLM/OpenAI."""
    dict_msgs: List[Dict[str, Any]] = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            dict_msgs.append({"role": "system", "content": str(msg.content)})
        elif isinstance(msg, HumanMessage):
            dict_msgs.append({"role": "user", "content": str(msg.content)})
        elif isinstance(msg, AIMessage):
            d: Dict[str, Any] = {"role": "assistant", "content": str(msg.content or "")}
            if getattr(msg, "tool_calls", None):
                d["tool_calls"] = [
                    {
                        "id": tc.get("id", f"call_{i}"),
                        "type": "function",
                        "function": {
                            "name": tc.get("name"),
                            "arguments": json.dumps(tc.get("args", {}))
                            if isinstance(tc.get("args"), dict)
                            else str(tc.get("args", "{}")),
                        },
                    }
                    for i, tc in enumerate(msg.tool_calls)
                ]
            dict_msgs.append(d)
        elif isinstance(msg, ToolMessage):
            dict_msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": getattr(msg, "tool_call_id", ""),
                    "name": getattr(msg, "name", ""),
                    "content": str(msg.content),
                }
            )
        elif isinstance(msg, dict):
            dict_msgs.append(msg)
    return dict_msgs


class SuperAgent:
    """Agente maestro simplificado con acceso completo a herramientas y streaming."""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model
        self.llm_bridge = LLMBridge(model=self.model)

    async def execute_stream(
        self,
        task: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 25,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if messages is None:
            messages = []

        default_system = "Eres KogniTerm en modo fast path. Responde claro, breve y ejecuta tools cuando ayuden."
        sys_content = system_prompt or default_system

        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": sys_content})
        elif system_prompt:
            messages[0]["content"] = system_prompt

        if task:
            messages.append({"role": "user", "content": task})

        tools_used: List[str] = []
        full_content: List[str] = []
        error_msg: Optional[str] = None

        async for event in self.llm_bridge.chat(messages=messages, max_steps=max_steps):
            ev_type = event.get("type")
            if ev_type in ("content", "chunk"):
                text = event.get("text", "")
                if text:
                    full_content.append(text)
                    yield {"type": "chunk", "text": text}
            elif ev_type == "reasoning":
                yield {"type": "reasoning", "text": event.get("text", "")}
            elif ev_type == "tool_start":
                name = event.get("name", "")
                if name and name not in tools_used:
                    tools_used.append(name)
                yield {"type": "tool_start", "name": name, "args": event.get("args", {})}
            elif ev_type == "tool_result":
                yield {"type": "tool_result", "name": event.get("name", ""), "result": event.get("result")}
            elif ev_type == "error":
                error_msg = event.get("message")
                yield {"type": "error", "message": error_msg}
            elif ev_type == "done":
                content = event.get("content", "")
                if content and not full_content:
                    full_content.append(content)

        output_text = "".join(full_content).strip()
        success = error_msg is None

        if error_msg:
            output_text = (
                f"{output_text}\n\n[Respuesta interrumpida debido a un error: {error_msg}]"
                if output_text
                else f"[Error: {error_msg}]"
            )

        yield {
            "type": "done",
            "output": output_text or "Tarea completada.",
            "tools_used": tools_used,
            "success": success,
            "error": error_msg,
        }

    async def run(
        self,
        task: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 25,
    ) -> Dict[str, Any]:
        """Ejecuta una tarea y devuelve el resultado final consolidado."""
        output_text = ""
        tools_used: List[str] = []
        error_msg: Optional[str] = None
        success = True

        async for event in self.execute_stream(
            task=task,
            messages=messages,
            system_prompt=system_prompt,
            max_steps=max_steps,
        ):
            ev_type = event.get("type")
            if ev_type in ("content", "chunk"):
                output_text += event.get("text", "")
            elif ev_type == "tool_start":
                tools_used.append(event.get("name", ""))
            elif ev_type == "error":
                error_msg = event.get("message")
                success = False
            elif ev_type == "done":
                output_text = event.get("output", output_text)
                tools_used = event.get("tools_used", tools_used)
                success = event.get("success", success)
                error_msg = event.get("error", error_msg)

        return {
            "output": output_text.strip(),
            "tools_used": tools_used,
            "success": success,
            "error": error_msg,
        }


class SuperAgentRunner:
    """
    Motor asíncrono ultrarrápido basado en SuperAgent para KogniTerm.
    Ofrece compatibilidad completa con AgentInteractionManager, gestionando streaming
    en vivo de pensamiento/texto y confirmaciones Human-in-the-Loop sin sobrecarga de LangGraph.
    """

    def __init__(
        self,
        llm_service: LLMService,
        terminal_ui: Optional[TerminalUI] = None,
        interrupt_queue: Optional[queue.Queue] = None,
        command_approval_handler=None,
    ) -> None:
        self.llm_service = llm_service
        self.terminal_ui = terminal_ui
        self.interrupt_queue = interrupt_queue
        self.command_approval_handler = command_approval_handler

        model_name = getattr(llm_service, "model_name", None) or os.environ.get("LITELLM_MODEL")
        self.agent = SuperAgent(model=model_name)

    def invoke(self, state: AgentState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Punto de entrada síncrono para AgentInteractionManager."""
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import nest_asyncio

                nest_asyncio.apply()
                return loop.run_until_complete(self._run_async(state))
            else:
                return asyncio.run(self._run_async(state))
        except Exception as e:
            logger.debug(f"Fallback en SuperAgentRunner.invoke: {e}")
            return asyncio.run(self._run_async(state))

    async def _run_async(self, state: AgentState) -> Dict[str, Any]:
        state.stop_requested = False

        # 1. Pre-procesamiento de referencias a archivos (@) y skills (#)
        if state.messages and isinstance(state.messages[-1], HumanMessage):
            workspace_directory = os.getcwd()
            sm = getattr(self.llm_service, "skill_manager", None)
            processed_content = process_prompt_references(
                state.messages[-1].content, workspace_directory, sm
            )
            state.messages[-1] = HumanMessage(content=processed_content)

        # 2. Obtener el system prompt enriquecido de KogniTerm
        try:
            sys_msg = get_system_message(self.llm_service)
            system_prompt = sys_msg.content if hasattr(sys_msg, "content") else str(sys_msg)
        except Exception as exc:
            logger.debug(f"No se pudo generar system_message dinámico: {exc}")
            system_prompt = "Eres KogniTerm, un asistente evolutivo de terminal de alta velocidad."

        # 3. Convertir mensajes al formato de LiteLLM
        llm_messages = _langchain_to_dict_messages(state.messages)

        accumulated_chunks = []
        thinking_text = ""

        if self.terminal_ui and hasattr(self.terminal_ui, "print_status"):
            try:
                self.terminal_ui.print_status("⚡ SuperAgent procesando...", spinner_style="dots")
            except Exception:
                pass

        try:
            async for event in self.agent.execute_stream(
                messages=llm_messages,
                system_prompt=system_prompt,
                max_steps=30,
            ):
                ev_type = event.get("type")

                if ev_type == "reasoning":
                    r_text = event.get("text", "")
                    thinking_text += r_text
                    if self.terminal_ui and hasattr(self.terminal_ui, "print_thinking_chunk"):
                        try:
                            self.terminal_ui.print_thinking_chunk(r_text)
                        except Exception:
                            pass

                elif ev_type in ("content", "chunk"):
                    c_text = event.get("text", "")
                    accumulated_chunks.append(c_text)
                    if self.terminal_ui and hasattr(self.terminal_ui, "print_stream_chunk"):
                        try:
                            self.terminal_ui.print_stream_chunk(c_text)
                        except Exception:
                            pass

                elif ev_type == "tool_start":
                    t_name = event.get("name", "")
                    t_args = event.get("args", {})

                    # Pausa para confirmación de comandos de terminal
                    if t_name in ("execute_command", "run_shell"):
                        cmd = t_args.get("command", "")
                        state.command_to_confirm = cmd
                        state.tool_call_id_to_confirm = t_name
                        return {
                            "messages": state.messages,
                            "command_to_confirm": state.command_to_confirm,
                            "tool_call_id_to_confirm": state.tool_call_id_to_confirm,
                        }

                    # Pausa para confirmación de modificaciones de archivo si aplica
                    if t_name in (
                        "edit_file",
                        "replace_all_file",
                        "delete_file",
                        "advanced_file_editor",
                        "file_update_tool",
                    ):
                        if getattr(state, "require_tool_confirmation", False):
                            state.tool_pending_confirmation = t_name
                            state.tool_args_pending_confirmation = t_args
                            state.tool_call_id_to_confirm = t_name
                            return {
                                "messages": state.messages,
                                "tool_pending_confirmation": state.tool_pending_confirmation,
                                "tool_args_pending_confirmation": state.tool_args_pending_confirmation,
                                "tool_call_id_to_confirm": state.tool_call_id_to_confirm,
                            }

                elif ev_type == "done":
                    final_text = event.get("output", "").strip() or "".join(accumulated_chunks).strip()
                    if final_text:
                        state.add_message(AIMessage(content=final_text))

                    # 4. Verificación de sintaxis Python tras operaciones de edición
                    try:
                        verification_node(state, self.llm_service, self.terminal_ui)
                    except Exception as ve:
                        logger.debug(f"Verificación de sintaxis omitida o fallida: {ve}")

                    # 5. Aprendizaje en segundo plano (fire-and-forget)
                    try:
                        threading.Thread(
                            target=learning_node,
                            args=(state, self.llm_service, self.terminal_ui),
                            daemon=True,
                        ).start()
                    except Exception as le:
                        logger.debug(f"Aprendizaje en segundo plano no iniciado: {le}")

                    return {
                        "messages": state.messages,
                        "command_to_confirm": None,
                        "tool_call_id_to_confirm": None,
                    }

        except Exception as exc:
            logger.error(f"Error en SuperAgentRunner: {exc}", exc_info=True)
            if self.terminal_ui and hasattr(self.terminal_ui, "print_message"):
                self.terminal_ui.print_message(f"❌ Error en SuperAgent: {exc}", style="red")

        return {
            "messages": state.messages,
            "command_to_confirm": getattr(state, "command_to_confirm", None),
            "tool_call_id_to_confirm": getattr(state, "tool_call_id_to_confirm", None),
        }


def create_super_agent(
    llm_service: LLMService,
    terminal_ui: Optional[TerminalUI] = None,
    interrupt_queue: Optional[queue.Queue] = None,
    command_approval_handler=None,
) -> SuperAgentRunner:
    """Función de fábrica para instanciar SuperAgentRunner."""
    return SuperAgentRunner(
        llm_service=llm_service,
        terminal_ui=terminal_ui,
        interrupt_queue=interrupt_queue,
        command_approval_handler=command_approval_handler,
    )
