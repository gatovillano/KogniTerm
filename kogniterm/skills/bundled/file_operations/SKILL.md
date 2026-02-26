---
name: file_operations
version: 1.0.0
author: "KogniTerm Core"
description: "Realiza operaciones CRUD (Crear, Leer, Actualizar, Borrar) en archivos y directorios"
category: "filesystem"
tags: ["file", "filesystem", "crud", "read", "write", "delete"]
dependencies: []
required_permissions: ["filesystem"]
security_level: "high"
allowlist: true
auto_approve: false
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite realizar operaciones completas de archivos y directorios.

## Herramientas disponibles

### file_operations

Realiza operaciones CRUD en archivos y directorios.

**Parámetros:**

- `operation` (string, requerido): La operación a realizar. Valores posibles:
  - `read_file`: Lee un archivo
  - `read_many_files`: Lee múltiples archivos eficientemente
  - `write_file`: Escribe o crea un archivo
  - `delete_file`: Elimina un archivo
  - `list_directory`: Lista el contenido de un directorio
  - `create_directory`: Crea un directorio
  - `move_file`: Mueve o renombra un archivo/directorio
  - `copy_file`: Copia un archivo/directorio de forma recursiva
  - `append_file`: Añade contenido al final de un archivo
  - `get_file_info`: Extrae metadatos (tamaño, fechas) de un archivo/directorio
  - `search_in_file`: Busca texto o regex dentro de un archivo
- `path` (string, opcional): Ruta absoluta del archivo/directorio
- `content` (string, opcional): Contenido para escribir (`write_file` o `append_file`)
- `paths` (array, opcional): Lista de rutas para `read_many_files`
- `recursive` (boolean, opcional): Listado recursivo (`list_directory`)
- `start_line` (integer, opcional): Línea de inicio (1-indexed) para la operación `read_file`
- `end_line` (integer, opcional): Línea final (1-indexed) para la operación `read_file`
- `destination` (string, opcional): Ruta de destino para `move_file` y `copy_file`
- `pattern` (string, opcional): Patrón de búsqueda (texto o regex) para `search_in_file`

**Ejemplos:**

```json
{
  "tool": "file_operations",
  "args": {
    "operation": "read_file",
    "path": "/home/user/project/main.py",
    "start_line": 10,
    "end_line": 50
  }
}
```

```json
{
  "tool": "file_operations",
  "args": {
    "operation": "write_file",
    "path": "/home/user/project/new_file.py",
    "content": "# Nuevo archivo Python\nprint('Hello World')"
  }
}
```

```json
{
  "tool": "file_operations",
  "args": {
    "operation": "read_many_files",
    "paths": ["/home/user/file1.py", "/home/user/file2.py", "/home/user/file3.py"]
  }
}
```

## Consideraciones de seguridad

- **Nivel de seguridad: high** - Requiere confirmación del usuario
- **Permisos requeridos:** filesystem
- **Requiere allowlisting:** true
- **Auto-aprobación:** false (excepto operaciones de solo lectura)

### Flujo de operaciones

1. **read_file, list_directory, read_many_files, get_file_info, search_in_file**: Operaciones de solo lectura
   - Pueden tener auto_approve enabled
   - No modifican el sistema de archivos

2. **write_file, delete_file, create_directory, move_file, copy_file, append_file**: Operaciones de escritura
   - Siempre requieren confirmación del usuario
   - Muestran diff antes de ejecutar
   - Validan race conditions

## Patrones ignorados

Esta herramienta ignora por defecto:

- Directorios: `venv`, `.git`, `__pycache__`, `.venv`
- Archivos en `.gitignore` y `.kognitermignore`
