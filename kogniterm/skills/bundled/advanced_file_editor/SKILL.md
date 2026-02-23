---
name: advanced_file_editor
version: 1.0.0
author: "KogniTerm Core"
description: "Realiza operaciones de edición avanzadas en archivos con validación de race conditions y confirmación previa"
category: "filesystem"
tags: ["file", "edit", "advanced", "diff", "race-condition", "validation"]
dependencies: []
required_permissions: ["filesystem"]
security_level: "high"
allowlist: true
auto_approve: false
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite realizar operaciones de edición avanzadas en archivos con características de seguridad mejoradas.

## Herramientas disponibles:

### advanced_file_editor

Realiza operaciones de edición avanzadas en archivos con validación de race conditions y confirmación previa.

**Parámetros:**
- `path` (string, requerido): La ruta del archivo a editar.
- `action` (string, requerido): La operación a realizar. Valores posibles:
  - `insert_line`: Inserta contenido en una línea específica
  - `replace_regex`: Reemplaza contenido usando expresiones regulares
  - `prepend_content`: Añade contenido al inicio del archivo
  - `append_content`: Añade contenido al final del archivo
- `content` (string, opcional): El contenido a insertar, añadir o usar para reemplazar.
- `line_number` (integer, opcional): El número de línea para la acción 'insert_line' (basado en 1).
- `regex_pattern` (string, opcional): El patrón de expresión regular a buscar para la acción 'replace_regex'.
- `replacement_content` (string, opcional): El contenido de reemplazo para la acción 'replace_regex'.

**Ejemplos:**
```json
{
  "tool": "advanced_file_editor",
  "args": {
    "path": "/home/user/project/main.py",
    "action": "insert_line",
    "content": "print('Hola mundo')",
    "line_number": 5
  }
}
```

```json
{
  "tool": "advanced_file_editor",
  "args": {
    "path": "/home/user/project/config.py",
    "action": "replace_regex",
    "regex_pattern": "DEBUG = .*",
    "replacement_content": "DEBUG = False"
  }
}
```

```json
{
  "tool": "advanced_file_editor",
  "args": {
    "path": "/home/user/project/README.md",
    "action": "append_content",
    "content": "\n## Instalación\n\n```bash\npip install requirements.txt\n```"
  }
}
```

## Características avanzadas:

### 1. Validación de Race Conditions
La herramienta valida que el archivo no haya sido modificado externamente antes de aplicar cambios, evitando conflictos de concurrencia.

### 2. Confirmación previa
Antes de aplicar cualquier cambio, la herramienta muestra un diff detallado y requiere confirmación explícita del usuario.

### 3. Manejo de interrupciones
Si la operación es interrumpida durante la escritura, el sistema mantiene la integridad del archivo y notifica cualquier problema.

### 4. Validación de expresiones regulares
Antes de aplicar reemplazos con regex, la herramienta valida que el patrón sea válido y que el reemplazo sea seguro.

## Consideraciones de seguridad:

- **Nivel de seguridad: high** - Requiere confirmación del usuario
- **Permisos requeridos:** filesystem
- **Requiere allowlisting:** true
- **Auto-aprobación:** false (siempre requiere confirmación)

### Flujo de operaciones:

1. **Lectura del archivo**: Lee el contenido actual del archivo
2. **Aplicación de cambios**: Aplica la operación solicitada
3. **Generación de diff**: Crea un diff unificado entre el contenido original y modificado
4. **Confirmación**: Muestra el diff y espera confirmación del usuario
5. **Escritura segura**: Aplica los cambios con validación de race conditions

## Patrones ignorados:

Esta herramienta ignora por defecto:
- Directorios: `venv`, `.git`, `__pycache__`, `.venv`
- Archivos en `.gitignore` y `.kognitermignore`

## Errores comunes:

- **Race condition**: El archivo fue modificado por otro proceso durante la operación
- **Regex inválido**: El patrón de expresión regular no es sintácticamente correcto
- **Permisos insuficientes**: El usuario no tiene permisos para escribir en el archivo
- **Ruta no encontrada**: El archivo especificado no existe