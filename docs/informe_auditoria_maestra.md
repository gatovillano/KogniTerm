# 📊 Informe Maestro de Auditoría — KogniTerm

**Proyecto:** KogniTerm (Gemini-Interpreter)  
**Directorio:** `/home/gato/Proyectos/Gemini-Interpreter`  
**Fecha:** 2025-07-15  
**Realizado por:** KogniTerm (KogniDeepCoder + KogniDeepResearcher)

---

## Resumen Ejecutivo

KogniTerm es un sistema terminal inteligente multi-agente construido sobre LangGraph, con soporte para múltiples proveedores LLM, un sistema de skills extensible, y una arquitectura desktop en Tauri. El proyecto muestra **fortalezas significativas** en parseo universal Text-to-Tool, soporte multi-proveedor, y diseño modular de skills. Sin embargo, acumula **deuda técnica considerable** que amenaza la mantenibilidad a largo plazo.

| Métrica | Valor | Estado |
|---------|-------|--------|
| Líneas de código (Python) | ~12,000+ | — |
| Funciones con CC > 50 | 3 | 🔴 |
| Bugs críticos identificados | 6 | 🔴 |
| Código duplicado estimado | ~40% en agentes | 🟠 |
| Skills registradas | 31 | ✅ |
| Cobertura de tests | < 10% | 🔴 |
| Dependencias desactualizadas | 2+ | 🟡 |

---

## 🔴 1. Bugs Críticos (Acción Inmediata)

### 1.1 Docstring sin cerrar en `history_manager.py`
- **Archivo:** `kogniterm/core/history_manager.py`, línea ~482
- **Problema:** El método `_to_litellm_message_for_len_calc()` tiene un docstring que nunca cierra con `"""`. Todo el cuerpo del método se convierte en string literal, retornando `None` implícitamente.
- **Impacto:** `_get_message_length()` recibe `None` → `TypeError` en `json.dumps(None)`.
- **Fix:** Añadir `"""` de cierre antes del primer `if`.

### 1.2 Referencia a `self` en función de módulo en `bash_agent.py`
- **Archivo:** `kogniterm/core/agents/bash_agent.py`, línea ~390
- **Problema:** `call_model_node` es una función de módulo (no método) pero referencia `self._safe_call(...)`.
- **Impacto:** `NameError: name 'self' is not defined` en runtime cuando la TUI consolida streaming.
- **Fix:** Llamar directamente `terminal_ui.app.hide_live_display()` con try/except.

### 1.3 `_current_agent_state` no inicializado en `LLMService`
- **Archivo:** `kogniterm/core/llm_service.py`
- **Problema:** `execute_tool_node` asigna `llm_service._current_agent_state` pero el atributo nunca se inicializa en `__init__`.
- **Impacto:** `AttributeError` si otro código accede al atributo antes de la primera ejecución.
- **Fix:** `self._current_agent_state = None` en `__init__`.

### 1.4 Métodos duplicados en `file_operations_tool.py`
- **Archivo:** `kogniterm/core/tools/file_operations_tool.py`, líneas 119 y 154
- **Problema:** `_validate_workspace_path` definido dos veces con contenido idéntico.
- **Impacto:** Código muerto, riesgo de inconsistencia si se modifica una versión.
- **Fix:** Eliminar la segunda definición.

### 1.5 Métodos duplicados en `terminal_ui.py`
- **Archivo:** `kogniterm/terminal/terminal_ui.py`, líneas 202 y 221
- **Problema:** `ask_approval_sync` definido dos veces. La primera tiene un bug donde retorna `False` silenciosamente si hay un loop asyncio corriendo.
- **Impacto:** Aprobaciones de comandos denegadas silenciosamente en ciertos contextos.
- **Fix:** Mantener una sola versión con manejo explícito.

### 1.6 `_extract_balanced_content` duplicado en `llm_service.py`
- **Archivo:** `kogniterm/core/llm_service.py`, líneas ~450 y ~1780
- **Problema:** Función definida dos veces con firmas ligeramente diferentes.
- **Fix:** Eliminar la duplicación, mantener la versión más robusta.

---

## 🟠 2. Problemas Arquitectónicos

### 2.1 `LLMService` — God Class (1,781 líneas, CC=209)
**El problema más grave del proyecto.**

Responsabilidades actuales (10+):
1. Configuración de proveedor/API keys
2. Conversión de mensajes LangChain ↔ LiteLLM
3. Parsing de tool calls desde texto
4. Gestión de herramientas (tool_map, schemas)
5. Rate limiting
6. Streaming con timeout
7. Fallback entre modos (normal, bypass, ultra-minimal)
8. Resumen de conversación
9. Gestión de workspace context
10. Invocación de herramientas con interrupción

