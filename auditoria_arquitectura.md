# Auditoría de Arquitectura — KogniTerm

**Proyecto:** KogniTerm  
**Ruta:** `/home/gato/Proyectos/Gemini-Interpreter`  
**Fecha:** 2025-01-28  
**Arquitecto:** BashAgent (KogniTerm)  
**Estado:** Completado

---

## 1. Resumen Ejecutivo

KogniTerm es un **agente de terminal AI** con backend en FastAPI y frontend en terminal UI (TUI) basada en Rich. El proyecto muestra una arquitectura madura con separación clara de responsabilidades, pero con áreas de mejora en gestión de estado, manejo de errores y desacoplamiento de dependencias.

### Puntuación General: **7.2/10**

| Dimensión | Puntuación | Observación |
|-----------|-----------|-------------|
| **Arquitectura general** | 8/10 | Separación clara de capas, pero con fugas de responsabilidad |
| **Patrones de diseño** | 7/10 | Uso correcto de StateGraph, pero con oportunidades de refactorización |
| **Calidad de código** | 6/10 | Code smells detectados, alta complejidad en nodos críticos |
| **Manejo de errores** | 5/10 | Excepciones genéricas, logging inconsistente |
| **Testabilidad** | 4/10 | Baja cobertura de tests, dependencias hardcodeadas |
| **Documentación** | 7/10 | Docstrings presentes, pero arquitectura general no documentada |

---

## 2. Visión General de la Arquitectura

### 2.1 Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CAPA DE PRESENTACIÓN                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Terminal TUI │  │   VS Code    │  │   Web Dashboard (futuro) │  │
│  │   (Rich)     │  │  Extensión   │  │                          │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────────┘  │
└─────────┼─────────────────┼─────────────────────────────────────────┘
          │                 │
          ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CAPA DE AGENTES (LangGraph)                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  BashAgent (1290 líneas) — Orquestador principal             │   │
│  │  ├── call_model_node      (CC: 17)                           │   │
│  │  ├── execute_tool_node    (CC: 67) ⚠️ Muy alta               │   │
│  │  ├── verification_node    (CC: 19)                           │   │
│  │  ├── task_tracker_node    (CC: 13)                           │   │
│  │  └── learning_node        (CC: 22)                           │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │  CodeAgent (851 líneas) — Desarrollo de código               │   │
│  │  └── execute_single_tool  (CC: 26)                          │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │  DeepResearcher (837 líneas) — Investigación profunda        │   │
│  │  ├── planning_node        (CC: 23)                          │   │
│  │  ├── research_node        (CC: 17)                          │   │
│  │  ├── reflection_node      (CC: 17)                          │   │
│  │  └── synthesis_node       (CC: 32) ⚠️ Muy alta              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CAPA DE SERVICIOS COMPARTIDOS                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐   │
│  │   LLMService     │  │  SessionPool     │  │  MemoryService  │   │
│  │ (Google Gemini)  │  │  (FastAPI)       │  │  (SQLite)       │   │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐   │
│  │ ToolManager      │  │  TaskTracker     │  │  PromptService  │   │
│  │ (Skill registry) │  │  (Skill bundled) │  │  (YAML-based)   │   │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       CAPA DE INFRAESTRUCTURA                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Backend  │  Docker Compose  │  Redis (cache)         │   │
│  │  - WebSocket      │  - API           │  - Sesiones            │   │
│  │  - REST API       │  - TUI           │  - Colas               │   │
│  │  - Health checks  │  - Logs          │                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Flujo de Ejecución Principal

```
Usuario → TUI → BashAgent → call_model_node
                              ↓
                         route_tools
                              ↓
              ┌──────────────┴──────────────┐
              ▼                             ▼
    task_tracker_node              execute_tool_node
    (ejecución directa)            (ThreadPoolExecutor)
              │                             │
              └──────────────┬──────────────┘
                             ▼
                       verification_node
                             │
                             ▼
                       call_model_node (siguiente turno)
```

---

## 3. Análisis de Componentes

### 3.1 Agentes

| Agente | Líneas | Complejidad Promedio | Nodos Críticos | Responsabilidad |
|--------|--------|---------------------|----------------|------------------|
| `bash_agent.py` | 1,290 | 13.05 | `execute_tool_node` (CC: 67), `learning_node` (CC: 22) | Orquestación general, ejecución de herramientas, gestión de confirmaciones |
| `code_agent.py` | 851 | 12.27 | `call_model_node` (CC: 31), `execute_single_tool` (CC: 26) | Desarrollo de código, edición de archivos |
| `deep_researcher.py` | 837 | 10.36 | `synthesis_node` (CC: 32), `planning_node` (CC: 23) | Investigación profunda, síntesis de información |

