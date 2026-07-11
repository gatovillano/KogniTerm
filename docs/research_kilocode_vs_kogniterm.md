# Investigación Comparativa: Arquitectura de Agentes — KiloCode CLI vs KogniTerm

> Documento generado por `BashAgent` como parte de la tarea de investigación profunda.
> Fecha de análisis: sesión de investigación sobre el repo clonado `Kilo-Org/kilocode` (paquete `packages/opencode`) y el código local de `kogniterm/`.

---

## 0. Resumen Ejecutivo

| Dimensión | **KiloCode CLI** | **KogniTerm** |
|---|---|---|
| Lenguaje / Runtime | TypeScript (Node), **Effect** (Layers/Context/State) | Python, **LangGraph** (`StateGraph`/`END`) |
| Motor LLM | Vercel AI SDK (`streamText`/`generateObject`) + runtime nativo | `llm_service.invoke()` (generador streaming) sobre google-generativeai / anthropic |
| Definición de agentes | **Config-driven** (Markdown `.kilo/agent/*.md`) | **Code-driven** (grafos LangGraph construidos en Python) |
| Bucle agente | `session/llm.ts` + herramienta `task` + `agent_manager` | `create_bash_agent()` → nodos `call_model`/`execute_tool`/`verify` |
| Subagentes | `task` (waves paralelas), `agent_manager` (worktree/local) | `call_agent` / `call_agents_parallel` + `DelegationManager` (RBAC) |
| Permisos | Mapas `bash`/`readOnlyBash` (`allow`/`ask`/`deny`) + herencia `deny` | `command_approval_handler` + excepción `UserConfirmationRequired` + roles `LEAF`/`ORCHESTRATOR` |
| UI | Hono (HTTP/SSE) + SolidJS + OpenTUI | Rich (CLI) + prompt-toolkit (TUI) + server WebSocket |
| Memoria / Aprendizaje | `KiloSession`, plugins, skills, MCP | `.kogniterm/llm_context.md`, `MessageManager`, nodo `learning` |
| Madurez | Fork de opencode/Cline/Roo, ~25.9k★ | Proyecto local en evolución |

**Conclusión rápida:** KiloCode es una arquitectura *declarativa y basada en efectos* (TypeScript/Effect) con agentes configurados en Markdown y orquestación vía herramientas (`task`, `agent_manager`). KogniTerm es una arquitectura *imperativa y basada en grafos* (Python/LangGraph) donde cada agente es un grafo compilado en código y la delegación está gobernada por un `DelegationManager` con RBAC y límites de profundidad/concurrencia.

---

## 1. KiloCode CLI — Caracterización del Agente

### 1.1 Stack y origen
- Repositorio: `Kilo-Org/kilocode` (~25.9k★ en GitHub). Fork de `opencode` / `Cline` / `Roo`.
- Paquete analizado: `packages/opencode` (TypeScript).
- Tecnologías: **Effect** (capa funcional con `Layer`, `Context`, `State`), **Vercel AI SDK** (`streamText`, `generateObject`), **Hono** (servidor HTTP/SSE), **SolidJS + OpenTUI** (TUI), **Zod / Effect Schema** (validación).

### 1.2 Configuración de agentes (`src/config/agent.ts`)
Los agentes se definen en **Markdown** (`.kilo/agent/*.md` o global `agent/*.md`). El esquema `Info` incluye:
```
name, displayName, source, model, variant, temperature,
tools, permission, mode (primary | subagent | all), prompt
```
- Soporta "modes" vía `loadMode`.
- Un agente puede ser **primario** (orquestador) o **subagente**.

### 1.3 Runtime del agente (`src/agent/agent.ts`)
- Construido sobre **Effect + Layer + Provider**.
- Generación dinámica de agentes por LLM: `generateObject` con el esquema `GeneratedAgent`.
- Integra `Plugin`, `Skill` y `MCP`.

