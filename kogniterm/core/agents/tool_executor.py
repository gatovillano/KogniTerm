import os
import threading
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
    # Herramientas idempotentes/de solo lectura seguras para ejecución concurrente
    PARALLELIZABLE_TOOLS = {
        "read_file", "view_file", "list_dir", "grep_search", "search_web",
        "read_url_content", "get_file_info", "read_resource", "find_by_name",
        "web_search", "task_tracker", "fetch_url", "inspect_code", "ask_question",
        "read_document", "read_code"
    }

    # Semáforo de concurrencia: limita el número de herramientas que se ejecutan simultáneamente
    # para evitar sobrecarga del sistema (CPU, I/O, red, etc.)
    _concurrency_semaphore = threading.Semaphore(int(os.getenv("KOGNITERM_MAX_CONCURRENT_TOOLS", "32")))

    @staticmethod
    def is_parallel_safe(tool_name: str, is_autonomous: bool = False) -> bool:
        """Determina si una herramienta puede ejecutarse en paralelo de forma segura."""
        if tool_name in ToolExecutor.PARALLELIZABLE_TOOLS:
            return True
        if is_autonomous and tool_name not in {
            "execute_command", "bash", "shell", "run_command", "cmd_execution"
        }:
            return True
        return False

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

        tool = llm_service.get_tool(tool_name) if llm_service and hasattr(llm_service, "get_tool") else None
        cap_def = None
        if not tool:
            from kogniterm.capabilities import default_tool_registry
            cap_def = default_tool_registry.get_tool(tool_name)
            if cap_def:
                tool = cap_def.handler

        if not tool:
            sm = getattr(llm_service, "skill_manager", None)
            if sm and hasattr(sm, "get_skill_instructions"):
                instructions = sm.get_skill_instructions(tool_name)
                if instructions:
                    return tool_id, (
                        f"ℹ️ '{tool_name}' es una SKILL PROCEDIMENTAL (instrucciones en texto Markdown), "
                        f"NO una herramienta ejecutable de código.\n\n"
                        f"### INSTRUCCIONES DE LA SKILL '{tool_name}' ###\n\n{instructions}\n\n"
                        f"Por favor, continúa tu respuesta utilizando estas instrucciones sin intentar volver a ejecutar '{tool_name}' como función."
                    ), None
            return tool_id, f"Error: Herramienta '{tool_name}' no encontrada.", None

        # Obtener descripción específica y dinámica de la acción en curso
        action_desc = get_tool_action_description(tool or cap_def, tool_args, tool_name=tool_name)
        if not action_desc and cap_def:
            action_desc = cap_def.description

        # Obtener skill_name
        skill_name = ""
        if hasattr(llm_service, "skill_manager"):
            skill = llm_service.skill_manager.get_skill_for_tool(tool_name)
            if skill:
                skill_name = skill.name

        # Notificación inicial
        from ..utils.tool_utils import format_tool_action_target
        action_target = format_tool_action_target(tool_name, tool_args)
        if terminal_ui:
            if is_tui:
                terminal_ui.print_tool_notification(
                    tool_name, action_target or action_desc, skill_name=skill_name
                )
            else:
                suffix = f": [bold white]{action_target}[/bold white]" if action_target else ""
                console.print(f"[cyan]🛠️  {tool_name}{suffix}[/cyan]")
        else:
            suffix = f": [bold white]{action_target}[/bold white]" if action_target else ""
            console.print(f"[cyan]🛠️  {tool_name}{suffix}[/cyan]")
        # Adquirir semáforo de concurrencia antes de ejecutar la herramienta
        # para evitar que se ejecuten demasiadas herramientas simultáneamente
        ToolExecutor._concurrency_semaphore.acquire()
        logger.debug(f"Semáforo adquirido para {tool_name}. Disponible: {ToolExecutor._concurrency_semaphore._value}")
        
        try:
            full_tool_output = ""
            last_ui_update = 0
            ui_update_interval = 0.1
            is_terminal_tool = (
                tool_name in {"execute_command", "execute_command_tool", "run_command", "run_command_tool", "bash", "cmd_execution", "python_executor", "python_executor_tool", "shell", "terminal"}
                or any(kw in tool_name.lower() for kw in ["command", "bash", "terminal", "shell", "python_exec"])
            )

            if cap_def:
                import inspect
                import asyncio
                if inspect.iscoroutinefunction(cap_def.handler):
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    if loop.is_running():
                        import nest_asyncio
                        nest_asyncio.apply()
                        res = loop.run_until_complete(cap_def.handler(**tool_args))
                    else:
                        res = loop.run_until_complete(cap_def.handler(**tool_args))
                else:
                    res = cap_def.handler(**tool_args)
            else:
                res = llm_service._invoke_tool_with_interrupt(
                    tool, tool_args, delegation_context
                )
            if isinstance(res, str):
                full_tool_output = res
            elif isinstance(res, (dict, list)):
                full_tool_output = json.dumps(res, ensure_ascii=False)
            elif hasattr(res, "__iter__") and not isinstance(res, (bytes, bytearray)):
                for part in res:
                    if part:
                        full_tool_output += str(part)
                        current_time = time.time()
                        if (
                            not is_tui
                            and terminal_ui
                            and (current_time - last_ui_update > ui_update_interval)
                        ):
                            if is_terminal_tool and hasattr(terminal_ui, "update_terminal_output"):
                                terminal_ui.update_terminal_output(
                                    tool_name, full_tool_output, tool_call_id=tool_id, command=command_hint
                                )
                            elif is_terminal_tool and hasattr(terminal_ui, "update_tool_display"):
                                terminal_ui.update_tool_display(
                                    tool_name, full_tool_output, command=command_hint
                                )
                            last_ui_update = current_time
            else:
                full_tool_output = str(res) if res is not None else ""

            # Emitir actualización final para la UI (solo para herramientas de terminal/comando)
            if is_terminal_tool and hasattr(terminal_ui, "update_terminal_output"):
                terminal_ui.update_terminal_output(
                    tool_name, full_tool_output, tool_call_id=tool_id, command=command_hint
                )
            elif is_terminal_tool and hasattr(terminal_ui, "update_tool_display"):
                terminal_ui.update_tool_display(
                    tool_name, full_tool_output, command=command_hint
                )
            elif terminal_ui:
                # Para herramientas de edición de archivos, mostrar únicamente el diff aplicado
                # Se pasa full_tool_output (normalizado) para extraer el diff del resultado
                ToolExecutor._render_file_edit_diff(
                    terminal_ui, tool_name, tool_args, full_tool_output
                )
            # Post-procesamiento (Skills refresh, etc.)
            full_tool_output = ToolExecutor._handle_special_tools(tool_name, full_tool_output, llm_service)

            # Aplicar truncado inteligente para salidas extensas (preservando errores y guardando log completo)
            from ..utils.output_pruner import smart_prune_tool_output
            full_tool_output = smart_prune_tool_output(full_tool_output, tool_name=tool_name)

            # Renderizado de resultado (CLI, solo para comandos)
            if not is_tui and is_terminal_tool:
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
            # Liberar el semáforo de concurrencia
            ToolExecutor._concurrency_semaphore.release()
            logger.debug(f"Semáforo liberado para {tool_name}. Disponible: {ToolExecutor._concurrency_semaphore._value}")
            
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
            # Si la herramienta es 'skill_factory' y terminó con éxito, añadir al output
            # la lista de herramientas para que el LLM sepa qué puede invocar.
            if tool_name == "skill_factory":
                try:
                    new_tool_names = list(llm_service.skill_manager.tool_registry.keys())
                    logger.info(f"Arsenal actualizado. Herramientas disponibles: {new_tool_names}")
                    output += f"\n\n✅ Arsenal actualizado automáticamente. Herramientas ahora disponibles: {new_tool_names}"
                except Exception as e:
                    logger.warning(f"Error al refrescar skills tras skill_factory: {e}")
        return output

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
    def _render_file_edit_diff(terminal_ui, tool_name: str, tool_args: Dict[str, Any], result: Any) -> None:
        """
        Muestra el diff aplicado en la TUI después de que una herramienta de
        edición de archivos haya sido ejecutada con éxito.

        Busca el diff en el resultado (``applied_diff`` o ``diff``) y lo
        renderiza mediante ``DiffRenderer``.
        """
        file_edit_tools = {
            "advanced_file_editor", "advanced_file_editor_tool",
            "sophisticated_editor_tool", "replace_file_content",
            "file_update_tool", "file_update",
            "file_operations", "file_operations_tool",
            "write_file_tool", "write", "write_file",
            "edit_file", "replace_all_file",
        }

        if tool_name not in file_edit_tools:
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

        # Extraer file_path de distintas convenciones de parámetros
        if not file_path:
            file_path = tool_args.get("path") or tool_args.get("file_path") or tool_args.get("target_file") or tool_args.get("TargetFile") or ""

        if not diff_content or not file_path:
            return

        if hasattr(terminal_ui, "show_applied_diff"):
            terminal_ui.show_applied_diff(
                tool_name=tool_name,
                file_path=file_path,
                diff_content=diff_content,
            )
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

            if hasattr(terminal_ui, "console"):
                terminal_ui.console.print(panel)
            elif hasattr(terminal_ui, "print_message"):
                terminal_ui.print_message(
                    f"### ✅ Cambios aplicados en `{file_path}`\n"
                    f"**Operación:** `{tool_name}`\n\n"
                    f"```diff\n{diff_content}\n```"
                )
            elif hasattr(terminal_ui, "update_live") and hasattr(terminal_ui, "stop_live"):
                terminal_ui.update_live(panel)
                terminal_ui.stop_live()
        except Exception as e:
            logger.warning(f"No se pudo renderizar diff post-edición: {e}")

    @staticmethod
    def execute_tool_node(
        state: AgentState,
        llm_service: LLMService,
        terminal_ui: Optional[Any] = None,
        interrupt_queue: Optional[queue.Queue] = None,
        delegation_context: Optional[Any] = None,
        force_parallel: bool = False,
    ):
        """Nodo de ejecución optimizado con procesamiento concurrente para herramientas de agentes."""
        last_message = state.messages[-1]
        if not (isinstance(last_message, AIMessage) and last_message.tool_calls):
            return state

        tool_messages = []
        is_tui = getattr(terminal_ui, "is_tui", False)

        del_ctx = delegation_context or getattr(state, "delegation_context", None)
        is_autonomous = getattr(state, "autonomous_approvals", False) or del_ctx is not None

        # 1. Validación previa de RBAC e historial
        valid_tool_calls = []
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
            valid_tool_calls.append(tc)

        # 2. Agrupación en lotes concurrentes vs secuenciales
        batches: List[tuple[str, List[Dict[str, Any]]]] = []
        current_batch: List[Dict[str, Any]] = []
        current_mode: Optional[str] = None

        for tc in valid_tool_calls:
            # Caso interactivo: execute_command no autónomo requiere confirmación
            if tc["name"] == "execute_command" and not is_autonomous:
                if current_batch:
                    batches.append((current_mode, current_batch))
                    current_batch = []
                    current_mode = None
                batches.append(("interactive_command", [tc]))
                continue

            can_parallel = force_parallel or ToolExecutor.is_parallel_safe(tc["name"], is_autonomous=is_autonomous)
            mode = "parallel" if can_parallel else "sequential"

            if current_mode is None:
                current_mode = mode
                current_batch.append(tc)
            elif current_mode == mode and mode == "parallel":
                current_batch.append(tc)
            else:
                batches.append((current_mode, current_batch))
                current_batch = [tc]
                current_mode = mode

        if current_batch:
            batches.append((current_mode, current_batch))

        # 3. Ejecutar los lotes en orden
        for mode, batch in batches:
            if mode == "interactive_command":
                tc = batch[0]
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

            if mode == "parallel" and len(batch) > 1:
                # Ejecución concurrente usando ThreadPoolExecutor
                max_w = min(len(batch), 16)
                res_map: Dict[str, tuple] = {}
                with ThreadPoolExecutor(max_workers=max_w) as executor:
                    futures = {
                        executor.submit(
                            ToolExecutor.execute_single_tool,
                            tc,
                            llm_service,
                            terminal_ui,
                            del_ctx,
                        ): tc
                        for tc in batch
                    }
                    for fut in as_completed(futures):
                        tc = futures[fut]
                        try:
                            res_map[tc["id"]] = fut.result()
                        except Exception as exc:
                            res_map[tc["id"]] = (tc["id"], f"Error: {exc}", exc)

                # Mantener orden determinista idéntico a las llamadas originales
                for tc in batch:
                    tid, content, exc = res_map.get(tc["id"], (tc["id"], "", None))
                    if isinstance(exc, UserConfirmationRequired):
                        if not is_autonomous:
                            state.add_pending_confirmation(
                                tool_name=exc.tool_name,
                                tool_args=exc.tool_args,
                                tool_call_id=tid,
                                raw_tool_output=exc.raw_tool_output,
                            )
                        else:
                            logger.info("Subagente autónomo: omitida la pausa de confirmación de usuario para '%s'.", exc.tool_name)

                    if tid and tc["name"] == "complete_task":
                        state.completed = True
                        state.result = content

                    tool_messages.append(ToolMessage(content=content, tool_call_id=tid))
            else:
                # Ejecución secuencial (o batch paralelo de 1 elemento)
                for tc in batch:
                    tid, content, exc = ToolExecutor.execute_single_tool(
                        tc,
                        llm_service,
                        terminal_ui,
                        del_ctx,
                    )

                    if isinstance(exc, UserConfirmationRequired):
                        if not is_autonomous:
                            state.add_pending_confirmation(
                                tool_name=exc.tool_name,
                                tool_args=exc.tool_args,
                                tool_call_id=tid,
                                raw_tool_output=exc.raw_tool_output,
                            )
                        else:
                            logger.info("Subagente autónomo: omitida la pausa de confirmación de usuario para '%s'.", exc.tool_name)

                    if tid and tc["name"] == "complete_task":
                        state.completed = True
                        state.result = content

                    tool_messages.append(ToolMessage(content=content, tool_call_id=tid))

        state.messages.extend(tool_messages)
        if terminal_ui:
            terminal_ui.stop_live()
            # Reactivar spinner si el agente sigue procesando y el LLM aún no responde
            if hasattr(terminal_ui, "resume_spinner"):
                terminal_ui.resume_spinner()
        return state

    @staticmethod
    def execute_tools_parallel(
        state: AgentState,
        llm_service: LLMService,
        terminal_ui: Optional[Any] = None,
        delegation_context: Optional[Any] = None,
        interrupt_queue: Optional[queue.Queue] = None,
    ):
        """
        Ejecución paralela de herramientas para subagentes o nodos autónomos (ej. DeepResearcher).
        """
        return ToolExecutor.execute_tool_node(
            state=state,
            llm_service=llm_service,
            terminal_ui=terminal_ui,
            interrupt_queue=interrupt_queue,
            delegation_context=delegation_context,
            force_parallel=True,
        )



    @staticmethod
    async def execute_single_tool_async(tc, llm_service, terminal_ui, interrupt_queue):
        """
        Versión asíncrona de execute_single_tool.
        Ejecuta la herramienta en un thread separado para no bloquear el event loop.
        """
        tool_name = tc['name']
        tool_args = tc['args']
        tool_id = tc['id']

        tool = llm_service.get_tool(tool_name)
        if not tool:
            return tool_id, f"Error: Herramienta '{tool_name}' no encontrada.", None

        try:
            from ..async_io_manager import get_io_manager

            io_manager = get_io_manager()

            # Función síncrona que se ejecutará en el executor
            def run_tool_sync():
                full_tool_output = ""
                tool_output_generator = llm_service._invoke_tool_with_interrupt(tool, tool_args)
                for chunk in tool_output_generator:
                    full_tool_output += str(chunk)
                return full_tool_output

            # Ejecutar de forma asíncrona
            result = io_manager.run_in_executor(run_tool_sync)

            if result.success:
                processed_tool_output = ToolExecutor._handle_special_tools(
                    tool_name, result.result, llm_service
                )
                return tool_id, processed_tool_output, None
            else:
                return tool_id, f"Error al ejecutar la herramienta {tool_name}: {result.error}", Exception(result.error)

        except UserConfirmationRequired as e:
            return tool_id, json.dumps(e.raw_tool_output), e
        except InterruptedError:
            return tool_id, f"Ejecución de herramienta '{tool_name}' interrumpida por el usuario.", InterruptedError("Interrumpido por el usuario.")
        except Exception as e:
            return tool_id, f"Error al ejecutar la herramienta {tool_name}: {e}", e


def should_continue(state: AgentState) -> str:
    from langgraph.graph import END

    if state.completed:
        return END
    if (
        state.critical_loop_detected
        or state.command_to_confirm is not None
        or state.has_pending_confirmations()
    ):
        return END
    last_message = state.messages[-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "execute_tool"
    if isinstance(last_message, ToolMessage):
        return "call_model"

    is_autonomous = getattr(state, "autonomous_approvals", False) or getattr(state, "delegation_context", None) is not None
    if is_autonomous and not state.completed:
        logger.info("should_continue: Subagente autónomo emitió texto intermedio sin completarse. Continuando flujo call_model.")
        return "call_model"

    return END
