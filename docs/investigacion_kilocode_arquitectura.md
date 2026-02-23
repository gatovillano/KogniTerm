# Análisis Arquitectónico: KiloCode vs KogniTerm

## Diferencias Fundamentales en el Diseño del Agente

---

## 1. Arquitectura del Task (Clase Principal)

### KiloCode: Task.ts (~2000+ líneas)

```typescript
export class Task extends EventEmitter<TaskEvents> implements TaskLike {
    // Identificadores
    readonly taskId: string
    readonly instanceId: string
    readonly rootTaskId?: string
    readonly parentTaskId?: string
    
    // Estado del task
    todoList?: TodoItem[]
    readonly rootTask: Task | undefined
    readonly parentTask: Task | undefined
    
    // Modo del task (persistente)
    private _taskMode: string | undefined
    private taskModeReady: Promise<void>
    
    // Protocolo de herramientas (bloqueado por tarea)
    private _taskToolProtocol: ToolProtocol | undefined
    
    // API
    apiConfiguration: ProviderSettings
    api: ApiHandler
    
    // Control de estado
    abort: boolean = false
    isPaused: boolean = false
    isInitialized = false
    
    // Mensajes
    apiConversationHistory: ApiMessage[] = []
    clineMessages: ClineMessage[] = []
    
    // Tracking de errores
    consecutiveMistakeCount: number = 0
    consecutiveMistakeLimit: number
    consecutiveMistakeCountForApplyDiff: Map<string, number> = new Map()
    consecutiveMistakeCountForEditFile: Map<string, number> = new Map()
    
    // Servicios
    toolRepetitionDetector: ToolRepetitionDetector
    fileContextTracker: FileContextTracker
    rooIgnoreController?: RooIgnoreController
    rooProtectedController?: RooProtectedController
    
    // Message Manager
    private _messageManager?: MessageManager
}
```

### KogniTerm: bash_agent.py (basado en LangGraph)

```python
# Estructura basada en LangGraph StateGraph
class AgentState(TypedDict):
    messages: List[BaseMessage]
    command_to_confirm: Optional[str]
    tool_call_id_to_confirm: Optional[str]
    # ... campos básicos
```

---

## 2. Diferencias Clave en la Arquitectura

### 2.1 Sistema de Eventos vs Flujo Lineal

| Aspecto | KiloCode | KogniTerm |
|---------|----------|-----------|
| **Patrón** | EventEmitter | LangGraph StateGraph |
| **Estado** | Mutable con Eventos | Inmutable con Transiciones |
| **Comunicación** | `emit()` + listeners | Nodos del Grafo |
| **Async** | Promises + Streams | AsyncIO |

**KiloCode usa EventEmitter:**
```typescript
export class Task extends EventEmitter<TaskEvents> {
    emit(event: string, ...args: any[]): boolean
    on(event: string, listener: (...args: any[]) => void): this
}
```

**KogniTerm usa LangGraph:**
```python
workflow = StateGraph(AgentState)
workflow.add_node("call_model", call_model_node)
workflow.add_node("execute_tool", execute_tool_node)
```

### 2.2 Sistema de Mensajes Dual

**KiloCode separa:**
- `apiConversationHistory`: Mensajes enviados al LLM
- `clineMessages`: Mensajes para la UI

```typescript
// KiloCode mantiene dos historias separadas
apiConversationHistory: ApiMessage[] = []  // Para la API
clineMessages: ClineMessage[] = []          // Para la UI
```

**KogniTerm usa una sola lista:**
```python
state.messages: List[BaseMessage]  # Mixtos
```

### 2.3 Sistema de Modos (Task Modes)

**KiloCode tiene modos persistentes:**
```typescript
private _taskMode: string | undefined
// Modos: "Read", "Write", "Agent" etc.
// Cada modo tiene diferentes herramientas disponibles
```

**KogniTerm no tiene sistema de modos formalizado.**

### 2.4 Tool Protocol Locking

**KiloCode bloquea el protocolo de herramientas:**
```typescript
private _taskToolProtocol: ToolProtocol | undefined
// Si la tarea empezó con XML tools, continúa con XML
// aunque el usuario cambie a Native Tool Calling después
```

**KogniTerm no implementa esta funcionalidad.**

### 2.5 Manejo de Contexto de Ventana

**KiloCode tiene condensación automática:**
```typescript
const FORCED_CONTEXT_REDUCTION_PERCENT = 75 // Keep 75%

// En manageContext:
if (contextTokens > maxTokens * 0.9) {
    // Condensar automáticamente
    const summary = await summarizeConversation(...)
}
```

**KogniTerm no tiene este sistema.**

---

## 3. Componentes Centrales de KiloCode

### 3.1 ToolRepetitionDetector

```typescript
toolRepetitionDetector: ToolRepetitionDetector

// Detecta cuando el agente repite la misma herramienta
if (this.toolRepetitionDetector.isRepetitive(toolName, toolInput)) {
    // Escalar error o tomar acción correctiva
}
```

### 3.2 FileContextTracker

