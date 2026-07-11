"""
Skill: call_agents_parallel
Herramienta para invocar múltiples agentes especializados en paralelo.

Soporta N agentes simultáneos con visualización en pestañas en la TUI.
Cada agente puede ser de tipo predefinido (code_agent, researcher_agent)
o dinámico con un system_prompt personalizado.
"""

import os
import logging
import threading
import asyncio
import concurrent.futures
import time
import uuid
from typing import Any, List, Dict, Optional

from kogniterm.core.delegation.agent_pool import AgentPool

from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()

# Límite de recursión configurable
AGENT_RECURSION_LIMIT = int(os.getenv("RESEARCHER_RECURSION_LIMIT", "1000"))

AUTONOMY_DIALOG_TEXT = "Los agentes operarán de forma autónoma y no solicitarán autorización para aplicar cambios."

# ─── Proxy de UI por panel ────────────────────────────────────────────────────


class ParallelPanelUI:
    """
    Wrapper de terminal_ui que redirige todo el output de un agente al
    ChatLogWidget de su pestaña asignada en el TabbedContent.

    Soporta tanto modo TUI local (Textual directo) como modo servidor (WS).
    """

    def __init__(self, original_ui: Any, panel_id: str):
        self.original_ui = original_ui
        self.panel_id = panel_id
        self.console = getattr(original_ui, "console", console)
        self.is_tui = bool(getattr(original_ui, "is_tui", False))
        self.interrupt_queue = getattr(original_ui, "interrupt_queue", None)
        self.app = getattr(original_ui, "app", original_ui)
        self._accumulated_text = ""

    @property
    def _is_server_mode(self) -> bool:
        """True cuando original_ui es un ServerUI (modo WS), no una TUI Textual."""
        return hasattr(self.original_ui, "_push") and not hasattr(
            self.original_ui, "query_one"
        )

    def _get_panel(self):
        """Retorna el ChatLogWidget de esta pestaña (modo TUI local)."""
        return _get_agent_chat_log(self.app, self.panel_id)

    def _schedule(self, fn, *args, **kwargs):
        """Llama a fn desde cualquier hilo de forma segura."""
        if threading.current_thread() is threading.main_thread():
            fn(*args, **kwargs)
        else:
            try:
                self.app.call_from_thread(fn, *args, **kwargs)
            except Exception as e:
                logger.debug("ParallelPanelUI._schedule: %s", e)

    # ── Métodos de streaming ──────────────────────────────────────────────────

    def print_stream(self, text: str, **kwargs):
        if not text:
            return
        self._accumulated_text += text
        if self._is_server_mode:
            self.original_ui._push("stream", text, agent_id=self.panel_id)
            return
        panel = self._get_panel()
        if panel and hasattr(panel, "write_stream"):
            self._schedule(panel.write_stream, text)

    def write_stream_to_chat(self, content: str, **kwargs):
        self.print_stream(content, **kwargs)

    def update_live(self, renderable, **kwargs):
        if self._is_server_mode:
            if isinstance(renderable, str):
                self.original_ui._push(
                    "live_update",
                    {"thinking": "", "response": renderable},
                    agent_id=self.panel_id,
                )
            return
        panel = self._get_panel()
        if panel is None:
            return

        def _do():
            if hasattr(panel, "write_stream"):
                panel.write_stream(renderable)
            elif hasattr(panel, "update"):
                panel.update(renderable)
            if hasattr(panel, "scroll_end"):
                panel.scroll_end(animate=False)

        self._schedule(_do)

    def stop_live(self, **kwargs):
        if self._is_server_mode:
            self.original_ui._push("live_stop", {}, agent_id=self.panel_id)
            return
        panel = self._get_panel()
        if panel and hasattr(panel, "stop_stream"):
            self._schedule(panel.stop_stream)
        self._accumulated_text = ""

    def print_message(
        self,
        message: str,
        style: str = "",
        is_user_message: bool = False,
        status: str = None,
        use_bubble: bool = False,
        **kwargs,
    ):
        if self._is_server_mode:
            self.original_ui._push("message", {"text": message}, agent_id=self.panel_id)
            return
        panel = self._get_panel()
        if panel and hasattr(panel, "write_agent_message"):
            self._schedule(panel.write_agent_message, message)

    def print_tool_notification(
        self, tool_name: str, action_desc: str = "", skill_name: str = "", **kwargs
    ):
        if self._is_server_mode:
            self.original_ui._push(
                "tool_call",
                {"name": tool_name, "description": action_desc, "skill": skill_name},
                agent_id=self.panel_id,
            )
            return
        panel = self._get_panel()
        if panel and hasattr(panel, "write_tool_notification"):
            self._schedule(
                panel.write_tool_notification, tool_name, action_desc, skill_name
            )

    def update_terminal_output(
        self, tool_name: str, output: str, command: str = "", **kwargs
    ):
        if not output:
            return
        if self._is_server_mode:
            msg = f"\n**$ {command or tool_name}**\n```\n{output}\n```"
            self._accumulated_text += msg
            self.original_ui._push(
                "live_update",
                {"thinking": "", "response": self._accumulated_text},
                agent_id=self.panel_id,
            )
            return
        panel = self._get_panel()
        if panel and hasattr(panel, "write_stream"):
            chunk = ("__TERMINAL__", tool_name, output, command or tool_name)
            self._schedule(panel.write_stream, chunk)

    def update_tool_display(
        self, tool_name: str, output: str, command: str = "", **kwargs
    ):
        self.update_terminal_output(tool_name, output, command, **kwargs)

    def print_success_box(self, message: str, title: str = "Éxito", **kwargs):
        self.print_message(f"✅ **{title}**: {message}", **kwargs)

    def print_error_box(self, message: str, title: str = "Error", **kwargs):
        self.print_message(f"❌ **{title}**: {message}", **kwargs)

    def print_warning_box(self, message: str, title: str = "Advertencia", **kwargs):
        self.print_message(f"⚠️ **{title}**: {message}", **kwargs)

    def update_task_tracker(self, *args, **kwargs):
        if self.original_ui and hasattr(self.original_ui, "update_task_tracker"):
            self.original_ui.update_task_tracker(*args, **kwargs)

    # ── Delegación genérica ───────────────────────────────────────────────────

    def ask_approval_sync(
        self, message: str, title: str = "Aprobación Requerida", **kwargs
    ) -> bool:
        if self.original_ui:
            method = getattr(self.original_ui, "ask_approval_sync", None)
            if method:
                return method(message=message, title=title, **kwargs)
        return True

    def ask_deep_agent_autonomy_sync(self, agent_label: str) -> bool:
        if self.original_ui:
            method = getattr(self.original_ui, "ask_deep_agent_autonomy_sync", None)
            if method:
                return method(agent_label)
        return True

    def get_interrupt_queue(self):
        if self.original_ui:
            method = getattr(self.original_ui, "get_interrupt_queue", None)
            if method:
                return method()
        return self.interrupt_queue

    def put(self, message):
        if self.original_ui and hasattr(self.original_ui, "put"):
            return self.original_ui.put(message)

    def put_nowait(self, message):
        if self.original_ui and hasattr(self.original_ui, "put_nowait"):
            return self.original_ui.put_nowait(message)

    def __getattr__(self, name):
        if self.original_ui is not None:
            return getattr(self.original_ui, name)
        return lambda *a, **kw: None


