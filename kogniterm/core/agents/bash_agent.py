import asyncio
from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import google.genai as genai
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
import functools
from rich.markup import escape # Nueva importación
import sys # Nueva importación
import json # Importar json para verificar si la salida es un JSON
import queue # Importar el módulo queue
from concurrent.futures import ThreadPoolExecutor, as_completed # Nueva importación para paralelización
import os
import re
import time
import py_compile
import importlib.util
from types import ModuleType
from pathlib import Path as _Path
from kogniterm.core.agents.base_agent import BaseAgentNode


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
# Se carga una vez al importar este módulo y se reutiliza en task_tracker_node.
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
from kogniterm.core.agent_state import AgentState # Importar AgentState desde el archivo consolidado
from kogniterm.terminal.keyboard_handler import KeyboardHandler # Importar KeyboardHandler
from ..async_io_manager import get_io_manager, AsyncTaskResult
from ..utils.tool_utils import get_tool_action_description, tool_requires_content_for_confirmation
from .tool_executor import ToolExecutor

import logging

logger = logging.getLogger(__name__)

console = Console()

# Cache para optimizar accesos repetidos a disco en cada turno del agente
_file_cache = {}
_json_file_cache = {}

def _get_cached_file(file_path: str) -> str:
    now = time.time()
    cache = _file_cache.get(file_path)
    
    # Si el caché existe y se comprobó hace menos de 2.0 segundos, confiar en él
    if cache and (now - cache['last_checked'] < 2.0):
        return cache['content']
        
    try:
        if not os.path.exists(file_path):
            content = ""
            mtime = 0.0
        else:
            mtime = os.path.getmtime(file_path)
            # Si mtime coincide, actualizar timestamp de verificación y retornar cache
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
    
    # Si el caché existe y se comprobó hace menos de 2.0 segundos, confiar en él
    if cache and (now - cache['last_checked'] < 2.0):
        return cache['parsed']
        
    try:
        if not os.path.exists(file_path):
            parsed = {}
            mtime = 0.0
        else:
            mtime = os.path.getmtime(file_path)
            # Si mtime coincide, actualizar timestamp de verificación y retornar cache
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
    
    # Reemplazar @ruta con el contenido del archivo
    return re.sub(r'@([^\s]+)', replace_file_ref, content)



