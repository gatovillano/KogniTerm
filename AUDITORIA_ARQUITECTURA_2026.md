# Auditoría de Arquitectura — KogniTerm

**Fecha**: 2026
**Alcance**: paquete `kogniterm/` (Python), con atención a `terminal/`, `server/`, `core/`, `ui/`
**Veredicto global**: La intuición del usuario es correcta. El proyecto presenta **degradación arquitectónica acelerada** por acumulación de implementaciones sucesivas, con dependencias entre capas invertidas y duplicación masiva de responsabilidades.

---

## 1. Diagnóstico ejecutivo

El proyecto 🥇 KogniTerm nació como una **TUI monolítica** (Rich/prompt_toolkit) y evolucionó hacia una **arquitectura cliente-servidor** (FastAPI + WebSocket/SSE/REST) sin una migración definitiva. El resultado es un sistema **híbrido en estado transitorio permanente** donde:

- La TUI **ya no es dueña de la lógica**: se conecta a un servidor central, pero conserva dependencias directas de capas de negocio.
- El servidor **hereda dependencias de la UI**: el backend importa e instancia clases de `terminal/`.
- Existen **dos directorios UI paralelos** (`ui/` y `terminal/`) con archivos equivalentes (shims).
- Los agentes (`core/agents/`) tienen **3 implementaciones coexistentes** (`.py`, `.bak`, `.backup`) y lógica duplicada entre sí.

Este es el patrón clásico de **"refactor incompleto"**: secean las capas nuevas, pero nunca se eliminan las antiguas, por lo que el sistema arrastra doble implementación y la arqueología de "qué módulo es el canónico".

---

## 2. Métricas de tamaño (señal de God Objects)

| Archivo | Líneas | Bytes | Observación |
|---|---|---|---|
| `server/app.py` | 3,517 | 154,749 | **God Object**: API + auth + WS + SSE + REST + PTY + config |
| `server/session_pool.py` | 1,797 | 81,593 | Motor de sesiones + monkey-patch de `os` + render de Rich |
| `terminal/meta_command_processor.py` | 2,433 | 129,889 | Lógica de comandos + render UI + config + insights |
| `terminal/cli.py` | 1,118 | 46,727 | 8 subcomandos en un solo archivo |
| `terminal/command_approval_handler.py` | 882 | 46,424 | UI de aprobación + carga dinámica de skills + reglas |
| `core/llm_service.py` | ~2,820 | 156,532 | Orquestador + parsers + providers + tools |
| `terminal/tui/tui_app.py` | ~4,500 | — | TUI monolítica |

**Regla de referencia**: archivos >800 líneas con múltiples responsabilidades son el foco #1 de cualquier auditoría de mantenibilidad (mantenibilidad ya está en rango C según auditoría previa).

---

## 3. Hallazgo crítico #1 — Dependencia inversa `server/ → terminal/`

**Verificado en código**:

```
kogniterm/server/session_pool.py:844   from kogniterm.terminal.command_approval_handler import CommandApprovalHandler
kogniterm/server/session_pool.py:851   self.command_approval_handler = CommandApprovalHandler(...)
kogniterm/server/session_pool.py:874   command_approval_handler=self.command_approval_handler
kogniterm/server/app.py:968-969        session.command_approval_handler.auto_approve = ...
```

Y la dependencia inversa también existe:

```
kogniterm/terminal/terminal.py:89      from kogniterm.terminal.command_approval_handler import CommandApprovalHandler
kogniterm/terminal/tui/tui_app.py:91   (ídem)
kogniterm/core/agents/code_crew.py:4   (ídem)
```

**Consecuencia**: `CommandApprovalHandler` es simultáneamente:
1. Un componente de UI (usa `prompt_toolkit`, `rich.Panel`, `Padding`, `Markdown`, `StringIO`).
2. Un componente de dominio (invocado por `session_pool` para decisiones de política).
3. Un **cargador de módulos dinámicos** vía `importlib` de skills bundled (mezcla de infraestructura con lógica de UI).

**Resultado**: `server/` no puede ejecutarse sin `prompt_toolkit`/`rich` instalados. Y `terminal/` no puede ser eliminado como cliente "thin" porque el backend depende de él.

### Solución
Crear un **puerto/adapter**:
```
kogniterm/core/approval/
├── approval_policy.py     # ← SRP: decide (rechaza/auto/aprueba/espera). Sin UI. Usado por server/ y core/agents/
└── approval_ui.py         # ← Adapter TUI: implementa la interfaz usando prompt_toolkit/rich
```