# ─── Funciones auxiliares ─────────────────────────────────────────────────────


def _get_agent_chat_log(app: Any, pid: str):
    """Busca el ChatLogWidget correspondiente a pid, tolerando prefijo live_display_."""
    try:
        from kogniterm.terminal.tui.components.chat_log import ChatLogWidget

        if hasattr(app, "query_one"):
            try:
                return app.query_one(f"#{pid}", ChatLogWidget)
            except Exception:
                return app.query_one(f"#live_display_{pid}", ChatLogWidget)
    except Exception:
        pass
    return None


def _request_autonomous_execution(agent_label: str, terminal_ui: Any = None) -> bool:
    """Solicita consentimiento antes de iniciar un agente en modo autónomo."""
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


def _is_server_mode(terminal_ui: Any) -> bool:
    return hasattr(terminal_ui, "_push") and not hasattr(terminal_ui, "query_one")


# ─── Motor de creación de agente por tipo ────────────────────────────────────


def _build_agent_graph(
    agent_type: str,
    system_prompt: Optional[str],
    llm_service: Any,
    agent_ui: Any,
    interrupt_queue: Any,
):
    """Instancia el grafo LangGraph correcto según el tipo de agente solicitado."""
    if agent_type == "code_agent":
        from kogniterm.core.agents.deep_coder import create_deep_coder

        return create_deep_coder(llm_service, agent_ui, interrupt_queue)

    if agent_type == "researcher_agent":
        from kogniterm.core.agents.deep_researcher import create_deep_researcher

        return create_deep_researcher(llm_service, agent_ui, interrupt_queue)

    # Agente dinámico con prompt personalizado
    from kogniterm.core.agents.dynamic_agent import create_dynamic_agent

    prompt = system_prompt or (
        f"Eres un agente especializado experto en '{agent_type}'. "
        "Realiza la tarea asignada de forma totalmente autónoma, exhaustiva y precisa. "
        "Tu único interlocutor es el Orquestador Principal. Entrega siempre tus hallazgos completos y detallados."
    )
    return create_dynamic_agent(llm_service, prompt, agent_ui, interrupt_queue)