### 1.4 Orquestación y subagentes
- **`src/tool/task.ts`** — Herramienta `task` que lanza subagentes (foreground/background). Implementa "waves" de paralelización y propagación de costos al padre (`KiloCostPropagation`).
- **`src/kilocode/tool/agent-manager.ts`** — Herramienta `agent_manager` para spawnear múltiples sesiones (modo `worktree`/`local`) con modelos específicos por tarea.
- **`src/agent/subagent-permissions.ts`** — `deriveSubagentSessionPermission` hereda reglas `deny` del agente/sesión padre al subagente.
- Prompts estratégicos en `src/agent/prompt/`:
  - `orchestrator.txt` (descompone en waves, delega a `explore`/`general`)
  - `debug.txt` (diagnóstico sistemático)
  - `explore.txt`, `ask.txt`

### 1.5 Permisos Bash (`src/kilocode/agent/index.ts`)
- Mapas `bash` y `readOnlyBash` con reglas granulares `allow`/`ask`/`deny` por patrón de comando (ej. `cat *`: allow, `*`: ask).

### 1.6 Bucle LLM (`src/session/llm.ts`)
- Streaming unificado (AI SDK o runtime nativo) con `AbortController`.
- Integración `KiloSession` para telemetría/export.

---

## 2. KogniTerm — Caracterización del Agente

### 2.1 Stack y modelo de ejecución
- **Python** + **LangGraph** (`StateGraph`, `END` de `langgraph.graph`).
- Mensajes con `langchain_core.messages` (`AIMessage`, `ToolMessage`, `HumanMessage`, `SystemMessage`).
- UI: **Rich** (CLI clásica), **prompt-toolkit** (TUI), y **server WebSocket** (`session_pool.py`) para modo remoto.
- Proveedores LLM: `google-generativeai`, `anthropic` (gestionados por `llm_service.invoke()`).

### 2.2 Estado del grafo — `AgentState` (`core/agent_state.py`)
Dataclass que fluye por el grafo. Campos clave:
```python
messages: List[BaseMessage]
command_to_confirm / tool_call_id_to_confirm   # confirmación de shell
tool_pending_confirmation / file_update_diff_pending_confirmation  # confirmación de archivos
autonomous_approvals: bool                      # subagentes autónomos
delegation_context: Optional[DelegationContext] # contexto RBAC del subagente
tool_call_history: deque(maxlen=5)              # detección de bucles
critical_loop_detected: bool
completed / result                              # finalización vía complete_task
current_agent_mode: str = "bash"
file_hash_cache                                 # detección de race conditions
```
Incluye un `MessageManager` (inspirado explícitamente en el MessageManager de KiloCode, ver línea 125 del archivo) y `HistoryManager` para persistencia.

### 2.3 Núcleo del orquestador — `bash_agent.py`
`create_bash_agent()` compila un grafo LangGraph:
```python
bash_agent_graph = StateGraph(AgentState)
bash_agent_graph.add_node("call_model", ...)
bash_agent_graph.add_node("execute_tool", ...)
bash_agent_graph.add_node("verify", ...)        # py_compile para Python
bash_agent_graph.add_conditional_edges("call_model", should_continue, {...})
bash_agent_graph.add_edge("execute_tool", "verify")
bash_agent_graph.add_edge("verify", "call_model")
return bash_agent_graph.compile()
```
- **`call_model_node`** (`BaseAgentNode.call_model`): streaming con renderizado en vivo (Live/Spinner), detección de bucles críticos (`_detect_critical_loop`: 4 llamadas idénticas), y manejo de interrupción vía `interrupt_queue`.
- **`execute_tool_node`**: ejecuta `tool_calls` en paralelo con `ThreadPoolExecutor(max_workers=10)`; detecta `execute_command` para pedir confirmación al orquestador principal; captura `UserConfirmationRequired` para herramientas de archivo.
- **`verification_node`**: corre `py_compile` sin involucrar al LLM (corta ciclos de tool calls).
- **`learning_node`** + `create_learning_agent`: grafo separado para auto-mejora.

