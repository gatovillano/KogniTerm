---
name: file-operations
version: 2.0.0
author: "KogniTerm Core"
description: "Conjunto avanzado de herramientas para operaciones CRUD y edición sofisticada de archivos."
category: "filesystem"
tags: ["file", "filesystem", "crud", "read", "write", "delete", "edit", "sophisticated"]
dependencies: []
required_permissions: ["filesystem"]
security_level: "high"
allowlist: true
auto_approve: false
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill proporciona herramientas granulares y avanzadas para interactuar con el sistema de archivos. Se recomienda usar la herramienta específica para cada tarea.

## Herramientas disponibles

> [!TIP]
> **Flujo de trabajo recomendado (2026-07):**
> 1. Lee el archivo con `read_file_tool` — ahora devuelve líneas numeradas por defecto.
> 2. Para cambios grandes o cualquier cosa con `line_number`: usa `replace_lines` (es 1-based, copia los números del read).
> 3. Para cambios pequeños: usa `replace_block` con un `target_content` único y exacto.
> 4. `insert_after_match` solo cuando tengas un ancla única.
> 5. `fuzzy=true` está disponible pero **DESACTIVADO por defecto**. Actívalo solo si el whitespace del archivo es inestable.

> [!WARNING]
> El matching es **EXACTO** por defecto. Si tu `target_content` aparece más de una vez, la operación falla con la lista de líneas donde aparece. Usa `context_hint` con un fragmento único cercano para desambiguar, o `replace_lines` por rango.

> [!NOTE]
> Todas las operaciones exitosas devuelven `matched_span` (líneas y texto que se reemplazó) y `applied_diff` (unified diff). **Verifica estos campos** en cada edición para confirmar que diste en el lugar correcto.



### sophisticated_editor_tool (PREMIUM)

Herramienta avanzada para edición precisa de archivos. Combina múltiples estrategias de edición con protección contra Race Conditions.

**Alias:** `sophisticated_editor_tool`, `replace_file_content` y `advanced_file_editor` son el mismo objeto. Usa `advanced_file_editor` en código nuevo.

**Acciones disponibles (`action`):**
- `insert_line`: Inserta `content` en la línea `line_number` (1-based).
- `replace_block`: Reemplaza un bloque de texto literal (`target_content`) con `replacement_content`. **Match EXACTO por defecto.** Si el target aparece varias veces, falla salvo que proporciones `context_hint` o pongas `require_unique=false`. Usa `fuzzy=true` solo si el whitespace del archivo es inestable.
- `replace_lines`: Reemplaza desde `line_number` hasta `end_line` (inclusive) con `replacement_content`. Opcionalmente valida con `target_content` (con matching exacto).
- `insert_after_match`: Inserta `content` justo después de la coincidencia de `target_content` (exacto por defecto).
- `insert_before_match`: Inserta `content` justo antes de la coincidencia de `target_content`.
- `replace_regex`: Reemplaza ocurrencias de `regex_pattern` con `replacement_content`.
- `delete_lines`: Borra desde `line_number` hasta `end_line` (inclusive).
- `prepend_content`: Añade `content` al inicio del archivo.
- `append_content`: Añade `content` al final del archivo.
- `full_replacement`: Reemplaza todo el contenido del archivo (equivalente a `write_file`).

**Parámetros nuevos (2026-07):**
- `fuzzy` (bool, default `false`): si `true`, permite coincidencia flexible para `replace_block` e `insert_*_match`. **No recomendado por defecto**.
- `require_unique` (bool, default `true`): si `true`, falla cuando el target aparece > 1 vez.
- `context_hint` (string, opcional): substring que debe estar dentro de ±20 líneas del match correcto. Útil para desambiguar.

**Parámetros clásicos:** `path`, `content`, `line_number`, `end_line`, `regex_pattern`, `replacement_content`, `target_content`, `confirm`.

**Resultado de éxito incluye:**
- `status`: `"success"`.
- `matched_span`: `{start, end, line_start, line_end, matched_text, fuzzy, score}` — qué se reemplazó exactamente.
- `applied_diff`: unified diff del cambio. Verifica este campo para confirmar la edición.

### file_read_tool

Funciones de lectura y metadatos.
- `read_file_tool(path, start_line, end_line, with_line_numbers=True)` — **devuelve líneas numeradas por defecto** en formato `   12 | código`. Usa `with_line_numbers=false` para contenido crudo. Inspecciónalo siempre antes de editar.
- `read_many_files_tool(paths, with_line_numbers=True)`
- `get_file_info_tool(path)`

### file_write_tool

Operaciones básicas de creación y adición.
- `write_file_tool(path, content)`
- `append_file_tool(path, content)`
- `create_directory_tool(path)`

### file_management_tool

Gestión de archivos y directorios.
- `delete_file_tool(path)`
- `move_file_tool(path, destination)`
- `copy_file_tool(path, destination)`

### Otros:
- `list_directory_tool(path, recursive)`
- `search_in_file_tool(path, pattern)`
- `glob_search_tool(pattern, path)`

## Consideraciones de seguridad

- **Nivel de seguridad: high** - Requiere confirmación del usuario para escrituras.
- **Protección contra Race Conditions:** El `sophisticated_editor_tool` valida que el archivo no haya cambiado entre la lectura y la escritura.
- **Diff Preview:** Todas las herramientas de escritura generan un diff para revisión antes de aplicar los cambios.

## Patrones ignorados por defecto

- Directorios: `venv`, `.git`, `__pycache__`, `.venv`, `node_modules`.
- Archivos/directorios ocultos (que empiezan con `.`).