# ─── Función principal ────────────────────────────────────────────────────────


def call_agents_parallel(
    agents: List[Dict[str, str]],
    llm_service: Any = None,
    terminal_ui: Any = None,
    interrupt_queue: Any = None,
    approval_handler: Any = None,
) -> str:
    """
    Invoca múltiples agentes especializados en paralelo.

    Cada elemento de `agents` es un dict con:
        - name  (str): Nombre descriptivo del agente (ej. "Investigador")
        - task  (str): Tarea asignada
        - type  (str, opcional): "code_agent" | "researcher_agent" | cualquier rol dinámico.
                                  Por defecto "researcher_agent".
        - system_prompt (str, opcional): Prompt del sistema para agentes dinámicos.

    Args:
        agents: Lista de especificaciones de agentes.
        llm_service: Servicio LLM compartido.
        terminal_ui: Interfaz de terminal / TUI.
        interrupt_queue: Cola de interrupciones.
        approval_handler: Manejador de aprobaciones.

    Returns:
        str: XML con los resultados de cada agente.
    """
    import queue as _queue
    from langchain_core.messages import HumanMessage as _HumanMessage

    if not agents:
        return "Error: No se especificaron agentes para ejecutar."

    # ── Registrar herramienta de finalización complete_task ──────────────────
    from langchain_core.tools import tool
    from typing import Optional, Any

    class AgentTaskCompleted(BaseException):
        """Excepción para detener inmediatamente el grafo del agente al completar su tarea."""
        def __init__(self, result: str):
            self.result = result

    @tool
    def complete_task(result: str, delegation_context: Optional[Any] = None) -> str:
        """
        Entrega el resultado final de la tarea asignada y finaliza el proceso de este agente.
        Úsala de forma obligatoria cuando hayas completado el objetivo asignado.
        El argumento 'result' debe contener el reporte o código final detallado de tu trabajo.
        """
        if delegation_context is not None:
            delegation_context.metadata["result"] = result
            delegation_context.metadata["completed"] = True
            logger.info(
                "complete_task: Resultado registrado para subagente %s",
                delegation_context.agent_id,
            )
        else:
            logger.warning("complete_task: Invocado sin delegation_context")
        
        # Levantar excepción BaseException para terminar inmediatamente el ciclo del LLM y no ser atrapada por ToolNode
        raise AgentTaskCompleted(result)

    if llm_service is not None and "complete_task" not in llm_service.tool_map:
        llm_service.register_tool(complete_task)
        llm_service.sync_tools()

    # ── Resolver terminal_ui / interrupt_queue ────────────────────────────────
    if terminal_ui is None and llm_service is not None:
        terminal_ui = getattr(llm_service, "terminal_ui", None)
    if interrupt_queue is None and llm_service is not None:
        interrupt_queue = getattr(llm_service, "interrupt_queue", None)
    if interrupt_queue is None:
        interrupt_queue = _queue.Queue()

    server_mode = _is_server_mode(terminal_ui)
    is_tui_local = (not server_mode) and bool(getattr(terminal_ui, "is_tui", False))
    target_app = _resolve_tui_app(terminal_ui) if is_tui_local else None

    logger.info(
        "call_agents_parallel: %d agentes | server_mode=%s | tui_local=%s",
        len(agents),
        server_mode,
        is_tui_local,
    )

    # ── Solicitar consentimiento ──────────────────────────────────────────────
    authorized = []
    for spec in agents:
        label = spec.get("name", spec.get("type", "Agente"))
        if _request_autonomous_execution(label, terminal_ui):
            authorized.append(spec)
        else:
            logger.info("call_agents_parallel: %s cancelado por el usuario.", label)

    if not authorized:
        return "Ejecución paralela cancelada por el usuario."

    # ── Construir panel_id determinista y único por agente ────────────────────
    import uuid
    run_hash = uuid.uuid4().hex[:6]
    def _panel_id(spec: Dict, index: int) -> str:
        slug = spec.get("name", f"agent_{index}").lower()
        slug = "".join(c if c.isalnum() else "_" for c in slug)[:15]
        return f"agent_panel_{slug}_{run_hash}_{index}"

    panel_ids = [_panel_id(spec, i) for i, spec in enumerate(authorized)]

    # ── Activar contenedor de pestañas en la TUI ─────────────────────────────
    _activate_parallel_container(
        authorized, panel_ids, terminal_ui, server_mode, is_tui_local, target_app
    )

    # ── Crear proxy de UI para cada agente ───────────────────────────────────
    agent_uis = [ParallelPanelUI(terminal_ui, pid) for pid in panel_ids]

    # ── Función de ejecución de un agente (Asíncrona) ────────────────────────
    async def run_agent_async(spec: Dict, agent_ui: ParallelPanelUI, panel_id: str) -> str:
        import time
        t0 = time.time()
        delegation_status = "success"
        delegation_result = ""

        name = spec.get("name", "Agente")
        task = spec.get("task", "")
        agent_type = spec.get("type") or spec.get("name", "dynamic_agent")
        system_prompt = spec.get("system_prompt")

        import uuid
        from kogniterm.core.delegation import AgentRole

        # --- Resolver la configuración del agente declarativamente ---
        from kogniterm.core.agents.config_manager import AgentConfigManager
        config_mgr = AgentConfigManager(workspace_dir=getattr(llm_service, "current_workspace_dir", None))
        config_mgr.discover_configs()
        agent_config = config_mgr.get_agent_config(agent_type) or config_mgr.get_agent_config(name)
        
        role = AgentRole.LEAF
        allowed_tools = spec.get("allowed_tools")
        if agent_config:
            role_str = agent_config.get("role", "leaf").lower()
            role = AgentRole.ORCHESTRATOR if role_str == "orchestrator" else AgentRole.LEAF
            if not system_prompt:
                system_prompt = agent_config.get("system_prompt")
            if allowed_tools is None:
                allowed_tools = agent_config.get("allowed_tools")

        # Calcular conjunto de herramientas bloqueadas personalizadas si se define allowed_tools
        blocked_tools_set = None
        if allowed_tools is not None and llm_service:
            all_tools = set(llm_service.tool_map.keys()) if hasattr(llm_service, "tool_map") else set()
            from kogniterm.core.delegation.agent_roles import DEFAULT_BLOCKED_TOOLS
            mandatory_blocked = DEFAULT_BLOCKED_TOOLS.get(role, frozenset())
            # Bloquear todas las que no estén permitidas, más las obligatorias por seguridad
            blocked_tools_set = frozenset(
                (all_tools - set(allowed_tools)) | mandatory_blocked
            )

        child_ctx = None
        child_id = f"child_{name}_{uuid.uuid4().hex[:8]}"
        parent_id = "parallel_orchestrator"

        # Registrar subagente en el manager de delegación
        if (
            llm_service
            and hasattr(llm_service, "delegation_manager")
            and llm_service.delegation_manager
        ):
            try:
                child_ctx = llm_service.delegation_manager.register_agent(
                    agent_id=child_id,
                    parent_id=parent_id,
                    role=role,
                    blocked_tools=blocked_tools_set
                )
                if (
                    hasattr(llm_service, "heartbeat_monitor")
                    and llm_service.heartbeat_monitor
                ):
                    llm_service.heartbeat_monitor.update_heartbeat(
                        child_id, threshold=300.0
                    )
            except Exception as e:
                logger.error(
                    "run_agent[%s]: No se pudo registrar delegación: %s", name, e
                )

        try:
            from kogniterm.core.agent_state import AgentState

            task_message = (
                f"{task}\n\n"
                "---\n"
                "⚠️ **REGLAS CRÍTICAS DE SUB-AGENTE AUTÓNOMO** ⚠️\n"
                "1. **NO INTERACTÚAS CON EL USUARIO**: Tu único receptor es el Orquestador Principal. NUNCA hagas preguntas al usuario ni le ofrezcas guardar archivos 'si lo desea'. Toma decisiones y ejecuta todas las herramientas necesarias de forma autónoma.\n"
                "2. **task_tracker**: Tu PRIMERA acción DEBE ser inicializar `task_tracker(action='init', agent_name='{name}', plan=[...])` y actualizar su estado.\n"
                "3. 🏁 **FINALIZACIÓN COMPLETA CON `complete_task`**: Cuando completes la tarea, DEBES invocar la herramienta `complete_task(result=...)`.\n"
                "   **REGLA DE ENTREGABLE**: El argumento `result` DEBE contener el INFORME TÉCNICO COMPLETO, EXHAUSTIVO Y DETALLADO de tu trabajo (código completo, hallazgos, análisis de archivos, etc.). NUNCA envíes frases breves, ni digas 'el informe ya fue entregado', ni omitas información."
            )

            # Inyectar instrucciones de complete_task en el prompt del sistema si existe
            if system_prompt:
                system_prompt = (
                    f"{system_prompt}\n\n"
                    "🏁 **IMPORTANTE**: Eres un subagente autónomo. Entrega SIEMPRE tu informe técnico completo y detallado dentro del parámetro `result` de la herramienta `complete_task`."
                )

            agent_graph = _build_agent_graph(
                agent_type, system_prompt, llm_service, agent_ui, interrupt_queue
            )
            initial_state = AgentState(
                messages=[_HumanMessage(content=task_message)],
                autonomous_approvals=True,
            )
            if child_ctx:
                initial_state.delegation_context = child_ctx

            # Configurar el contexto local para que llm_service.invoke() lo conozca en este hilo
            old_ctx = getattr(llm_service, "current_delegation_context", None)
            if child_ctx:
                llm_service.current_delegation_context = child_ctx

            try:
                final_state = await agent_graph.ainvoke(
                    initial_state,
                    config={"recursion_limit": AGENT_RECURSION_LIMIT},
                )
            except AgentTaskCompleted as task_exc:
                result = task_exc.result
                delegation_result = result
                logger.info("run_agent[%s]: Finalizado exitosamente vía AgentTaskCompleted exception.", name)
                status_emoji = "✅"
                if child_ctx:
                    child_ctx.metadata["completed"] = True
                    child_ctx.metadata["result"] = result
                
                # Actualizar el título de la pestaña con el estado
                if agent_ui and hasattr(agent_ui, "update_agent_tab_title"):
                    try:
                        agent_ui.update_agent_tab_title(panel_id, f"{name} {status_emoji}")
                    except Exception as ex:
                        pass
                return result
            finally:
                if child_ctx:
                    llm_service.current_delegation_context = old_ctx

            if final_state.get("completed"):
                result = final_state.get("result", "Sin respuesta")
                logger.info(
                    "run_agent[%s]: Finalizado exitosamente vía completed flag.", name
                )
                status_emoji = "✅"
            elif child_ctx and child_ctx.metadata.get("completed"):
                result = child_ctx.metadata.get("result", "Sin respuesta")
                logger.info(
                    "run_agent[%s]: Finalizado exitosamente vía complete_task.", name
                )
                status_emoji = "✅"
            else:
                msgs = final_state.get("messages", [])
                result = "Sin respuesta"
                if msgs:
                    # Buscar el último AIMessage con contenido sustancial (ignorando placeholders de streaming)
                    for m in reversed(msgs):
                        content_str = str(getattr(m, "content", "") or "").strip()
                        if content_str and content_str != "Ejecutando herramientas..." and not content_str.startswith("Proceso finalizado") and len(content_str) > 5:
                            result = content_str
                            break
                    if result == "Sin respuesta":
                        result = str(msgs[-1].content) if msgs[-1].content else "Sin respuesta"
                logger.info(
                    "run_agent[%s]: Finalizado (sin llamar a complete_task).", name
                )
                status_emoji = "🏁"

            # Actualizar el título de la pestaña con el estado
            if agent_ui and hasattr(agent_ui, "update_agent_tab_title"):
                try:
                    agent_ui.update_agent_tab_title(panel_id, f"{name} {status_emoji}")
                except Exception as ex:
                    logger.warning(
                        "No se pudo actualizar el título de la pestaña para %s: %s",
                        name,
                        ex,
                    )

            delegation_result = result
            return result

        except Exception as e:
            logger.exception("run_agent[%s]: error: %s", name, e)
            delegation_status = "failed"
            delegation_result = str(e)
            # Actualizar el título de la pestaña con error
            if agent_ui and hasattr(agent_ui, "update_agent_tab_title"):
                try:
                    agent_ui.update_agent_tab_title(panel_id, f"{name} ❌")
                except Exception:
                    pass
            return f"Error en {name}: {e}"
        finally:
            if llm_service and hasattr(llm_service, "telemetry_tracker") and llm_service.telemetry_tracker:
                duration = time.time() - t0
                summary = delegation_result[:200] + "..." if len(delegation_result) > 200 else delegation_result
                llm_service.telemetry_tracker.record_delegation(
                    subagent_id=child_id,
                    subagent_name=name,
                    task=task,
                    depth=getattr(child_ctx, "depth", 1) if child_ctx else 1,
                    status=delegation_status,
                    duration=duration,
                    summary=summary
                )

    # ── Lanzar agentes en paralelo y esperar a que finalicen ──────────────────
    
    async def _run_single_agent(spec, agent_ui, pid):
        name = spec.get("name", "Agente")
        try:
            res = await run_agent_async(spec, agent_ui, pid)
        except Exception as e:
            logger.exception("Excepción en tarea asíncrona de %s: %s", name, e)
            res = f"Error crítico en {name}: {e}"
        
        # Notificar al usuario visualmente en la TUI
        if terminal_ui:
            terminal_ui.print_message(f"🏁 **Agente ({name}) completó su tarea:**\n{res}")
            
        return name, res

    async def _run_all_parallel():
        pool = AgentPool(max_concurrent=len(authorized))

        # Wrap cada agente como un grafo compatible con AgentPool
        class _AgentGraphWrapper:
            """Adapta la función run_agent_async al interface ainvoke esperado por AgentPool.
            Retorna la tupla (name, res) para mantener compatibilidad con el resultado downstream.
            """
            def __init__(self, spec, agent_ui, pid):
                self._spec = spec
                self._agent_ui = agent_ui
                self._pid = pid
                self._name = spec.get("name", "Agente")

            async def ainvoke(self, state, config=None):
                res = await run_agent_async(self._spec, self._agent_ui, self._pid)
                if terminal_ui:
                    terminal_ui.print_message(f"🏁 **Agente ({self._name}) completó su tarea:**\n{res}")
                return self._name, res

        agents_specs = [
            {
                "id": spec.get("name", f"agent_{i}"),
                "graph": _AgentGraphWrapper(spec, agent_ui, pid),
                "initial_state": {},
                "recursion_limit": 1000,
            }
            for i, (spec, agent_ui, pid) in enumerate(zip(authorized, agent_uis, panel_ids))
        ]


        results = await pool.execute_parallel(agents_specs)

        # Consolidar: mostrar resumen y desactivar paneles al finalizar todos
        try:
            _deactivate_parallel_container(
                panel_ids, terminal_ui, server_mode, is_tui_local, target_app
            )
            if terminal_ui:
                terminal_ui.print_message("🏁 **Todas las misiones paralelas han finalizado**")
        except Exception as e:
            logger.exception("Error al desactivar el contenedor de agentes: %s", e)

        return results

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            results = loop.run_until_complete(_run_all_parallel())
        else:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                results = new_loop.run_until_complete(_run_all_parallel())
            finally:
                new_loop.close()

    except Exception as e:
        logger.exception("Error general al ejecutar agentes paralelos: %s", e)
        return f"Error al ejecutar agentes paralelos: {e}"

    # Construir informe XML estructurado para el agente orquestador (BashAgent)
    output_blocks = ["<parallel_agents_results>"]
    for item in results:
        if isinstance(item, Exception):
            output_blocks.append(f"  <agent name='Desconocido' status='error'>{item}</agent>")
        else:
            name, res = item
            output_blocks.append(f"  <agent name='{name}'>\n{res}\n  </agent>")
    output_blocks.append("</parallel_agents_results>")
    
    return "\n".join(output_blocks)