```python
# core/approval/approval_policy.py
class ApprovalPolicy:
    def should_execute(self, tool_call, session_ctx) -> ApprovalDecision: ...
    async def wait_for_decision(self, tool_id) -> ApprovalDecision: ...
    def resolve(self, tool_id, decision: str) -> None: ...
```
El `session_pool` solo habla con `ApprovalPolicy` (o con un `NullPolicy` en modo autónomo/autopass). La TUI registra una implementación de la UI.

---

## 4. Hallazgo crítico #2 — Doble directorio UI (`ui/` vs `terminal/`)

```
kogniterm/terminal/terminal_ui.py     12 líneas  ← SHIM
kogniterm/terminal/visual_components.py 36 líneas ← SHIM
kogniterm/terminal/themes.py          24 líneas  ← SHIM
kogniterm/terminal/security.py        12 líneas  ← SHIM explícito
kogniterm/ui/terminal_ui.py                    ← CANÓNICO
kogniterm/ui/visual_components.py
kogniterm/ui/themes.py
kogniterm/ui/security.py
```

El shim de `security.py` lo admite explícitamente:
> *"SHIM DE COMPATIBILIDAD — la implementación canónica ahora vive en `kogniterm/ui/security.py`"*

**Problema**: coexisten dos "capas UI". `ui/` es canónica, pero `terminal/` sigue siendo la capa UI real (contiene la TUI de 4,500 líneas). El resultado es ambiguo: **no está claro si `ui/` es la capa de presentación o un servicio de render compartido**.

**Solución**: Decidir una taxonomía única y eliminar shims:
- `kogniterm/ui/` → **capa de presentación compartida** (Rich rendering, temas, seguridad de output) — consumida por TUI **y** server (para renderizar diffs en canales como Telegram/Slack).
- `kogniterm/terminal/` → **solo clientes** (`cli.py`, `tui/`, bootstrap).
- Eliminar `security.py` shim y usar `from kogniterm.ui.security import ...` en todas partes.

---

## 5. Hallazgo crítico #3 — Duplicación de agentes y capas de tool execution

```
core/agents/
├── base_agent.py            12,989   ✅ existe
├── tool_executor.py         28,158   ✅ existe
├── bash_agent.py            33,611
├── bash_agent.py (sin .bak pero con código inline duplicado)
├── code_agent.py            43,278
├── code_agent.py.backup     17,935   ← muerto
├── code_agent.py.bak        42,151   ← muerto
├── super_agent.py           36,893
├── super_agent.py.bak       35,759   ← muerto
├── tool_executor.py.bak     27,505   ← muerto
├── researcher_agent.py      18,583
├── researcher_agent_backup.py 13,111 ← muerto
├── deep_researcher.py       35,960
├── deep_coder.py            22,685
├── code_crew.py, code_crew_agents.py, research_agents.py, researcher_crew.py, specialized_agents.py
└── parallel_tool_dispatcher.py
```

**Hallazgos**:
1. **5 archivos `.bak`/`.backup` en el árbol de producción** — riesgo real: un `import` mal escrito carga código obsoleto y `py_compile` no detecta nada.
2. **`code_crew.py`, `research_agents.py`, `researcher_crew.py`, `specialized_agents.py`** (fechados `Jan 1 2026`, ~2-6 KB) parecen restos de la integración con CrewAI. Verificar si están referenciados; si no, son 以及 restos de una implementación **abandonada**.
3. Duplicación de `execute_single_tool`, `should_continue`, `handle_tool_confirmation` en bash/code/researcher/deep_researcher (ya documentado en auditorías previas, **pendiente**).

**Solución**:
- Borrar `.bak`/`.backup` (git ya tiene historia).
- Eliminar los restos de CrewAI si no están en uso (`grep -r "code_crew\|researcher_crew" kogniterm/`).
- Completar la migración de los 4 agentes pesados a `BaseAgentNode` + `ToolExecutor` (trabajo ya planificado en `docs/refactor_implementation_plan.md`, rama `refactor/agent-base-extraction`).

---

## 6. Hallazgo crítico #4 — Contaminación de `session_pool.py` con presentación y monkey-patch global

`session_pool.py` (1,797 líneas) mezcla:

