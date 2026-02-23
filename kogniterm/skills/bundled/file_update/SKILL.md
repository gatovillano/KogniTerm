---
name: file_update
version: 1.0.0
author: "KogniTerm Core"
description: "Actualiza el contenido de un archivo existente, mostrando las diferencias antes de aplicar"
category: "filesystem"
tags: ["file", "update", "write", "edit", "filesystem"]
dependencies: []
required_permissions: ["filesystem"]
security_level: "elevated"
allowlist: true
auto_approve: false
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite actualizar el contenido de un archivo existente, mostrando las diferencias (diff) antes de aplicar los cambios.

## Herramientas disponibles:

### file_update

Actualiza el contenido de un archivo existente. Muestra las diferencias y requiere confirmación del usuario antes de aplicar los cambios.

**Parámetros:**
- `path` (string, requerido): La ruta del archivo a actualizar
- `content` (string, requerido): El nuevo contenido del archivo

**Ejemplo:**
```json
{
  "tool": "file_update",
  "args": {
    "path": "/home/gato/proyecto/config.txt",
    "content": "Nuevo contenido del archivo..."
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: elevated** - Requiere confirmación del usuario
- **Permisos requeridos:** filesystem
- **Requiere allowlisting:** true
- **Auto-aprobado:** false

## Uso recomendado:

1. Usa esta herramienta para actualizar archivos existentes
2. Primero lee el archivo actual para ver su contenido
3. La herramienta muestra un diff de los cambios antes de aplicar
4. El usuario debe confirmar explícitamente para aplicar los cambios
5. El archivo debe existir previamente (para nuevos archivos usa file_operations)
6. Maneja errores de permisos y archivos no encontrados
