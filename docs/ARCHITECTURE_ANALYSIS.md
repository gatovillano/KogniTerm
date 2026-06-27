# 🔍 Análisis Arquitectónico KogniTerm — Informe Consolidado

**Fecha:** 2026-02-21  
**Agente:** KogniTerm BashAgent (DeepAnalysis)  
**Versión:** 1.0

---

## 📋 Resumen Ejecutivo

KogniTerm es un **agent de terminal AI multi-canal** con arquitectura de **4 capas** que integra un sistema de skills plugin avanzado, multi-proveedor LLM con fallback, delegación jerárquica de sub-agentes y persistencia de sesiones.

**Stack tecnológico:** Python · LiteLLM · LangChain/LangGraph · FastAPI · Textual TUI · Rich · ChromaDB

---

## 🏗️ Arquitectura de 4 Capas

```
┌─────────────────────────────────────────────────────────┐
│  CAPA 1: PRESENTACIÓN (terminal/)                        │
│  ├─ terminal.py (258 LOC) — Punto de entrada CLI/TUI    │
│  ├─ KogniTermTUI — Interfaz Textual (3,063 LOC)         │
│  ├─ Componentes: ChatLog, ChatInput, StatusFooter       │
│  └─ CommandApprovalModal — Confirmación de acciones      │
├─────────────────────────────────────────────────────────┤
│  CAPA 2: NEGOCIO (core/)                                │
│  ├─ LLMService (2,416 LOC) — Fachada principal          │
│  ├─ AgentState (235 LOC) — Estado del grafo             │
│  ├─ MessageManager (411 LOC) — Doble historial          │
│  ├─ HistoryManager (1,038 LOC) — Persistencia            │
│  ├─ CommandExecutor (325 LOC) — Ejecución PTY           │
│  ├─ SkillManager (1,336 LOC) — Sistema de skills        │
│  ├─ MultiProviderManager — Fallback entre proveedores   │
│  ├─ DelegationManager (102 LOC) — Sub-agentes           │
│  └─ WorkspaceContext (190 LOC) — Contexto proyecto      │
├─────────────────────────────────────────────────────────┤
│  CAPA 3: SKILLS (skills/bundled/ — 25 skills)           │
│  ├─ file-operations/  ├─ memory-*/                      │
│  ├─ task-tracker/      ├─ code-tools/                    │
│  ├─ web-tools/        ├─ python-executor/               │
│  ├─ pc-interaction/   ├─ execute-command/               │
│  ├─ call-agent/       ├─ call-agents-parallel/          │
│  ├─ skill-factory/    ├─ plan-creation/                 │
│  └─ ... y más                                           │
├─────────────────────────────────────────────────────────┤
│  CAPA 4: INFRAESTRUCTURA (server/)                       │
│  ├─ app.py (1,038 LOC) — FastAPI REST/WS/SSE            │
│  ├─ session_pool.py (937 LOC) — Pool de sesiones        │
│  └─ channel_adapters.py (805 LOC) — Telegram/Slack/CLI  │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 Flujo de Ejecución Principal

```
terminal.py
  ├─ Carga .env (local + global con override)
  ├─ LLMService() → Inicializa SkillManager, MultiProviderManager, HistoryManager
  ├─ CommandExecutor() → Ejecución segura de comandos
  ├─ AgentState() → Estado inicial del grafo
  └─ KogniTermTUI()
      ├─ on_mount()
      │   ├─ _check_workspace_index() → Indexación ChromaDB
      │   ├─ _try_server_connect() → WebSocket al servidor (fallback local)
      │   └─ _start_deep_research_investigation() → Genera llm_context.md
      └─ execute_command() → process_agent_request()
          ├─ AgentInteractionManager.invoke_agent()
          │   └─ BashAgent (LangGraph)
          │       ├─ build_tool_call_schema()
          │       ├─ invoke_llm() → MultiProviderManager con fallback
          │       ├─ execute_tools() → _invoke_tool_with_interrupt()
          │       └─ ToolOutputWidget → update_terminal_output()
          └─ CommandApprovalHandler
              ├─ command_to_confirm → ask_for_approval_sync()
              └─ tool_pending_confirmation → handle_command_approval()
