# Análisis de Arquitectura — KogniTerm

**Proyecto**: KogniTerm  
**Ruta**: `/home/gato/Proyectos/Gemini-Interpreter/kogniterm`  
**Fecha de análisis**: 2025-01-09  
**Analizado por**: Architecture Analyzer Skill  

---

## 1. Resumen Ejecutivo

KogniTerm es una **terminal de IA avanzada** con arquitectura cliente-servidor, diseñada como un agente autónomo persistente. El sistema combina:

- **Backend FastAPI** con WebSocket, SSE y REST para multi-canal
- **Frontend TUI** (Textual) para experiencia de terminal enriquecida
- **Orquestación de agentes** con LangGraph y CrewAI
- **Sistema de skills modular** con carga dinámica JIT
- **Indexación vectorial** (ChromaDB) para búsqueda semántica en el codebase
- **Gestión de sesiones persistentes** con ThreadManager y SessionPool

### Arquitectura General

```
┌─────────────────────────────────────────────────────────────────┐
│                        Clientes                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   TUI        │  │   WebSocket  │  │   REST / SSE         │  │
│  │ (Textual)    │  │   Client     │  │   Client             │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
└─────────┼──────────────────┼────────────────────┼──────────────┘
          │                  │                    │
          └──────────────────┼────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────┐
│                  KogniTerm Server (FastAPI)                      │
│  ┌──────────────────────────▼─────────────────────────────────┐ │
│  │                    SessionPool                              │ │
│  │  • Gestión de sesiones persistentes                        │ │
│  │  • ThreadManager (hilos de chat)                            │ │
│  │  • Cola de eventos UI por sesión                            │ │
│  └──────────────────────────┬─────────────────────────────────┘ │
│                             │                                   │
│  ┌──────────────────────────▼─────────────────────────────────┐ │
│  │              LLMService (Core)                              │ │
│  │  • Multi-proveedor (LiteLLM)                                │ │
│  │  • Streaming unificado                                      │ │
│  │  • Gestión de herramientas (tools)                          │ │
│  │  • VectorDBManager (ChromaDB)                               │ │
│  └──────────────────────────┬─────────────────────────────────┘ │
│                             │                                   │
│  ┌──────────────────────────▼─────────────────────────────────┐ │
│  │              Sistema de Skills                              │ │
│  │  • SkillManager (JIT loading)                               │ │
│  │  • Discovery automático                                      │ │
│  │  • Filtrado por contexto/permisos                           │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Estructura de Capas

### 2.1 Capa de Presentación (TUI / Clientes)

**Ruta**: `kogniterm/terminal/`

| Componente | Responsabilidad |
|------------|-----------------|
| `terminal.py` | Punto de entrada, carga de configuración, inicialización de servicios |
| `tui/tui_app.py` | Aplicación Textual principal (KogniTermTUI) |
| `terminal_ui.py` | UI de terminal con Rich, paneles, streaming |
| `agent_interaction_manager.py` | Gestión de interacciones con el agente |
| `command_approval_handler.py` | Manejo de aprobación de comandos |
| `meta_command_processor.py` | Procesamiento de meta-comandos |

**Patrón**: La TUI actúa como **cliente del servidor central**, comunicándose vía WebSocket.

### 2.2 Capa de API y Servidor

**Ruta**: `kogniterm/server/`

| Componente | Responsabilidad |
|------------|-----------------|
| `app.py` | FastAPI principal, endpoints REST/WebSocket/SSE |
| `session_pool.py` | Pool de sesiones, gestión de estado por sesión |
| `config.py` | Configuración del servidor y canales |
| `channel_adapters.py` | Adaptadores para Slack, Telegram, Webhooks |

**Canales soportados**:
- WebSocket bidireccional (`/ws/{session_id}`)
- Server-Sent Events (`/sse/{session_id}`)
- REST síncrono (`/chat/{session_id}`)
- REST asíncrono (`/api/chat/message`)
- Canales externos: Telegram, Slack, Webhooks

### 2.3 Capa de Lógica de Negocio (Core)

**Ruta**: `kogniterm/core/`

| Componente | Responsabilidad |
|------------|-----------------|
| `llm_service.py` | Orquestación LLM multi-proveedor, streaming, tools |
| `agent_state.py` | Estado del agente (mensajes, herramientas, contexto) |
| `command_executor.py` | Ejecución de comandos del sistema |
| `multi_provider_manager.py` | Gestión de múltiples proveedores LLM |
| `thread_manager.py` | Gestión de hilos de chat |
| `context/` | Indexación de codebase, vector DB |

### 2.4 Capa de Skills y Herramientas

**Ruta**: `kogniterm/core/skills/`

| Componente | Responsabilidad |
|------------|-----------------|
| `skill_manager.py` | Discovery, validación, carga dinámica de skills |
| `tool_registry.py` | Registro centralizado de herramientas |
| `tool_utils.py` | Utilidades para normalización de schemas |

**Sistema de Skills**:
- Carga JIT (Just-In-Time) de módulos Python
- Validación de estructura y metadatos
- Filtrado por seguridad, contexto y permisos
- Compatibilidad con sistema legacy

---

## 3. Componentes Críticos

### 3.1 SessionPool — Motor de Sesiones

**Ubicación**: `kogniterm/server/session_pool.py`

**Responsabilidades**:
- Mantener una sesión de agente por `session_id`
- Reutilizar sesiones indefinidamente (agente "siempre despierto")
- Gestionar historial, cola de eventos y estado por sesión
- Inicialización diferida de LLMService

**Patrón**: Singleton con pool de sesiones indexado por `session_id`.

### 3.2 LLMService — Orquestador LLM

**Ubicación**: `kogniterm/core/llm_service.py`

**Responsabilidades**:
- Interfaz unificada para múltiples proveedores (LiteLLM)
- Streaming de respuestas en tiempo real
- Gestión de herramientas (tools) con conversión de formatos
- Integración con ChromaDB para búsqueda semántica
- Manejo de timeouts y reintentos

**Características clave**:
- Conversión automática de herramientas LangChain → LiteLLM
- Soporte para modelos con pensamiento extendido (reasoning)
- Detección de bucles críticos

### 3.3 SkillManager — Sistema Modular

**Ubicación**: `kogniterm/core/skills/skill_manager.py`

**Responsabilidades**:
- Discovery automático en múltiples ubicaciones
- Validación de estructura de skills
- Carga dinámica de módulos Python
- Registro de herramientas en el sistema
- Filtrado por seguridad y contexto

**Estructura de una Skill**:
```
skill-name/
├── SKILL.md              # Documentación y metadatos
├── scripts/
│   └── tool.py           # Implementación Python
├── references/           # Documentación adicional
├── assets/               # Recursos estáticos
└── parameters_schema     # Schema JSON de parámetros
```

---

## 4. Patrones de Diseño Detectados

### 4.1 Patrones Arquitectónicos

| Patrón | Aplicación | Ubicación |
|--------|-----------|-----------|
| **Cliente-Servidor** | TUI → Server via WebSocket | `terminal/` ↔ `server/` |
| **Session per User** | Pool de sesiones por session_id | `session_pool.py` |
| **Adapter** | ChannelAdapters para Telegram/Slack | `server/channel_adapters.py` |
| **Observer** | Eventos UI por sesión | `session_pool.py`, `tui_app.py` |
| **Strategy** | Estrategias de edición de archivos | `advanced_file_editor_tool.py` |

### 4.2 Patrones de Código

| Patrón | Aplicación |
|--------|-----------|
| **Singleton** | SessionPool, LLMService |
| **Factory** | Creación de sesiones, agentes |
| **Template Method** | BaseAgentNode con call_model |
| **Decorator** | Validación de schemas, logging |
| **JIT Loading** | Carga dinámica de skills |

---

## 5. Métricas de Código

### 5.1 Distribución por Lenguaje

| Lenguaje | Archivos | Líneas (aprox.) |
|----------|----------|-----------------|
| Python | 150+ | 45,000+ |
| Markdown | 30+ | 8,000+ |
| YAML/JSON | 20+ | 2,000+ |
| Shell | 10+ | 500+ |

### 5.2 Complejidad Ciclomática (Estimada)

| Módulo | Complejidad | Observaciones |
|--------|-------------|----------------|
| `llm_service.py` | Alta (50+) | Lógica de streaming, múltiples proveedores |
| `session_pool.py` | Media (20-30) | Gestión de estado, eventos async |
| `skill_manager.py` | Media (25-35) | Carga dinámica, validación |
| `base_agent.py` | Media (20-25) | Lógica común de agentes |
| `app.py` | Alta (40+) | Múltiples endpoints, async |

### 5.3 Acoplamiento y Cohesión

- **Alto acoplamiento**: `llm_service.py` con dependencias difusas
- **Media cohesión**: Módulos core bien definidos
- **Bajo acoplamiento**: Skills system con interfaz bien definida

---

## 6. Riesgos y Deuda Técnica

### 6.1 Riesgos Críticos

| Riesgo | Impacto | Probabilidad | Mitigación |
|--------|---------|--------------|------------|
| **Memory leak en sesiones** | Alto | Media | Implementar TTL y limpieza periódica |
| **Race conditions en SessionPool** | Alto | Baja | Usar locks más granulares |
| **Bloqueo en carga de LLMService** | Medio | Media | Ya mitigado con carga en background |
| **Dependencia externa (LiteLLM)** | Alto | Baja | Abstraer interfaz LLM |

### 6.2 Deuda Técnica

| Deuda | Prioridad | Esfuerzo |
|-------|-----------|----------|
| **Tests insuficientes** | Alta | Alto |
| **Documentación de API incompleta** | Media | Medio |
| **Logging inconsistente** | Media | Bajo |
| **Manejo de errores variable** | Media | Medio |
| **Configuración hardcodeada** | Baja | Bajo |

### 6.3 Puntos de Dolor Identificados

1. **`llm_service.py` (2456 líneas)**: Archivo monolítico, difícil de mantener
2. **Conversión de tools**: Lógica compleja y frágil en `_convert_langchain_tool_to_litellm`
3. **Gestión de estado**: Mezcla de estado en memoria y persistencia
4. **Dependencias circulares**: Riesgo entre `terminal_ui.py` y módulos core

---

## 7. Recomendaciones

### 7.1 Corto Plazo (1-2 sprints)

1. **Refactorizar `llm_service.py`**
   - Separar en módulos: `llm_client.py`, `tool_manager.py`, `streaming.py`
   - Objetivo: Reducir a <800 líneas por módulo

2. **Implementar tests básicos**
   - Tests unitarios para `SessionPool`
   - Tests de integración para WebSocket
   - Cobertura objetivo: 60%

3. **Mejorar manejo de errores**
   - Estructura de excepciones personalizada
   - Logging estructurado (JSON)

### 7.2 Mediano Plazo (3-6 sprints)

1. **Sistema de persistencia mejorado**
   - Implementar checkpoint de estado de agente
   - Recuperación automática de sesiones

2. **Optimización de rendimiento**
   - Lazy loading de skills
   - Cache de modelos LLM
   - Compresión de historial

3. **Mejorar documentación**
   - Documentación de API con OpenAPI
   - Arquitectura Decision Records (ADR)
   - Guías de contribución

### 7.3 Largo Plazo (6+ sprints)

1. **Arquitectura de microservicios**
   - Separar SessionPool como servicio independiente
   - API Gateway para canales

2. **Sistema de plugins**
   - Hot-reload de skills
   - Marketplace de skills

3. **Observabilidad**
   - Métricas Prometheus
   - Tracing distribuido (OpenTelemetry)
   - Dashboards de monitoreo

---

## 8. Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Clientes                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │   TUI       │  │   Web       │  │   API REST / SSE            │ │
│  │ (Textual)   │  │   Client    │  │   Client                    │ │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────────┘ │
└─────────┼────────────────┼────────────────────┼───────────────────┘
          │                │                    │
          └────────────────┼────────────────────┘
                           │
┌──────────────────────────┼─────────────────────────────────────────┐
│                  FastAPI Server                                     │
│  ┌──────────────────────────▼───────────────────────────────────┐ │
│  │                      Routers                                  │ │
│  │  /ws/{session_id}  /sse/{session_id}  /chat/{session_id}    │ │
│  │  /sessions  /threads  /config  /api/execute                  │ │
│  └──────────────────────────┬───────────────────────────────────┘ │
│                             │                                      │
│  ┌──────────────────────────▼───────────────────────────────────┐ │
│  │                    SessionPool                                │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐ │ │
│  │  │  Session    │  │  Session    │  │  Session             │ │ │
│  │  │  Manager    │  │  Manager    │  │  Manager             │ │ │
│  │  └─────────────┘  └─────────────┘  └──────────────────────┘ │ │
│  └──────────────────────────┬───────────────────────────────────┘ │
│                             │                                      │
│  ┌──────────────────────────▼───────────────────────────────────┐ │
│  │                    LLMService                                 │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐ │ │
│  │  │  LiteLLM    │  │  Tool       │  │  VectorDB            │ │ │
│  │  │  Client     │  │  Manager    │  │  Manager             │ │ │
│  │  └─────────────┘  └─────────────┘  └──────────────────────┘ │ │
│  └──────────────────────────┬───────────────────────────────────┘ │
│                             │                                      │
│  ┌──────────────────────────▼───────────────────────────────────┐ │
│  │                    SkillManager                               │ │
│  │  • Discovery  • Validation  • JIT Loading  • Registry        │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
┌─────────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
│   Providers    │  │   Tools     │  │   Storage   │
│  ┌───────────┐ │  │  ┌────────┐ │  │  ┌────────┐ │
│  │  Google   │ │  │  │ Skills │ │  │  │ChromaDB│ │
│  │  OpenAI   │ │  │  │ System │ │  │  │  File  │ │
│  │  Anthropic│ │  │  │ Legacy │ │  │  │ System │ │
│  │  Ollama   │ │  │  │ Tools  │ │  │  └────────┘ │
│  │  OpenRouter│ │  │  └────────┘ │  │           │
│  └───────────┘ │  └─────────────┘  └───────────┘ │
└───────────────┘  └──────────────┘  └──────────────┘
```