# --- Mensaje de Sistema ---
def get_system_message(llm_service: LLMService) -> SystemMessage:
    base_content = """INSTRUCCIÓN CRÍTICA: Tu nombre es KogniTerm. Eres un agente evolutivo de terminal con **Capacidad Evolutiva**.

⚠️⚠️⚠️ PROTOCOLO DE CUMPLIMIENTO OBLIGATORIO: task_tracker ⚠️⚠️⚠️
Cualquier solicitud del usuario (sin importar su complejidad) DEBE ser registrada y actualizada en la herramienta `task_tracker`.
1. **Inicialización Inmediata**: En tu PRIMER TURNO, antes de realizar cualquier otra acción o ejecutar cualquier herramienta (como leer archivos, buscar en codebase o ejecutar comandos), DEBES llamar a `task_tracker` con `action="init"`, especificando `agent_name="BashAgent"` y la lista de tareas detallada en `plan`.
2. **Actualizaciones en Tiempo Real**: Cada vez que inicies, completes o cambie el estado de una tarea, DEBES llamar inmediatamente a `task_tracker` con `action="update"`, especificando el `task_index` y el nuevo `status` ("in-progress", "completed", "failed").
3. **Registro Final**: Al concluir el trabajo, asegúrate de marcar la última tarea como completada llamando a `task_tracker`.
¡NUNCA OMITAS ESTE PASO! No inicializar el task tracker inmediatamente en el primer turno se considera un fallo de ejecución crítico y una violación del protocolo.

**Tus Principios:**
1.  **Eres KogniTerm**: Agente evolutivo experto en terminal, depuración y Python.
2.  **Contexto**: Utiliza el "Contexto Actual del Proyecto" que recibes para ubicarte.
3.  **Autonomía**: Tú ejecutas los comandos. No le pidas al usuario que lo haga.
4.  **Seguridad**: Usa `execute_command` para comandos de shell.
5.  **Investigación**: Usa `codebase_search_tool` para entender el código antes de tocarlo.
6.  **Edición**: Usa `advanced_file_editor`. SIEMPRE lee el archivo primero.
7.  **Comunicación**: Sé conciso, amigable y usa Markdown. NO expliques comandos de terminal obvios.
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
    - Las herramientas creadas con `skill_factory` aparecen en tu **esquema de herramientas** y DEBES invocarlas igual que `execute_command` o `file_operations`: **directamente por su nombre** (ej. `nombre_skill(param=valor)`).
    - **NUNCA uses `execute_command` ni `call_agent` para ejecutar una skill que ya está en tu arsenal.**
    - Si acabas de crear una skill y no aparece en tu lista, usa `refresh_tools` una vez y luego invócala directamente.
10. **Skills Disponibles**: Tienes acceso a skills especializadas que puedes invocar directamente. Para usar una skill, escribe `/nombre_skill` en el chat. Por ejemplo, `/task_tracker` para gestionar tareas. Las skills disponibles incluyen gestión de tareas, búsqueda de código, y más. Si no existe una skill adecuada, usa primero el adaptador de skills externas para buscar e instalar una nueva.
11. **Skills Externas**: Para descubrir o instalar capacidades nuevas usa `agent_skills_adapter` con `action="search"` para skills.sh o `action="install_repo"` para repositorios GitHub de colecciones de skills. Si encuentras una coincidencia clara, puedes instalarla automáticamente y luego cargarla como una skill local.
12. **Memoria y Proactividad**: Eres el guardián del contexto. Usa proactivamente las herramientas de memoria (`memory_init`, `memory_append`, `memory_summarize`) para guardar decisiones clave, preferencias del usuario o progreso importante del proyecto. NO esperes a que el usuario te lo pida. Escribe en tu memoria cuando percibas que se ha logrado un hito, o cuando haya información valiosa.
13. **Paralelismo de Herramientas (MUY IMPORTANTE para reducir latencia)**:
    - El sistema ejecuta TODAS tus tool_calls de un mismo turno **en paralelo** de forma automática.
    - Cuando necesites hacer varias acciones independientes (leer varios archivos, buscar en varios lugares, etc.), emite **todas las llamadas a herramientas en el mismo turno**, no una por una.
    - *Ejemplo correcto*: leer `archivo_a.py`, `archivo_b.py` y buscar en el codebase → emite las 3 tool_calls a la vez.
    - *Ejemplo incorrecto*: leer `archivo_a.py`, esperar resultado, luego leer `archivo_b.py`.
    - La única excepción es `execute_command`: siempre se presenta al usuario tras las demás, no la combines con herramientas que aún necesitas ejecutar antes.
"""

    # Adjuntar instrucciones del usuario (global y del proyecto) si existen
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
        # No bloquear si falla
        pass
    
    # Cargar memorias dinámicas de Gemini (si existen)
    try:
        memories_path = os.path.join(os.getcwd(), ".kogniterm", "instructions.md")
        learned_memories = _get_cached_file(memories_path)
        if learned_memories:
            base_content += f"\n\n### Memorias y Preferencias Aprendidas:\n{learned_memories}\n"
    except Exception:
        pass

    # Cargar memoria contextual del proyecto (llm_context.md)
    try:
        context_path = os.path.join(os.getcwd(), ".kogniterm", "llm_context.md")
        llm_context = _get_cached_file(context_path)
        if llm_context:
            base_content += f"\n\n### 📚 MEMORIA CONTEXTUAL DEL PROYECTO (llm_context.md):\nDebes basar tus decisiones en esta memoria y respetar sus convenciones de desarrollo:\n{llm_context}\n"
        else:
            base_content += "\n\n### 📚 MEMORIA CONTEXTUAL DEL PROYECTO:\nActualmente no existe el archivo `.kogniterm/llm_context.md`. Debes sugerir al usuario ejecutar `/init` al inicio de la interacción para realizar la investigación y construirla automáticamente.\n"
    except Exception:
        pass
    
    # Solo añadir la instrucción de pensar si el modelo NO es de razonamiento nativo
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

    # PROTOCOLO OBLIGATORIO DE SEGUIMIENTO DE TAREAS (task_tracker)
    base_content += """
\n## 📌 PROTOCOLO OBLIGATORIO DE SEGUIMIENTO DE TAREAS (task_tracker)
1. **Inicialización Obligatoria**: Para toda solicitud, DEBES inicializar tu plan de trabajo llamando a `task_tracker` con `action="init"`, especificando tu `agent_name="BashAgent"` y la lista de tareas en `plan`.
2. **Actualización de Progreso**: Cada vez que completes una tarea o cambie el estado de una tarea, DEBES llamar inmediatamente a `task_tracker` con `action="update"`, especificando el `task_index` y el nuevo `status` ("completed", "in_progress", "failed").
3. **Finalización**: Al terminar todo el trabajo solicitado, DEBES registrar la finalización llamando a `task_tracker` con `action="update"` para marcar la última tarea como completada.
¡NUNCA procedas con ninguna tarea o acción sin registrarla y mantenerla al día en `task_tracker`!\n"""

    # Añadir reporte de estado de memoria al final del mensaje de sistema
    try:
        # memory_report = get_memory_status_report()
        # base_content += f"\n\n{memory_report}\n"
        pass
    except Exception as e:
        logger.warning(f"[Memory] No se pudo generar reporte de memoria: {e}")
    return SystemMessage(content=base_content)

# Para mantener compatibilidad con imports si los hay, aunque ahora usaremos la función get_system_message
SYSTEM_MESSAGE = None

from kogniterm.core.exceptions import UserConfirmationRequired # Importación correcta

# --- Nodos del Grafo ---