# ─── Gestión de paneles TUI ───────────────────────────────────────────────────


def _activate_parallel_container(
    agents: List[Dict],
    panel_ids: List[str],
    terminal_ui: Any,
    server_mode: bool,
    is_tui_local: bool,
    target_app: Any,
):
    """Muestra el TabbedContent y crea una pestaña por agente."""
    if server_mode:
        for spec, pid in zip(agents, panel_ids):
            try:
                terminal_ui.show_agent_panel(pid, spec.get("name", pid))
            except Exception as e:
                logger.warning("show_agent_panel(%s): %s", pid, e)
        return

    if not (is_tui_local and target_app):
        return

    def _do():
        try:
            # Usar método de alto nivel si está disponible
            if hasattr(target_app, "activate_parallel_container"):
                target_app.activate_parallel_container()
            else:
                try:
                    target_app.query_one("#bottom_container").display = True
                except Exception:
                    pass
                try:
                    target_app.query_one("#parallel_agents_container").display = True
                except Exception:
                    pass

            # Crear una pestaña por agente diferenciando nombres duplicados
            name_counts = {}
            for s in agents:
                n = s.get("name", "Agente")
                name_counts[n] = name_counts.get(n, 0) + 1

            name_seen = {}
            for spec, pid in zip(agents, panel_ids):
                raw_name = spec.get("name", pid)
                if name_counts.get(raw_name, 0) > 1:
                    name_seen[raw_name] = name_seen.get(raw_name, 0) + 1
                    tab_title = f"{raw_name} #{name_seen[raw_name]}"
                else:
                    tab_title = raw_name

                try:
                    target_app.add_agent_tab(pid, tab_title)
                except Exception as e:
                    logger.warning("add_agent_tab(%s): %s", pid, e)

            target_app.refresh(layout=True)

            # Escribir mensajes de bienvenida en cada panel
            for spec, pid in zip(agents, panel_ids):
                try:
                    panel = _get_agent_chat_log(target_app, pid)
                    if panel is not None:
                        name = spec.get("name", pid)
                        agent_type = spec.get("type", "researcher_agent")
                        emoji = "🧪" if "research" in agent_type else "💻"
                        panel.write_stream(f"{emoji} **{name}** iniciando...")
                except Exception:
                    pass

        except Exception as e:
            logger.warning("_activate_parallel_container._do: %s", e)

    if threading.current_thread() is threading.main_thread():
        _do()
    else:
        target_app.call_from_thread(_do)

    # Pequeña pausa para estabilizar UI
    time.sleep(0.1)