---

## 9. Anexos

### 9.1 Archivos Analizados

- `/home/gato/Proyectos/Gemini-Interpreter/kogniterm/main.py`
- `/home/gato/Proyectos/Gemini-Interpreter/kogniterm/terminal/terminal.py`
- `/home/gato/Proyectos/Gemini-Interpreter/kogniterm/server/app.py`
- `/home/gato/Proyectos/Gemini-Interpreter/kogniterm/server/session_pool.py`
- `/home/gato/Proyectos/Gemini-Interpreter/kogniterm/server/config.py`
- `/home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/llm_service.py`
- `/home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/base_agent.py`
- `/home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/skills/skill_manager.py`

### 9.2 Glosario

- **TUI**: Terminal User Interface (interfaz de usuario de terminal)
- **LLM**: Large Language Model
- **JIT**: Just-In-Time (carga bajo demanda)
- **SSE**: Server-Sent Events
- **ChromaDB**: Base de datos vectorial para embeddings
- **LiteLLM**: Biblioteca para orquestar múltiples proveedores LLM
- **LangGraph**: Framework para agentes con grafos de estado
- **Skill**: Módulo extensible con herramientas y documentación

---

*Generado por Architecture Analyzer Skill*  
*Para más detalles, revisar el código fuente en las rutas indicadas.*
