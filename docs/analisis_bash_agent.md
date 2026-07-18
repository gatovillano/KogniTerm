# 📊 INFORME DE ANÁLISIS TÉCNICO: `bash_agent.py`
## Proyecto: Gemini-Interpreter / KogniTerm
**Archivo:** `core/agents/bash_agent.py` | **Líneas:** 1506 | **Fecha:** Análisis estático

---

## 1. ARQUITECTURA GENERAL Y ESTRUCTURA

### 1.1 Organización del archivo
| Rango | Componente | Responsabilidad |
|-------|-----------|-----------------|
| 1–99 | Imports + helpers | Carga dinámica de skills, caché de memoria de código, contexto semántico |
| 100–399 | Confirmaciones | Lógica de aprobación/re-ejecución post-confirmación de usuario |
| 400–470 | Re-ejecución | Ejecución de herramientas una vez aprobadas |
| 471–580 | `verification_node` | Validación post-ejecución (sintaxis, lint) |
| 581–967 | `call_model_node` | Nodo principal del LLM, detección de bucles, manejo de TUI |
| 968–989 | `_print_tool_notification` | Helper de notificaciones visuales |
| 990–1312 | `execute_tool_node` | Orquestador de ejecución paralela de herramientas |
| 1313–1434 | `learning_node` | Análisis posterior de sesión para persistencia de preferencias |
| 1435–1506 | Creación de grafos | `create_bash_agent` y `create_learning_agent` |

### 1.2 Flujo del grafo LangChain
```
[ENTRY] → call_model
                │
                ├─ (si tool_calls) → execute_tool
                │                         │
                │                         ├─ (si hay resultados) → verify → call_model
                │                         ├─ (si más tool_calls) → execute_tool (loop)
                │                         └─ (si END) → finalizar
                │
                └─ (si respuesta final) → END
```

**Nodos:** 4 (`call_model`, `execute_tool`, `verify`, `learning`)  
**Grafo adicional:** `create_learning_agent` (independiente, post-sesión)

---

## 2. ANÁLISIS DE `call_model_node` (L581–967)

### 2.1 Funcionalidad principal
- Invoca al LLM con el historial de mensajes actualizado
- Inyecta contexto semántico (`_build_semantic_code_context`) y memoria de código (`_get_code_memory`)
- Detecta bucles críticos (4 repeticiones consecutivas de misma herramienta+args)
- Maneja confirmaciones pendientes heredadas de `execute_tool_node` (TUI/CLI)
- Gestiona interrupciones del usuario

### 2.2 Mecanismo anti-bucles
```python
# Lógica simplificada (líneas ~750-850 aprox)
if len(state.tool_call_history) >= 4:
    last_4 = state.tool_call_history[-4:]
    if all(
        (h["name"] == last_4[0]["name"]) and (h["args_hash"] == last_4[0]["args_hash"])
        for h in last_4
    ):
        state.critical_loop_detected = True
        # Mensaje de interrupción al usuario
```

**Problema detectado:** La detección se activa solo cuando hay 4 repeticiones *exactas*, pero no contempla variaciones sutiles que también generan bucles.

---

## 3. ANÁLISIS DE `execute_tool_node` (L990–1312)

### 3.1 Estrategia de paralelismo actual
```python
# Línea 1015-1016
parallel_calls = [tc for tc in last_message.tool_calls if tc['name'] != 'execute_command']
interactive_calls = [tc for tc in last_message.tool_calls if tc['name'] == 'execute_command']
```

**Diseño:** 
1. **Paso 1:** Particionar herramientas en `parallel_calls` (todo excepto `execute_command`) e `interactive_calls` (solo `execute_command`)
2. **Paso 2:** Registrar historial para detección de bucles
3. **Paso 3:** Verificar interrupciones tempranas
4. **Paso 4:** Pre-fetch de metadata (skill_name, descripción)
5. **Paso 5:** Emitir notificaciones visuales batch
6. **Paso 6:** Iniciar `KeyboardHandler` solo si no hay interactivas y no es TUI
7. **Paso 7:** Submit batch al `ThreadPoolExecutor`
8. **Paso 8:** Procesar `execute_command` DESPUÉS de paralelas

### 3.2 Problemas críticos identificados

#### 🔴 CRÍTICO 1: Falta de timeout en ejecución paralela
```python
# Línea 1076
tool_id, content, exception = future.result()  # BLOQUEO INDEFINIDO
```
**Riesgo:** Si una herramienta se cuelga, el nodo entero se bloquea sin posibilidad de recuperación.

#### 🔴 CRÍTICO 2: Race condition en `tool_call_history`
```python
# Líneas 1019-1024
for tc in last_message.tool_calls:
    state.tool_call_history.append(...)  # No thread-safe
```
**Riesgo:** En escenarios de alta concurrencia, el historial puede corromperse.

#### 🟡 MEDIO 1: `execute_tool_node` tiene múltiples responsabilidades (323 líneas)
- Particionamiento de herramientas
- Gestión de metadata
- Notificaciones visuales
- Ejecución paralela
- Manejo de confirmaciones TUI
- Re-ejecución post-aprobación
- Limpieza de estado