**Propuesta de descomposición:**
```
kogniterm/core/
├── llm_service.py          # Orquestador (~150 líneas)
├── llm/
│   ├── provider_config.py   # APIs y credenciales
│   ├── message_converter.py # LangChain ↔ LiteLLM
│   ├── tool_parser.py       # Parsing de tool calls
│   ├── streaming_executor.py # Streaming con timeout
│   ├── fallback_handler.py  # Cadena de fallback
│   └── rate_limiter.py      # Rate limiting
```

### 2.2 `SkillLoader._load_module_tools()` — CC=73, 805 líneas
Detecta herramientas usando 5 estrategias con anidamiento de hasta 7 niveles.

**Propuesta:** Patrón Chain of Responsibility con estrategias separadas.

### 2.3 Dependencia circular `llm_service ↔ skill_manager`
Funciona por inyección pero es frágil. Si skill_manager necesita llm_service durante inicialización → `AttributeError`.

**Propuesta:** Usar un registro de herramientas compartido como punto de encuentro, eliminando la referencia directa.

### 2.4 ToolManager legacy sin usar
`kogniterm/core/tools/tool_manager.py` (149 líneas) coexiste con SkillManager pero está en desuso.

**Propuesta:** Eliminar o documentar como deprecated.

---

## 🟠 3. Deuda Técnica y Código Duplicado

### 3.1 `call_model_node` — 90% duplicado en 4 archivos
| Archivo | Líneas | Duplicación |
|---------|--------|-------------|
| `bash_agent.py` | ~150 | Base |
| `code_agent.py` | ~120 | 90% idéntico |
| `researcher_agent.py` | ~60 | 70% idéntico |
| `deep_researcher.py` | ~120 | 90% idéntico |

**Propuesta:** Extraer a `BaseAgentNode` en `kogniterm/core/agents/base_agent.py`:
```python
class BaseAgentNode:
    @classmethod
    def create_call_model_node(cls, system_message_fn, agent_name):
        def call_model_node(state, llm_service, terminal_ui=None, interrupt_queue=None):
            # Lógica compartida: streaming, rendering, TUI/CLI, interrupción
            ...
        return call_model_node
```

### 3.2 `execute_single_tool` — 3 versiones casi idénticas
**Propuesta:** Función compartida en `kogniterm/core/agents/tool_executor.py`.

### 3.3 `handle_tool_confirmation` — duplicado en bash_agent y code_agent
### 3.4 `should_continue` — duplicado en 3 agentes

### 3.5 Clases que violan SRP
| Clase | Líneas | Responsabilidades | Recomendación |
|-------|--------|-------------------|---------------|
| `LLMService` | 1,781 | 10+ | Descomponer en 6 módulos |
| `KogniTermApp` | ~800 | UI, meta-commands, indexing, sessions, tags | Separar componentes |
| `FileCompleter` | ~300 | File watching, Docker, magic commands, cache | Separar completers |
| `HistoryManager` | 697 | Load/save, clean, truncate, summarize | Pipeline modular |
| `SkillLoader` | 805 | Import, detección, metadata injection | Chain of Responsibility |

---

## 🟠 4. Problemas de Concurrencia

### 4.1 ThreadPoolExecutor sin sincronización por recurso
- **Problema:** 10 workers ejecutan herramientas en paralelo sin coordinación por tipo de recurso. Escrituras concurrentes al mismo archivo = corrupción.
- **Fix:** Agrupar tools por recurso (archivos en secuencia, independientes en paralelo).

### 4.2 `KogniTermKernel` sin thread safety
- **Problema:** `current_execution_outputs` es lista mutable sin lock. Si `execute_code` se llama mientras `_iopub_listener` está activo, se pierden outputs.
- **Fix:** Lock por ejecución + event de completado.

### 4.3 `conversation_history` modificado in-place desde múltiples hilos
- **Problema:** Múltiples agentes pueden llamar a `_save_history` simultáneamente.
- **Fix:** `_history_lock = threading.Lock()` para todas las operaciones de lectura/escritura.

---

## 🟡 5. Rendimiento

### 5.1 Serialización costosa en history_manager
Cada operación de historial serializa/deserializa JSON completo. Con historiales largos (>500 mensajes), esto se vuelve un cuello de botella.

**Propuesta:** Implementar append-only con checkpoint periódico.

### 5.2 Re-indexación innecesaria del codebase
El `workspace_context` re-indexa archivos que no han cambiado.

**Propuesta:** Usar hash de contenido o timestamps para indexación incremental.

### 5.3 ChromaDB sin pooling de conexiones
Cada búsqueda semántica crea nueva conexión.

**Propuesta:** Singleton de cliente Chroma con connection pooling.

---

## 🟡 6. Seguridad

### 6.1 Inyección de comandos en `execute_command`
Las herramientas de ejecución de comandos podrían ser abusadas si el LLM genera comandos maliciosos.

**Mitigación actual:** CommandApprovalHandler con detección de comandos destructivos.
**Mejora:** Lista blanca de comandos peligrosos, sandboxing con namespaces.

### 6.2 Manejo de API keys
Las keys se almacenan en variables de entorno pero se imprimen en logs de debug en algunos casos.

