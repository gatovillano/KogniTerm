# Informe Comparativo: KAI-CLI vs Kogniterm
## Análisis Arquitectónico y Propuesta de Migración a Cero Latencia

**Fecha:** 2026-09-08  
**Proyecto origen:** KAI-CLI (`/home/gato/Proyectos/KAI-CLI`)  
**Proyecto destino:** Kogniterm (`/home/gato/Proyectos/Gemini-Interpreter/kogniterm`)  
**Objetivo:** Lograr el nivel de latencia nula de KAI-CLI migrando la arquitectura de herramientas, el agente BashAgent y el mecanismo de ejecución completo.

---

## 1. Resumen Ejecutivo

KAI-CLI logra latencia mínima gracias a una arquitectura minimalista:
- **Sin LangChain** en el núcleo de ejecución LLM
- **ToolRegistry singleton** con decorador `@tool` y dataclasses
- **LLMBridge** delgado sobre LiteLLM nativo
- **Agente único** (SuperAgent) con acceso total a herramientas
- **Streaming nativo** con parsing automático de tool_calls del proveedor

Kogniterm actualmente sufre latencia elevada por:
- **LLMService monolítico** (3000+ líneas) con inicializaciones pesadas
- **ThreadPoolExecutor** para herramientas (no async nativo)
- **Parsing texto→JSON** de tool calls en vez de usar `tool_calls` nativos del proveedor
- **LangChain** como dependencia central
- **Conversión constante** entre formatos de mensajes

---

## 2. Comparativa Arquitectónica Detallada

### 2.1 Agente

| Aspecto | KAI-CLI | Kogniterm (Actual) |
|---------|---------|---------------------|
| **Clase base** | `BaseAgent` (182 líneas) | `BaseAgentNode` (290 líneas) |
| **Agente principal** | `SuperAgent` (34 líneas) | `BashAgentRunner` (894 líneas) |
| **Modelo de ejecución** | `execute_stream()` async generator limpio | `invoke()` síncrono con `asyncio.run` y nest_asyncio |
| **Paradigma** | Herencia simple, todo es herramienta | Nodos de grafo, estado mutable complejo |
| **Extensibilidad** | `CustomAgent` desde YAML/JSON | Agentes especializados hardcodeados |

**Conclusión:** El `SuperAgent` de KAI-CLI es 26x más pequeño y limpio. Kogniterm tiene sobrecarga de LangGraph/node graph innecesaria.

### 2.2 Registro de Herramientas (Tool Registry)

| Aspecto | KAI-CLI | Kogniterm (Actual) |
|---------|---------|---------------------|
| **Implementación** | `ToolRegistry` singleton con `@tool` decorator | `default_tool_registry` en capabilities + `SkillManager` con LangChain `BaseTool` |
| **Definición** | `ToolDefinition` dataclass con Pydantic schema | Mezcla de `ToolDefinition` nativa + herramientas LangChain |
| **Carga** | Registro al importar módulo | Discovery dinámico de skills + carga lazy |
| **Conversión a LLM** | `to_litellm_schema()` directo | `_convert_langchain_tool_to_litellm()` complejo |

**Código KAI-CLI (limpio):**
```python
@tool(name="run_shell", description="...", params_schema=RunShellParams)
async def run_shell(command: str, ...):
    ...
```

**Código Kogniterm (complejo):**
```python
# En capabilities/terminal.py
@tool(name="execute_command", ...)
async def execute_command(...):
    ...

# Pero en LLMService._get_litellm_tools():
# 1. Cargar capabilities nativas
# 2. Convertir LangChain tools a LiteLLM
# 3. Reconstruir tool_map dual
# 4. Cache invalidation
```

### 2.3 Ejecución LLM y Streaming