1. **Contexto de sesión** (`contextvars`, `session_context`) ✅ correcto
2. **Monkey-patch global del módulo `os`** ❌
```python
_original_getcwd = os.getcwd
_original_chdir = os.chdir
def custom_getcwd(): ...
os.getcwd = custom_getcwd   # ← patch GLOBAL del módulo os
os.chdir = custom_chdir     # ← patch GLOBAL del módulo os
```
Esto afecta a **todo el proceso**, incluyendo hilos ajenos al agente, y es la causa raíz de comportamiento no determinista bajo concurrencia (WebSocket + REST + PTY simultáneos). Los tests existentes (`test_websocket_handshake_live_state`, `test_server_session_persistence`) dependen de este comportamiento, lo que explica por qué nadie lo ha tocado.

3. **Renderizado de Rich** ❌
```python
from rich.console import Console
from kogniterm.ui.terminal_ui import TerminalUI
def extract_thinking_and_response(renderable) -> tuple[str, str]:
    # recursión sobre Padding, Group, Panel, Table, Markdown...
```
El backend **desmonta objetos Rich** (`Panel`, `Table`, `Padding`) para extraer texto plano y mandarlo por WebSocket. Esto significa que:
- La capa de transporte depende de la librería de presentación.
- Los clientes (web/desktop/vscode) reciben **texto ya rasterizado por Rich**, no datos estructurados.

