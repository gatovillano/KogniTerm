# Advanced File Editor - Herramienta Profesional de Edición

## Descripción

Herramienta profesional de edición de archivos con múltiples estrategias, operaciones por lote y rollback automático.

## Capacidades

- **Múltiples Estrategias de Edición**: Soporta 10 acciones diferentes (insertar, reemplazar, eliminar, búsqueda por regex, etc.)
- **Operaciones por Lote**: Ejecutar múltiples operaciones en un solo archivo de forma atómica
- **Rollback Automático**: Si una operación falla, se revierte todo el lote
- **Validación de Seguridad**: Verifica la validez de cada operación antes de ejecutar
- **Transacciones**: Sistema de transacciones con IDs únicos para seguimiento
- **Logging Profesional**: Trazabilidad completa de todas las operaciones

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
| `replace_block` | Reemplaza un bloque de texto | `target_content`, `replacement_content` |
| `replace_lines` | Reemplaza un rango de líneas | `line_number`, `replacement_content` |
| `insert_after_match` | Inserta después de una coincidencia | `target_content`, `content` |
| `insert_before_match` | Inserta antes de una coincidencia | `target_content`, `content` |
| `replace_regex` | Reemplaza usando expresión regular | `regex_pattern`, `replacement_content` |
| `delete_lines` | Elimina un rango de líneas | `line_number`, `end_line` (opcional) |
| `prepend_content` | Añade contenido al inicio | `content` |
| `append_content` | Añade contenido al final | `content` |
| `full_replacement` | Reemplaza todo el contenido | `content` |

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