def _deactivate_parallel_container(
    panel_ids: List[str],
    terminal_ui: Any,
    server_mode: bool,
    is_tui_local: bool,
    target_app: Any,
):
    """Elimina las pestañas de agentes y oculta el contenedor paralelo."""
    if server_mode:
        try:
            terminal_ui.hide_agent_panels()
        except Exception as e:
            logger.warning("hide_agent_panels: %s", e)
        return

    if not (is_tui_local and target_app):
        return

    def _do():
        try:
            # Esperar para que el usuario vea resultados finales
            time.sleep(0.5)

            # Eliminar pestañas dinámicas
            for pid in panel_ids:
                try:
                    target_app.remove_agent_tab(pid)
                except Exception as e:
                    logger.debug("remove_agent_tab(%s): %s", pid, e)

            # Ocultar el contenedor
            if hasattr(target_app, "deactivate_parallel_container"):
                target_app.deactivate_parallel_container()
            else:
                try:
                    target_app.query_one("#parallel_agents_container").display = False
                except Exception:
                    pass
                target_app.refresh(layout=True)

        except Exception as e:
            logger.warning("_deactivate_parallel_container._do: %s", e)

    if threading.current_thread() is threading.main_thread():
        _do()
    else:
        target_app.call_from_thread(_do)