### 2.4 Ejecución de herramientas — `tool_executor.py`
Clase `ToolExecutor` centraliza la ejecución síncrona/asíncrona:
- `execute_single_tool`: invoca `llm_service._invoke_tool_with_interrupt(...)`, notifica en TUI/CLI, maneja `UserConfirmationRequired` / `InterruptedError`.
- `execute_tool_node`: mismo patrón de paralelismo que `bash_agent`, con validación **RBAC** (`blocked_tools` del `delegation_context`).
- `should_continue`: si `completed` → `END`; si bucle/cuelga confirmación → `END`; si `AIMessage` con `tool_calls` → `execute_tool`; si `ToolMessage` → `call_model`; subagente autónomo con texto intermedio → `call_model`.

### 2.5 Delegación y subagentes — `call_agent` / `call_agents_parallel`
Implementación en `kogniterm/skills/bundled/call-agent/scripts/tool.py`:
1. Monta widget de streaming en TUI (`mount_agent_stream`).
2. Registra el hijo en `DelegationManager` con `role=AgentRole.LEAF` y calcula `blocked_tools` (RBAC).
3. Establece `llm_service.current_delegation_context = child_ctx` (thread-local).
4. Construye el grafo según `agent_name`:
   - `code_agent`/`code_crew` → `create_deep_coder`
   - `researcher_agent` → `create_deep_researcher`
   - otro → `create_dynamic_agent` (agente genérico con `system_prompt` personalizado)
5. `initial_state = AgentState(messages=[HumanMessage(task)], autonomous_approvals=True)` → el subagente **no pide confirmación** al usuario.
6. `agent_graph.invoke(initial_state, config={"recursion_limit": RESEARCHER_RECURSION_LIMIT})`.
7. `finally`: restaura contexto, `unregister_agent`, remueve del `heartbeat_monitor`.

### 2.6 Módulo de delegación — `core/delegation/`
- **`DelegationManager`**: registra agentes con límites `max_depth` y `max_concurrent_children`; valida profundidad y concurrencia; resuelve `blocked_tools` por rol.
- **`AgentRole`**: `LEAF` (no delega, no muta memoria, no ejecuta comandos destructivos) vs `ORCHESTRATOR` (acceso total).
- **`DEFAULT_BLOCKED_TOOLS`** para `LEAF`: `call_agent`, `call_agents_parallel`, `skill_factory`, `refresh_tools`, `memory_append`, `memory_init`, `memory_summarize`.
- **`DelegationContext`**: `agent_id`, `parent_id`, `role`, `depth`, `toolsets`, `blocked_tools: FrozenSet`, `conversation`, `metadata`.
- **`HeartbeatMonitor`**: supervisa actividad de subagentes (threshold 300s).

### 2.7 Permisos y confirmación
- **Orquestador principal (interactivo)**: `execute_command` fija `state.command_to_confirm`; el `AgentInteractionManager`/`SessionPool` bloquea hasta que el usuario aprueba vía `command_approval_handler.handle_command_approval()`.
- **Herramientas de archivo**: lanzan `UserConfirmationRequired`; el nodo pausa y muestra diff para confirmación.
- **Subagentes**: `autonomous_approvals=True` + `delegation_context` → omiten la pausa de confirmación (ej. `tool_executor.py` línea 259: *"Subagente autónomo: omitida la pausa de confirmación"*).

### 2.8 Bucle de interrupción y detección de bucles
- `KeyboardHandler` + `interrupt_queue` para cancelar generación (CLI).
- `_detect_critical_loop`: 4 llamadas a tool idénticas (nombre + hash de args) → detiene el flujo.

---

## 3. Análisis Comparativo Detallado