```

---

## 🧩 Componentes Críticos y Sus Relaciones

### 1. LLMService (2,416 LOC) — ⚠️ Candidato urgente a refactorización
- **Rol:** Fachada única para todas las operaciones del modelo
- **Relaciones:**
  - → MultiProviderManager: Fallback automático entre proveedores
  - → SkillManager: Carga dinámica de skills
  - → HistoryManager: Gestión de historial con resumos
  - → WorkspaceContext: Contexto del proyecto
  - ← AgentInteractionManager: Lo invoca para el grafo LangGraph
- **Funcionalidades:** Streaming, rate limiting, continuación automática, tool execution loop

### 2. AgentState (235 LOC) — Núcleo del estado
- **Rol:** Estado que fluye a través del grafo LangGraph
- **Patrón:** @dataclass con __setattr__ personalizado para sincronización
- **Relaciones:**
  - ↔ MessageManager: Sincronización bidireccional de mensajes
  - ↔ HistoryManager: Persistencia automática
  - ← AgentInteractionManager: Lo pasa al grafo
  - ← CommandApprovalHandler: Lee/escribe confirmaciones

### 3. MessageManager (411 LOC) — ⭐ Componente único
- **Rol:** Gestión dual de mensajes (API vs UI)
- **Características:**
  - _api_history: Formato LangChain para el LLM
  - _ui_messages: Formato para mostrar al usuario
  - rewind_to_timestamp(): Operaciones de rewind consistentes
  - ContextEvent: Tracking de condensaciones

### 4. SkillManager (1,336 LOC) — ⚠️ Candidato a refactorización
- **Rol:** Corazón del sistema de skills
- **Subcomponentes:** SkillValidator, SkillLoader, SkillRegistry, ToolRegistry
- **Relaciones:**
  - → SkillLoader: Carga JIT de módulos Python
  - → ToolRegistry: Registra herramientas para el LLM
  - ← LLMService: Lo inicializa y usa
- **Discovery:** 5 niveles (bundled → global → managed → workspace → external)

### 5. DelegationManager (102 LOC)
- **Rol:** Control de sub-agentes delegados
- **Límites:** max_depth=2, max_concurrent_children=3
- **Roles:** ORCHESTRATOR (acceso completo) vs LEAF (sin delegación, sin comandos)

### 6. CommandExecutor (325 LOC)
- **Rol:** Ejecución segura de comandos bash con PTY
- **Relaciones:**
  - ← execute_command skill: Lo invoca
  - → CommandApprovalHandler: Verificación de seguridad

### 7. FastAPI Server (1,038 + 937 + 805 LOC)
- **Rol:** Backend multi-canal
- **Canales:** WebSocket, SSE, REST, Telegram, Slack, Webhook, CLI
- **Relaciones:**
  - ↔ SessionPool: Gestiona sesiones persistentes
  - → AgentSession: Crea instancias de agente por sesión

---

## 📊 Métricas del Sistema

| Métrica | Valor |
|---------|-------|
| Archivos Python | ~156 |
| Líneas de código totales | ~43,463 |
| Skills disponibles | 25 (bundled) |
| Componentes core | 8 principales |
| Patrones de diseño | 7+ identificados |
| Niveles de seguridad | 5 (low → elevated) |
| Canales soportados | 6 (WS, SSE, REST, Telegram, Slack, CLI) |
| Proveedores LLM | 6+ (OpenRouter, Gemini, OpenAI, Anthropic, Ollama, KiloCode) |

---

## 🎯 Patrones de Diseño Identificados

| Patrón | Implementación | Ubicación |
|--------|----------------|-----------|
| Strategy | MultiProviderManager con fallback | core/multi_provider_manager.py |
| Observer | HeartbeatMonitor + interrupt_queue | core/delegation.py |
| Facade | LLMService como fachada única | core/llm_service.py |
| Command | CommandExecutor con confirmación | core/command_executor.py |
| Repository | HistoryManager + SessionManager | core/history_manager.py |
| Factory | SkillManager + skill_factory | core/skills/skill_manager.py |
| State Machine | AgentState como dataclass | core/agent_state.py |
| Plugin/JIT Loading | SkillLoader con importlib | core/skills/skill_manager.py |
| Adapter | ServerUI, Channel Adapters | server/session_pool.py |
| Proxy | WorkspaceContext | core/context/workspace_context.py |

---

## ⚠️ Riesgos y Deuda Técnica

### 🔴 Crítico
1. **LLMService (2,416 LOC)** — Monolítico, viola SRP. Debe descomponerse en: provider_config, message_converter, tool_parser, streaming_executor, fallback_handler, rate_limiter
2. **SkillManager (1,336 LOC)** — Acoplamiento alto, SkillLoader con CC=73 y 805 líneas
3. **Sin tests** — Cobertura <5% (solo 1 archivo de test para 156 archivos)

### 🟡 Alto
4. **Archivos .backup** en producción (agent_state.py.backup, llm_service.py.backup, code_agent.py.backup)
5. **Race conditions** en session_pool.py y command_approval_handler.py
6. **Dependencias circulares** potenciales: llm_service ↔ skill_manager
7. **bash_agent.py (1,326 LOC)** — Complejidad alta, acoplamiento

### 🟢 Mejoras
8. Docstrings solo en ~40% de funciones
9. Sin sistema de métricas/monitoreo
10. Sin circuit breaker para proveedores LLM

---

## ✅ Fortalezas Arquitectónicas

1. **Sistema de skills excepcionalmente robusto** — Discovery multinivel, JIT loading, seguridad por niveles, semantic routing
2. **Doble historial de mensajes** — Permite rewind consistente entre UI y API
3. **Multi-proveedor con fallback** — Resiliencia ante fallos de proveedores
4. **Delegación jerárquica con límites** — Control de profundidad y concurrencia
5. **Multi-canal nativo** — Telegram, Slack, WebSocket, REST desde el mismo core
6. **Comando de confirmación** — Sistema de aprobación seguro
7. **Persistencia de sesiones** — Sesiones que sobreviven a reinicios

---

## 📝 Recomendaciones Prioritarias

1. Refactorizar LLMService en componentes más pequeños
2. Agregar tests unitarios
3. Eliminar archivos .backup
4. Implementar circuit breaker
5. Agregar métricas de rendimiento

---

*Análisis completado el 2026-02-21. Todas las tareas registradas en task_tracker.*