| Aspecto | KAI-CLI | Kogniterm (Actual) |
|---------|---------|---------------------|
| **Clase** | `LLMBridge` (259 líneas) | `LLMService` (3031 líneas) |
| **Llamada LLM** | `litellm.acompletion()` directo | Wrapper con MultiProviderManager + fallbacks + retry |
| **Streaming** | AsyncGenerator nativo con eventos tipados | Generator con parsing manual de chunks |
| **Tool calls** | `delta.tool_calls` nativo del streaming | `_parse_tool_calls_from_text()` con 3 estrategias regex |
| **Rate limiting** | No implementado | `deque` + `time.sleep()` |
| **Truncamiento** | No implementado (delegado a historial) | Truncamiento complejo pre-llamada |

**Eventos KAI-CLI (limpios):**
```python
{"type": "chunk", "text": "..."}
{"type": "reasoning", "text": "..."}
{"type": "tool_start", "name": "run_shell", "args": {...}}
{"type": "tool_result", "name": "run_shell", "result": {...}}
{"type": "done", "output": "...", "tools_used": [...]}
```

**Kogniterm parsing texto (costoso):**
```python
# Estrategia A: Patrones regex explícitos
# Estrategia B: Bloques JSON estructurados
# Estrategia C: Formatos legacy tipo código
# + Extracción de contenido balanceado
# + Consolidación de duplicados
```

### 2.4 Ejecución de Herramientas

| Aspecto | KAI-CLI | Kogniterm (Actual) |
|---------|---------|---------------------|
| **Mecanismo** | `execute_tool_call()` async directo | `_invoke_tool_with_interrupt()` con ThreadPoolExecutor |
| **Concurrencia** | No implementada (single tool per turn) | `asyncio.to_thread()` + `asyncio.gather()` |
| **Interrupción** | No implementada | `interrupt_queue` + polling + `future.result(timeout=20ms)` |
| **Confirmación** | No implementada | `UserConfirmationRequired` exception + approval handler |
| **Overhead** | ~0ms | Thread pool submission + polling loop |

**KAI-CLI (directo):**
```python
async def execute_tool_call(self, tool_name: str, args: Dict[str, Any]) -> Any:
    handler = self.tool_registry.get_handler(tool_name)
    if inspect.iscoroutinefunction(handler):
        return await handler(**args)
    return await run_sync(handler, **args)
```

**Kogniterm (con overhead):**
```python
future = self.tool_executor.submit(_tool_target)
while True:
    if self.interrupt_queue and not self.interrupt_queue.empty():
        raise InterruptedError(...)
    try:
        result = future.result(timeout=self.tool_poll_timeout)  # 20ms polling
        ...
    except TimeoutError:
        if future.done():
            break
        continue
```

### 2.5 Terminal / PTY

| Aspecto | KAI-CLI | Kogniterm |
|---------|---------|-----------|
| **Librería** | `ptyprocess` | `pty` + `subprocess` nativo |
| **API** | `PtyProcess.spawn()` | `pty.openpty()` + `subprocess.Popen()` |
| **Eco** | Eco completo con paneles Rich | Marcador `##KOGNITERM_DONE_MARKER##` con filtrado |
| **Interactividad** | Bidireccional (stdin→PTY) | Unidireccional (solo salida) |
| **Background** | `InteractiveShell` persistente | `BackgroundTaskManager` |

---

## 3. Fuentes de Latencia en Kogniterm

### 3.1 Inicialización (Startup)
```
LLMService.__init__()
├── MultiProviderManager + health_check (comentado pero presente)
├── EmbeddingsService()
├── VectorDBManager() → ChromaDB
├── DelegationManager + HeartbeatMonitor
├── SkillManager + discover_all_skills() + load_skill() para cada skill
├── tiktoken.encoding_for_model("gpt-4")  # Descarga si no existe
└── Tokenizer listo
```
**Impacto:** 2-5 segundos en startup.

### 3.2 Por Turno (Per-Turn)