**Principio violado:** Single Responsibility Principle

#### 🟡 MEDIO 2: Inicialización condicional de `KeyboardHandler`
```python
# Líneas 1057-1060
if not interactive_calls and not is_tui:
    kh = KeyboardHandler(interrupt_queue)
    kh.start()
```
**Problema:** Si hay `interactive_calls`, no se puede interrumpir la ejecución de herramientas paralelas.

#### 🟢 BAJO 1: `metadata_map` se construye secuencialmente
```python
# Líneas 1035-1049
for tc in parallel_calls + interactive_calls:
    tool = llm_service.get_tool(tc['name'])
    # ... obtener skill_name, bajada
```
**Oportunidad:** Aunque es I/O en memoria, se podría paralelizar si el número de herramientas es grande.

---

## 4. ANÁLISIS DE `verification_node` (L471–580)

### 4.1 Funcionalidad
- Compara el estado del archivo antes/después de la ejecución
- Detecta archivos modificados por herramientas de edición
- Ejecuta verificaciones en orden: `py_compile` → `ruff` → AST parsing
- Muestra resumen de advertencias/errores con formato enriquecido

### 4.2 Problemas detectados

#### 🟡 MEDIO 1: Verificación limitada a Python
Solo aplica `py_compile` y `ruff` a archivos `.py`. No hay verificación para otros tipos de archivo.

#### 🟡 MEDIO 2: AST parsing con manejo frágil de excepciones
```python
# Líneas ~520-540
try:
    tree = ast.parse(content)
    # ... análisis
except SyntaxError:
    pass  # Silencioso
```
**Problema:** Los errores de sintaxis se ignoran sin feedback al usuario.

---

## 5. ANÁLISIS DE `learning_node` (L1313–1434)

### 5.1 Funcionalidad
- Analiza la conversación reciente (últimos 6 mensajes)
- Extrae preferencias, patrones de código y reglas ejecutivas
- Persiste aprendizajes en memoria del proyecto
- Se ejecuta en grafo independiente (no bloquea respuesta)

### 5.2 Problemas detectados

#### 🟡 MEDIO 1: Costo innecesario de LLM
Invoca al LLM en *cada turno significativo*, incluso cuando no hay aprendizaje nuevo.

#### 🟢 BAJO 1: Ventana de contexto fija
```python
# Línea 1331
recent_msgs = state.messages[-6:]
```
Hardcodeado; debería ser configurable.

---

## 6. ANÁLISIS DE HELPERS Y UTILIDADES

### 6.1 `_load_file_ops_module` (L26–99)
Carga dinámicamente skills con guiones en el nombre. **Funciona correctamente**, pero es frágil dependiendo de la estructura de directorios.

### 6.2 `_get_code_memory` (L80–99)
Caché en memoria con TTL de 2 segundos. **Problema:** No invalida por cambios en el contenido del archivo.

### 6.3 `_print_tool_notification` (L968–989)
Helper centralizado para notificaciones. **Bien diseñado**, pero mezcla lógica TUI/CLI.

---

## 7. BUGS Y CODE SMELLS DETECTADOS

### 7.1 Bugs confirmados
1. **Race condition en `tool_call_history`** (CRÍTICO)
2. **Bloqueo indefinido en `future.result()`** (CRÍTICO)
3. **Validación silenciosa de errores de sintaxis** (MEDIO)
4. **Cache sin invalidación por contenido** (BAJO)

### 7.2 Code smells
1. **God Function:** `execute_tool_node` (323 líneas, 8 responsabilidades)
2. **Duplicación:** Lógica de notificaciones repetida en múltiples nodos
3. **Condicionales anidadas:** Hasta 4 niveles en `handle_tool_confirmation`
4. **Magic numbers:** `_CODE_MD_CACHE_TTL = 2.0`, `4` repeticiones para loop, `10` workers máximos

---

## 8. RECOMENDACIONES DE REFACTORIZACIÓN

### 8.1 Refactorizaciones inmediatas (Alta prioridad)

1. **Agregar timeout a ejecución paralela:**
```python
# Antes
tool_id, content, exception = future.result()

# Después
try:
    tool_id, content, exception = future.result(timeout=30.0)
except TimeoutError:
    logger.error(f"Timeout en herramienta {tool_id}")
    continue
```