**Hallazgo:** Los tres agentes comparten estructuras similares (StateGraph, nodos `call_model`, `execute_tool`, `should_continue`), pero **no hay una clase base común** que elimine la duplicación.

### 3.2 Servicios Compartidos

| Servicio | Responsabilidad | Estado |
|----------|-----------------|--------|
| `LLMService` | Abstracción de Google Gemini, gestión de tools | ✅ Bien definido |
| `SessionPool` | Pool de sesiones WebSocket | ✅ Funcional |
| `MemoryService` | Persistencia de memoria en SQLite | ✅ Funcional |
| `ToolManager` | Registro y descubrimiento de skills/tools | ✅ Funcional |
| `TaskTracker` | Seguimiento de tareas (skill bundled) | ⚠️ Acoplamiento a `bash_agent` |

---

## 4. Code Smells y Deuda Técnica

### 4.1 Code Smells Identificados

#### 🔴 CRÍTICO

| # | Code Smell | Ubicación | Impacto | Recomendación |
|---|-----------|-----------|---------|---------------|
| 1 | **God Method** | `execute_tool_node` (bash_agent.py) | CC: 67 — imposible de testear | Extraer lógica a métodos especializados: `_execute_file_tool`, `_execute_shell_tool`, `_execute_search_tool` |
| 2 | **Duplicación de Código** | `should_continue` en 3 agentes | Mantenibilidad | Extraer a `BaseAgent.should_continue(state)` |
| 3 | **Feature Envy** | `bash_agent.py` accede a `state.tool_pending_confirmation` desde múltiples nodos | Acoplamiento | Encapsular en `AgentState.get_pending_confirmation()` |
| 4 | **Cargar módulos dinámicamente** | `_load_file_ops_module`, `_ensure_task_tracker_module_loaded` | Complejidad innecesaria | Usar imports estáticos con `importlib` solo para plugins externos |

#### 🟡 MEDIO

| # | Code Smell | Ubicación | Impacto | Recomendación |
|---|-----------|-----------|---------|---------------|
| 5 | **Long Method** | `get_system_message` (bash_agent.py) | 80+ líneas construyendo string | Usar template engine (Jinja2) o builder pattern |
| 6 | **Magic Strings** | `"Aprobado"`, `"Denegado"` en `handle_tool_confirmation` | Fragilidad | Constantes enum o `ConfirmationStatus` |
| 7 | **Cargar módulos con guiones** | `file-operations` skill | Workaround frágil | Renombrar skill a `file_operations` o usar entry_points |
| 8 | **Global state** | `_task_tracker_module`, `_task_tracker_fn` | Testing difícil | Inyectar como dependencia en `create_bash_agent` |

#### 🟢 BAJO

| # | Code Smell | Ubicación | Impacto | Recomendación |
|---|-----------|-----------|---------|---------------|
| 9 | **Comentarios obsoletos** | `# Nueva importación` en imports | Basura visual | Limpiar comentarios de versionado |
| 10 | **Hardcoded paths** | `_Path(__file__).resolve().parent.parent.parent` | Portabilidad | Usar `importlib.resources` o configuración |

### 4.2 Archivos de Backup Detectados

```
code_agent.py.backup
llm_service.py.backup
agent_state.py.backup
```

**Acción recomendada:** Eliminar o mover a `.archive/` — estos archivos indican refactorizaciones incompletas.

### 4.3 Dependencias Problemáticas

```python
# bash_agent.py:324 — Importación condicional dentro de función
from kogniterm.core.exceptions import UserConfirmationRequired

# bash_agent.py:459-462 — Importaciones dentro de nodo
from kogniterm.terminal.themes import Icons
from rich.padding import Padding
```

**Problema:** Importaciones dentro de funciones dificultan el testing y ocultan dependencias.

**Solución:** Mover al top-level del módulo.

---

## 5. Análisis de Complejidad Ciclomática

### 5.1 Métricas por Agente