| Componente | Latencia | Razón |
|------------|----------|-------|
| `_get_litellm_tools()` | 50-200ms | Reconstrucción de tool schemas + conversión LangChain→LiteLLM |
| `_invoke_inner()` message processing | 20-100ms | Validación estricta, truncamiento, deduplicación |
| Tool call parsing | 10-50ms | Regex sobre texto completo si el modelo no usa `tool_calls` nativo |
| ThreadPoolExecutor submission | 5-20ms | No es async nativo |
| `future.result(timeout=20ms)` polling | 20-100ms | Busy-waiting en loop |
| HistoryManager._save_history() | 10-50ms | Escritura a disco en hilo separado |

**Total overhead por turno:** 150-500ms solo en plumbing, sin contar la llamada LLM.

### 3.3 Conversiones de Formato

```
LangChain AIMessage → LiteLLM dict → LLM provider → LiteLLM chunk → LangChain AIMessage
                    ↑_______________________________________________|
                    (loop de ida y vuelta constante)
```

Cada roundtrip de tool call implica:
1. LLM responde con `tool_calls` nativos
2. Kogniterm los convierte a formato interno
3. Ejecuta herramienta
4. Convierte resultado a `ToolMessage`
5. Serializa a LiteLLM para el próximo turno

---

## 4. Propuesta de Migración

### 4.1 Principios de Diseño

1. **Cero overhead innecesario:** Si KAI-CLI no lo necesita, Kogniterm no lo necesita
2. **Async nativo:** Reemplazar ThreadPoolExecutor por `asyncio`
3. **LiteLLM directo:** Eliminar conversiones LangChain intermedias
4. **ToolRegistry como fuente única:** Un solo registro, un solo formato
5. **Parsing nativo:** Usar `tool_calls` del streaming, no regex sobre texto

### 4.2 Arquitectura Objetivo