### 3.1 Paradigma de definición de agentes
| | KiloCode | KogniTerm |
|---|---|---|
| Formato | **Markdown** + esquema `Info` | **Código Python** (funciones `create_*_agent`) |
| Separación config/código | Alta (agentes desacoplados del runtime) | Baja (agente = grafo en código) |
| Dinamismo | Generación de agentes por LLM (`generateObject`) | Agentes dinámicos bajo demanda (`create_dynamic_agent`) |
| Ventaja | Fácil de extender por usuarios sin tocar TS | Tipado fuerte, depuración directa |
| Desventaja | Requiere parser de Markdown + validación | Cambiar un agente implica editar código |

### 3.2 Bucle del agente (runtime)
- **KiloCode**: Effect + `Layer`/`Provider` + Vercel AI SDK. El bucle vive en `session/llm.ts` con `AbortController`. Altamente funcional y composable, pero con curva de aprendizaje de Effect.
- **KogniTerm**: LangGraph `StateGraph` con nodos explícitos y `should_continue` como router. Más imperativo y visualmente trazable; el estado es un dataclass mutable compartido.

### 3.3 Orquestación / Subagentes
| Mecanismo | KiloCode | KogniTerm |
|---|---|---|
| Herramienta de delegación | `task` (waves), `agent_manager` | `call_agent`, `call_agents_parallel` |
| Paralelismo | Waves de paralelización + worktree/local | `ThreadPoolExecutor` en `execute_tool_node` + `call_agents_parallel` |
| Gobernanza | Herencia de permisos `deny` al subagente | `DelegationManager` (RBAC, profundidad, concurrencia) |
| Aislamiento | Sesiones separadas (worktree) | `delegation_context` + `blocked_tools` (FrozenSet) |
| Finalización | Costos propagados al padre (`KiloCostPropagation`) | `complete_task` → `state.completed = True` |

**Diferencia clave:** KiloCode orquesta mediante *herramientas que el propio LLM invoca* (`task`, `agent_manager`), mientras que KogniTerm orquesta mediante *skills de Python que el LLM invoca* (`call_agent`) y que compilan y ejecutan un grafo LangGraph hijo de forma síncrona, con un `DelegationManager` que impone límites estructurales (profundidad/concurrencia/RBAC).

### 3.4 Permisos y seguridad
- **KiloCode**: reglas declarativas `allow`/`ask`/`deny` por patrón de comando; herencia de `deny` al subagente (`deriveSubagentSessionPermission`).
- **KogniTerm**:
  - Orquestador: confirmación interactiva (`command_approval_handler`) y diff para archivos (`UserConfirmationRequired`).
  - Subagente: `autonomous_approvals=True` + `blocked_tools` (RBAC por rol). El `DelegationManager` bloquea herramientas peligrosas (delegación, memoria, skill_factory) para `LEAF`.
- **Veredicto**: KiloCode es más granular a nivel de *comando bash*; KogniTerm es más granular a nivel de *herramienta/rol* y añade límites estructurales de topología (profundidad/concurrencia).

### 3.5 Streaming y UI
- **KiloCode**: servidor Hono (SSE) + TUI SolidJS/OpenTUI. Arquitectura cliente-servidor limpia.
- **KogniTerm**: Rich (CLI), prompt-toolkit (TUI), y `server/session_pool.py` (WebSocket). El `AgentInteractionManager` es el pegamento entre el grafo y la UI; soporta tres modos de frontend desde el mismo núcleo.

### 3.6 Memoria y aprendizaje
- **KiloCode**: `KiloSession` (telemetría/export), plugins, skills, MCP.
- **KogniTerm**: `.kogniterm/llm_context.md` (memoria contextual), `MessageManager`/`HistoryManager`, y un grafo `learning` separado (`create_learning_agent`) para auto-mejora. Notable: el `MessageManager` fue *inspirado explícitamente en KiloCode* (ver `agent_state.py` línea 125).

### 3.7 Detección de bucles y robustez
- **KiloCode**: waves + propagación de costos; depende del prompt `orchestrator.txt`.
- **KogniTerm**: `_detect_critical_loop` (4 tool calls idénticas) + `verification_node` (py_compile sin LLM) + `critical_loop_detected` que corta el grafo. Más defensivo a nivel de código.

