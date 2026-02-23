# Investigación de KiloCode: Mejoras para KogniTerm

## Resumen Ejecutivo

He analizado el repositorio de **Kilo-Org/kilocode** (15,226 estrellas en GitHub) para identificar técnicas que mejoren la **precisión e inteligencia del agente** respecto al contexto del código. A continuación presento las mejoras organizadas por categoría.

---

## 1. Arquitectura del Sistema de Mensajes

### Diferencias Clave

| Característica | KogniTerm (actual) | KiloCode |
|---------------|---------------------|----------|
| Sistema de mensajes | Lista simple de mensajes | MessageManager centralizado |
| Rewind de conversación | Básico | Sistema robusto con cleanup |
| Contexto de ventana | No hay condensación | Condensación automática |
| Tracking de archivos | Limitado | FileContextTracker |

### Mejoras Propuestas:

#### 1.1 MessageManager (Prioridad ALTA)
KiloCode tiene un `MessageManager` que maneja **todas** las operaciones de rewind de forma centralizada:

```typescript
// KiloCode: MessageManager
await task.messageManager.rewindToTimestamp(ts, { includeTargetMessage: false })
```

** Beneficios:**
- Manejo consistente de mensajes huérfanos (condensed summaries, truncation markers)
- Cleanup automático después de truncaciones
- Prevención de inconsistencias entre mensajes UI y API

**Implementación sugerida para KogniTerm:**
- Crear una clase `MessageManager` en `kogniterm/core/message_manager.py`
- Centralizar todas las operaciones de eliminación/rewind
- Mantener consistencia entre `apiConversationHistory` y mensajes visibles

#### 1.2 Sistema de Condensación de Contexto (Prioridad ALTA)

KiloCode implementa `manageContext()` que:
- Detecta cuando se acerca al límite de tokens
- Condensa automáticamente la conversación usando el mismo modelo
- Mantiene un resumen que permite continuar la conversación

```typescript
// KiloCode: manageContext
const truncateResult = await manageContext({
  messages: this.apiConversationHistory,
  totalTokens: contextTokens,
  maxTokens,
  contextWindow,
  autoCondenseContext: true,
  autoCondenseContextPercent: 75, // Keep 75% after truncation
})
```

**Para KogniTerm:**
- Implementar un sistema de condensación de contexto
- Usar el mismo LLM para crear resúmenes
- Mantener la historia de conversación mientras se reduce el tamaño

---

## 2. Sistema de Contexto de Código

### 2.1 FileContextTracker (Prioridad MEDIA)

KiloCode rastrea **qué archivos se han editado** durante la sesión:

```typescript
// KiloCode
await task.fileContextTracker.trackFileContext(relPath, "roo_edited" as RecordSource)
```

**Beneficios:**
- El agente sabe qué archivos ha modificado
- Puede tomar decisiones basadas en el historial de cambios
- Útil para evitar ediciones conflictivas

**Para KogniTerm:**
- Implementar `FileContextTracker` en `kogniterm/core/context/`
- Guardar historial de archivos editados por sesión
- Proporcionar este contexto al LLM en cada request

### 2.2 Búsqueda Semántica (Prioridad MEDIA)

KiloCode usa **CodebaseSearchTool** con indexación vectorial:

```typescript
// KiloCode: CodebaseSearchTool
const searchResults = await manager.searchIndex(query, directoryPrefix)
```

KogniTerm ya tiene `CodebaseIndexer` y `EmbeddingsService`, pero:
- **Falta integración activa** con el agente
- El agente no usa búsqueda semántica automáticamente

**Mejora sugerida:**
- Activar el uso de `codebase_search` en el mensaje del sistema
- Instruir al agente a usar búsqueda semántica para código complejo

---

## 3. Sistema de Herramientas Inteligentes

### 3.1 ToolRepetitionDetector (Prioridad ALTA)

KiloCode detecta cuando el agente está en un **bucle de repetición**:

```typescript
// KiloCode: ToolRepetitionDetector
if (this.isToolRepeated(toolName, toolInput)) {
  // Escalar error después de N intentos
}
```

KogniTerm ya tiene detección básica de bucles en `bash_agent.py`:
```python
# KogniTerm: bash_agent.py - ya implementado
if len(state.tool_call_history) >= 4:
    if all(tc['name'] == last_calls[0]['name'] ...):
        state.critical_loop_detected = True
```

**Mejora sugerida:**
- Extender para detectar patrones más sofisticados
- Implementar backoff exponencial antes de detener

### 3.2 Estrategias de Búsqueda Múltiples (Prioridad ALTA)

KiloCode usa **3 estrategias** para encontrar texto a reemplazar:

| Estrategia | Descripción |
|-----------|-------------|
| **Exacta** | Coincidencia literal del string |
| **Whitespace-tolerant** | Ignora diferencias de espacios/blancos |
| **Token-based** | Ignora tokens individuales |

```typescript
// KiloCode: EditFileTool.ts
const wsRegex = buildWhitespaceTolerantRegex(oldLF)
const tokenRegex = buildTokenRegex(oldLF)

// Estrategia 1: exact literal match
const exactOccurrences = countOccurrences(currentContentLF, oldLF)

// Estrategia 2: whitespace-tolerant regex  
const wsOccurrences = countRegexMatches(currentContentLF, wsRegex)

// Estrategia 3: token-based regex
const tokenOccurrences = countRegexMatches(currentContentLF, tokenRegex)
```

**Para KogniTerm:**
- Implementar estas 3 estrategias en `advanced_file_editor_tool.py`
- Proporcionar mensajes de error más precisos cuando no encuentra coincidencia
- Agregar parámetro `expected_replacements` para validar cantidad

### 3.3 Validación de Conteo de Ocurrencias (Prioridad MEDIA)

```typescript
// KiloCode: EditFileTool.ts
if (exactOccurrences === expectedReplacements) {
  currentContentLF = safeLiteralReplace(currentContentLF, oldLF, newLF)
} else {
  // Probar siguiente estrategia o error
}
```

**Beneficio:** Evita reemplazos accidentales de más de lo esperado.

---

## 4. Sistema de Protección de Archivos

### 4.1 RooIgnoreController (Prioridad MEDIA)

KiloCode tiene un sistema para **ignorar archivos** basado en `.gitignore` y `.kognitermignore`:

```typescript
// KiloCode
const accessAllowed = task.rooIgnoreController?.validateAccess(relPath)
if (!accessAllowed) {
  await task.say("rooignore_error", relPath)
  return
}
```

**Para KogniTerm:**
- Ya tiene patrones de ignore en `WorkspaceContext`
- Integrar con herramientas de edición para validar acceso

### 4.2 RooProtectedController (Prioridad BAJA)

Archivos protegidos de edición (configurables por el usuario).

---

## 5. Manejo de Errores Inteligente

### 5.1 ConsecutiveMistakeCount (Prioridad ALTA)

KiloCode cuenta los **errores consecutivos** por herramienta:

```typescript
// KiloCode
task.consecutiveMistakeCount++
task.recordToolError("edit_file", formattedError)

// Después de 2 errores en el mismo archivo
if (currentCount >= 2) {
  await task.say("diff_error", formattedError)
}
```

**Para KogniTerm:**
- Implementar tracking de errores por tipo de herramienta
- Proporcionar sugerencias de recuperación más específicas

### 5.2 Mensajes de Error Detallados (Prioridad MEDIA)

KiloCode proporciona **sugerencias de recuperación** en cada error:

```
<error_details>
Recovery suggestions:
1. Verify the file exists and is readable
2. Check file permissions
3. If the file may have changed, use read_file to confirm its current contents
</error_details>
```

---

## 6. Sistema de Checkpoints (Prioridad BAJA)

KiloCode permite **guardar y restaurar** el estado de la tarea:

```typescript
// KiloCode
await task.checkpointSave(force, suppressMessage)
await task.checkpointRestore(options)
```

Esto permite al usuario retomar una tarea desde un punto anterior.

---

## Resumen de Prioridades

| Prioridad | Mejora | Impacto |
|-----------|--------|---------|
| **ALTA** | MessageManager con rewind centralizado | Consistencia de mensajes |
| **ALTA** | Sistema de condensación de contexto | Manejo de conversaciones largas |
| **ALTA** | Estrategias de búsqueda múltiples | Precisión en ediciones |
| **ALTA** | ToolRepetitionDetector mejorado | Evita bucles infinitos |
| **MEDIA** | FileContextTracker | Contexto de cambios |
| **MEDIA** | ConsecutiveMistakeCount | Mejor manejo de errores |
| **MEDIA** | Mensajes de error detallados | UX mejorada |
| **BAJA** | Sistema de checkpoints | Persistencia de tareas |
| **BAJA** | Protección de archivos | Seguridad |

---

## Próximos Pasos Recomendados

1. **Inmediato**: Mejorar el sistema de edición con estrategias múltiples
2. **Corto plazo**: Implementar MessageManager y condensación de contexto
3. **Mediano plazo**: FileContextTracker y tracking de errores

---

*Investigación realizada el 11-02-2026*
*Fuente: github.com/Kilo-Org/kilocode*
