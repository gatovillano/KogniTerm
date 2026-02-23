---
name: file_read_directory
version: 1.0.0
author: "KogniTerm Core"
description: "Lee el contenido de un directorio (no recursivo), listando archivos y subdirectorios"
category: "filesystem"
tags: ["file", "directory", "read", "list", "filesystem"]
dependencies: []
required_permissions: ["filesystem"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite leer el contenido de un directorio (no recursivo), mostrando los archivos y subdirectorios.

## Herramientas disponibles:

### file_read_directory

Lee el contenido de un directorio y lo lista de forma no recursiva.

**Parámetros:**
- `path` (string, requerido): La ruta del directorio a leer

**Ejemplo:**
```json
{
  "tool": "file_read_directory",
  "args": {
    "path": "/home/gato/proyecto"
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: standard** - No requiere aprobación
- **Permisos requeridos:** filesystem
- **Requiere allowlisting:** false
- **Auto-aprobado:** true

## Uso recomendado:

1. Usa esta herramienta para explorar la estructura de directorios
2. La lista es no recursiva (solo muestra el contenido directo)
3. Distingue entre archivos y directorios en la salida
4. Útil para verificar qué archivos existen en una ubicación
5. Maneja errores de permisos y directorios no encontrados