```typescript
fileContextTracker: FileContextTracker

// Rastrea qué archivos se han editado
await task.fileContextTracker.trackFileContext(relPath, "roo_edited")
```

### 3.3 MessageManager

```typescript
private _messageManager?: MessageManager

// Manejo centralizado de rewinds
await task.messageManager.rewindToTimestamp(ts)
await task.messageManager.rewindToIndex(index)
```

### 3.4 AutoApprovalHandler

```typescript
autoApprovalHandler: AutoApprovalHandler

// Maneja aprobaciones automáticas basadas en reglas
const approvalResult = await this.autoApprovalHandler.checkAutoApprovalLimits(...)
```

---

## 4. Propuestas de Mejora para KogniTerm

### 4.1 Implementar Sistema de Mensajes Dual

```python
# Propuesta para kogniterm/core/message_manager.py

class MessageManager:
    def __init__(self, agent_state):
        self.api_history: List[Dict] = []  # Para LLM
        self.ui_messages: List[BaseMessage] = []  # Para UI
        self._deleted_api_cost: float = 0
    
    def rewind_to_timestamp(self, ts: float):
        """Rewind both histories consistently"""
        # Mantener consistencia entre ambas listas
    
    def get_effective_history(self):
        """Filtrar mensajes condensados para la API"""
        return filter_condensed_messages(self.api_history)
```

### 4.2 Sistema de Modos

```python
# Propuesta para kogniterm/core/modes.py

class AgentMode:
    def __init__(self, name: str, tools: List[str], system_prompt: str):
        self.name = name
        self.tools = tools
        self.system_prompt = system_prompt

class ModeManager:
    MODES = {
        "read": AgentMode("Read", ["read_file", "search"], READ_PROMPT),
        "write": AgentMode("Write", ["edit_file", "write_file"], WRITE_PROMPT),
        "agent": AgentMode("Agent", ALL_TOOLS, AGENT_PROMPT),
    }
    
    def get_mode_tools(self, mode: str) -> List[str]:
        return self.MODES.get(mode, []).tools
```

### 4.3 Sistema de Contexto Automático

```python
# Propuesta para kogniterm/core/context_manager.py

class ContextManager:
    def __init__(self, llm_service):
        self.llm = llm_service
        self.context_window = 200000  # tokens
    
    async def manage_context(self, messages: List, total_tokens: int):
        """Condensa contexto cuando se acerca al límite"""
        if total_tokens > self.context_window * 0.9:
            summary = await self.llm.summarize(messages)
            return self.create_condensed_history(messages, summary)
        return messages
```

### 4.4 FileContextTracker

```python
# Propuesta para kogniterm/core/context/file_tracker.py

class FileContextTracker:
    def __init__(self):
        self.edited_files: Dict[str, str] = {}  # path -> action
    
    async def track_edit(self, path: str, action: str = "modified"):
        self.edited_files[path] = action
    
    def get_recent_edits(self, limit: int = 10) -> List[str]:
        return list(self.edited_files.keys())[-limit:]
```

### 4.5 ToolRepetitionDetector

```python
# Propuesta para kogniterm/core/tools/repetition_detector.py

class ToolRepetitionDetector:
    def __init__(self, max_history: int = 10):
        self.history: List[Dict] = []
        self.max_history = max_history
    
    def is_repetitive(self, tool_name: str, tool_args: Dict) -> bool:
        """Detecta si la herramienta se está usando de forma repetitiva"""
        # Comparar con últimos 5 usos
        recent = self.history[-5:]
        return all(t['name'] == tool_name and t['args'] == tool_args 
                   for t in recent)
```

---

## 5. Comparativa de Flujo de Ejecución

### KiloCode Flow:
```
User Input
    ↓
Task.processUserMessage()
    ↓
Task.attemptApiRequest()
    ├→ manageContext() [auto-condense if needed]
    ├→ buildToolsArray()
    ├→ api.createMessage()
    ↓
Stream Response
    ├→ AssistantMessageParser (parse tools)
    ├→ Execute Tools
    ├→ ToolRepetitionDetector.check()
    ├→ FileContextTracker.track()
    ↓
Response to UI
```

### KogniTerm Flow (actual):
```
User Input
    ↓
call_model_node()
    ↓
LLMService.invoke()
    ↓
execute_tool_node()
    ↓
Tool Execution
    ↓
Response to UI
```

---

## 6. Recomendaciones de Implementación

### Fase 1: Infraestructura Básica
1. **MessageManager** - Sistema centralizado de mensajes
2. **FileContextTracker** - Tracking de archivos editados
3. **ToolRepetitionDetector** - Detección de bucles

### Fase 2: Inteligencia de Contexto
1. **ContextManager** - Condensación automática
2. **ModeManager** - Sistema de modos

### Fase 3: Características Avanzadas
1. **Checkpoint System** - Persistencia de tareas
2. **AutoApproval Handler** - Aprobaciones automáticas

---

*Documento creado el 11-02-2026*
*Basado en el análisis de github.com/Kilo-Org/kilocode*