# ─── Schema de herramienta para el LLM ───────────────────────────────────────

tool_schema = {
    "name": "call_agents_parallel",
    "description": (
        "Invoca múltiples agentes especializados simultáneamente para acelerar el procesamiento "
        "de tareas complejas. Cada agente trabaja en paralelo en su propio panel visual con pestañas. "
        "Úsalo cuando necesitas delegar subtareas independientes a agentes especializados "
        "(investigación, desarrollo, análisis, etc.) al mismo tiempo.\n\n"
        "Tipos de agente disponibles:\n"
        "- 'code_agent': Motor de desarrollo de software (DeepCoder). Ideal para escribir, "
        "  editar y validar código.\n"
        "- 'researcher_agent': Motor de investigación profunda (DeepResearcher). Ideal para "
        "  leer archivos, analizar contexto, buscar información.\n"
        "- Cualquier otro string: Agente dinámico genérico con el rol indicado. Usar junto "
        "  con 'system_prompt' para personalizar su comportamiento."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agents": {
                "type": "array",
                "description": "Lista de agentes a invocar en paralelo. Mínimo 2, máximo 8.",
                "minItems": 1,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "required": ["name", "task"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Nombre descriptivo del agente (ej. 'Investigador', 'Desarrollador'). Se muestra como título de la pestaña en la TUI.",
                        },
                        "task": {
                            "type": "string",
                            "description": "Descripción detallada de la tarea asignada a este agente.",
                        },
                        "type": {
                            "type": "string",
                            "description": "Tipo o rol especializado del agente. Opciones predefinidas: 'code_agent' (DeepCoder), 'researcher_agent' (DeepResearcher), o cualquier otro rol dinámico específico como 'security_expert', 'tester', 'architect', etc.",
                        },
                        "system_prompt": {
                            "type": "string",
                            "description": "Opcional. Prompt de sistema personalizado para agentes con type dinámico.",
                        },
                    },
                },
            }
        },
        "required": ["agents"],
    },
}
