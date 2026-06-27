import json
import logging
import queue
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any, Union, Generator

from langchain_core.messages import AIMessage, ToolMessage
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.text import Text
from rich.padding import Padding

from ..agent_state import AgentState
from ..llm_service import LLMService
from ..exceptions import UserConfirmationRequired
from ..utils.tool_utils import get_tool_action_description

logger = logging.getLogger(__name__)
console = Console()


class ToolExecutor:
    """
    Clase centralizada para la ejecución de herramientas de agentes.
    Consolida la lógica de ejecución síncrona/asíncrona, notificaciones y manejo de confirmaciones.
    """

    @staticmethod
    def execute_single_tool(
        tc: Dict[str, Any],
        llm_service: LLMService,
        terminal_ui: Optional[Any] = None,
        delegation_context: Optional[Any] = None,
    ) -> tuple:
        """Ejecuta una herramienta individual y retorna (tool_id, content, exception)."""
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_id = tc["id"]
        is_tui = getattr(terminal_ui, "is_tui", False)

        if (
            delegation_context
            and hasattr(delegation_context, "blocked_tools")
            and tool_name in delegation_context.blocked_tools
        ):
            role_name = getattr(
                delegation_context.role, "value", str(delegation_context.role)
            )
            logger.warning(
                f"La herramienta '{tool_name}' fue bloqueada para el subagente (rol: {role_name})"
            )
            return (
                tool_id,
                f"Error: La herramienta '{tool_name}' está deshabilitada debido a restricciones del rol ({role_name}).",
                None,
            )

        command_hint = ""
        if isinstance(tool_args, dict):
            command_hint = (
                tool_args.get("command")
                or tool_args.get("path")
                or tool_args.get("file_path")
                or ""
            )

        tool = llm_service.get_tool(tool_name)
        if not tool:
            return tool_id, f"Error: Herramienta '{tool_name}' no encontrada.", None

        action_desc = get_tool_action_description(tool, tool_args)

        # Obtener skill_name
        skill_name = ""
        if hasattr(llm_service, "skill_manager"):
            skill = llm_service.skill_manager.get_skill_for_tool(tool_name)
            if skill:
                skill_name = skill.name

        # Notificación inicial
        if terminal_ui:
            if is_tui:
                terminal_ui.print_tool_notification(
                    tool_name, action_desc, skill_name=skill_name
                )
            else:
                args_json = json.dumps(tool_args, indent=2, ensure_ascii=False)
                console.print(
                    Panel(
                        Syntax(args_json, "json", theme="monokai"),
                        title=f"[bold cyan]🛠️ Ejecutando: {tool_name}[/bold cyan]",
                        border_style="cyan",
                    )
                )

        try:
            full_tool_output = ""
            last_ui_update = 0
            for part in llm_service._invoke_tool_with_interrupt(
                tool, tool_args, delegation_context
            ):
                if part:
                    full_tool_output += str(part)
                    current_time = time.time()
                    # Solo refrescar live UI en CLI; en TUI el render final se gestiona al acabar
                    if (
                        not is_tui
                        and terminal_ui
                        and hasattr(terminal_ui, "update_tool_display")
                        and (current_time - last_ui_update > ui_update_interval)
                    ):
                        terminal_ui.update_tool_display(
                            tool_name, full_tool_output, command=command_hint
                        )
                        last_ui_update = current_time
            # Post-procesamiento (Skills refresh, etc.)
            ToolExecutor._handle_special_tools(tool_name, full_tool_output, llm_service)

            # Renderizado de resultado (CLI)
            if not is_tui:
                ToolExecutor._render_cli_result(tool_name, full_tool_output)

            return tool_id, full_tool_output, None

        except UserConfirmationRequired as e:
            return tool_id, json.dumps(e.raw_tool_output), e
        except InterruptedError:
            return tool_id, f"Interrumpido.", InterruptedError("Interrumpido")
        except Exception as e:
            logger.error(f"Error en {tool_name}: {e}")
            return tool_id, f"Error: {e}", e
        finally:
            # Ocultar y consolidar panel de herramientas si existe
            if terminal_ui and hasattr(terminal_ui, "stop_live"):
                terminal_ui.stop_live()

    @staticmethod
    def _handle_special_tools(tool_name, output, llm_service):
        if tool_name in ["refresh_tools", "skill_factory"] and hasattr(
            llm_service, "skill_manager"
        ):
            llm_service.skill_manager.refresh_skills(force=True)
            # Sincronizar el tool_map para que el agente tenga disponibles
            # las nuevas skills inmediatamente en el mismo ciclo de conversación.
            if hasattr(llm_service, "sync_tools"):
                llm_service.sync_tools()
                logger.info(
                    f"[{tool_name}] tool_map sincronizado tras refresh. Herramientas activas: {list(llm_service.tool_map.keys())}"
                )

    @staticmethod
    def _render_cli_result(tool_name, output):
        display = output[:1000] + ("..." if len(output) > 1000 else "")
        console.print(
            Panel(
                Markdown(display) if "```" in display else Text(display),
                title=f"[bold green]✅ {tool_name}[/bold green]",
                border_style="green",
            )
        )

    @staticmethod
    def execute_tool_node(
        state: AgentState,
        llm_service: LLMService,
        terminal_ui: Optional[Any] = None,
        interrupt_queue: Optional[queue.Queue] = None,
    ):
        """Nodo de ejecución para grafos de agentes."""
        last_message = state.messages[-1]
        if not (isinstance(last_message, AIMessage) and last_message.tool_calls):
            return state

        tool_messages = []
        is_tui = getattr(terminal_ui, "is_tui", False)
        shared_executor = getattr(llm_service, "tool_executor", None)
        managed_executor = None
        executor = shared_executor or ThreadPoolExecutor(max_workers=10)
        if shared_executor is None:
            managed_executor = executor

        # 1. Registrar y Verificar Interrupciones
        try:
            futures = []
            del_ctx = getattr(state, "delegation_context", None)

            for tc in last_message.tool_calls:
                # Detección de bucles (hash de args)
                state.tool_call_history.append(
                    {"name": tc["name"], "args_hash": hash(str(tc["args"]))}
                )

                # Validar permisos RBAC antes de proceder
                if (
                    del_ctx
                    and hasattr(del_ctx, "blocked_tools")
                    and tc["name"] in del_ctx.blocked_tools
                ):
                    role_name = getattr(del_ctx.role, "value", str(del_ctx.role))
                    logger.warning(
                        f"La herramienta '{tc['name']}' fue bloqueada para el subagente (rol: {role_name})"
                    )
                    tool_messages.append(
                        ToolMessage(
                            content=f"Error: La herramienta '{tc['name']}' está deshabilitada debido a restricciones del rol ({role_name}).",
                            tool_call_id=tc["id"],
                        )
                    )
                    continue

                # Caso especial: execute_command (esperar confirmación solo si es el orquestador principal e interactivo)
                is_autonomous = getattr(state, "autonomous_approvals", False) or del_ctx is not None
                if tc["name"] == "execute_command" and not is_autonomous:
                    state.command_to_confirm = tc["args"].get("command")
                    state.tool_call_id_to_confirm = tc["id"]
                    if terminal_ui:
                        skill_name = ""
                        if hasattr(llm_service, "skill_manager"):
                            skill = llm_service.skill_manager.get_skill_for_tool(
                                tc["name"]
                            )
                            if skill:
                                skill_name = skill.name
                        terminal_ui.print_tool_notification(
                            "execute_command",
                            f"Preparando: {state.command_to_confirm}",
                            skill_name=skill_name,
                        )

                    if tool_messages:
                        state.messages.extend(tool_messages)
                    return {
                        "messages": state.messages,
                        "command_to_confirm": state.command_to_confirm,
                    }

                futures.append(
                    executor.submit(
                        ToolExecutor.execute_single_tool,
                        tc,
                        llm_service,
                        terminal_ui,
                        del_ctx,
                    )
                )

            for future in as_completed(futures):
                tid, content, exc = future.result()
                if isinstance(exc, UserConfirmationRequired):
                    if not is_autonomous:
                        state.tool_pending_confirmation = exc.tool_name
                        state.tool_args_pending_confirmation = exc.tool_args
                        state.tool_call_id_to_confirm = tid
                        state.file_update_diff_pending_confirmation = exc.raw_tool_output
                    else:
                        logger.info("Subagente autónomo: omitida la pausa de confirmación de usuario para '%s'.", exc.tool_name)

                if tid and any(
                    tc["id"] == tid and tc["name"] == "complete_task"
                    for tc in last_message.tool_calls
                ):
                    state.completed = True
                    state.result = content

                tool_messages.append(ToolMessage(content=content, tool_call_id=tid))
        finally:
            if managed_executor is not None:
                managed_executor.shutdown(wait=False)

        state.messages.extend(tool_messages)
        if terminal_ui:
            terminal_ui.stop_live()
            # Reactivar spinner si el agente sigue procesando y el LLM aún no responde
            if hasattr(terminal_ui, "resume_spinner"):
                terminal_ui.resume_spinner()
        return state


def should_continue(state: AgentState) -> str:
    from langgraph.graph import END

    if state.completed:
        return END
    if (
        state.critical_loop_detected
        or state.command_to_confirm
        or state.file_update_diff_pending_confirmation
    ):
        return END
    last_message = state.messages[-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "execute_tool"
    return "call_model" if isinstance(last_message, ToolMessage) else END