2. **Extraer funciones de `execute_tool_node`:**
```python
def _partition_tool_calls(tool_calls: list) -> tuple:
    parallel = [tc for tc in tool_calls if tc['name'] != 'execute_command']
    interactive = [tc for tc in tool_calls if tc['name'] == 'execute_command']
    return parallel, interactive

def _build_tool_metadata(llm_service, tool_calls) -> dict:
    metadata_map = {}
    for tc in tool_calls:
        tool = llm_service.get_tool(tc['name'])
        skill_name = _get_skill_name(llm_service, tc['name'])
        bajada = get_tool_action_description(tool, tc['args']) if tool else ""
        metadata_map[tc['id']] = (skill_name, bajada)
    return metadata_map

def _execute_parallel_tools(parallel_calls, llm_service, terminal_ui, interrupt_queue, metadata_map, is_tui):
    executor = ThreadPoolExecutor(max_workers=min(len(parallel_calls), 10))
    futures_map = {}
    for tc in parallel_calls:
        future = executor.submit(execute_single_tool, tc, llm_service, terminal_ui, interrupt_queue)
        futures_map[future] = tc['id']
    
    results = []
    for future in as_completed(futures_map):
        try:
            result = future.result(timeout=30.0)
            results.append(result)
        except TimeoutError:
            logger.error(f"Timeout en herramienta {futures_map[future]}")
        except Exception as e:
            logger.error(f"Error en herramienta: {e}")
    
    executor.shutdown(wait=True)
    return results
```

3. **Inicializar `KeyboardHandler` siempre:**
```python
# Inicializar siempre para permitir interrupciones
kh = KeyboardHandler(interrupt_queue)
kh.start()
```

### 8.2 Mejoras de arquitectura (Media prioridad)

4. **Crear `services/tool_executor.py`:**
Mover la lógica de ejecución paralela a un servicio separado.

5. **Implementar cache con hash de contenido:**
```python
def _get_code_memory(base_content: str) -> str:
    instructions_path = os.path.join(os.getcwd(), ".kogniterm", "code_memory.md")
    content_hash = _get_file_hash(instructions_path)
    cache_key = f"{instructions_path}:{content_hash}"
    
    if cache_key in _code_md_cache:
        cm = _code_md_cache[cache_key]
    else:
        cm = _get_cached_file(instructions_path)
        _code_md_cache[cache_key] = cm
    
    if cm:
        base_content += f"\n\n### 🧠 MEMORIA DE CÓDIGO (code_memory.md):\n{cm}\n"
    return base_content
```

6. **Agregar verificación genérica de archivos:**
```python
def _verify_file_generic(file_path: str) -> List[str]:
    warnings = []
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.py':
        warnings.extend(_verify_python_file(file_path))
    elif ext in ['.js', '.ts', '.jsx', '.tsx']:
        warnings.extend(_verify_javascript_file(file_path))
    elif ext in ['.json', '.yaml', '.yml']:
        warnings.extend(_verify_config_file(file_path))
    
    return warnings
```

### 8.3 Mejoras de testing (Media prioridad)

7. **Agregar tests unitarios para cada nodo:**
- `test_call_model_node_detects_loop`
- `test_execute_tool_node_parallel_execution`
- `test_execute_tool_node_tui_confirmation`
- `test_verification_node_python_syntax`
- `test_learning_node_filters_noise`

### 8.4 Mejoras de robustez (Baja prioridad)

8. **Agregar manejo de señales (SIGINT/SIGTERM):**
```python
import signal

def _setup_signal_handlers(interrupt_queue):
    def handler(signum, frame):
        interrupt_queue.put(True)
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
```

9. **Validar `tool_args` antes de ejecutar:**
```python
def _validate_tool_args(tool_name: str, tool_args: dict) -> Optional[str]:
    tool = llm_service.get_tool(tool_name)
    if not tool:
        return f"Herramienta {tool_name} no encontrada"
    # Validar esquema si está disponible
    if hasattr(tool, 'args_schema'):
        try:
            tool.args_schema.validate(tool_args)
        except ValidationError as e:
            return str(e)
    return None
```

---

## 9. RESUMEN EJECUTIVO

### Fortalezas
✅ Arquitectura de grafo bien estructurada y desacoplada  
✅ Estrategia de paralelismo inteligente (batch submit, separación de interactivas)  
✅ Solución elegante para confirmaciones en TUI (postergación a hilo principal)  
✅ Sistema de caché para reducir I/O  
✅ Detección de bucles críticos  
✅ Grafo de aprendizaje independiente (no bloquea respuesta)

### Debilidades
❌ Falta de timeout en ejecución paralela (riesgo de bloqueo)  
❌ Race condition potencial en `tool_call_history`  
❌ `execute_tool_node` muy largo (323 líneas, múltiples responsabilidades)  
❌ Verificación limitada a Python  
❌ Cache de memoria sin invalidación por contenido  
❌ Learning node puede ser ruidoso/costoso

### Riesgos
- **Bloqueo indefinido** si una herramienta se cuelga
- **Condiciones de carrera** en escenarios de alta concurrencia
- **Costo elevado** por invocaciones repetidas al LLM en `learning_node`

### Acciones inmediatas sugeridas
1. Agregar `timeout` a `future.result()` en `execute_tool_node`
2. Refactorizar `execute_tool_node` en funciones ≤50 líneas
3. Implementar cache con hash de contenido para `code_memory.md`
4. Inicializar `KeyboardHandler` siempre (no solo cuando no hay interactivas)

---

**Fin del análisis técnico.**
