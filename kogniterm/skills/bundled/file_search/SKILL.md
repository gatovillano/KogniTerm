---
name: file_search
version: 1.0.0
author: "KogniTerm Core"
description: "Busca archivos que coincidan con un patrón glob en un directorio específico"
category: "filesystem"
tags: ["file", "search", "glob", "filesystem", "find"]
dependencies: []
required_permissions: ["filesystem"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite buscar archivos usando patrones glob en el sistema de archivos.

## Herramientas disponibles:

### file_search

Busca archivos que coincidan con un patrón glob en un directorio específico o en el directorio de trabajo actual.

**Parámetros:**
- `pattern` (string, requerido): El patrón glob a buscar (ej. '*.txt', 'src/**/*.py')
- `path` (string, opcional): El directorio absoluto donde buscar. Si no se proporciona, busca en el directorio de trabajo actual

**Ejemplo:**
```json
{
  "tool": "file_search",
  "args": {
    "pattern": "*.py",
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

1. Usa esta herramienta para encontrar archivos por extensión o patrón
2. Los patrones comunes incluyen: *.py, *.js, **/*.txt, src/**/*.py
3. La búsqueda es recursiva cuando se usan **
4. Devuelve rutas absolutas de los archivos encontrados
5. El path debe ser una ruta absoluta si se proporciona
