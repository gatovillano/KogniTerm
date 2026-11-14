# Arquitectura de KogniTerm - Informe de Análisis

## Resumen Ejecutivo

KogniTerm es un intérprete de terminal basado en LLM (Large Language Model) con arquitectura modular y extensible. El sistema implementa un patrón de **"gestión dual de mensajes"** donde se mantienen separados los mensajes para la API (historial de conversación con el LLM) y los mensajes para la UI (interfaz de usuario).

---

## Arquitectura de Alto Nivel

### 1. Componentes Core

#### 1.1 MessageManager (`core/message_manager.py`)
**Responsabilidad:** Gestión centralizada de mensajes duales y rewind.

**Patrones Clave:**
- **Doble historial:** `history_for_api` (para el LLM) vs `messages` (para UI)
- **Rewind centralizado:** Permite deshacer cambios en ambos historiales simultáneamente
- **Sincronización:** `sync_from_agent_state()` mantiene consistencia con `AgentState`

**Estructura de datos:**
```python
class MessageManager:
    - history_for_api: List[BaseMessage]      # Historial para API
    - messages: List[Dict]                     # Mensajes para UI
    - current_tool: Optional[ToolCall]         # Herramienta actual
    - pending_tool_responses: Dict             # Respuestas pendientes
    - _lock: threading.Lock                    # Sincronización
```

#### 1.2 AgentState (`core/agent_state.py`)
**Responsabilidad:** Estructura de estado persistente del agente.

**Campos críticos:**
- `messages`: Historial de mensajes (formato UI)
- `history_for_api`: Historial LangChain para el LLM
- `message_manager`: Referencia al gestor de mensajes
- `pending_tool_approvals`: Herramientas pendientes de confirmación
- `last_tool_call`: Última llamada de herramienta ejecutada

#### 1.3 HistoryManager (`core/history_manager.py`)
**Responsabilidad:** Persistencia y gestión del historial de conversación.

**Características destacadas:**
- **AutoSavingMessageList:** Lista que persiste automáticamente tras mutaciones
- **Truncamiento inteligente:** Protege pares AIMessage-ToolMessage
- **Resumen automático:** Cuando el historial excede límites, genera resúmenes
- **Procesamiento por pasadas:** Limpieza → Cálculo → Resumen/Truncamiento

**Límites configurables:**
- `max_history_messages`: 100 (por defecto)
- `max_history_chars`: 150,000 (por defecto)
- `MIN_MESSAGES_TO_KEEP`: 10

#### 1.4 CommandExecutor (`core/command_executor.py`)
**Responsabilidad:** Ejecución de comandos en pseudo-terminal.

**Patrones:**
- **Sesión persistente:** Mantiene estado entre comandos (variables, directorio actual)
- **PTY management:** Usa `pty.openpty()` para emular terminal
- **Echo filtering:** Filtra eco de comandos para salida limpia
- **Marker-based completion:** Usa marcadores para detectar fin de ejecución

---

### 2. Sistema de Skills

#### 2.1 SkillManager (`core/skills/skill_manager.py`)
**Responsabilidad:** Discovery, carga y registro de skills.

**Arquitectura de discovery:**
```
Rutas de búsqueda (prioridad):
1. ~/.kogniterm/skills/managed/     (usuario)
2. ./skills/bundled/                  (proyecto)
3. ./skills/workspace/                (trabajo actual)
4. ./skills/external/                 (externas)
```

**Estructura de Skill:**
```python
@dataclass
class Skill:
    - path: Path                          # Ruta del directorio
    - name: str                           # Nombre único
    - version: str                        # Versión semántica
    - description: str                    # Descripción
    - category: str                       # Categoría
    - security_level: str                 # Nivel de seguridad
    - allowed_tools/denied_tools: List    # Filtrado de herramientas
    - auto_approve: bool                  # Aprobación automática
    - sandbox_required: bool              # ¿Requiere aislamiento?
```

**Flujo de carga JIT:**
1. Discovery de `SKILL.md` files
2. Validación de estructura y metadatos
3. Carga dinámica de `scripts/*.py`
4. Registro en `tool_registry` con metadata
5. Inyección de `llm_service` y `terminal_ui`

#### 2.2 Formato SKILL.md
```markdown
---
name: skill_name
description: Descripción de la skill
category: utility
security_level: low
auto_approve: false
---
# Instrucciones para el LLM

Contenido markdown con instrucciones...
```

---

### 3. Servicios

#### 3.1 EmbeddingsService (`core/embeddings_service.py`)
**Responsabilidad:** Generación de embeddings con múltiples proveedores.

**Proveedores soportados:**
- `GeminiAdapter`: Usa `google.genai`
- `OpenAIAdapter`: Usa `openai` client
- `OllamaAdapter`: HTTP API local
- `SentenceTransformersAdapter`: Modelos locales
- `FastEmbedAdapter`: Biblioteca rápida

