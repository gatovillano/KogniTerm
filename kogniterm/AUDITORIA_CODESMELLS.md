# 🔍 Auditoría de Code Smells, Spaghetti Code y Duplicación — KogniTerm

**Fecha:** 2025-01-20
**Agente:** KogniTerm (BashAgent / Orchestrator)
**Alcance:** `kogniterm/` (análisis estático radon + búsqueda semántica de duplicados)
**Estado:** Completado (solo auditoría, sin ediciones)

---

## 1. Resumen Ejecutivo

Se detectaron **tres categorías críticas de deuda técnica**:

1. **Spaghetti code / Alta complejidad ciclomática** — funciones con CC extremo (hasta 86 y 62).
2. **Código duplicado masivo** — lógica de agentes (`execute_single_tool`, `should_continue`, `handle_tool_confirmation`) replicada en 5+ módulos.
3. **God objects / Archivos gigantes** — `llm_service.py` (2820 líneas), `bash_agent.py` (1513), `skill_manager.py` (1369).

> ⚠️ Ya existe un plan de refactor previo en `docs/refactor_implementation_plan.md` (Status: In Progress, Priority 1). Esta auditoría lo confirma y añade datos cuantitativos.

---

## 2. Complejidad Ciclomática (CC) — Top Críticos

| Archivo | Función / Método | CC | Severidad |
|---------|------------------|----|-----------|
| `terminal/command_approval_handler.py` | `handle_command_approval` | **86** | 🔴 Crítica |
| `core/agents/bash_agent.py` | `execute_tool_node` | **62** | 🔴 Crítica |
| `core/skills/skill_manager.py` | `_load_module_tools` | **77** | 🔴 Crítica |
| `core/multi_provider_manager.py` | `_determine_ideal_provider` | **44** | 🟠 Alta |
| `terminal/cli.py` | `handle_config` / `handle_telegram_config` | 24 / 24 | 🟠 Alta |
| `terminal/cli.py` | `handle_upgrade` | 19 | 🟡 Media |
| `terminal/cli.py` | `handle_keys` | 15 | 🟡 Media |
| `terminal/agent_interaction_manager.py` | `invoke_agent` | 28 | 🟠 Alta |
| `terminal/agent_interaction_manager.py` | `__init__` | 16 | 🟡 Media |
| `terminal/file_completer.py` | `FileCompleter` | 16 | 🟡 Media |
| `terminal/command_approval_handler.py` | `_resolve_tool_call_id` | 10 | 🟡 Media |
| `ui/terminal_ui.py` | `detect_terminal_theme` | 15 | 🟡 Media |
| `core/context/project_memory_builder.py` | (módulo) | MI 29.22 | 🟠 Baja mant. |
| `core/context/codebase_indexer.py` | (módulo) | MI 29.93 | 🟠 Baja mant. |

**Promedios por archivo (CC):**
- `command_approval_handler.py`: 10.47
- `agent_interaction_manager.py`: 22.33
- `cli.py`: 10.43
- `file_completer.py`: 15.11

---

## 3. Índice de Mantenibilidad (MI) — Peores Casos

Radon clasifica: A (≥20), B (10-19), C (<10). Valores críticos:

| Archivo | MI | Rango |
|---------|----|-------|
| `terminal/cli.py` | **0.00** | 🔴 C |
| `core/skills/skill_manager.py` | **0.00** | 🔴 C |
| `terminal/command_approval_handler.py` | 23.00 | 🟢 A (pero CC 86 interno) |
| `terminal/file_completer.py` | 25.35 | 🟢 A |
| `core/context/project_memory_builder.py` | 29.22 | 🟢 A |
| `core/context/codebase_indexer.py` | 29.93 | 🟢 A |
| `core/skills/skill_migrator.py` | 42.33 | 🟢 A |
| `core/utils/tool_utils.py` | 37.15 | 🟢 A |
| `ui/visual_components.py` | 47.10 | 🟢 A |
| `ui/themes.py` | 46.76 | 🟢 A |
| `terminal/agent_interaction_manager.py` | 52.82 | 🟢 A |
| `terminal/terminal.py` | 51.09 | 🟢 A |
| `terminal/config_manager.py` | 57.54 | 🟢 A |
| `ui/terminal_ui.py` | 54.95 | 🟢 A |

> Nota: `cli.py` y `skill_manager.py` tienen MI=0 (peor categoría C) a pesar de CC promedio no extremo → indican halagos de líneas/volumen y baja cohesión.

---

## 4. Código Duplicado (Smell: Don't Repeat Yourself violado)

### 4.1 Lógica de Grafos de Agentes (CRÍTICO)
Las siguientes funciones están **copiadas y pegadas** en múltiples agentes:

| Función | Archivos que la contienen |
|---------|---------------------------|
| `execute_single_tool` | `bash_agent.py` (L923), `code_agent.py` (L417), `researcher_agent.py` (L165), `deep_researcher.py` (L644), `dynamic_agent.py` (vía ToolExecutor) |
| `should_continue` | `bash_agent.py` (L1442), `code_agent.py` (L791), `researcher_agent.py` (L293), `deep_researcher.py` (L733) |
| `handle_tool_confirmation` | `bash_agent.py` (L388), `code_agent.py` (L103) |
| `create_call_model_node` | `bash_agent.py`, `code_agent.py`, `researcher_agent.py` (patrón repetido) |