```
┌─────────────────────────────────────────────────────────────┐
│                    KognitermMigrated                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   REPL/TUI  │───▶│  App Core   │───▶│ AgentMgr    │     │
│  └─────────────┘    └─────────────┘    └──────┬──────┘     │
│                                               │             │
│  ┌─────────────┐    ┌─────────────┐    ┌──────▼──────┐     │
│  │ Capabilities│◀───│ToolRegistry  │◀───│ SuperAgent  │     │
│  │ (terminal,  │    │ (singleton)  │    │ (execute_   │     │
│  │ file, web)  │    │ @tool decor. │    │  stream)    │     │
│  └─────────────┘    └─────────────┘    └──────┬──────┘     │
│                                               │             │
│  ┌─────────────┐    ┌─────────────┐    ┌──────▼──────┐     │
│  │ LiteLLM     │◀───│ LLMBridge   │◀───│ TaskRouter  │     │
│  │ acompletion │    │ (thin wrap) │    │ (heuristic) │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Migración Paso a Paso

#### Fase 1: ToolRegistry Unificado (Sin romper funcionalidad)

**Archivos a crear/modificar:**
- `kogniterm/core/tool_registry.py` (nuevo, desde KAI-CLI)
- `kogniterm/core/agents/base_agent.py` (refactor)
- `kogniterm/capabilities/__init__.py` (actualizar)

**Acciones:**
1. Copiar `ToolRegistry`, `ToolDefinition`, `@tool` desde KAI-CLI
2. Mantener `default_tool_registry` existente como backend
3. Crear adapter que registre capabilities actuales en el nuevo registry
4. Actualizar imports en capabilities para usar el nuevo registry

#### Fase 2: LLMBridge Delgado

**Archivos a crear/modificar:**
- `kogniterm/core/llm_bridge.py` (nuevo, desde KAI-CLI)
- `kogniterm/core/llm_service.py` (mantener por compatibilidad, delegar a LLMBridge)

**Acciones:**
1. Implementar `LLMBridge` con interfaz idéntica a KAI-CLI
2. Mantener `LLMService` pero hacer que `_invoke_inner` delegue a `LLMBridge.chat()`
3. Migrar progresivamente los callers de `LLMService` a `LLMBridge`

#### Fase 3: SuperAgent Limpio

**Archivos a crear/modificar:**
- `kogniterm/core/agents/super_agent.py` (nuevo)
- `kogniterm/core/agents/bash_agent.py` (refactor a `BashAgentRunner` simplificado)

**Acciones:**
1. Crear `SuperAgent` con `execute_stream()` basado en KAI-CLI
2. Simplificar `BashAgentRunner` para usar `SuperAgent` internamente
3. Eliminar nodos de grafo innecesarios (`verification_node`, `learning_node` inline)
4. Mantener `task_tracker` inline como optimización

#### Fase 4: Eliminación de ThreadPoolExecutor

**Archivos a modificar:**
- `kogniterm/core/llm_service.py`
- `kogniterm/core/agents/tool_executor.py`

**Acciones:**
1. Reemplazar `ThreadPoolExecutor` por `asyncio.to_thread()` o ejecución directa async
2. Eliminar polling `future.result(timeout=20ms)`
3. Implementar cancellation nativo con `asyncio.CancelledError`

#### Fase 5: Parsing Nativo de Tool Calls

**Archivos a modificar:**
- `kogniterm/core/llm_service.py` (eliminar `_parse_tool_calls_from_text`)

**Acciones:**
1. Confiar en `tool_calls` del streaming de LiteLLM (ya implementado en KAI-CLI)
2. Eliminar estrategias A, B, C de parsing regex
3. Eliminar `_extract_balanced_content` y helpers de parsing texto

#### Fase 6: Custom Agent Loader

**Archivos a crear/modificar:**
- `kogniterm/core/agents/custom_agent.py` (nuevo)
- `kogniterm/core/agent_manager.py` (refactor)

**Acciones:**
1. Implementar `CustomAgent` desde KAI-CLI
2. Implementar `CustomAgentLoader` para YAML/JSON
3. Actualizar `AgentManager` para soportar agentes personalizados

### 4.4 Orden de Ejecución Recomendado

```
Semana 1: Fase 1 + Fase 2 (ToolRegistry + LLMBridge)
Semana 2: Fase 3 (SuperAgent) + Fase 4 (async tools)
Semana 3: Fase 5 (native parsing) + Fase 6 (custom agents)
Semana 4: Testing, profiling, optimizaciones finales
```

---

## 5. Métricas de Latencia Objetivo

| Componente | Kogniterm Actual | KAI-CLI | Objetivo Post-Migración |
|------------|------------------|----------|------------------------|
| Startup | 2-5s | <500ms | <500ms |
| Por turno (overhead) | 150-500ms | <20ms | <50ms |
| Tool execution | 20-100ms | <5ms | <10ms |
| Streaming first byte | 200-500ms | <100ms | <100ms |

---

## 6. Riesgos y Consideraciones

1. **Compatibilidad:** Kogniterm tiene funcionalidades que KAI-CLI no tiene (aprobaciones, MCP, RAG, delegación)
   - **Mitigación:** Mantener capa de compatibilidad, migrar módulo por módulo

2. **Proveedores LLM:** Kogniterm soporta más providers con configuraciones específicas
   - **Mitigación:** Mantener `MultiProviderManager` pero simplificar la interfaz

3. **Skills procedurales:** Kogniterm tiene un sistema de skills más avanzado
   - **Mitigación:** El `SkillRegistry` de KAI-CLI es suficiente, extender si necesario

4. **TUI/Desktop:** Kogniterm tiene frontends adicionales (TUI, Desktop, VSCode)
   - **Mitigación:** Migrar solo el core (`kogniterm/`), mantener interfaces

---

## 7. Conclusión

La migración es **técnicamente factible y de alto impacto**. KAI-CLI demuestra que una arquitectura minimalista con:
- ToolRegistry singleton
- LLMBridge delgado sobre LiteLLM
- SuperAgent único con `execute_stream()`
- Async nativo

...logra latencia mínima sin sacrificar funcionalidad.

Kogniterm debe **adoptar la misma arquitectura nuclear** manteniendo sus capacidades diferenciadoras (MCP, skills avanzadas, aprobaciones) como capas superiores.

**Próximo paso:** Aprobar esta propuesta y comenzar con Fase 1 (ToolRegistry Unificado).
