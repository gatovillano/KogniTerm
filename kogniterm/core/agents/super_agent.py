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
from kogniterm.core.utils.tool_utils import format_tool_action_target
from kogniterm.terminal.terminal_ui import TerminalUI

logger = logging.getLogger(__name__)


TERMINAL_TOOLS = {
    "execute_command", "execute_command_tool", "run_command", "run_command_tool",
    "bash", "cmd_execution", "python_executor", "python_executor_tool", "shell", "terminal"
}


def is_terminal_tool(name: str) -> bool:
    if not name:
        return False
    name_lower = name.lower()
    return name_lower in TERMINAL_TOOLS or any(kw in name_lower for kw in ["command", "bash", "terminal", "shell", "python_exec"])


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
            t_id = getattr(msg, "tool_call_id", "") or "call_unknown"
            t_name = getattr(msg, "name", "") or "tool"

            # Validar que el ToolMessage esté precedido por un assistant message con su tool_call_id
            needs_synthetic_assistant = True
            if dict_msgs and dict_msgs[-1].get("role") == "assistant":
                prev_tc = dict_msgs[-1].get("tool_calls", [])
                if any(tc.get("id") == t_id for tc in prev_tc):
                    needs_synthetic_assistant = False
                elif not prev_tc:
                    dict_msgs[-1]["tool_calls"] = [{
                        "id": t_id,
                        "type": "function",
                        "function": {"name": t_name, "arguments": "{}"}
                    }]
                    needs_synthetic_assistant = False

            if needs_synthetic_assistant:
                dict_msgs.append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": t_id,
                        "type": "function",
                        "function": {"name": t_name, "arguments": "{}"}
                    }]
                })

            dict_msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": t_id,
                    "name": t_name,
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

    def set_model(self, model: str) -> None:
        """Actualiza el modelo del agente y de su puente LLM."""
        self.model = model
        if hasattr(self, "llm_bridge") and self.llm_bridge:
            self.llm_bridge.set_model(model)

    async def execute_stream(
        self,
        task: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 25,
        interrupt_queue: Optional[Any] = None,
        stop_check: Optional[Any] = None,
        model: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if messages is None:
            messages = []

        default_system = "Eres KogniTerm un agente de experto en terminal y edición de código. Responde claro, breve y ejecuta tools cuando ayuden."
        sys_content = system_prompt or default_system

        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": sys_content})
        elif system_prompt:
            messages[0]["content"] = system_prompt

        if task:
            messages.append({"role": "user", "content": task})

        target_model = model or self.model
        if target_model and getattr(self, "model", None) != target_model:
            self.set_model(target_model)

        tools_used: List[str] = []
        full_content: List[str] = []
        error_msg: Optional[str] = None

        chat_kwargs: Dict[str, Any] = {
            "messages": messages,
            "max_steps": max_steps,
        }
        try:
            import inspect
            sig = inspect.signature(self.llm_bridge.chat)
            if "model" in sig.parameters and target_model is not None:
                chat_kwargs["model"] = target_model
            if "interrupt_queue" in sig.parameters and interrupt_queue is not None:
                chat_kwargs["interrupt_queue"] = interrupt_queue
            if "stop_check" in sig.parameters and stop_check is not None:
                chat_kwargs["stop_check"] = stop_check
        except Exception:
            if target_model is not None:
                chat_kwargs["model"] = target_model
            if interrupt_queue is not None:
                chat_kwargs["interrupt_queue"] = interrupt_queue
            if stop_check is not None:
                chat_kwargs["stop_check"] = stop_check

        async for event in self.llm_bridge.chat(**chat_kwargs):
            ev_type = event.get("type")
            if ev_type == "interrupted":
                yield event
                return
            elif ev_type in ("content", "chunk"):
                text = event.get("text", "")
                if text:
                    full_content.append(text)
                    yield {"type": "chunk", "text": text}
            elif ev_type == "reasoning":
                yield {"type": "reasoning", "text": event.get("text", "")}
            elif ev_type == "tool_calls_start":
                yield event
            elif ev_type == "tool_start":
                name = event.get("name", "")
                if name and name not in tools_used:
                    tools_used.append(name)
                yield {
                    "type": "tool_start",
                    "name": name,
                    "args": event.get("args", {}),
                    "id": event.get("id"),
                }
            elif ev_type == "tool_result":
                yield {
                    "type": "tool_result",
                    "name": event.get("name", ""),
                    "result": event.get("result"),
                    "id": event.get("id"),
                }
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
        custom_system_prompt: Optional[str] = None,
    ) -> None:
        self.llm_service = llm_service
        self.terminal_ui = terminal_ui
        self.interrupt_queue = interrupt_queue or getattr(llm_service, "interrupt_queue", None)
        self.command_approval_handler = command_approval_handler
        self.custom_system_prompt = custom_system_prompt

        model_name = getattr(llm_service, "model_name", None) or os.environ.get("LITELLM_MODEL")
        self.agent = SuperAgent(model=model_name)

        # Vincular UI y LLMService a task_tracker para sincronización de panel visual
        try:
            from kogniterm.core.ai_cli_bridge.tool_registry_adapter import bind_task_tracker_context
            bind_task_tracker_context(terminal_ui=self.terminal_ui, llm_service=self.llm_service)
        except Exception:
            pass

    def set_model(self, model: str) -> None:
        """Actualiza el modelo de SuperAgent y propaga al puente subyacente."""
        if hasattr(self, "agent") and self.agent:
            self.agent.set_model(model)

    # Conjunto de herramientas que editan archivos y pueden producir un diff aplicado
    _FILE_EDIT_TOOLS = {
        "advanced_file_editor",
        "advanced_file_editor_tool",
        "sophisticated_editor_tool",
        "replace_file_content",
        "file_update_tool",
        "file_update",
        "file_operations",
        "file_operations_tool",
        "write_file_tool",
        "write",
        "write_file",
        "edit_file",
        "replace_all_file",
    }

    def _show_applied_diff_if_any(self, tool_name: str, result: Any, tool_args: Dict[str, Any]) -> None:
        """
        Muestra el diff aplicado en la TUI después de que una herramienta de
        edición de archivos haya sido ejecutada con éxito.

        Busca el diff aplicado en el resultado de la herramienta (campo
        ``applied_diff`` o ``diff``) y lo renderiza mediante ``DiffRenderer``
        directamente en el historial de la TUI.
        """
        if not self.terminal_ui or tool_name not in self._FILE_EDIT_TOOLS:
            return

        diff_content = ""
        file_path = ""

        # Extraer diff y path del resultado normalizado
        if isinstance(result, dict):
            diff_content = result.get("applied_diff") or result.get("diff") or ""
            file_path = result.get("path") or ""
        elif isinstance(result, str):
            try:
                parsed = json.loads(result)
                if isinstance(parsed, dict):
                    diff_content = parsed.get("applied_diff") or parsed.get("diff") or ""
                    file_path = parsed.get("path") or ""
            except Exception:
                pass

        if not diff_content:
            # Generar diff a partir del path y el contenido esperado
            content = ""
            for key in ("content", "new_content", "replacement_content", "text"):
                content = tool_args.get(key, "")
                if content:
                    break

            # Extraer file_path de distintas convenciones de parámetros
            file_path = tool_args.get("path") or tool_args.get("file_path") or tool_args.get("target_file") or tool_args.get("TargetFile") or ""

            if file_path and content:
                try:
                    import difflib
                    old_content = ""
                    if os.path.exists(file_path):
                        with open(file_path, "r", encoding="utf-8") as f:
                            old_content = f.read()
                    unified = "".join(difflib.unified_diff(
                        old_content.splitlines(keepends=True),
                        content.splitlines(keepends=True),
                        fromfile=f"a/{file_path}",
                        tofile=f"b/{file_path}",
                    ))
                    if unified:
                        diff_content = unified
                except Exception:
                    pass

        if not diff_content or not file_path:
            return

        try:
            from kogniterm.utils.diff_renderer import DiffRenderer
            from rich.panel import Panel
            from rich.text import Text
            from rich.console import Group

            diff_renderer = DiffRenderer()
            diff_table = diff_renderer.render_diff_from_string(diff_content, file_path)

            title_text = f"✅ Diff aplicado: {file_path}"
            subtitle = Text(f"Operación: {tool_name}", style="dim cyan")

            panel = Panel(
                Group(subtitle, Text(""), diff_table),
                title=title_text,
                border_style="green",
                expand=True,
            )

            # Renderizar en la TUI persistente
            if hasattr(self.terminal_ui, "update_live") and hasattr(self.terminal_ui, "stop_live"):
                self.terminal_ui.update_live(panel)
                self.terminal_ui.stop_live()
            elif hasattr(self.terminal_ui, "console"):
                self.terminal_ui.console.print(panel)
            else:
                self.terminal_ui.print_message(
                    f"### ✅ Cambios aplicados en `{file_path}`\n"
                    f"**Operación:** `{tool_name}`\n\n"
                    f"```diff\n{diff_content}\n```"
                )
        except Exception as e:
            logger.warning(f"No se pudo renderizar diff en super_agent: {e}")
            try:
                self.terminal_ui.print_message(
                    f"### ✅ Cambios aplicados en `{file_path}`\n\n```diff\n{diff_content}\n```"
                )
            except Exception:
                pass

    def invoke(self, state: AgentState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Punto de entrada síncrono para AgentInteractionManager y call-agent."""
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

    async def ainvoke(self, state: AgentState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Punto de entrada asíncrono para call-agents-parallel u orquestadores async."""
        return await self._run_async(state)

    async def _run_async(self, state: AgentState) -> Dict[str, Any]:
        state.stop_requested = False
        if self.llm_service is not None and hasattr(self.llm_service, "stop_generation_flag"):
            self.llm_service.stop_generation_flag = False

        # Sincronizar dinámicamente el modelo con llm_service o el entorno si cambió
        current_model = getattr(self.llm_service, "model_name", None) or os.environ.get("LITELLM_MODEL")
        if current_model and getattr(self.agent, "model", None) != current_model:
            self.set_model(current_model)

        def _check_stop() -> bool:
            if self.interrupt_queue is not None and hasattr(self.interrupt_queue, "empty"):
                try:
                    if not self.interrupt_queue.empty():
                        return True
                except Exception:
                    pass
            if self.llm_service is not None:
                flag = getattr(self.llm_service, "stop_generation_flag", None)
                if flag is True:
                    return True
            if getattr(state, "stop_requested", False) is True:
                return True
            return False

        # 1. Pre-procesamiento de referencias a archivos (@) y skills (#)
        if state.messages and isinstance(state.messages[-1], HumanMessage):
            workspace_directory = os.getcwd()
            sm = getattr(self.llm_service, "skill_manager", None)
            processed_content = process_prompt_references(
                state.messages[-1].content, workspace_directory, sm
            )
            state.messages[-1] = HumanMessage(content=processed_content)

        # 2. Vincular UI y LLMService a task_tracker para sincronización de panel visual
        try:
            from kogniterm.core.ai_cli_bridge.tool_registry_adapter import bind_task_tracker_context
            bind_task_tracker_context(terminal_ui=self.terminal_ui, llm_service=self.llm_service)
        except Exception:
            pass

        # 3. Obtener el system prompt enriquecido de KogniTerm o personalizado
        if self.custom_system_prompt:
            system_prompt = self.custom_system_prompt
        else:
            try:
                sys_msg = get_system_message(self.llm_service)
                system_prompt = sys_msg.content if hasattr(sys_msg, "content") else str(sys_msg)
            except Exception as exc:
                logger.debug(f"No se pudo generar system_message dinámico: {exc}")
                system_prompt = "Eres KogniTerm, un asistente evolutivo de terminal de alta velocidad."

        # 4. Convertir mensajes al formato de LiteLLM
        llm_messages = _langchain_to_dict_messages(state.messages)

        accumulated_chunks = []
        thinking_text = ""
        text_streamed = False

        if self.terminal_ui and hasattr(self.terminal_ui, "print_status"):
            try:
                self.terminal_ui.print_status("⚡ SuperAgent procesando...", spinner_style="dots")
            except Exception:
                pass

        target_model = current_model or getattr(self.agent, "model", None)
        stream_kwargs: Dict[str, Any] = {
            "messages": llm_messages,
            "system_prompt": system_prompt,
            "max_steps": 30,
        }
        try:
            import inspect
            sig = inspect.signature(self.agent.execute_stream)
            if "model" in sig.parameters and target_model is not None:
                stream_kwargs["model"] = target_model
            if "interrupt_queue" in sig.parameters and self.interrupt_queue is not None:
                stream_kwargs["interrupt_queue"] = self.interrupt_queue
            if "stop_check" in sig.parameters and _check_stop is not None:
                stream_kwargs["stop_check"] = _check_stop
        except Exception:
            if target_model is not None:
                stream_kwargs["model"] = target_model
            if self.interrupt_queue is not None:
                stream_kwargs["interrupt_queue"] = self.interrupt_queue
            if _check_stop is not None:
                stream_kwargs["stop_check"] = _check_stop

        try:
            async for event in self.agent.execute_stream(**stream_kwargs):
                ev_type = event.get("type")

                # Comprobación inmediata de interrupción
                if _check_stop() or ev_type == "interrupted":
                    logger.info("SuperAgentRunner: Interrupción detectada.")
                    while self.interrupt_queue is not None and hasattr(self.interrupt_queue, "empty"):
                        try:
                            if self.interrupt_queue.empty():
                                break
                            self.interrupt_queue.get_nowait()
                        except Exception:
                            break
                    if self.llm_service is not None and hasattr(self.llm_service, "stop_generation_flag"):
                        self.llm_service.stop_generation_flag = False
                    state.stop_requested = True

                    if self.terminal_ui and hasattr(self.terminal_ui, "stop_live"):
                        try:
                            self.terminal_ui.stop_live()
                        except Exception:
                            pass

                    if self.terminal_ui and hasattr(self.terminal_ui, "print_message"):
                        try:
                            self.terminal_ui.print_message("\n⚠️ Generación cancelada por el usuario.", style="yellow")
                        except Exception:
                            pass

                    return {
                        "messages": state.messages,
                        "command_to_confirm": None,
                        "tool_call_id_to_confirm": None,
                    }

                if ev_type == "reasoning":
                    r_text = event.get("text", "")
                    thinking_text += r_text
                    if self.terminal_ui and hasattr(self.terminal_ui, "update_live"):
                        try:
                            from rich.markdown import Markdown
                            from rich.panel import Panel
                            from kogniterm.ui.themes import ColorPalette

                            thinking_panel = Panel(
                                Markdown(thinking_text),
                                title=f"[{ColorPalette.TEXT_DIM}]💭 Pensando...[/{ColorPalette.TEXT_DIM}]",
                                border_style=ColorPalette.TEXT_DIM,
                                style=ColorPalette.TEXT_DIM,
                                padding=(0, 2),
                                expand=True,
                            )
                            self.terminal_ui.update_live(thinking_panel)
                        except Exception:
                            pass

                elif ev_type in ("content", "chunk"):
                    c_text = event.get("text", "")
                    if c_text:
                        if thinking_text and not text_streamed:
                            if self.terminal_ui and hasattr(self.terminal_ui, "stop_live"):
                                try:
                                    self.terminal_ui.stop_live()
                                except Exception:
                                    pass
                        accumulated_chunks.append(c_text)
                        text_streamed = True
                        if self.terminal_ui and hasattr(self.terminal_ui, "print_stream"):
                            try:
                                self.terminal_ui.print_stream(c_text)
                            except Exception:
                                pass

                elif ev_type == "tool_calls_start":
                    tc_list = event.get("tool_calls", [])
                    raw_content = event.get("content", "")
                    parsed_calls = []
                    for tc in tc_list:
                        fn = tc.get("function", {})
                        args_str = fn.get("arguments", "{}")
                        try:
                            fn_args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        except Exception:
                            fn_args = {}
                        parsed_calls.append({
                            "id": tc.get("id", ""),
                            "name": fn.get("name", ""),
                            "args": fn_args,
                        })
                    state.add_message(AIMessage(content=raw_content or "", tool_calls=parsed_calls))

                elif ev_type == "tool_start":
                    t_name = event.get("name", "")
                    t_args = event.get("args", {})
                    t_id = event.get("id") or t_name

                    # Asegurar que el AIMessage con este tool call esté registrado en state.messages
                    has_tc = False
                    if state.messages and isinstance(state.messages[-1], AIMessage):
                        last_tc = getattr(state.messages[-1], "tool_calls", [])
                        if any(tc.get("id") == t_id for tc in last_tc):
                            has_tc = True
                    if not has_tc:
                        state.add_message(AIMessage(
                            content="".join(accumulated_chunks) or "",
                            tool_calls=[{"id": t_id, "name": t_name, "args": t_args}]
                        ))

                    # Almacenar args para uso en tool_result (mostrar diff post-edición)
                    state.last_tool_args = t_args

                    if self.terminal_ui and hasattr(self.terminal_ui, "print_tool_notification"):
                        try:
                            action_desc = format_tool_action_target(t_name, t_args)
                            self.terminal_ui.print_tool_notification(t_name, action_desc)
                        except Exception:
                            pass

                    # Registro inmediato de complete_task si un subagente lo invoca
                    if t_name == "complete_task":
                        task_res = t_args.get("result", "")
                        state.completed = True
                        if hasattr(state, "delegation_context") and state.delegation_context:
                            state.delegation_context.metadata["completed"] = True
                            state.delegation_context.metadata["result"] = task_res

                    # Pausa para confirmación de comandos de terminal (delegado a command_approval_handler en UI)
                    if t_name in ("execute_command", "run_shell"):
                        if not getattr(state, "autonomous_approvals", False):
                            cmd = t_args.get("command", "")
                            state.command_to_confirm = cmd
                            state.tool_call_id_to_confirm = t_id
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
                        if getattr(state, "require_tool_confirmation", False) and not getattr(state, "autonomous_approvals", False):
                            state.tool_pending_confirmation = t_name
                            state.tool_args_pending_confirmation = t_args
                            state.tool_call_id_to_confirm = t_id
                            return {
                                "messages": state.messages,
                                "tool_pending_confirmation": state.tool_pending_confirmation,
                                "tool_args_pending_confirmation": state.tool_args_pending_confirmation,
                                "tool_call_id_to_confirm": state.tool_call_id_to_confirm,
                            }

                elif ev_type == "tool_result":
                    t_name = event.get("name", "")
                    t_res = event.get("result", "")
                    t_id = event.get("id") or t_name

                    # Recuperar args del tool_start almacenados en state
                    t_args = getattr(state, "last_tool_args", {}) or {}

                    # Sincronizar ToolMessage en el historial de state.messages para conservar contexto
                    res_str = json.dumps(t_res, ensure_ascii=False) if isinstance(t_res, (dict, list)) else str(t_res)
                    state.add_message(ToolMessage(content=res_str, tool_call_id=t_id, name=t_name))

                    # Si fue complete_task, marcar estado completado
                    if t_name == "complete_task":
                        state.completed = True
                        if hasattr(state, "delegation_context") and state.delegation_context:
                            state.delegation_context.metadata["completed"] = True
                            if not state.delegation_context.metadata.get("result"):
                                state.delegation_context.metadata["result"] = str(t_res)

                    # Las herramientas no necesitan mostrar toda su salida en pantalla,
                    # solamente la terminal. Para el resto basta el indicador de ejecución.
                    if is_terminal_tool(t_name):
                        if self.terminal_ui and hasattr(self.terminal_ui, "update_tool_display"):
                            try:
                                self.terminal_ui.update_tool_display(t_name, res_str)
                            except Exception:
                                pass
                    else:
                        # Mostrar diff aplicado después de operaciones de edición de archivos
                        self._show_applied_diff_if_any(t_name, t_res, t_args)

                elif ev_type == "done":
                    if self.terminal_ui and hasattr(self.terminal_ui, "stop_live"):
                        try:
                            self.terminal_ui.stop_live()
                        except Exception:
                            pass

                    final_text = event.get("output", "").strip() or "".join(accumulated_chunks).strip()
                    res_val = getattr(state, "delegation_context", None) and state.delegation_context.metadata.get("result")
                    if res_val and not final_text:
                        final_text = str(res_val)

                    if not text_streamed and final_text:
                        if self.terminal_ui and hasattr(self.terminal_ui, "print_stream"):
                            try:
                                self.terminal_ui.print_stream(final_text)
                            except Exception:
                                pass
                        text_streamed = True

                    if self.terminal_ui and hasattr(self.terminal_ui, "console") and not hasattr(self.terminal_ui, "app"):
                        try:
                            self.terminal_ui.console.print()
                        except Exception:
                            pass

                    if final_text:
                        if not (state.messages and isinstance(state.messages[-1], AIMessage) and state.messages[-1].content == final_text):
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
                        "completed": getattr(state, "completed", False),
                        "result": final_text,
                    }

        except Exception as exc:
            logger.error(f"Error en SuperAgentRunner: {exc}", exc_info=True)
            if self.terminal_ui and hasattr(self.terminal_ui, "print_message"):
                self.terminal_ui.print_message(f"❌ Error en SuperAgent: {exc}", style="red")

        return {
            "messages": state.messages,
            "command_to_confirm": getattr(state, "command_to_confirm", None),
            "tool_call_id_to_confirm": getattr(state, "tool_call_id_to_confirm", None),
            "completed": getattr(state, "completed", False),
            "result": getattr(state, "delegation_context", None) and state.delegation_context.metadata.get("result"),
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