**Patrones:**
- **Singleton pattern:** `EmbeddingsService.get_instance()`
- **Batch processing:** Procesamiento por lotes de 100 textos
- **Cache local:** Modelos guardados en `.kogniterm/models/`

#### 3.2 LLMService (`core/llm_service.py`)
**Responsabilidad:** Interfaz unificada con múltiples proveedores de LLM.

**Características:**
- Conversión de herramientas LangChain a formato LiteLLM
- Streaming de respuestas
- Manejo de reasoning_content (razonamiento)
- Soporte para múltiples providers (Gemini, OpenAI, LiteLLM)

---

### 4. Flujos de Ejecución

#### 4.1 Flujo Principal (main.py)
```
1. Inicialización
   → ConfigManager carga settings
   → MessageManager crea estructuras vacías
   → HistoryManager carga historial persistente
   → SkillManager descubre y carga skills

2. Bucle de procesamiento
   → input_user → MessageManager.add_message()
   → MessageManager.get_history_for_api()
   → LLMService.generate_response()
   → tool_calls → CommandExecutor.execute()
   → output → MessageManager.add_message(ToolMessage)
```

#### 4.2 Manejo de Herramientas
```
LLM genera tool_calls
    ↓
MessageManager almacena en pending_tool_calls
    ↓
Si status == "requires_confirmation":
    → Esperar confirmación usuario (INSTRUCCIÓN CRÍTICA #1)
    → NO generar nuevas tool_calls
    ↓
Usuario confirma
    ↓
CommandExecutor ejecuta comando
    ↓
ToolMessage con resultado
    ↓
MessageManager.add_message(ToolMessage)
```

---

## Patrones de Diseño Identificados

### 1. **Dual Message Management**
- Separación clara entre historial API y mensajes UI
- Permite operaciones de "rewind" sin afectar ambos

### 2. **Auto-Save Observer**
- `AutoSavingMessageList` notifica cambios a `HistoryManager`
- Persistencia automática con `AutosaveManager` versionado

### 3. **JIT Skill Loading**
- Carga bajo demanda de skills
- Inyección de dependencias (llm_service, terminal_ui)

### 4. **Provider Pattern**
- EmbeddingsService y LLMService usan adapters
- Fácil adición de nuevos proveedores

### 5. **Context Manager para Autosave**
```python
with message_list.suspend_autosave():
    # Operaciones sin guardar
```

---

## Consideraciones de Seguridad

### Niveles de Seguridad de Skills
1. **low**: Acceso básico, sin riesgo
2. **standard**: Acceso a recursos del sistema
3. **medium**: Operaciones moderadas (archivos, red)
4. **high**: Operaciones privilegiadas
5. **elevated**: Requiere confirmación explícita

### Sistema de Permisos
- `required_permissions`: Permisos necesarios
- `allowed_tools/denied_tools`: Filtrado de herramientas
- `auto_approve`: Si True, no requiere confirmación

---

## Métricas del Sistema

### Complejidad Ciclomática Estimada
- `MessageManager`: Media (manejo de estados complejos)
- `HistoryManager`: Alta (múltiples pasadas de procesamiento)
- `SkillManager`: Alta (discovery, validación, carga)
- `CommandExecutor`: Media-Alta (manejo de PTY, señales)

### Puntos de Extensión
1. Nuevos proveedores LLM (implementar adapter)
2. Nuevos proveedores embeddings (implementar EmbeddingAdapter)
3. Nuevas skills (añadir directorio y SKILL.md)
4. Nuevas herramientas (añadir a scripts/ de una skill)

---

## Recomendaciones

### Optimizaciones Identificadas
1. **Cache de embeddings:** Implementar caché para embeddings repetidos
2. **Streaming de comandos:** Mejorar el manejo de salida en tiempo real
3. **Compresión de historial:** Implementar compresión de mensajes antiguos
4. **Pool de hilos:** Para operaciones de I/O concurrente

### Mantenibilidad
- Documentar mejor los tipos de mensajes LangChain vs LiteLLM
- Separar concernos en `LLMService` (conversión vs generación)
- Añadir tests de integración para flujos de herramientas

---

## Archivos Clave por Funcionalidad

| Funcionalidad | Archivo Principal | Backup |
|--------------|-------------------|--------|
| Gestión mensajes | `message_manager.py` | - |
| Estado agente | `agent_state.py` | `agent_state.py.backup` |
| Historial | `history_manager.py` | - |
| Ejecución comandos | `command_executor.py` | - |
| Skills | `skill_manager.py` | - |
| Embeddings | `embeddings_service.py` | - |
| LLM | `llm_service.py` | `llm_service.py.backup` |

---

*Documento generado automáticamente mediante análisis estático del código fuente.*