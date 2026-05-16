---
name: file_operations
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
> **Flujo de trabajo recomendado:** Siempre lee el archivo con `read_file_tool` antes de usar `sophisticated_editor_tool`. Prefiere `replace_block` (ahora flexible con los espacios) o `replace_lines` (muy preciso) para evitar errores de coincidencia.



### sophisticated_editor_tool (PREMIUM)

Herramienta avanzada para edición precisa de archivos. Combina múltiples estrategias de edición con protección contra Race Conditions.

**Acciones disponibles (`action`):**
- `insert_line`: Inserta `content` en la línea `line_number`.
- `replace_block`: Reemplaza un bloque de texto literal (`target_content`) con `replacement_content`. **Muy robusto**: ahora tolera pequeñas variaciones en espacios y sangría. Recomendado para fragmentos de código.
- `replace_lines`: Reemplaza desde `line_number` hasta `end_line` (inclusive) con `replacement_content`. Opcionalmente valida con `target_content`.
- `insert_after_match`: Inserta `content` justo después de la coincidencia de `target_content`.
- `insert_before_match`: Inserta `content` justo antes de la coincidencia de `target_content`.
- `replace_regex`: Reemplaza ocurrencias de `regex_pattern` con `replacement_content`. Útil para patrones complejos.
- `delete_lines`: Borra desde `line_number` hasta `end_line` (inclusive). Si no se da `end_line`, borra solo una línea.
- `prepend_content`: Añade `content` al inicio del archivo.
- `append_content`: Añade `content` al final del archivo.
- `full_replacement`: Reemplaza todo el contenido del archivo (equivalente a `write_file`).

**Parámetros adicionales:** `path`, `content`, `line_number`, `end_line`, `regex_pattern`, `replacement_content`, `target_content`.

### file_read_tool

Funciones de lectura y metadatos.
- `read_file_tool(path, start_line, end_line)`
- `read_many_files_tool(paths)`
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
