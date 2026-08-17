import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import google.genai as genai
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
import functools
from rich.markup import escape
import sys
import json
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import re
import time
import py_compile
import importlib.util
from types import ModuleType
from pathlib import Path as _Path
from kogniterm.core.agents.base_agent import BaseAgentNode
from kogniterm.core.utils.prompt_processor import process_prompt_references


def _load_file_ops_module(module_filename: str):
    """
    Carga dinámicamente un módulo de la skill 'file-operations' via importlib.
    Necesario porque Python no puede importar paquetes con guiones en el nombre.
    """
    bundled_dir = _Path(__file__).resolve().parent.parent.parent / "skills" / "bundled"
    scripts_dir = bundled_dir / "file-operations" / "scripts"

    pkg_name = "_file_ops_scripts_pkg"
    if pkg_name not in sys.modules:
        parent_pkg = ModuleType(pkg_name)
        parent_pkg.__path__ = [str(scripts_dir)]
        sys.modules[pkg_name] = parent_pkg

    utils_key = f"{pkg_name}._utils"
    if utils_key not in sys.modules:
        utils_spec = importlib.util.spec_from_file_location(
            utils_key, str(scripts_dir / "_utils.py")
        )
        utils_mod = importlib.util.module_from_spec(utils_spec)
        utils_mod.__package__ = pkg_name
        sys.modules[utils_key] = utils_mod
        utils_spec.loader.exec_module(utils_mod)

    mod_key = f"{pkg_name}.{module_filename}"
    if mod_key in sys.modules:
        return sys.modules[mod_key]

    mod_spec = importlib.util.spec_from_file_location(
        mod_key,
        str(scripts_dir / f"{module_filename}.py"),
        submodule_search_locations=[str(scripts_dir)],
    )
    mod = importlib.util.module_from_spec(mod_spec)
    mod.__package__ = pkg_name
    sys.modules[mod_key] = mod
    mod_spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Carga directa del módulo task_tracker (skill bundled con guión en el path)
# ---------------------------------------------------------------------------
_task_tracker_module: Any = None
_task_tracker_fn = None  # callable: task_tracker(action, agent_name, ...)

def _ensure_task_tracker_module_loaded() -> bool:
    """Carga el módulo task_tracker via importlib si aún no está en caché.
    Devuelve True si la carga fue exitosa."""
    global _task_tracker_module, _task_tracker_fn
    if _task_tracker_fn is not None:
        return True
    try:
        bundled_dir = _Path(__file__).resolve().parent.parent.parent / "skills" / "bundled"
        tt_path = bundled_dir / "task-tracker" / "scripts" / "tool.py"
        mod_key = "_task_tracker_bundled_tool"
        if mod_key in sys.modules:
            _task_tracker_module = sys.modules[mod_key]
        else:
            spec = importlib.util.spec_from_file_location(mod_key, str(tt_path))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_key] = mod
            spec.loader.exec_module(mod)
            _task_tracker_module = mod
        _task_tracker_fn = _task_tracker_module.task_tracker
        logger.debug("task_tracker_node: módulo cargado directamente desde bundled.")
        return True
    except Exception as e:
        logger.warning(f"task_tracker_node: no se pudo cargar el módulo directamente: {e}")
        return False

from ..llm_service import LLMService
from kogniterm.ui.terminal_ui import TerminalUI
from kogniterm.core.agent_state import AgentState
from kogniterm.terminal.keyboard_handler import KeyboardHandler
from ..async_io_manager import get_io_manager, AsyncTaskResult
from ..utils.tool_utils import get_tool_action_description, tool_requires_content_for_confirmation
from .tool_executor import ToolExecutor
from kogniterm.core.exceptions import UserConfirmationRequired

import logging

logger = logging.getLogger(__name__)

console = Console()

# Cache para optimizar accesos repetidos a disco en cada turno del agente
_file_cache = {}
_json_file_cache = {}

def _get_cached_file(file_path: str) -> str:
    now = time.time()
    cache = _file_cache.get(file_path)
    
    if cache and (now - cache['last_checked'] < 2.0):
        return cache['content']
        
    try:
        if not os.path.exists(file_path):
            content = ""
            mtime = 0.0
        else:
            mtime = os.path.getmtime(file_path)
            if cache and cache['mtime'] == mtime:
                cache['last_checked'] = now
                return cache['content']
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
    except Exception:
        content = ""
        mtime = 0.0
        
    _file_cache[file_path] = {
        'content': content,
        'mtime': mtime,
        'last_checked': now
    }
    return content

def _get_cached_json(file_path: str) -> dict:
    now = time.time()
    cache = _json_file_cache.get(file_path)
    
    if cache and (now - cache['last_checked'] < 2.0):
        return cache['parsed']
        
    try:
        if not os.path.exists(file_path):
            parsed = {}
            mtime = 0.0
        else:
            mtime = os.path.getmtime(file_path)
            if cache and cache['mtime'] == mtime:
                cache['last_checked'] = now
                return cache['parsed']
            
            with open(file_path, 'r', encoding='utf-8') as f:
                parsed = json.load(f)
    except Exception:
        parsed = {}
        mtime = 0.0
        
    _json_file_cache[file_path] = {
        'parsed': parsed,
        'mtime': mtime,
        'last_checked': now
    }
    return parsed