| Agente | Promedio CC | Máximo CC | Nodo Más Complejo | Evaluación |
|--------|-------------|-----------|-------------------|------------|
| `bash_agent.py` | 13.05 | 67 | `execute_tool_node` | ⚠️ Requiere refactorización |
| `code_agent.py` | 12.27 | 31 | `call_model_node` | 🟡 Aceptable con tests |
| `deep_researcher.py` | 10.36 | 32 | `synthesis_node` | 🟡 Aceptable con tests |

### 5.2 Umbrales de Alerta

| CC | Nivel | Acción Requerida |
|----|-------|------------------|
| 1-10 | Bajo | Ninguna |
| 11-20 | Medio | Considerar refactorización |
| 21-40 | Alto | Refactorización recomendada |
| 41+ | Crítico | Refactorización obligatoria |

**Acciones inmediatas:**
1. `execute_tool_node` (CC: 67) — **Refactorizar urgentemente**
2. `synthesis_node` (CC: 32) — Planificar refactorización
3. `call_model_node` en `code_agent.py` (CC: 31) — Monitorear

---

## 6. Patrones de Diseño Identificados

### 6.1 Patrones Aplicados Correctamente

| Patrón | Uso | Evaluación |
|--------|-----|------------|
| **State Pattern** | `AgentState` como estado compartido | ✅ Bien implementado |
| **Graph/Workflow** | LangGraph `StateGraph` para orquestación | ✅ Correcto |
| **Dependency Injection** | `llm_service`, `terminal_ui` como parámetros | ✅ Bueno |
| **Strategy Pattern** | Tools como estrategias intercambiables | ✅ Correcto |
| **Singleton** | `_task_tracker_module` como caché | ⚠️ Funcional pero testabilidad |

### 6.2 Patrones Faltantes o Mejorables

| Patrón | Aplicación Sugerida | Beneficio |
|--------|---------------------|-----------|
| **Template Method** | Clase base `BaseAgent` con flujo común | Eliminar duplicación entre agentes |
| **Chain of Responsibility** | Pipeline de herramientas | Mejor extensibilidad |
| **Observer** | Eventos de estado del agente | Desacoplar TUI del agente |
| **Factory** | Creación de nodos especializados | Mejor testabilidad |
| **Circuit Breaker** | Protección contra LLM caído | Resiliencia |

---

## 7. Análisis de Dependencias

### 7.1 Dependencias Externas

| Dependencia | Versión | Uso | Riesgo |
|-------------|---------|-----|--------|
| `langgraph` | Latest | Orquestación de agentes | 🟡 Breaking changes frecuentes |
| `google.genai` | Latest | LLM backend | 🟡 Cambios de API |
| `fastapi` | Latest | API backend | 🟢 Estable |
| `rich` | Latest | TUI | 🟢 Estable |
| `docker` | Latest | Contenedores | 🟢 Estable |

### 7.2 Dependencias Internas Críticas

```
bash_agent.py ──→ base_agent.py (BaseAgentNode)
bash_agent.py ──→ prompt_processor.py
bash_agent.py ──→ exceptions.py
bash_agent.py ──→ skills/bundled/file-operations/ (carga dinámica)
bash_agent.py ──→ skills/bundled/task-tracker/ (carga dinámica)
```

**Riesgo:** El acoplamiento a skills bundled mediante carga dinámica dificulta:
- Testing unitario
- Refactorización
- Detección de errores en tiempo de importación

---

## 8. Evaluación de la Extensión VS Code

### 8.1 Estado Actual

| Componente | Estado | Observación |
|------------|--------|-------------|
| **Estructura base** | 🟡 En desarrollo | Carpetas `src/`, `package.json` presentes |
| **API Client** | 🟡 Parcial | Conexión WebSocket al backend |
| **Comandos** | 🟡 Básicos | `kogniterm.start`, `kogniterm.stop` |
| **Tests** | 🔴 Ausentes | Sin tests detectados |
| **CI/CD** | 🔴 Ausente | Sin GitHub Actions |

### 8.2 Recomendaciones

1. **Completar MVP antes de producción:**
   - Tests de integración con backend
   - Manejo de reconexión WebSocket
   - Configuración de usuario persistente

2. **Arquitectura sugerida:**
```
vscode-extension/
├── src/
│   ├── extension.ts          # Entry point
│   ├── api/
│   │   ├── client.ts         # WebSocket client
│   │   └── types.ts          # TypeScript types
│   ├── commands/
│   │   ├── start.ts
│   │   ├── stop.ts
│   │   └── status.ts
│   ├── ui/
│   │   └── terminal.ts       # Terminal panel integration
│   └── config/
│       └── settings.ts       # User preferences
├── tests/
│   └── integration/
│       └── backend.test.ts
└── package.json
```

