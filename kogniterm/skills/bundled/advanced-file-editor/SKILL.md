---
name: advanced-file-editor
description: Herramienta profesional de edición de archivos con múltiples estrategias, operaciones por lote y rollback automático.
category: file_operations
---
# Advanced File Editor - Herramienta Profesional de Edición

## Descripción

Herramienta profesional de edición de archivos con múltiples estrategias, operaciones por lote y rollback automático.

## Capacidades

- **Múltiples Estrategias de Edición**: Soporta 10 acciones diferentes (insertar, reemplazar, eliminar, búsqueda por regex, etc.)
- **Operaciones por Lote ATÓMICAS**: Ejecutar múltiples operaciones en un solo archivo de forma **todo-o-nada**. Si una operación falla, NINGÚN cambio se persiste en disco.
- **Match EXACTO por defecto**: El matching flexible (fuzzy) está disponible pero **desactivado por defecto** para evitar el sobre-match que producía ediciones erráticas.
- **Validación de Seguridad**: Verifica la validez de cada operación antes de ejecutar.
- **Transacciones con rollback**: Cada conjunto de operaciones tiene un `transaction_id`. Se puede revertir con `action: "rollback", transaction_id: "..."`.
- **Feedback rico al LLM**: Las operaciones exitosas devuelven `matched_span` y `applied_diff` para que el LLM verifique el cambio.
- **Logging Profesional**: Trazabilidad completa de todas las operaciones.

## Uso Básico

### Edición Simple

```json
{
  "path": "/ruta/al/archivo.txt",
  "action": "replace_block",
  "target_content": "texto a buscar",
  "replacement_content": "nuevo texto",
  "confirm": true
}
```

### Operaciones por Lote

```json
{
  "path": "/ruta/al/archivo.txt",
  "operations": [
    {
      "action": "insert_line",
      "line_number": 5,
      "content": "nueva línea"
    },
    {
      "action": "replace_block",
      "target_content": "viejo texto",
      "replacement_content": "nuevo texto"
    }
  ],
  "confirm": true
}
```

**Nota importante**: En operaciones por lote, el parámetro `path` se hereda del contexto principal. No es necesario especificarlo en cada operación individual.

## Acciones Disponibles

| Acción | Descripción | Parámetros Requeridos |
|--------|-------------|----------------------|
| `insert_line` | Inserta contenido en una línea específica | `line_number`, `content` |
| `replace_block` | Reemplaza un bloque de texto. Match EXACTO por defecto. | `target_content`, `replacement_content` |
| `replace_lines` | Reemplaza un rango de líneas (1-based) | `line_number`, `replacement_content` |
| `insert_after_match` | Inserta después de una coincidencia exacta | `target_content`, `content` |
| `insert_before_match` | Inserta antes de una coincidencia exacta | `target_content`, `content` |
| `replace_regex` | Reemplaza usando expresión regular | `regex_pattern`, `replacement_content` |
| `delete_lines` | Elimina un rango de líneas | `line_number`, `end_line` (opcional) |
| `prepend_content` | Añade contenido al inicio | `content` |
| `append_content` | Añade contenido al final | `content` |
| `full_replacement` | Reemplaza todo el contenido | `content` |
| `rollback` | Revierte una transacción previa | `transaction_id` |

## Parámetros de control del match

- `fuzzy` (bool, default `false`): permite coincidencia flexible en `replace_block` / `insert_*_match`. **Recomendado: dejar en false salvo necesidad real.**
- `require_unique` (bool, default `true`): si `true`, falla con lista de líneas cuando el target aparece más de una vez.
- `context_hint` (string, opcional): substring único que debe estar dentro de ±20 líneas del match correcto. Permite desambiguar entre múltiples matches.

## Atomicidad del batch (2026-07)

Cuando se proporciona `operations: [...]`, las operaciones se aplican de forma **atómica**:

1. Se validan TODAS las operaciones contra el contenido en memoria.
2. Si todas validan, se escribe el archivo una sola vez.
3. Si UNA falla, el archivo en disco queda **idéntico** al original (cero cambios parciales).
4. El resultado indica `failed_at: N` y el mensaje de la operación que falló.

Antes (comportamiento anterior): cada operación escribía a disco; un batch de 5 ops donde la 3ª fallaba dejaba 2 cambios persistidos. **Esto ya no ocurre.**

## Características Avanzadas

### Transacciones

Cada conjunto de operaciones se envuelve en una transacción con ID único:
- Permite seguimiento de cambios
- Soporta rollback manual si es necesario
- Mantiene historial de operaciones

### Manejo de Errores

- Validación previa de todas las operaciones
- Rollback automático si falla cualquier operación
- Mensajes de error detallados con sugerencias
- Prevención de race conditions

### FlexibleMatcher

El sistema usa un matcher flexible que:
- Ignora variaciones menores de espaciado
- Soporta búsqueda de bloques con espacios flexibles
- Permite búsquedas más robustas en código

## Seguridad

- **Race Condition Guard**: Protege contra modificaciones concurrentes
- **Validación de Paths**: Limpia y normaliza rutas
- **Confirmación Humana**: Requiere confirmación explícita para cambios
- **Preview de Cambios**: Muestra diff antes de aplicar

## Ejemplos de Uso

### Añadir una función a un archivo Python
```json
{
  "path": "mi_archivo.py",
  "action": "insert_after_match",
  "target_content": "def main():",
  "content": "\n    # Nuevo código aquí"
}
```

### Reemplazar múltiples secciones
```json
{
  "path": "config.json",
  "operations": [
    {"action": "replace_block", "target_content": "\"version\": \"1.0\"", "replacement_content": "\"version\": \"2.0\""},
    {"action": "append_content", "content": "\n\"new_key\": \"value\""}
  ]
}
```

### Crear archivo nuevo
```json
{
  "path": "nuevo_archivo.txt",
  "action": "full_replacement",
  "content": "Contenido inicial del archivo"
}
```