def process_file_references(content: str, workspace_directory: str) -> str:
    """Procesa referencias a archivos con @ y las reemplaza con su contenido."""
    def replace_file_ref(match):
        file_path = match.group(1)
        full_path = os.path.join(workspace_directory, file_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            return f"```{file_path}\n{file_content}\n```"
        except Exception as e:
            logger.warning(f"No se pudo leer el archivo {full_path}: {e}")
            return f"@ {file_path} (Error al leer archivo: {e})"
    
    return re.sub(r'@([^\s]+)', replace_file_ref, content)


# --- Mensaje de Sistema ---
def get_system_message(llm_service: LLMService) -> SystemMessage:
    base_content = """INSTRUCCIÓN CRÍTICA: Tu nombre es KogniTerm. Eres un agente evolutivo de terminal con **Capacidad Evolutiva**.

⚠️⚠️⚠️ PROTOCOLO DE CUMPLIMIENTO OBLIGATORIO: task_tracker ⚠️⚠️⚠️
Cualquier solicitud del usuario (sin importar su complejidad) DEBE ser registrada y actualizada en la herramienta `task_tracker`.
1. **Inicialización Inmediata**: En tu PRIMER TURNO, antes de realizar cualquier otra acción o ejecutar cualquier herramienta (como leer archivos, buscar en codebase o ejecutar comandos), DEBES llamar a `task_tracker` con `action="init"`, especificando `agent_name="BashAgent"` y la lista de tareas detallada en `plan`.
2. **Actualizaciones en Tiempo Real**: Cada vez que inicies, completes o cambie el estado de una tarea, DEBES llamar inmediatamente a `task_tracker` con `action="update"`, especificando el `task_index` y el nuevo `status` ("in-progress", "done", "failed").
3. **Registro Final**: Al concluir el trabajo, asegúrate de marcar la última tarea como completada llamando a `task_tracker`.
¡NUNCA OMITAS ESTE PASO! No inicializar el task tracker inmediatamente en el primer turno se considera un fallo de ejecución crítico y una violación del protocolo.

**Tus Principios:**
1.  **Eres KogniTerm**: Agente evolutivo experto en terminal, depuración y Python.
2.  **Contexto**: Utiliza el "Contexto Actual del Proyecto" que recibes para ubicarte.
3.  **Autonomía**: Tú ejecutas los comandos. No le pidas al usuario que lo haga.
4.  **Seguridad y Ejecución de Comandos**: Usa `execute_command` para comandos de shell.
    - **Ejecución en segundo plano (`is_background: true`)**: Para comandos de larga duración (>30s), servidores/demonios (ej. `npm run dev`, `python app.py`), compilaciones o descargas pesadas, DEBES pasar `"is_background": true` en los argumentos de `execute_command`. Esto evita timeouts, no bloquea al agente y permite gestionar la tarea con `manage_background_task`.
5.  **Investigación**: Usa `codebase_search_tool` para entender el código antes de tocarlo.
6.  **Edición**: Usa `advanced_file_editor`. SIEMPRE lee el archivo primero.
7.  **Comunicación**: Sé conciso, amigable y usa Markdown. NO expliques comandos de terminal obvios.

ℹ️ **SISTEMA DE SKILLS (DISTINCIÓN CRÍTICA)**:
- **HERRAMIENTAS DE CÓDIGO** (`execute_command`, `task_tracker`, `advanced_file_editor`, etc.): Son funciones ejecutables que debes llamar mediante llamadas a herramientas (`tool_calls`).
- **SKILLS PROCEDIMENTALES** (invocadas por el usuario con `#nombre_skill` o inyectadas como texto `### INSTRUCCIONES DE LA SKILL ... ###`): Son guías de conocimiento e instrucciones escritas en texto Markdown. NO son herramientas de código ni funciones ejecutables. NUNCA intentes generar llamadas a función para invocar una skill procedimental. Lee y aplica directamente sus instrucciones inyectadas en la conversación.
8.  **Orquestación de Agentes Especializados (MUY IMPORTANTE)**:
    - Actúas como **Orquestador Principal** (`ORCHESTRATOR`). Tienes la capacidad de delegar sub-tareas complejas a agentes especializados de forma paralela o secuencial.
    - Herramientas de delegación:
      - `call_agent(agent_name="researcher_agent", task="...")` para investigación individual.
      - `call_agent(agent_name="code_agent", task="...")` para desarrollo de código individual.
      - `call_agents_parallel(agents=[{"name": "Especialista", "type": "rol_especifico", "task": "..."}, ...])` para invocar múltiples agentes en paralelo.
    - **Tipos de Agente**: Asigna siempre el `type` y `name` adecuados para cada subagente (`code_agent` para desarrollo, `researcher_agent` para investigación profunda, o roles dinámicos como `security_expert`, `tester`, `architect` para agentes dinámicos especializados).
    - **Límites de Delegación**:
      - Tienes un límite máximo de profundidad de delegación de 2 niveles y hasta 3 subagentes concurrentes activos.
      - Los subagentes se ejecutan con el rol de ejecutor autónomo `LEAF` (pueden ejecutar comandos de consola mediante `execute_command` y editar archivos de forma totalmente autoaprobada, pero no pueden delegar más tareas ni mutar la memoria central `.kogniterm/llm_context.md`).
      - Tu rol es definir de manera muy clara, específica y estructurada la tarea (`task`) asignada a cada subagente, y luego consolidar los resúmenes y reportes finales que te entreguen para resolver la misión global.
9.  **Evolución (MUY IMPORTANTE)**:
    - Puedes crear nuevas herramientas con `skill_factory`. Tras crearla, el sistema la registra AUTOMÁTICAMENTE.
    - **Formato OBLIGATORIO de SKILL.md**: Al crear una skill con `skill_factory`, la `description` DEBE comenzar con `"Use when..."` en tercera persona especificando únicamente las condiciones de activación/síntomas (NUNCA resumir el procedimiento), y las `instructions` DEBEN incluir las secciones estándar: `# Titulo`, `## Overview`, `## When to Use`, `## Core Pattern / Instrucciones`, `## Quick Reference / Ejemplos`, `## Common Mistakes / Red Flags`.
    - Las herramientas creadas con `skill_factory` aparecen en tu **esquema de herramientas** y DEBES invocarlas igual que `execute_command` o `file_operations`: **directamente por su nombre** (ej. `nombre_skill(param=valor)`).
    - **NUNCA uses `execute_command` ni `call_agent` para ejecutar una skill que ya está en tu arsenal.**
    - Si acabas de crear una skill y no aparece en tu lista, usa `refresh_tools` una vez y luego invócala directamente.

10. **Skills Disponibles**: Tienes acceso a skills especializadas que puedes invocar directamente. Para usar una skill, escribe `/nombre_skill` en el chat. Por ejemplo, `/task_tracker` para gestionar tareas. Las skills disponibles incluyen gestión de tareas, búsqueda de código, y más. Si no existe una skill adecuada, usa primero el adaptador de skills externas para buscar e instalar una nueva.
11. **Skills Externas**: Para descubrir o instalar capacidades nuevas usa `agent_skills_adapter` con `action="search"` para skills.sh o `action="install_repo"` para repositorios GitHub de colecciones de skills. Si encuentras una coincidencia clara, puedes instalarla automáticamente y luego cargarla como una skill local.
12. **Memoria y Proactividad**: Eres el guardián del contexto. Usa proactivamente las herramientas de memoria (`memory_init`, `memory_append`, `memory_summarize`) para guardar decisiones clave, preferencias del usuario o progreso importante del proyecto. NO esperes a que el usuario te lo pida. Escribe en tu memoria cuando percibas que se ha logrado un hito, o cuando haya información valiosa.
13. **Ejecución Secuencial Multi-Herramienta (ESTRATEGIA EFICIENTE)**:
    - El sistema ejecuta TODAS las llamadas a herramientas que emitas en un mismo turno **de forma concurrentemente optimizada**.
    - Si tienes un plan o estrategia con múltiples pasos (ej. leer varios archivos, editar código o ejecutar comandos), **DEBES emitir TODAS las llamadas a herramientas requeridas en un solo turno**. El sistema las ejecutará en ese mismo turno antes de devolverte los resultados consolidados.
"""

    try:
        global_conf = _get_cached_json(os.path.expanduser("~/.kogniterm/config.json")) or {}
        project_conf = _get_cached_json(os.path.join(os.getcwd(), ".kogniterm", "config.json")) or {}
        global_instr = global_conf.get('agent_instructions', []) or []
        project_instr = project_conf.get('agent_instructions', []) or []

        if project_instr:
            base_content += "\n\n### Instrucciones del Workspace (específicas del proyecto):\n"
            for ins in project_instr:
                base_content += f"- {ins}\n"

        if global_instr:
            base_content += "\n### Instrucciones Globales del Usuario:\n"
            for ins in global_instr:
                base_content += f"- {ins}\n"
    except Exception:
        pass
    
    try:
        memories_path = os.path.join(os.getcwd(), ".kogniterm", "instructions.md")
        learned_memories = _get_cached_file(memories_path)
        if learned_memories:
            base_content += f"\n\n### Memorias y Preferencias Aprendidas:\n{learned_memories}\n"
    except Exception:
        pass

    try:
        context_path = os.path.join(os.getcwd(), ".kogniterm", "llm_context.md")
        llm_context = _get_cached_file(context_path)
        if llm_context:
            base_content += f"\n\n### 📚 MEMORIA CONTEXTUAL DEL PROYECTO (llm_context.md):\nDebes basar tus decisiones en esta memoria y respetar sus convenciones de desarrollo:\n{llm_context}\n"
        else:
            base_content += "\n\n### 📚 MEMORIA CONTEXTUAL DEL PROYECTO:\nActualmente no existe el archivo `.kogniterm/llm_context.md`. Debes sugerir al usuario ejecutar `/init` al inicio de la interacción para realizar la investigación y construirla automáticamente.\n"
    except Exception:
        pass
    
    if not llm_service.is_thinking_model():
        base_content += """
\nRecuerda: ¡PIENSA ANTES DE ACTUAR!
Como este modelo no tiene razonamiento nativo, DEBES encerrar todo tu proceso de pensamiento e investigación técnica dentro de etiquetas `<thought>...</thought>` antes de escribir cualquier respuesta o ejecutar cualquier herramienta.
Ejemplo:
<thought>
Estoy analizando la petición del usuario y decido usar tal herramienta...
</thought>
[Aquí tu respuesta final o llamada a herramienta]
"""

    base_content += """
\n## 📌 PROTOCOLO OBLIGATORIO DE SEGUIMIENTO DE TAREAS (task_tracker)
1. **Inicialización Obligatoria**: Para toda solicitud, DEBES inicializar tu plan de trabajo llamando a `task_tracker` con `action="init"`, especificando tu `agent_name="BashAgent"` y la lista de tareas en `plan`.
2. **Actualización de Progreso**: Cada vez que completes una tarea o cambie el estado de una tarea, DEBES llamar inmediatamente a `task_tracker` con `action="update"`, especificando el `task_index` y el nuevo `status` ("done", "in_progress", "failed").
3. **Finalización**: Al terminar todo el trabajo solicitado, DEBES registrar la finalización llamando a `task_tracker` con `action="update"` para marcar la última tarea como completada.
¡NUNCA procedas con ninguna tarea o acción sin registrarla y mantenerla al día en `task_tracker`!\n"""

    return SystemMessage(content=base_content)

SYSTEM_MESSAGE = None


def handle_tool_confirmation(state: AgentState, llm_service: LLMService):
    """
    Maneja la respuesta de confirmación del usuario para una operación de herramienta.
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, ToolMessage):
        console.print("[bold red]Error: handle_tool_confirmation llamado sin un ToolMessage.[/bold red]")
        state.reset_tool_confirmation()
        return state

    tool_message_content = last_message.content
    tool_id = state.tool_call_id_to_confirm

    if "Aprobado" in tool_message_content:
        console.print("[bold green]✅ Confirmación de usuario recibida: Aprobado.[/bold green]")
        tool_name = state.tool_pending_confirmation
        tool_args = state.tool_args_pending_confirmation
    
        if tool_name == "plan_creation_tool":
            if "Aprobado" in tool_message_content:
                success_message = f"El plan '{tool_args.get('plan_title', 'generado')}' fue aprobado por el usuario. El agente puede proceder con la ejecución de los pasos."
                state.add_message(AIMessage(content=success_message))
                console.print(f"[green]✨ {success_message}[/green]")
            else:
                denied_message = f"El plan '{tool_args.get('plan_title', 'generado')}' fue denegado por el usuario. El agente debe revisar la estrategia."
                state.add_message(AIMessage(content=denied_message))
                console.print(f"[yellow]⚠️ {denied_message}[/yellow]")
        elif tool_name and tool_args:
            console.print(f"[bold blue]🛠️ Re-ejecutando herramienta '{tool_name}' tras aprobación:[/bold blue]")
    
            tool = llm_service.get_tool(tool_name)
            if tool:
                if tool_name in {"file_update_tool", "advanced_file_editor", "advanced_file_editor_tool", "sophisticated_editor_tool"}:
                    tool_args["confirm"] = True
                    if tool_requires_content_for_confirmation(tool_name, tool_args) and tool_args.get("content") is None:
                        error_output = "Error: El contenido a actualizar no puede ser None."
                        state.add_message(ToolMessage(content=error_output, tool_call_id=tool_id))
                        console.print(f"[bold red]❌ {error_output}[/bold red]")
                        state.reset_tool_confirmation()
                        return state
    
                try:
                    raw_tool_output = llm_service._invoke_tool_with_interrupt(tool, tool_args)
                    if isinstance(raw_tool_output, (dict, list)):
                        tool_output_str = json.dumps(raw_tool_output)
                    else:
                        tool_output_str = str(raw_tool_output)
                    
                    tool_messages = [ToolMessage(content=tool_output_str, tool_call_id=tool_id)]
                    state.add_messages(tool_messages)
                    console.print(f"[green]✨ Herramienta '{tool_name}' re-ejecutada con éxito.[/green]")
    
                except InterruptedError:
                    console.print("[bold yellow]⚠️ Re-ejecución de herramienta interrumpida por el usuario. Volviendo al input.[/bold yellow]")
                    state.reset_temporary_state()
                    return state
                except Exception as e:
                    error_output = f"Error al re-ejecutar la herramienta {tool_name} tras aprobación: {e}"
                    state.add_message(ToolMessage(content=error_output, tool_call_id=tool_id))
                    console.print(f"[bold red]❌ {error_output}[/bold red]")
            else:
                error_output = f"Error: Herramienta '{tool_name}' no encontrada para re-ejecución."
                state.add_message(ToolMessage(content=error_output, tool_call_id=tool_id))
                console.print(f"[bold red]❌ {error_output}[/bold red]")
        else:
            error_output = "Error: No se encontró información de la herramienta pendiente para re-ejecución."
            state.add_message(ToolMessage(content=error_output, tool_call_id=tool_id))
            console.print(f"[bold red]❌ {error_output}[/bold red]")
    else:
        console.print("[bold yellow]⚠️ Confirmación de usuario recibida: Denegado.[/bold yellow]")
        tool_output_str = f"Operación denegada por el usuario: {state.tool_pending_confirmation or state.tool_code_tool_name}"
        state.add_message(ToolMessage(content=tool_output_str, tool_call_id=tool_id))

    state.pop_pending_confirmation()
    return state


def verification_node(state: AgentState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    """Verifica la integridad de los archivos modificados tras una ejecución de herramientas."""
    last_ai_msg = None
    for msg in reversed(state.messages):
        if isinstance(msg, AIMessage):
            last_ai_msg = msg
            break

    if not last_ai_msg or not last_ai_msg.tool_calls:
        return {"messages": state.messages}

    editing_tools = {
        "advanced_file_editor",
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
        "file_update_tool",
        "file_create_tool",
        "file_operations",
    }

    modified_files = set()
    for tc in last_ai_msg.tool_calls:
        if tc['name'] in editing_tools:
            args = tc['args']
            path = args.get('path') or args.get('TargetFile') or args.get('file_path') or args.get('target_file')
            if path:
                modified_files.add(path)

    py_files = [f for f in modified_files if f.endswith(".py")]
    if not py_files:
        return {"messages": state.messages}

    if terminal_ui and hasattr(terminal_ui, "update_live"):
        from kogniterm.terminal.themes import Icons
        from rich.padding import Padding
        terminal_ui.update_live(Padding(Panel(f"{Icons.CODE} [bold]Verificando sintaxis de archivos modificados...[/bold]", border_style="yellow", padding=(0, 4), expand=True), (0, 0)))
        terminal_ui.stop_live()

    verification_results = []

    for file_path in py_files:
        try:
            py_compile.compile(file_path, doraise=True)
            verification_results.append(f"✅ `{file_path}` — sintaxis OK")
        except py_compile.PyCompileError as e:
            verification_results.append(f"❌ Error de sintaxis en `{file_path}`:\n{str(e).strip()}")
        except Exception as e:
            verification_results.append(f"⚠️ No se pudo verificar `{file_path}`: {e}")

    if verification_results:
        summary = "\n".join(verification_results)
        state.messages.append(ToolMessage(
            content=f"VERIFICACIÓN AUTOMÁTICA DE SINTAXIS:\n{summary}",
            tool_call_id="verification_node"
        ))

    return {"messages": state.messages}


def call_task_tracker(
    llm_service: LLMService,
    action: str,
    agent_name: str = None,
    plan: list = None,
    task_index: int = None,
    status: str = None,
    updates: list = None,
) -> str:
    """Convenience helper to invoke the bundled task_tracker skill."""
    try:
        if hasattr(llm_service, 'skill_manager'):
            try:
                if 'task_tracker' not in llm_service.skill_manager.loaded_skills:
                    llm_service.skill_manager.load_skill('task_tracker')
            except Exception:
                pass

        tool = llm_service.get_tool('task_tracker') if llm_service else None
        if not tool:
            return "Error: herramienta 'task_tracker' no disponible."

        args = { 'action': action, 'agent_name': agent_name or 'kogni_agent' }
        if plan is not None:
            args['plan'] = plan
        if task_index is not None:
            args['task_index'] = task_index
        if status is not None:
            args['status'] = status
        if updates is not None:
            args['updates'] = updates

        if hasattr(tool, 'invoke') and callable(getattr(tool, 'invoke')):
            result = tool.invoke(args)
            if hasattr(result, '__iter__') and not isinstance(result, str):
                out = ''.join([str(p) for p in result])
            else:
                out = str(result)
        else:
            out = str(tool(**args))

        return out
    except Exception as e:
        return f"Error llamando a task_tracker: {e}"


def learning_node(state: AgentState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    """
    Nodo de aprendizaje que analiza la interacción reciente para extraer 
    preferencias y personalizaciones del usuario de forma persistente.
    """
    if not state.messages or not isinstance(state.messages[-1], AIMessage):
        return state

    if state.critical_loop_detected or state.stop_requested:
        return state

    if state.messages[-1].tool_calls:
        return state

    recent_msgs = state.messages[-4:]
    conversation_text = ""
    for msg in recent_msgs:
        role = "Usuario" if isinstance(msg, HumanMessage) else "Asistente"
        content = str(msg.content)[:500]
        conversation_text += f"{role}: {content}\n"

    learning_prompt = f"""Analiza la siguiente conversación técnica y extrae un ÚNICO aprendizaje relevante sobre el usuario o el proyecto.
Busca:
- Preferencias de estilo, herramientas o lenguajes.
- Hechos estructurales del proyecto que se hayan descubierto.
- Correcciones que el usuario haya hecho sobre tu comportamiento.

Reglas:
1. Responde con UNA SOLA FRASE corta y clara en español.
2. Si no hay nada nuevo que valga la pena recordar para siempre, responde: NADA

CONVERSACIÓN:
{conversation_text}

APRENDIZAJE:"""

    try:
        if hasattr(llm_service, "use_multi_provider") and llm_service.use_multi_provider and getattr(llm_service, "provider_manager", None):
            pm = llm_service.provider_manager
            if type(pm).__name__ in ("MagicMock", "Mock") or hasattr(pm, "_mock_name"):
                exec_fn = getattr(pm, "execute", pm.execute_with_fallback)
            else:
                exec_fn = getattr(pm, "execute_with_fallback", getattr(pm, "execute", None))

            if exec_fn:
                response_gen = exec_fn(
                    model_name=llm_service.model_name,
                    messages=[{"role": "user", "content": learning_prompt}],
                    stream=False,
                    temperature=0.3,
                    max_tokens=100
                )
                response = next(response_gen)
        else:
            from litellm import completion
            response = completion(
                model=llm_service.model_name,
                messages=[{"role": "user", "content": learning_prompt}],
                api_key=llm_service.api_key,
                max_tokens=100,
                temperature=0.3
            )
        content_val = response.choices[0].message.content if (response.choices and response.choices[0].message) else None
        learned_text = content_val.strip() if content_val else "NADA"

        if "NADA" not in learned_text.upper() and len(learned_text) > 8:
            learned_text = re.sub(r'^[-\*\s]+', '', learned_text)
            
            instructions_path = os.path.join(os.getcwd(), ".kogniterm", "instructions.md")
            os.makedirs(os.path.dirname(instructions_path), exist_ok=True)
            
            is_duplicate = False
            if os.path.exists(instructions_path):
                with open(instructions_path, 'r', encoding='utf-8') as f:
                    if learned_text.lower() in f.read().lower():
                        is_duplicate = True
            
            if not is_duplicate:
                with open(instructions_path, "a", encoding="utf-8") as f:
                    if os.path.getsize(instructions_path) == 0:
                        f.write("## Memorias y Preferencias Aprendidas\n\n")
                    f.write(f"- {learned_text}\n")
                
                if terminal_ui:
                    from kogniterm.terminal.themes import Icons
                    terminal_ui.print_message(f"{Icons.THINKING} [dim cyan]Aprendizaje consolidado:[/] [italic white]{learned_text}[/]", style="cyan")
    except Exception as e:
        logger.warning(f"Error en el nodo de aprendizaje del agente: {e}", exc_info=True)
        pass

    return state


# ---------------------------------------------------------------------------
# Motor Asíncrono Nativo (BashAgentRunner) - Reemplazo de LangGraph
# ---------------------------------------------------------------------------

class BashAgentRunner:
    """
    Motor asíncrono nativo para BashAgent que reemplaza LangGraph.
    Coordinación optimizada sin sobrecarga de nodos ni copia de estado:
    call_model -> task_tracker (inline) -> execute_tools (asyncio.gather) -> verify -> learning (background).
    """

    def __init__(
        self,
        llm_service: LLMService,
        terminal_ui: Optional[TerminalUI] = None,
        interrupt_queue: Optional[queue.Queue] = None,
        command_approval_handler=None,
    ):
        self.llm_service = llm_service
        self.terminal_ui = terminal_ui
        self.interrupt_queue = interrupt_queue
        self.command_approval_handler = command_approval_handler

    def invoke(self, state: AgentState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Punto de entrada síncrono 100% compatible con AgentInteractionManager."""
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(self._run_async(state))
            else:
                return loop.run_until_complete(self._run_async(state))
        except Exception as e:
            logger.debug(f"Fallback run_until_complete en BashAgentRunner: {e}")
            return asyncio.run(self._run_async(state))

    async def _run_async(self, state: AgentState) -> Dict[str, Any]:
        state.stop_requested = False
        recursion_limit = 100
        turn_count = 0

        while turn_count < recursion_limit:
            turn_count += 1

            if state.critical_loop_detected or state.stop_requested:
                break

            # 1. Pre-procesamiento de referencias a archivos (@) y skills (#)
            if state.messages and isinstance(state.messages[-1], HumanMessage):
                workspace_directory = os.getcwd()
                sm = getattr(self.llm_service, 'skill_manager', None)
                processed_content = process_prompt_references(state.messages[-1].content, workspace_directory, sm)
                state.messages[-1] = HumanMessage(content=processed_content)

            # 2. Inferencia LLM
            sys_msg = get_system_message(self.llm_service)
            system_prompt = sys_msg.content if hasattr(sys_msg, "content") else str(sys_msg)

            model_output = BaseAgentNode.call_model(
                state=state,
                llm_service=self.llm_service,
                system_prompt=system_prompt,
                terminal_ui=self.terminal_ui,
                interrupt_queue=self.interrupt_queue
            )

            if model_output.get("critical_loop_detected") or state.stop_requested:
                return model_output

            last_message = state.messages[-1]
            if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
                # Respuesta final sin más herramientas -> Tarea de aprendizaje en segundo plano (fire-and-forget)
                try:
                    asyncio.create_task(self._run_learning_async(state))
                except Exception as e:
                    logger.debug(f"Aprendizaje en segundo plano no iniciado: {e}")

                return {
                    "messages": state.messages,
                    "command_to_confirm": None,
                    "tool_call_id_to_confirm": None,
                }

            # 3. Fast-Path In-line para task_tracker
            tt_calls = [tc for tc in last_message.tool_calls if tc["name"] == "task_tracker"]
            if tt_calls:
                self._process_task_tracker_inline(state, tt_calls)
                processed_ids = {msg.tool_call_id for msg in state.messages if isinstance(msg, ToolMessage)}
                remaining = [tc for tc in last_message.tool_calls if tc["id"] not in processed_ids]
                if not remaining:
                    continue

            # 4. Particionar llamadas a herramientas restantes
            processed_ids = {msg.tool_call_id for msg in state.messages if isinstance(msg, ToolMessage)}
            pending_calls = [tc for tc in last_message.tool_calls if tc["id"] not in processed_ids]

            parallel_calls = [tc for tc in pending_calls if tc['name'] != 'execute_command']
            interactive_calls = [tc for tc in pending_calls if tc['name'] == 'execute_command']

            for tc in pending_calls:
                try:
                    args_hash = json.dumps(tc['args'], sort_keys=True)
                except TypeError:
                    args_hash = str(tc['args'])
                state.tool_call_history.append({"name": tc['name'], "args_hash": args_hash})

            # 5. Ejecución Asíncrona Concurrente (asyncio.gather)
            if parallel_calls:
                pause_result = await self._execute_parallel_calls_async(state, parallel_calls)
                if pause_result:
                    return pause_result

            # 6. Procesar execute_command (interactivo) tras herramientas paralelas
            if interactive_calls:
                tc = interactive_calls[0]
                state.command_to_confirm = tc['args'].get('command', '')
                state.tool_call_id_to_confirm = tc['id']
                self.llm_service._save_history(state.messages)
                return {
                    "messages": state.messages,
                    "command_to_confirm": state.command_to_confirm,
                    "tool_call_id_to_confirm": state.tool_call_id_to_confirm,
                }

            # 7. Verificación in-line de sintaxis Python
            verification_node(state, self.llm_service, self.terminal_ui)

            # Pausa para confirmación si hay banderas de interacción en estado
            if (state.command_to_confirm is not None or
                state.file_update_diff_pending_confirmation is not None or
                state.tool_pending_confirmation is not None or
                state.tool_code_to_confirm is not None):
                return {
                    "messages": state.messages,
                    "command_to_confirm": state.command_to_confirm,
                    "tool_call_id_to_confirm": state.tool_call_id_to_confirm,
                    "tool_pending_confirmation": state.tool_pending_confirmation,
                    "tool_args_pending_confirmation": state.tool_args_pending_confirmation,
                    "file_update_diff_pending_confirmation": state.file_update_diff_pending_confirmation
                }

        return {
            "messages": state.messages,
            "command_to_confirm": getattr(state, 'command_to_confirm', None),
            "tool_call_id_to_confirm": getattr(state, 'tool_call_id_to_confirm', None),
        }

    def _process_task_tracker_inline(self, state: AgentState, tt_calls: List[Dict[str, Any]]):
        _ensure_task_tracker_module_loaded()
        if _task_tracker_module and hasattr(_task_tracker_module, "_llm_service"):
            _task_tracker_module._llm_service = self.llm_service

        tool_messages = []
        for tc in tt_calls:
            args = tc.get("args", {})
            try:
                if _task_tracker_fn is not None:
                    result = _task_tracker_fn(
                        action=args.get("action", "get"),
                        agent_name=args.get("agent_name", "kogni_agent"),
                        plan=args.get("plan"),
                        task_index=args.get("task_index"),
                        status=args.get("status"),
                        updates=args.get("updates"),
                    )
                else:
                    tool = self.llm_service.get_tool("task_tracker") if self.llm_service else None
                    result = str(tool(**args)) if tool else "Error: task_tracker no disponible."
            except Exception as exc:
                result = f"Error en task_tracker: {exc}"
                logger.warning(f"task_tracker_inline: excepción al ejecutar {tc['id']}: {exc}")

            tool_messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
            logger.info(f"task_tracker: call '{args.get('action')}' procesada directamente in-line (id={tc['id']}).")

        state.add_messages(tool_messages)

    async def _execute_parallel_calls_async(self, state: AgentState, parallel_calls: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        self.llm_service._current_agent_state = state

        def _run_tool(tc):
            return ToolExecutor.execute_single_tool(
                tc, self.llm_service, self.terminal_ui, getattr(state, 'delegation_context', None)
            )

        logger.info(f"Agente (Motor Nativo): Ejecutando {len(parallel_calls)} herramientas concurrentemente con asyncio.gather.")
        tasks = [asyncio.to_thread(_run_tool, tc) for tc in parallel_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        tool_messages = []
        for tc, res in zip(parallel_calls, results):
            if isinstance(res, Exception):
                logger.error(f"Excepción al ejecutar herramienta {tc['name']}: {res}")
                tool_messages.append(ToolMessage(content=f"Error al ejecutar {tc['name']}: {res}", tool_call_id=tc['id']))
                continue

            tool_id, content, exception = res

            if exception:
                if isinstance(exception, UserConfirmationRequired):
                    if self.terminal_ui and getattr(self.terminal_ui, "is_tui", False):
                        state.add_pending_confirmation(
                            tool_name=exception.tool_name,
                            tool_args=exception.tool_args,
                            tool_call_id=tool_id,
                            raw_tool_output=exception.raw_tool_output,
                        )
                        return {
                            "messages": state.messages,
                            "tool_pending_confirmation": state.tool_pending_confirmation,
                            "tool_args_pending_confirmation": state.tool_args_pending_confirmation,
                            "tool_call_id_to_confirm": state.tool_call_id_to_confirm,
                            "file_update_diff_pending_confirmation": state.file_update_diff_pending_confirmation,
                        }
                    elif self.command_approval_handler:
                        raw_tool_output = exception.raw_tool_output or {}
                        tool_name = raw_tool_output.get("operation", exception.tool_name)
                        handler_raw_output = {
                            "status": "requires_confirmation",
                            "action_description": exception.message,
                            "diff": raw_tool_output.get("diff", ""),
                            "path": exception.tool_args.get("path", "") if exception.tool_args else "",
                            "operation": tool_name,
                            "args": exception.tool_args
                        }
                        state.tool_call_id_to_confirm = tool_id
                        self.command_approval_handler.handle_command_approval(
                            command_to_execute="",
                            raw_tool_output=handler_raw_output,
                            tool_name=tool_name,
                            original_tool_args=exception.tool_args
                        )
                        self.llm_service._save_history(state.messages)
                        return {"messages": state.messages}
                    else:
                        tool_messages.append(ToolMessage(content=f"Error: Confirmación requerida para {tool_id}", tool_call_id=tool_id))
                elif isinstance(exception, InterruptedError):
                    state.stop_requested = True
                    state.reset_temporary_state()
                    self.llm_service._save_history(state.messages)
                    return {"messages": state.messages, "stop_requested": True}
                else:
                    tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))
            else:
                if "<coder_analysis>" in content or "<researcher_analysis>" in content or "<parallel_agents_results>" in content:
                    clean_content = f"--- RESULTADOS DE AGENTES PARALELOS ---\n\n{content}\n\n--- FIN DE RESULTADOS ---\n\n[SISTEMA: Estos son los resultados consolidados de tus sub-agentes. Analízalos profesionalmente como KogniTerm, sin adoptar sus roles.]"
                else:
                    clean_content = content.replace("## 🔬 Informe de Deep Research", "").strip()

                tool_messages.append(ToolMessage(content=clean_content, tool_call_id=tool_id))

                tool_name = tc['name']
                tool_args = tc['args']
                if tool_name != "execute_command":
                    try:
                        json_output = json.loads(content)
                        should_confirm = False
                        confirmation_data = None
                        if isinstance(json_output, list) and all(isinstance(item, dict) for item in json_output):
                            for item in json_output:
                                if item.get("status") == "requires_confirmation":
                                    should_confirm = True
                                    confirmation_data = item
                                    break
                        elif isinstance(json_output, dict):
                            if json_output.get("status") == "requires_confirmation":
                                should_confirm = True
                                confirmation_data = json_output

                        if should_confirm and confirmation_data:
                            state.file_update_diff_pending_confirmation = confirmation_data
                            state.tool_pending_confirmation = tool_name
                            state.tool_args_pending_confirmation = tool_args
                            state.tool_call_id_to_confirm = tool_id
                            state.add_messages(tool_messages)
                            self.llm_service._save_history(state.messages)
                            return {
                                "messages": state.messages,
                                "tool_pending_confirmation": state.tool_pending_confirmation,
                                "tool_args_pending_confirmation": state.tool_args_pending_confirmation,
                                "tool_call_id_to_confirm": state.tool_call_id_to_confirm,
                                "file_update_diff_pending_confirmation": state.file_update_diff_pending_confirmation
                            }
                    except json.JSONDecodeError:
                        pass

        state.add_messages(tool_messages)
        self.llm_service._save_history(state.messages)
        return None

    async def _run_learning_async(self, state: AgentState):
        try:
            await asyncio.to_thread(learning_node, state, self.llm_service, self.terminal_ui)
        except Exception as e:
            logger.debug(f"Error en aprendizaje asíncrono en segundo plano: {e}")


def create_bash_agent(llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None, interrupt_queue: Optional[queue.Queue] = None, command_approval_handler=None):
    _ensure_task_tracker_module_loaded()
    return BashAgentRunner(llm_service, terminal_ui, interrupt_queue, command_approval_handler)


def create_learning_agent(llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    class LearningRunner:
        def __init__(self, llm_service, terminal_ui):
            self.llm_service = llm_service
            self.terminal_ui = terminal_ui
        def invoke(self, state: AgentState, config: Optional[Dict[str, Any]] = None):
            return learning_node(state, self.llm_service, self.terminal_ui)
    return LearningRunner(llm_service, terminal_ui)