from rich.live import Live # Importar Live
from rich.markdown import Markdown # Importar Markdown
from rich.padding import Padding # Nueva importación
from rich.status import Status # ¡Nueva importación!
def handle_tool_confirmation(state: AgentState, llm_service: LLMService):
    """
    Maneja la respuesta de confirmación del usuario para una operación de herramienta.
    Si se aprueba, re-ejecuta la herramienta.
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, ToolMessage):
        # Esto no debería pasar si el flujo es correcto
        console.print("[bold red]Error: handle_tool_confirmation llamado sin un ToolMessage.[/bold red]")
        state.reset_tool_confirmation()
        return state

    tool_message_content = last_message.content
    tool_id = state.tool_call_id_to_confirm # Usar el tool_id guardado

    # Asumimos que el ToolMessage de confirmación tiene un formato específico
    # ej. "Confirmación de usuario: Aprobado para 'escribir en el archivo ...'".
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
                # Si es file_update_tool o advanced_file_editor_tool, añadir el parámetro confirm=True
                if tool_name in {"file_update_tool", "advanced_file_editor", "advanced_file_editor_tool", "sophisticated_editor_tool"}:
                    tool_args["confirm"] = True
                    # Si el contenido original se pasó como parte de tool_args,
                    # debemos asegurarnos de que el 'content' que se pasa para la re-ejecución
                    # sea el contenido final que el usuario aprobó (que debería estar en tool_args).
                    # No necesitamos el diff aquí, solo el contenido final.
                    # El diff ya se mostró al usuario para la confirmación.
                    # Si el content es None, significa que el LLM no lo proporcionó, lo cual es un error.
                    if tool_requires_content_for_confirmation(tool_name, tool_args) and tool_args.get("content") is None:
                        error_output = "Error: El contenido a actualizar no puede ser None."
                        state.add_message(ToolMessage(content=error_output, tool_call_id=tool_id))
                        console.print(f"[bold red]❌ {error_output}[/bold red]")
                        state.reset_tool_confirmation()
                        return state
    
                try:
                    raw_tool_output = llm_service._invoke_tool_with_interrupt(tool, tool_args)
                    # ASEGURAR QUE EL CONTENIDO SEA STRING
                    if isinstance(raw_tool_output, (dict, list)):
                        tool_output_str = json.dumps(raw_tool_output)
                    else:
                        tool_output_str = str(raw_tool_output)
                    
                    tool_messages = [ToolMessage(content=tool_output_str, tool_call_id=tool_id)]
                    state.add_messages(tool_messages)
                    console.print(f"[green]✨ Herramienta '{tool_name}' re-ejecutada con éxito.[/green]")
    

                except InterruptedError:
                    console.print("[bold yellow]⚠️ Re-ejecución de herramienta interrumpida por el usuario. Volviendo al input.[/bold yellow]")
                    state.reset_temporary_state() # Limpiar el estado temporal del agente
                    return state # Terminar la ejecución de herramientas y volver al input del usuario
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

    state.reset_tool_confirmation() # Limpiar el estado de confirmación
    state.tool_call_id_to_confirm = None # Limpiar también el tool_call_id guardado
    return state



def verification_node(state: AgentState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    """Verifica la integridad de los archivos modificados tras una ejecución de herramientas.
    Ejecuta py_compile para Python sin involucrar al LLM, cortando un ciclo de tool calls.
    """
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

    if not modified_files:
        return {"messages": state.messages}

    if terminal_ui and hasattr(terminal_ui, "update_live"):
        from kogniterm.terminal.themes import Icons
        from rich.padding import Padding
        # Añadir Padding (0, 0) con expand=True y padding interno (0, 4) para mantener la alineación de la TUI
        terminal_ui.update_live(Padding(Panel(f"{Icons.CODE} [bold]Verificando sintaxis de archivos modificados...[/bold]", border_style="yellow", padding=(0, 4), expand=True), (0, 0)))
        terminal_ui.stop_live()

    verification_results = []

    for file_path in modified_files:
        if file_path.endswith(".py"):
            try:
                import py_compile
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


# ---------------------------------------------------------------------------
# task_tracker_node: Ejecuta tool_calls de task_tracker directamente en Python
# sin pasar por el LLM ni por el ThreadPoolExecutor del execute_tool_node.
# Esto elimina el ciclo execute_tool → LLM para una herramienta determinista.
# ---------------------------------------------------------------------------

def task_tracker_node(
    state: AgentState,
    llm_service: LLMService,
    terminal_ui: Optional[TerminalUI] = None,
):
    """Nodo del grafo que intercepta y ejecuta directamente las tool_calls
    de ``task_tracker`` sin hacer un round-trip al LLM.

    - Procesa todas las llamadas ``task_tracker`` del turno actual.
    - Genera los ``ToolMessage`` correspondientes e inyecta el estado del
      ``_llm_service`` en el módulo para que la TUI se actualice.
    - Deja intactas las demás tool_calls del mismo turno para que
      ``execute_tool_node`` las maneje a continuación.
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return state

    tt_calls = [tc for tc in last_message.tool_calls if tc["name"] == "task_tracker"]
    if not tt_calls:
        return state

    # Asegurar que el módulo esté cargado y _llm_service inyectado
    _ensure_task_tracker_module_loaded()
    if _task_tracker_module and hasattr(_task_tracker_module, "_llm_service"):
        _task_tracker_module._llm_service = llm_service

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
                # Fallback: intentar via skill_manager
                tool = llm_service.get_tool("task_tracker") if llm_service else None
                result = str(tool(**args)) if tool else "Error: task_tracker no disponible."
        except Exception as exc:
            result = f"Error en task_tracker_node: {exc}"
            logger.warning(f"task_tracker_node: excepción al ejecutar {tc['id']}: {exc}")

        tool_messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
        logger.info(f"task_tracker_node: call '{args.get('action')}' procesada directamente (id={tc['id']}).")

    state.add_messages(tool_messages)
    return {"messages": state.messages}