---

## 4. Fortalezas y Debilidades

### KiloCode CLI
**Fortalezas**
- Configuración declarativa (Markdown) muy extensible.
- Efecto (Effect) aporta composición funcional robusta y manejo de errores tipado.
- Orquestación madura (waves, worktree, propagación de costos).
- Ecosistema grande (fork de opencode/Cline/Roo).

**Debilidades**
- Curva de aprendizaje de Effect/Layer.
- Acoplado a TypeScript/Node.
- Permisos granulares pero dependientes de patrones de comando (menos RBAC estructural).

### KogniTerm
**Fortalezas**
- Grafo LangGraph explícito y trazable; estado tipado (dataclass).
- `DelegationManager` con RBAC, límites de profundidad/concurrencia y `HeartbeatMonitor`.
- Soporte multi-frontend (CLI/TUI/WebSocket) desde un núcleo.
- Defensa contra bucles (detector + nodo de verificación).
- Memoria contextual + nodo de aprendizaje.

**Debilidades**
- Agentes definidos en código (menos flexible para el usuario final).
- Delegación síncrona por grafo hijo (el orquestador espera al subagente; el paralelismo real depende de `call_agents_parallel`/ThreadPoolExecutor).
- Acoplamiento entre capas señalado en `docs/ANALISIS_DEUDA_TECNICA.md` (UI ↔ Server ↔ Core).
- Menor escala/comunidad que KiloCode.

---

## 5. Recomendaciones de Evolución (para KogniTerm)

1. **Config-driven agents**: permitir definir agentes en YAML/Markdown (estilo KiloCode) sin tocar `create_*_agent`, reduciendo el acoplamiento código/config.
2. **Delegación asíncrona real**: `call_agents_parallel` ya apunta a `ThreadPoolExecutor`; formalizar un `AgentPool` (ver `kogniterm_hermes_comparison.md`) para paralelismo verdadero con `ainvoke`.
3. **Permisos granulares por comando**: combinar el RBAC por rol actual con reglas `allow`/`ask`/`deny` por patrón de comando (estilo KiloCode `bash` map).
4. **Reducción de acoplamiento**: aislar `AgentInteractionManager` tras una interfaz para que Core no importe UI/Server directamente.
5. **Telemetría de sesión**: adoptar un `KiloSession`-like para exportar trazas de delegación y costos.

---

## 6. Referencias de Código

**KiloCode (clonado en `/tmp/kilocode-research`)**
- `packages/opencode/src/config/agent.ts`
- `packages/opencode/src/agent/agent.ts`
- `packages/opencode/src/tool/task.ts`
- `packages/opencode/src/kilocode/tool/agent-manager.ts`
- `packages/opencode/src/agent/subagent-permissions.ts`
- `packages/opencode/src/agent/prompt/*.txt`
- `packages/opencode/src/kilocode/agent/index.ts`
- `packages/opencode/src/session/llm.ts`

**KogniTerm (local)**
- `kogniterm/core/agent_state.py`
- `kogniterm/core/agents/bash_agent.py` (`create_bash_agent`, `call_model_node`, `execute_tool_node`, `verification_node`, `learning_node`)
- `kogniterm/core/agents/base_agent.py` (`BaseAgentNode`)
- `kogniterm/core/agents/tool_executor.py` (`ToolExecutor`, `should_continue`)
- `kogniterm/core/agents/dynamic_agent.py` (`create_dynamic_agent`)
- `kogniterm/core/agents/researcher_agent.py` / `deep_researcher.py` / `deep_coder.py`
- `kogniterm/core/delegation/` (`delegation_manager.py`, `agent_roles.py`, `models.py`, `heartbeat_monitor.py`)
- `kogniterm/skills/bundled/call-agent/scripts/tool.py` (`call_agent_skill`)
- `kogniterm/terminal/agent_interaction_manager.py` (`AgentInteractionManager`)
- `kogniterm/server/session_pool.py`