4. **Carga de la UI handler** ❌ (ver Hallazgo #1).

**Solución (por orden)**:
1. Eliminar el patch de `os`; usar `pathlib` + `cwd` explícito en todos los módulos que necesitan directorio (CommandExecutor, file ops, indexers). `contextvars` ya da el aislamiento correcto.
2. Extraer la extracción de texto a un **adaptador de serialización** (`server/render_adapter.py`) que convierta `Renderable → {thinking, text, events[]}` en un punto único.
3. Idealmente: los agentes deberían emitir **eventos estructurados** (JSON), no `Renderable`. El render a Rich ocurre en el cliente.

---

## 7. Hallazgo crítico #5 — `server/app.py` monolítico

3,517 líneas en un solo módulo con:
- Modelos Pydantic (config, sessions, threads, workspaces, audio, telegram)
- Autenticación por token (`KOGNITERM_API_TOKEN` / `~/.kogniterm/api_token`)
- WebSocket bidireccional con streaming
- SSE
- REST chat
- Endpoints de workspace/files/skills/config/models/keys
- PTY (vía `pty_manager`)
- Background tasks / heartbeat

**Índice de Shalow (métrica de mantenimiento)**: cuanto mayor el MI, peor. Un archivo de 3.5k líneas con 40+ endpoints tiene MI ≈ 0 → rango C (mantenibilidad terrible).

**Solución**: dividir por *slices* (no por capa técnica):
```
server/
├── app.py                 # solo creación de FastAPI + wiring (objetivo: <200 líneas)
├── deps.py                # dependencias (auth, pool, llm_service)
├── schemas/               # modelos Pydantic
│   ├── chat.py, sessions.py, config.py, workspace.py, audio.py
├── routers/
│   ├── chat.py            # REST /chat
│   ├── ws.py              # WebSocket
│   ├── sse.py             # SSE
│   ├── sessions.py        # CRUD sesiones/hilos
│   ├── workspace.py       # files/dirs/threads
│   ├── config.py          # /api/config/all, /api/models/available
│   ├── skills.py          # /api/skills
│   ├── pty.py             # terminal embebida
│   ├── mcp.py
│   └── audio.py
└── middleware/auth.py
```

---

## 8. Hallazgo crítico #6 — Raíz del repositorio contaminada

El nivel raíz tiene **basura técnica crítica**:

```
./<MagicMock name='mock.get_thread().workspace_dir' id='135541724030080'>   ← ~30 archivos
./<MagicMock name='mock.get_thread().workspace_dir' id='132339062274624'>
... (se repiten ~30 veces)
./json            ← archivo literal llamado "json"
./tatus           ← archivo literal llamado "tatus"  (typo de "status")
./igue            ← archivo literal llamado "igue"   (typo)
./templates       ← vacío
./trategia        ← vacío
./scratch.py, ./scratch/  ← 70+ scripts de depuración
./test_environment/        ← restos de un experimento
./kogniterm*.cast  (9 archivos)  ← casts de asciinema, artefactos
./llm_service_patch.diff, pyproject.toml.bak
./bandit_report.json, bandit_results.json, bandit_audit.json, bandit_audit_current.json
```

Los archivos `<MagicMock name='mock.get_thread().workspace_dir' id='...'>` son **el bug más grave de higiene**: un test que imprimió un `MagicMock` directamente a un `open()`/path y creó un archivo con el nombre del `repr()`. Esto indica que en algún momento el código usó un `MagicMock` sin configurar como ruta de workspace → **carga de archivos desde rutas incorrectas en tests**, y potencialmente en producción si el registry se contaminó.

**Solución**:
1. Buscar el test que lo produce y corregirlo (usar `tmp_path` de pytest).
2. `rm` de los 30 archivos MagicMock.
3. Mover `scratch/`, `test_environment/`, `*.cast`, `*.json` de auditoría a `archive/` o eliminarlos.
4. Añadir a `.gitignore`: `scratch/`, `*.cast`, `<MagicMock*`, `nohup.out`.

---

## 9. Problemas secundarios

| # | Problema | Ubicación | Impacto |
|---|---|---|---|
| 1 | Shims con `import *` | `terminal/security.py` | Ensuciará `os.environ` con nombres inesperados; oculta errores de import |
| 2 | `kogniterm/skills/{bundled,managed,workspace}` — existe un directorio literal `{bundled,managed,workspace}` | `kogniterm/skills/` | Artefacto de un `mkdir -p` mal citado en un doc |
| 3 | `kogniterm/agent-browser/` (proyecto Node completo) dentro del paquete Python | `kogniterm/` | Se distribuye dentro del wheel; infla el paquete; `MANIFEST.in` probablemente lo ignora pero confunde |
| 4 | `kogniterm4.gif` (107 MB) dentro del paquete | `kogniterm/` | **El wheel/tar pesa >100 MB solo en un GIF** |
| 5 | Tres frontends (`kogniterm-web`, `kogniterm-desktop`, `kogniterm-desktop-v3`, `kogniterm-vscode`) | raíz | 4 implementaciones de cliente; `desktop` y `desktop-v3` solapadas (Tauri vs Electron) |
| 6 | `dashboard/`, `skills-fork/`, `plans/`, `docs/plans/`, `docs/superpowers/` | raíz | 5 ubicaciones de documentación |
| 7 | `kogniterm/scratch.py` | paquete | Script de depuración en el paquete |
| 8 | `kogniterm/config_manager.py` **y** `core/agents/config_manager.py` | dosubicaciones | Nombres duplicados, responsabilidades solapadas |

---

## 10. Arquitectura objetivo propuesta

```
kogniterm/
├── __init__.py
├── main.py                     # entrypoint único
├── cli/
│   ├── app.py                  # dispatcher Typer
│   └── commands/
│       ├── config.py  keys.py  models.py  index.py  skills.py  server.py
├── core/                       # ← CAPA DE DOMINIO (sin UI, sin HTTP)
│   ├── agents/                 # BaseAgentNode + ToolExecutor + agentes specialised
│   ├── approval/               # ApprovalPolicy (puerto)
│   ├── commands/               # MetaCommandProcessor → servicios puros
│   ├── llm/                    # llm_service, providers, parsing
│   ├── skills/                 # SkillManager, JIT loader
│   ├── context/                # history, message, thread, embeddings, vector db
│   ├── delegation/             # RBAC, roles
│   ├── services/               # audio, insights, telemetry, background tasks
│   └── models/                 # AgentState, schemas de dominio
├── server/                     # ← CAPA DE TRANSPORTE (HTTP/WS/SSE/PTY)
│   ├── app.py                  # <200 líneas
│   ├── routers/  schemas/  deps.py  middleware/
│   ├── session_pool.py         # solo sesiones (sin os-patch, sin Rich)
│   ├── render_adapter.py       # Renderable → eventos estructurados
│   └── channels/               # telegram, slack, webhook
├── ui/                         # ← CAPA DE PRESENTACIÓN (Rich, temas)
│   ├── terminal_ui.py  visual_components.py  themes.py  diff_view.py
├── clients/
│   ├── tui/                    # ← TUI Textual (ex-terminal/)
│   └── api_client.py           # cliente HTTP/WS compartido
└── utils/  logger.py  diff_renderer.py
```

**Reglas de dependencia** (verificables con un test de arquitectura):
```
utils  ←  core  ←  ui  ←  clients
             ↑        ↑
             └── server
```
- `core/` **nunca** importa `rich`, `prompt_toolkit`, `textual`, `fastapi`.
- `server/` **nunca** importa `prompt_toolkit` ni `textual`.
- `ui/` **nunca** importa `server/` ni `core/agents/`.

---

## 11. Plan de acción priorizado

### P0 — Contención (1 día, bajo riesgo)
1. ✅ Borrar 30 archivos `<MagicMock name=...>` y localizar/corregir el test que los genera.
2. ✅ Borrar `*.bak`, `*.backup`, `llm_service.py.backup`, `command_approval_handler.py.bak`, `agent_state.py.backup`, `code_agent.py.backup`.
3. ✅ Añadir `.gitignore` para `scratch/`, `*.cast`, `nohup.out`, `*.diff`.
4. ✅ Mover `kogniterm4.gif` (107 MB) a `docs/`/`assets/`; excluir `agent-browser/` del paquete (`setup.py`/`pyproject.toml`).
5. ✅ Verificar si `code_crew`/`researcher_crew`/`specialized_agents` están referenciados; eliminar si no.

### P1 — Desacoplar capas (1 semana)
6. Extraer `core/approval/approval_policy.py` (puro) + `ui/approval_prompt.py` (adapter).
   `session_pool` deja de importar de `terminal/`.
7. Eliminar shims (`terminal/security.py`, `terminal_ui.py`, `visual_components.py`, `themes.py`) → imports absolutos a `kogniterm.ui.*`.
8. Reemplazar imports de `core.agents.bash_agent.AgentState` por `core.agent_state.AgentState` (ver `command_approval_handler.py:7` — importa un *symbolo* de un módulo de agente: smell grave).
9. Extraer `Renderable → eventos` fuera de `session_pool.py`.

### P2 — Romper God Objects (2 semanas)
10. `server/app.py` → `routers/` (ver §7).
11. `terminal/meta_command_processor.py` → `core/commands/` + adaptadores de UI.
12. `terminal/cli.py` → `cli/commands/*` con Typer.
13. Eliminar monkey-patch de `os.getcwd`/`os.chdir` (ver §6.2) — **requiere suite de tests verde primero**.

### P3 — Unificar agentes (2 semanas, ya planificado)
14. Migrar `bash_agent`, `code_agent`, `researcher_agent`, `deep_researcher` a `BaseAgentNode` + `ToolExecutor`.
15. Eliminar `execute_single_tool`/`should_continue`/`handle_tool_confirmation` duplicados.
16. Retirar restos de CrewAI.

### P4 — Higiene del monorepo (1 día)
17. Un solo directorio de docs. Un solo cliente desktop (elegir Tauri **o** Electron). Decidir `kogniterm-web` vs `kogniterm-vscode` scope.

---

## 12. Veredicto

**Coincido con tu lectura, y la evidencia la refuerza.** El desorden no es cosmético: hay un **problema de límites de capa real** (server depende de terminal), **duplicación activa de 3 implementaciones de agentes**, **residuos de 2 frameworks de orquestación的不同** (propia + CrewAI), y **contaminación de la raíz con artefactos de test**.

Lo más importante: **P0 es trivial y elimina riesgo inmediato**; **P1 es donde está el valor real** (romper el acoplamiento server→terminal desbloquea todo lo demás, incluida la posibilidad de correr el backend headless sin dependencias de UI).

### Regla de oro para evitar que vuelva a pasar
Añadir un test de arquitectura (pytest) que falle si:
```python
# tests/unit/test_architecture_boundaries.py
FORBIDDEN = {
    "kogniterm/core/":      {"rich", "prompt_toolkit", "textual", "fastapi"},
    "kogniterm/server/":    {"prompt_toolkit", "textual"},
}
# Recorre imports reales (ast) y falla si aparece un forbid.
```
Eso convierte "el código está ordenado" en una invariante verificada por CI, no en una convención que se pierde en 6 meses.

---

## 13. Métricas de seguimiento sugeridas

| Métrica | Valor actual | Objetivo |
|---|---|---|
| Líneas en `server/app.py` | 3,517 | < 250 |
| Archivos >800 líneas en `kogniterm/` | ~8 | ≤ 3 |
| Archivos `.bak`/`.backup` | 6+ | 0 |
| Imports `server/ → terminal/` | 3 | 0 |
| Imports `core/ → rich/prompt_toolkit/fastapi` | ? | 0 |
| Módulos que importan `AgentState` desde `core.agents.bash_agent` | 1 | 0 |
| Raíz del repo: entradas no versionadas | ~100 | < 20 |