---

## 9. Recomendaciones Prioritarias

### 9.1 Acciones Inmediatas (Semana 1-2)

| # | Acción | Impacto | Esfuerzo |
|---|--------|---------|----------|
| 1 | Refactorizar `execute_tool_node` (CC: 67) | Alto | 2-3 días |
| 2 | Eliminar archivos `.backup` | Bajo | 1 hora |
| 3 | Mover importaciones al top-level | Medio | 1 día |
| 4 | Crear `BaseAgent` para eliminar duplicación | Alto | 2 días |

### 9.2 Acciones a Corto Plazo (Mes 1)

| # | Acción | Impacto | Esfuerzo |
|---|--------|---------|----------|
| 5 | Implementar tests unitarios para nodos críticos | Alto | 1 semana |
| 6 | Añadir logging estructurado (JSON) | Medio | 2 días |
| 7 | Documentar arquitectura en README | Medio | 1 día |
| 8 | Configurar pre-commit hooks (black, ruff, mypy) | Medio | 1 día |

### 9.3 Acciones a Mediano Plazo (Mes 2-3)

| # | Acción | Impacto | Esfuerzo |
|---|--------|---------|----------|
| 9 | Implementar Circuit Breaker para LLM | Alto | 3 días |
| 10 | Añadir métricas y observabilidad (Prometheus) | Alto | 1 semana |
| 11 | Completar tests de integración backend | Alto | 2 semanas |
| 12 | Diseñar sistema de plugins para skills | Medio | 1 semana |

---

## 10. Riesgos Identificados

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| **`execute_tool_node` se vuelve ingobernable** | Alta | Crítico | Refactorizar en sprint 1 |
| **Carga dinámica rompe en actualizaciones** | Media | Alto | Migrar a imports estáticos |
| **Falta de tests permite regresiones** | Alta | Alto | Implementar tests antes de nuevas features |
| **Acoplamiento a Gemini limita portabilidad** | Media | Medio | Abstraer `LLMService` con interfaces |
| **Extensión VS Code sin CI/CD** | Media | Bajo | Configurar GitHub Actions |

---

## 11. Conclusiones

KogniTerm presenta una **arquitectura funcional y escalable** en el backend, con un diseño de agentes basado en LangGraph que permite orquestación compleja de herramientas. Sin embargo, la deuda técnica acumulada en el agente principal (`bash_agent.py`) y la falta de tests representan riesgos significativos para el mantenimiento a largo plazo.

### Fortalezas
- ✅ Separación clara de capas (agentes, servicios, infraestructura)
- ✅ Uso de patrones modernos (StateGraph, DI)
- ✅ Sistema de skills extensible
- ✅ TUI robusta con Rich

### Debilidades
- ❌ Alta complejidad en nodos críticos (CC > 60)
- ❌ Duplicación de código entre agentes
- ❌ Carga dinámica de módulos frágil
- ❌ Baja cobertura de tests

### Próximos Pasos
1. **Refactorizar `execute_tool_node`** — dividir en métodos especializados
2. **Crear `BaseAgent`** — eliminar duplicación entre agentes
3. **Implementar tests unitarios** — empezar por nodos críticos
4. **Completar extensión VS Code** — tests de integración primero

---

## 12. Anexos

### 12.1 Métricas Detalladas

| Archivo | Líneas | Funciones | Complejidad Promedio |
|---------|--------|-----------|---------------------|
| `bash_agent.py` | 1,290 | 18 | 13.05 |
| `code_agent.py` | 851 | 11 | 12.27 |
| `deep_researcher.py` | 837 | 11 | 10.36 |

### 12.2 Herramientas Utilizadas

- `code_analysis` (radon) — métricas de complejidad
- `read_file_tool` — inspección de código
- `task_tracker` — gestión de auditoría

### 12.3 Referencias

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Clean Code — Robert C. Martin](https://www.oreilly.com/library/view/clean-code-a/9780136083238/)
- [Refactoring — Martin Fowler](https://refactoring.com/)

---

*Documento generado automáticamente por BashAgent durante la auditoría de arquitectura de KogniTerm.*