**Impacto:** Cualquier cambio de seguridad en `execute_single_tool` debe replicarse manualmente en 5 sitios → alto riesgo de divergencia y bugs.

### 4.2 Lógica de Confirmación de Herramientas (CRÍTICO)
El bloque `handle_command_approval(...)` con construcción de `raw_tool_output` dict aparece idéntico en:
- `server/session_pool.py` (L803-823)
- `terminal/tui/tui_app.py` (L2531-2551)
- `terminal/agent_interaction_manager.py` (invoca al handler)

Además `ask_for_approval_sync` está duplicado en `ui/terminal_ui.py` (CC 6 en dos métodos distintos).

### 4.3 Carga Dinámica de Módulos de Skills
`_load_file_ops_module` / `_load_bundled_skill_module` en `command_approval_handler.py` usan `importlib` con paquetes virtuales → patrón frágil repetido. Similar lógica en `skill_manager.py` (`_load_module_tools`, CC 77).

---

## 5. God Objects / Archivos Gigantes

| Archivo | Líneas | Problema |
|---------|--------|----------|
| `core/llm_service.py` | **2820** | God object. Debe dividirse en `core/llm/` (provider_config, message_converter, tool_parser, streaming_executor, fallback_handler, rate_limiter) |
| `core/agents/bash_agent.py` | **1513** | Orquestador + nodos de grafo + tools + estado |
| `core/skills/skill_manager.py` | **1369** | Discovery + carga + migración acoplados |
| `terminal/command_approval_handler.py` | 701 | 14 funciones, una con CC 86 |
| `terminal/cli.py` | 904 | Handlers de config repetitivos |

---

## 6. Code Smells Específicos

| Smell | Ubicación | Descripción |
|-------|-----------|-------------|
| **Long Method** | `handle_command_approval` (CC 86) | Función de ~300+ líneas con múltiples responsabilidades |
| **Long Parameter List** | `handle_command_approval` | 8+ parámetros posicionales |
| **Feature Envy** | `command_approval_handler` | Conoce demasiado de `AgentState`, `TerminalUI`, `CommandExecutor`, skills |
| **Shotgun Surgery** | Agentes duplicados | Un cambio toca 5 archivos |
| **Speculative Generality** | `dynamic_agent.py` | 80 líneas, posible sobre-ingeniería |
| **Dead Code / Legacy** | `core/tools/tool_manager.py` | `ToolManager` legacy no usado (confirmado en plan previo) |
| **Inconsistent Naming** | Varios | `execute_single_tool` vs `execute_single_tool_async_optimized` vs `ToolExecutor.execute_single_tool` |
| **Mixed Levels of Abstraction** | `agent_interaction_manager.__init__` | Lógica de filtrado de SystemMessage inline (CC 16) |

---

## 7. Plan de Refactorización Recomendado (Priorizado)

### 🔴 P0 — Crítico (hacer primero)
1. **Extraer base común de agentes** → crear `core/agents/base_agent.py` con `BaseAgentNode` conteniendo `execute_single_tool`, `should_continue`, `handle_tool_confirmation`, `create_call_model_node`. Refactorizar bash/code/researcher/deep_researcher/dynamic para heredar de él.
2. **Dividir `handle_command_approval`** (CC 86) en sub-funciones: `_build_tool_result_dict`, `_check_safety`, `_apply_diff_to_history`, `_resolve_confirmation`. Objetivo CC < 15 por función.
3. **Consolidar `ToolExecutor`** en `core/agents/tool_executor.py` (una sola versión de `execute_single_tool`).

### 🟠 P1 — Alto
4. **Descomponer `LLMService`** (2820 líneas) en módulos de `core/llm/` según plan previo.
5. **Deduplicar lógica de confirmación** entre `session_pool.py`, `tui_app.py`, `agent_interaction_manager.py` → pasar todo por `CommandApprovalHandler` único.
6. **Reducir `skill_manager._load_module_tools`** (CC 77) con carga por registry/plugin.

### 🟡 P2 — Medio
7. **Limpiar CLI handlers** (`handle_config`, `handle_telegram_config`, `handle_upgrade`) → tabla de configuraciones genérica.
8. **Eliminar `ToolManager` legacy** y `docker-compose.yml` WordPress.
9. **Unificar `ask_for_approval_sync`** en un solo método de `TerminalUI`.

---

## 8. Métricas de Referencia (Pre-Refactor)

- Total LOC auditadas (top archivos): **10,776 líneas**
- Funciones con CC > 40: **4** (86, 77, 62, 44)
- Archivos con MI=C (0.00): **2** (cli.py, skill_manager.py)
- Módulos con duplicación de grafo: **5 agentes**

---

## 9. Conclusión

El proyecto sufre de **deuda técnica estructural acumulada** durante la migración Tools→Skills y la transición cliente-servidor. La duplicación en agentes y la función `handle_command_approval` (CC 86) son los riesgos mayores para mantenibilidad y seguridad. Se recomienda ejecutar el plan de `docs/refactor_implementation_plan.md` priorizando P0 de esta auditoría.

**Próximo paso sugerido:** Aprobar refactor P0 y aplicar vía `code_agent` en rama dedicada.