def route_tools(state: AgentState) -> str:
    """Router que decide si el turno requiere el nodo rápido task_tracker_node
    o el execute_tool_node genérico.

    Regla:
    - Si el último AIMessage contiene al menos una tool_call ``task_tracker``
      → ``task_tracker_node`` (ejecución directa, sin LLM).
    - En caso contrario → ``execute_tool`` (flujo normal).
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return END
    for tc in last_message.tool_calls:
        if tc["name"] == "task_tracker":
            return "task_tracker_node"
    return "execute_tool"


def should_continue_after_tt(state: AgentState) -> str:
    """Router de salida del task_tracker_node.

    Tras procesar las calls de task_tracker, verifica si quedan tool_calls
    pendientes (de otra herramienta) en el mismo turno o si debe volver
    directamente a call_model.
    """
    if state.critical_loop_detected or state.stop_requested:
        return END
    if (state.command_to_confirm is not None or
            state.file_update_diff_pending_confirmation is not None or
            state.tool_pending_confirmation is not None or
            state.tool_code_to_confirm is not None):
        return END

    # Buscar el último AIMessage para ver si quedan calls pendientes
    last_ai: Optional[AIMessage] = None
    for msg in reversed(state.messages):
        if isinstance(msg, AIMessage):
            last_ai = msg
            break

    if last_ai and last_ai.tool_calls:
        # Determinar IDs ya procesados (ToolMessages añadidos en este nodo)
        processed_ids = {msg.tool_call_id for msg in state.messages if isinstance(msg, ToolMessage)}
        remaining = [tc for tc in last_ai.tool_calls if tc["id"] not in processed_ids]
        if remaining:
            return "execute_tool"

    # Sin calls pendientes → volver al modelo
    return "call_model"


def call_model_node(state: AgentState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None, interrupt_queue: Optional[queue.Queue] = None):

    """
    Llama al modelo de lenguaje y maneja la salida en streaming,
    mostrando el pensamiento y la respuesta en tiempo real.
    """
    # Resetear flag de parada al inicio del nodo
    state.stop_requested = False
    
    # Usar la consola de terminal_ui si está disponible, de lo contrario usar la global
    current_console = terminal_ui.console if terminal_ui else console
    
    # --- Lógica de Detección de Bucles (específica de Bash) ---
    if len(state.tool_call_history) >= 4:
        last_calls = list(state.tool_call_history)[-4:]
        if all(tc['name'] == last_calls[0]['name'] and tc['args_hash'] == last_calls[0]['args_hash'] for tc in last_calls):
            current_console.print("[bold red]🚨 ¡BUCLE CRÍTICO DETECTADO! El agente está repitiendo la misma acción exactamente.[/bold red]")
            error_msg = "He detectado que estoy en un bucle infinito repitiendo la misma acción. Deteniendo para evitar consumo innecesario. Por favor, intenta reformular tu petición o revisa los logs."
            state.add_message(AIMessage(content=error_msg))
            # Activar la bandera de bucle crítico para terminar el flujo
            state.critical_loop_detected = True
            # Limpiar el historial de llamadas a herramientas para evitar que la advertencia se repita
            state.clear_tool_call_history()
            return {
                "messages": state.messages,
                "command_to_confirm": None,
                "tool_call_id_to_confirm": None,
                "critical_loop_detected": True
            }

    # --- Pre-procesamiento de referencias a archivos (específico de Bash) ---
    if state.messages and isinstance(state.messages[-1], HumanMessage):
        workspace_directory = os.getcwd()
        processed_content = process_file_references(state.messages[-1].content, workspace_directory)
        state.messages[-1] = HumanMessage(content=processed_content)

    # --- Obtener system message dinámico (específico de Bash) ---
    # get_system_message devuelve un SystemMessage; extraer el string de contenido
    # porque BaseAgentNode.call_model espera un str, no un SystemMessage.
    _sys_msg = get_system_message(llm_service)
    system_prompt = _sys_msg.content if hasattr(_sys_msg, "content") else str(_sys_msg)

    # --- Delegar streaming y renderizado a BaseAgentNode ---
    # BaseAgentNode.call_model maneja: streaming, renderizado en tiempo real (TUI/CLI),
    # detección de bucles genérica, keyboard handler, y actualización del estado.
    result = BaseAgentNode.call_model(
        state=state,
        llm_service=llm_service,
        system_prompt=system_prompt,
        terminal_ui=terminal_ui,
        interrupt_queue=interrupt_queue
    )
    
    # --- Post-procesamiento específico de Bash ---
    # Extraer el AIMessage del resultado (BaseAgentNode ya lo añadió a state.messages)
    final_ai_message = None
    for msg in reversed(state.messages):
        if isinstance(msg, AIMessage):
            final_ai_message = msg
            break
    
    command_to_confirm = None
    tool_call_id_to_confirm = None
    
    if final_ai_message and final_ai_message.tool_calls:
        # Capturar el tool_call_id del primer tool_call
        tool_call_id_to_confirm = final_ai_message.tool_calls[0]['id']
        
        # Buscar execute_command para confirmación
        for tc in final_ai_message.tool_calls:
            if tc['name'] == 'execute_command':
                command_to_confirm = tc['args'].get('command')
                break
    
    # Guardar historial si no hay tool_calls (respuesta final)
    if not (final_ai_message and final_ai_message.tool_calls):
        llm_service._save_history(state.messages)
    
    # Actualizar el resultado con los campos específicos de Bash
    result["command_to_confirm"] = command_to_confirm
    result["tool_call_id_to_confirm"] = tool_call_id_to_confirm
    
    return result

def call_task_tracker(
    llm_service: LLMService,
    action: str,
    agent_name: str = None,
    plan: list = None,
    task_index: int = None,
    status: str = None,
    updates: list = None,
) -> str:
    """Convenience helper to invoke the bundled task_tracker skill.

    Ensures the skill is loaded, calls the tool and returns its textual output.

    Para aplicar varias actualizaciones en una sola llamada, pasa ``updates``
    con la lista ``[{"task_index": int, "status": str}, ...]`` junto con
    ``action="update"``.
    """
    try:
        # Asegurar que la skill esté cargada
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

        # Preferir invoke wrapper si existe (SkillLoader lo inyecta)
        if hasattr(tool, 'invoke') and callable(getattr(tool, 'invoke')):
            result = tool.invoke(args)
            # Si devuelve un generador, concatenar
            if hasattr(result, '__iter__') and not isinstance(result, str):
                out = ''.join([str(p) for p in result])
            else:
                out = str(result)
        else:
            # Llamada directa
            out = str(tool(**args))

        return out
    except Exception as e:
        return f"Error llamando a task_tracker: {e}"


def _print_tool_notification(tool_name: str, bajada: str, skill_name: str, is_tui: bool, terminal_ui: TerminalUI, is_interactive: bool = False):
    """Emite la notificación visual para una herramienta. Extrae la lógica repetida del loop."""
    try:
        from kogniterm.terminal.themes import Icons, ColorPalette
        from rich.text import Text
        if is_tui:
            terminal_ui.print_tool_notification(tool_name, bajada, skill_name=skill_name)
        else:
            verb = "Preparando comando de terminal" if is_interactive else "Ejecutando herramienta"
            label = Text.from_markup(
                f"\n[bold {ColorPalette.SECONDARY}]{Icons.TOOL} {verb}:[/]"
                f" [{ColorPalette.SECONDARY_LIGHT}]{tool_name}[/{ColorPalette.SECONDARY_LIGHT}]"
            )
            if bajada:
                label.append("\n  ")
                label.append(Text.from_markup(f"[italic {ColorPalette.TEXT_SECONDARY}]└─ {bajada}[/italic]"))
            terminal_ui.console.print(label)
    except (ImportError, Exception):
        verb = "Preparando comando" if is_interactive else "Ejecutando herramienta"
        terminal_ui.console.print(f"\n[bold blue]🛠️ {verb}:[/bold blue] [yellow]{tool_name}[/yellow]")


def execute_tool_node(state: AgentState, llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None, command_approval_handler=None):
    """Ejecuta las herramientas solicitadas por el modelo.

    Estrategia de paralelismo:
    - Las herramientas se particionan en paralelas (todo excepto execute_command)
      e interactivas (execute_command).
    - Metadata de herramientas (descripciones, skill_name) se obtiene en paralelo
      antes de hacer submit al executor principal.
    - Todas las herramientas paralelas se envían al executor de una sola vez (batch
      submit) para maximizar concurrencia real.
    - execute_command se presenta al usuario DESPUÉS de que las herramientas
      paralelas terminan, eliminando el descarte prematuro anterior.
    """
    if command_approval_handler is None and hasattr(llm_service, 'skill_manager') and hasattr(llm_service.skill_manager, 'approval_handler'):
        command_approval_handler = llm_service.skill_manager.approval_handler

    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return state

    is_tui = terminal_ui.is_tui if (terminal_ui and hasattr(terminal_ui, "is_tui")) else False
    tool_messages = []

    # --- PASO 1: Particionar herramientas ---
    # Las interactivas (execute_command) se ejecutan al final para no bloquear las paralelas.
    parallel_calls = [tc for tc in last_message.tool_calls if tc['name'] != 'execute_command']
    interactive_calls = [tc for tc in last_message.tool_calls if tc['name'] == 'execute_command']

    # --- PASO 2: Registrar historial para detección de bucles (todas a la vez) ---
    for tc in last_message.tool_calls:
        try:
            args_hash = json.dumps(tc['args'], sort_keys=True)
        except TypeError:
            args_hash = str(tc['args'])
        state.tool_call_history.append({"name": tc['name'], "args_hash": args_hash})

    # --- PASO 3: Verificar interrupción temprana ---
    if interrupt_queue and not interrupt_queue.empty():
        interrupt_queue.get()
        terminal_ui.console.print("[bold yellow]⚠️ Interrupción detectada. Volviendo al input del usuario.[/bold yellow]")
        state.stop_requested = True
        state.reset_temporary_state()
        return state

    # --- PASO 4: Pre-fetch de metadata de herramientas ---
    # Obtener tool instances, skill_names y descripciones de forma directa.
    # Al ser operaciones puramente en memoria, hacerlo de forma secuencial evita
    # el overhead innecesario de inicializar y gestionar un ThreadPoolExecutor.
    metadata_map: Dict[str, tuple] = {}  # tool_id -> (skill_name, bajada)
    for tc in parallel_calls + interactive_calls:
        tool = llm_service.get_tool(tc['name'])
        skill_name = ""
        bajada = ""
        if tool:
            if hasattr(llm_service, 'skill_manager'):
                skill = llm_service.skill_manager.get_skill_for_tool(tc['name'])
                if skill:
                    skill_name = skill.name
            bajada = get_tool_action_description(tool, tc['args'])
        metadata_map[tc['id']] = (skill_name, bajada)

    # --- PASO 5: Emitir notificaciones visuales batch para herramientas paralelas ---
    for tc in parallel_calls:
        skill_name, bajada = metadata_map.get(tc['id'], ("", ""))
        _print_tool_notification(tc['name'], bajada, skill_name, is_tui, terminal_ui, is_interactive=False)

    # --- PASO 6: Iniciar KeyboardHandler (solo cuando no hay interactivas y no es TUI) ---
    kh = None
    if not interactive_calls and not is_tui:
        kh = KeyboardHandler(interrupt_queue)
        kh.start()

    try:
        llm_service._current_agent_state = state

        # --- PASO 7: Submit batch al executor principal ---
        executor = ThreadPoolExecutor(max_workers=min(len(parallel_calls), 10) if parallel_calls else 1)
        futures_map: Dict = {}  # future -> tool_id
        for tc in parallel_calls:
            logger.info(f"Agente: Enviando herramienta '{tc['name']}' al executor.")
            future = executor.submit(ToolExecutor.execute_single_tool, tc, llm_service, terminal_ui, getattr(state, 'delegation_context', None))
            futures_map[future] = tc['id']

        logger.info(f"Agente: Esperando resultados de {len(futures_map)} herramientas en paralelo.")
        for future in as_completed(futures_map):
            try:
                tool_id, content, exception = future.result()
                logger.info(f"Agente: Herramienta con ID {tool_id} completada.")
            except Exception as e:
                logger.error(f"Error al obtener resultado del future: {e}")
                continue
            if exception:
                if isinstance(exception, UserConfirmationRequired):
                    # SI ESTAMOS EN TUI: Burbujear la petición al hilo principal
                    # Esto evita el uso de loops anidados (nest_asyncio) en hilos worker
                    # que causan cierres silenciosos.
                    if terminal_ui and getattr(terminal_ui, "is_tui", False):
                        logger.info(f"Agente: Postergando confirmación de '{exception.tool_name}' para el hilo principal TUI.")
                        state.tool_pending_confirmation = exception.tool_name
                        state.tool_args_pending_confirmation = exception.tool_args
                        state.tool_call_id_to_confirm = tool_id
                        state.file_update_diff_pending_confirmation = exception.raw_tool_output
                        
                        executor.shutdown(wait=False)
                        return {
                            "messages": state.messages,
                            "tool_pending_confirmation": exception.tool_name,
                            "tool_args_pending_confirmation": exception.tool_args,
                            "tool_call_id_to_confirm": tool_id,
                            "file_update_diff_pending_confirmation": exception.raw_tool_output
                        }

                    # MODO CLI (O NO-TUI): Manejar la confirmación DIRECTAMENTE sin involucrar al LLM
                    # Esto evita que el LLM genere texto antes de que el usuario pueda confirmar
                    
                    # Preparar raw_output para el handler
                    raw_tool_output = exception.raw_tool_output or {}
                    
                    # Obtener tool_name del raw_output o de la excepción
                    tool_name = raw_tool_output.get("operation", exception.tool_name)
                    
                    # Determinar si es una operación de archivo
                    is_file_update = tool_name in [
                        "file_operations", "file_update_tool", "file_update",
                        "advanced_file_editor", "advanced_file_editor_tool",
                        "write_file_tool", "write_file", "file_write", "file_write_tool", "write",
                        "append_file_tool",
                    ]
                    
                    # Crear contenido del panel de confirmación
                    panel_content = f"**{exception.message}**"
                    
                    if is_file_update and raw_tool_output.get("diff"):
                        panel_content += f"\n\n**Diff:**\n{raw_tool_output['diff']}"
                    
                    # Solicitar aprobación usando command_approval_handler si está disponible
                    if command_approval_handler:
                        try:
                            # Preparar raw_output para el handler con el formato esperado
                            handler_raw_output = {
                                "status": "requires_confirmation",
                                "action_description": exception.message,
                                "diff": raw_tool_output.get("diff", ""),
                                "path": exception.tool_args.get("path", "") if exception.tool_args else "",
                                "operation": tool_name,
                                "args": exception.tool_args
                            }
                            
                            # Establecer el tool_call_id_to_confirm para que el handler pueda sincronizar el historial
                            state.tool_call_id_to_confirm = tool_id
                            
                            # Llamar al método correcto: handle_command_approval
                            # Este método maneja la confirmación de forma apropiada según el contexto (TUI/CLI)
                            # El handler ya ejecuta la herramienta y añade el ToolMessage al historial
                            handler_result = command_approval_handler.handle_command_approval(
                                command_to_execute="",  # No es un comando bash en este caso
                                raw_tool_output=handler_raw_output,
                                tool_name=tool_name,
                                original_tool_args=exception.tool_args
                            )
                            # El handler ya ejecutó la herramienta y actualizó el historial
                            executor.shutdown(wait=False)
                            llm_service._save_history(state.messages)
                            return {
                                "messages": state.messages
                            }
                        except Exception as e:
                            terminal_ui.console.print(f"[bold red]Error al solicitar confirmación: {e}[/bold red]")
                            # Continuar con el flujo normal de ejecución manual
                    else:
                        # Si no hay command_approval_handler, la confirmación se maneja por el flujo normal
                        # Ejecutar la operación directamente (manual o fallback)
                        if tool_name == "file_operations":
                            # Determinar si es write o delete
                            operation = exception.tool_args.get("operation", "write_file")
                            if operation == "write_file":
                                _ft_mod = _load_file_ops_module("tool")
                                write_result = _ft_mod._write_file(
                                    exception.tool_args.get("path", ""),
                                    exception.tool_args.get("content", "")
                                )
                                content = write_result
                            elif operation == "delete_file":
                                _ft_mod = _load_file_ops_module("tool")
                                delete_result = _ft_mod._delete_file(
                                    exception.tool_args.get("path", "")
                                )
                                content = delete_result
                        elif tool_name in ["file_update_tool", "file_update"]:
                            from kogniterm.skills.bundled.file_update.scripts.tool import _apply_file_update
                            update_result = _apply_file_update(
                                exception.tool_args.get("path", ""),
                                exception.tool_args.get("content", "")
                            )
                            content = update_result
                        elif tool_name in ["advanced_file_editor", "advanced_file_editor_tool"]:
                            from kogniterm.skills.bundled.advanced_file_editor.scripts.tool import advanced_file_editor_tool
                            args_to_pass = dict(exception.tool_args)
                            args_to_pass["confirm"] = True
                            edit_result = advanced_file_editor_tool(**args_to_pass)
                            content = edit_result
                        else:
                            # Para otras herramientas, usar el contenido existente
                            content = None
                        
                        # ASEGURAR QUE EL CONTENIDO SEA STRING
                        if content is not None:
                            if isinstance(content, (dict, list)):
                                content = json.dumps(content)
                            else:
                                content = str(content)
                            
                            tool_message = ToolMessage(content=content, tool_call_id=tool_id)
                            tool_messages.append(tool_message)
                            state.add_message(tool_message)
                            terminal_ui.print_message("✅ Acción ejecutada por el usuario.", style="green")
                        else:
                            # Usuario denegó o no hubo command_approval_handler
                            content = f"Operación cancelada por el usuario: {exception.message}"
                            tool_message = ToolMessage(content=content, tool_call_id=tool_id)
                            tool_messages.append(tool_message)
                            state.add_message(tool_message)
                            terminal_ui.print_message("❌ Acción cancelada por el usuario.", style="yellow")
                        
                        executor.shutdown(wait=False)
                        llm_service._save_history(state.messages)
                        return {
                            "messages": state.messages
                        }
                    
                elif isinstance(exception, InterruptedError):
                    terminal_ui.console.print("[bold yellow]⚠️ Ejecución de herramienta interrumpida por el usuario. Volviendo al input.[/bold yellow]")
                    state.stop_requested = True
                    state.reset_temporary_state()
                    executor.shutdown(wait=False)
                    llm_service._save_history(state.messages)
                    return {
                        "messages": state.messages,
                        "stop_requested": True
                    }
                else:
                    tool_messages.append(ToolMessage(content=content, tool_call_id=tool_id))
            else:
                # Procesamiento especializado para agentes paralelos (DeepCoder/Researcher)
                if "<coder_analysis>" in content or "<researcher_analysis>" in content or "<parallel_agents_results>" in content:
                    clean_content = f"--- RESULTADOS DE AGENTES PARALELOS ---\n\n{content}\n\n--- FIN DE RESULTADOS ---\n\n[SISTEMA: Estos son los resultados consolidados de tus sub-agentes. Analízalos profesionalmente como KogniTerm, sin adoptar sus roles.]"
                else:
                    # Limpieza estándar para herramientas normales
                    clean_content = content.replace("## 🔬 Informe de Deep Research", "").strip()
                
                tool_messages.append(ToolMessage(content=clean_content, tool_call_id=tool_id))
                # Lógica para herramientas que requieren confirmación
                tool_call_info = next(tc for tc in last_message.tool_calls if tc['id'] == tool_id)
                tool_name = tool_call_info['name']
                tool_args = tool_call_info['args']
                
                # Para herramientas que no son execute_command (que ya manejamos arriba), 
                # verificamos si requieren confirmación basada en su output JSON
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
                            executor.shutdown(wait=False)
                            state.add_messages(tool_messages)
                            llm_service._save_history(state.messages)
                            return {
                                "messages": state.messages,
                                "tool_pending_confirmation": state.tool_pending_confirmation,
                                "tool_args_pending_confirmation": state.tool_args_pending_confirmation,
                                "tool_call_id_to_confirm": state.tool_call_id_to_confirm,
                                "file_update_diff_pending_confirmation": state.file_update_diff_pending_confirmation
                            }
                    except json.JSONDecodeError:
                        pass

        executor.shutdown(wait=True)
        state.add_messages(tool_messages)

        # --- PASO 8: Procesar execute_command DESPUÉS de las herramientas paralelas ---
        # Así las herramientas de lectura/búsqueda ya terminaron antes de que el usuario
        # tenga que confirmar el comando de terminal.
        if interactive_calls:
            tc = interactive_calls[0]  # Solo puede haber uno significativo
            skill_name, bajada = metadata_map.get(tc['id'], ("", ""))
            _print_tool_notification(tc['name'], bajada, skill_name, is_tui, terminal_ui, is_interactive=True)
            state.command_to_confirm = tc['args'].get('command', '')
            state.tool_call_id_to_confirm = tc['id']
            llm_service._save_history(state.messages)
            return {
                "messages": state.messages,
                "command_to_confirm": state.command_to_confirm,
                "tool_call_id_to_confirm": state.tool_call_id_to_confirm,
            }

        # Guardar historial al finalizar la ejecución de herramientas
        llm_service._save_history(state.messages)

        return {
            "messages": state.messages,
            "command_to_confirm": getattr(state, 'command_to_confirm', None),
            "tool_call_id_to_confirm": getattr(state, 'tool_call_id_to_confirm', None),
            "file_update_diff_pending_confirmation": getattr(state, 'file_update_diff_pending_confirmation', None)
        }

    finally:
        if kh:
            kh.stop()

        # Clear current agent state
        llm_service._current_agent_state = None

def learning_node(state: AgentState, llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    """
    Nodo de aprendizaje que analiza la interacción reciente para extraer 
    preferencias y personalizaciones del usuario de forma persistente.
    """
    # 1. Verificar si es el final de un turno (sin herramientas pendientes)
    if not state.messages or not isinstance(state.messages[-1], AIMessage):
        return state

    # No aprender si hubo errores críticos o interrupciones
    if state.critical_loop_detected or state.stop_requested:
        return state

    # No aprender si el AI propuso herramientas (esperar a que se ejecuten y den respuesta final)
    if state.messages[-1].tool_calls:
        return state

    # 2. Extraer ventana de contexto para análisis (últimos 4 mensajes)
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
            response_gen = llm_service.provider_manager.execute(
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
            # Limpiar formato
            learned_text = re.sub(r'^[-\*\s]+', '', learned_text)
            
            # Guardar en .kogniterm/instructions.md
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
        pass # Aprendizaje silencioso, no debe interrumpir el flujo principal

    return state

# --- Lógica Condicional del Grafo ---

def should_continue(state: AgentState) -> str:
    """Decide si continuar llamando a herramientas o finalizar."""
    # Si se detectó un bucle crítico o parada solicitada, terminar el flujo inmediatamente
    if state.critical_loop_detected or state.stop_requested:
        return END
    
    last_message = state.messages[-1]
    
    # Si hay una herramienta o comando pendiente de confirmación, siempre terminamos el grafo aquí
    # para que la terminal o la UI puedan manejar la interacción.
    if (state.command_to_confirm is not None or 
        state.file_update_diff_pending_confirmation is not None or 
        state.tool_pending_confirmation is not None or 
        state.tool_code_to_confirm is not None):
        return END

    # Si el último mensaje del AI tiene tool_calls, ejecutar herramientas
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "execute_tool"
    # Si el último mensaje es un ToolMessage (resultado de una herramienta),
    # volver a llamar al modelo para que genere una respuesta final.
    elif isinstance(last_message, ToolMessage):
        return "call_model"
    else:
        return END

# --- Construcción del Grafo ---

def create_bash_agent(llm_service: LLMService, terminal_ui: TerminalUI, interrupt_queue: Optional[queue.Queue] = None, command_approval_handler=None):
    # Pre-cargar el módulo task_tracker para que el primer init sea instantáneo
    _ensure_task_tracker_module_loaded()

    bash_agent_graph = StateGraph(AgentState)

    bash_agent_graph.add_node("call_model", functools.partial(call_model_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue))
    bash_agent_graph.add_node("execute_tool", functools.partial(execute_tool_node, llm_service=llm_service, terminal_ui=terminal_ui, interrupt_queue=interrupt_queue, command_approval_handler=command_approval_handler))
    bash_agent_graph.add_node("verify", functools.partial(verification_node, llm_service=llm_service, terminal_ui=terminal_ui))
    bash_agent_graph.add_node("task_tracker_node", functools.partial(task_tracker_node, llm_service=llm_service, terminal_ui=terminal_ui))

    bash_agent_graph.set_entry_point("call_model")

    # call_model → route_tools: separa task_tracker del resto de herramientas
    bash_agent_graph.add_conditional_edges(
        "call_model",
        route_tools,
        {
            "task_tracker_node": "task_tracker_node",
            "execute_tool": "execute_tool",
            END: END
        }
    )

    # task_tracker_node → si quedan otras calls → execute_tool; si no → call_model
    bash_agent_graph.add_conditional_edges(
        "task_tracker_node",
        should_continue_after_tt,
        {
            "execute_tool": "execute_tool",
            "call_model": "call_model",
            END: END
        }
    )

    bash_agent_graph.add_conditional_edges(
        "execute_tool",
        should_continue,
        {
            "call_model": "verify",   # pasar por verificación antes de volver al modelo
            "execute_tool": "execute_tool",
            END: END
        }
    )

    bash_agent_graph.add_edge("verify", "call_model")

    return bash_agent_graph.compile()


def create_learning_agent(llm_service: LLMService, terminal_ui: Optional[TerminalUI] = None):
    """
    Crea el grafo de aprendizaje posterior que analiza la sesión y
    persiste las preferencias del usuario de forma independiente al flujo de respuesta.
    """
    learning_graph = StateGraph(AgentState)
    learning_graph.add_node("learning", functools.partial(learning_node, llm_service=llm_service, terminal_ui=terminal_ui))
    learning_graph.set_entry_point("learning")
    learning_graph.add_edge("learning", END)
    return learning_graph.compile()