**Fix:** Sanitizar logs, nunca imprimir credenciales.

### 6.3 Path traversal en file operations
Aunque existe `_validate_workspace_path`, hay llamadas duplicadas y posibles bypass.

**Fix:** Validación centralizada con `os.path.realpath` + verificación de symlink.

---

## 🔴 7. Tests

### 7.1 Cobertura < 10%
Los tests existentes son mínimos:
- `test_basic.py` — solo importa módulos
- `test_interrupt.sh` — prueba de señal
- Varios archivos `test_*.py` que son scripts de debug, no tests formales

### 7.2 Archivos de debug mezclados con código
10+ archivos `debug_*.py` en la raíz del proyecto. Son scripts de diagnóstico que deberían estar en `/tests/` o eliminados.

### 7.3 Lo que NO está testeado
- Lógica de parseo de tool calls
- Sistema de skills (registro, carga, validación)
- Fallback entre modos de LLM
- Concurrencia y race conditions
- HistoryManager (truncate, summarize, clean)
- Agentes completos (solo funciones aisladas)

### 7.4 Recomendación
Implementar tests con pytest:
1. **Unit tests:** Cada función pura del core (parsers, converters, validators)
2. **Integration tests:** Flujo completo de agente con LLM mock
3. **Property tests:** Invariantes del sistema de historial
4. **Load tests:** Historial con 1000+ mensajes

---

## 🟡 8. Dependencias y Configuración

### 8.1 Versiones inconsistentes
- `requirements.txt` con `urllib3<2` (pin restrictivo que puede causar conflictos)
- `pyproject.toml` sin dependencias listadas
- Versión del paquete: inconsistencia entre 0.3.5 y 0.4.1

### 8.2 `docker-compose.yml` es de WordPress
El archivo `docker-compose.yml` del proyecto contiene configuración de WordPress, no relacionada con KogniTerm.

### 8.3 Dependencias potencialmente desactualizadas
Revisar versiones de: langchain, langgraph, litellm, chromadb.

---

## 📋 9. Recomendaciones Priorizadas

### Prioridad 1 — Corrección Inmediata (Semana 1)
1. ✅ Cerrar docstring en `history_manager.py` (1.1)
2. ✅ Fix `self` reference en `bash_agent.py` (1.2)
3. ✅ Inicializar `_current_agent_state` en `LLMService.__init__` (1.3)
4. ✅ Eliminar métodos duplicados (1.4, 1.5, 1.6)
5. ✅ Mover archivos `debug_*.py` a `/tests/debug/` o eliminar

### Prioridad 2 — Refactorización Estructural (Semanas 2-4)
6. 🔧 Descomponer `LLMService` en módulos especializados
7. 🔧 Extraer `BaseAgentNode` para eliminar duplicación de `call_model_node`
8. 🔧 Crear `tool_executor.py` compartido para `execute_single_tool`
9. 🔧 Añadir thread safety a `HistoryManager` y `KogniTermKernel`
10. 🔧 Eliminar `ToolManager` legacy o marcar como deprecated

### Prioridad 3 — Mejoras de Calidad (Semanas 4-6)
11. 📝 Implementar tests unitarios para funciones críticas
12. 📝 Añadir type hints a funciones sin tipar
13. 📝 Mejorar docstrings faltantes
14. 📝 Actualizar `pyproject.toml` con dependencias
15. 📝 Corregir `docker-compose.yml`

### Prioridad 4 — Optimización (Semanas 6-8)
16. ⚡ Historial append-only con checkpoint
17. ⚡ Indexación incremental del codebase
18. ⚡ Connection pooling para ChromaDB
19. ⚡ Agrupación de tools por recurso en ejecución paralela

### Prioridad 5 — Seguridad (Continuo)
20. 🔒 Sanitizar logs de credenciales
21. 🔒 Reforzar validación de paths contra symlink attacks
22. 🔒 Implementar lista blanca de comandos peligrosos

---

## ✅ Fortalezas del Proyecto

1. **Parseo Universal Text-to-Tool:** Sistema robusto que soporta proveedores sin tool calling nativo.
2. **Multi-proveedor:** Soporte para OpenAI, Anthropic, Mistral, OpenRouter, SiliconFlow, etc.
3. **Sistema de Skills:** 31 skills con carga JIT, validación de esquemas, y 3 niveles de gestión.
4. **TUI/CLI dual:** Interfaz rica con Textual + Rich/prompt_toolkit.
5. **Desktop Tauri:** Arquitectura moderna con React + Rust.
6. **Documentación extensiva:** 17 archivos en `docs/` con planes, análisis y registros.
7. **Interrupción robusta:** Sistema de interrupción con manejo de señales y colas.
8. **History con resumen:** Compresión inteligente del historial de conversación.

---

*Informe generado por KogniTerm con análisis paralelo de KogniDeepCoder y KogniDeepResearcher.*
