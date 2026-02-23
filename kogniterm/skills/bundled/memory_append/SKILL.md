---
name: memory_append
version: 1.0.0
author: "KogniTerm Core"
description: "Añade contenido a la memoria contextual del proyecto en 'llm_context.md'"
category: "memory"
tags: ["memory", "context", "notes", "append"]
dependencies: []
required_permissions: ["memory"]
security_level: "low"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite añadir contenido a la memoria contextual del proyecto.

## Herramientas disponibles:

### memory_append

Añade contenido a un archivo de memoria en el directorio `.kogniterm/`.

**Parámetros:**
- `content` (string, requerido): El contenido a añadir a la memoria
- `file_path` (string, opcional): Ruta del archivo de memoria (default: "llm_context.md")

**Ejemplo:**
```json
{
  "tool": "memory_append",
  "args": {
    "content": "El usuario prefiere que los archivos se guarden con encoding UTF-8",
    "file_path": "llm_context.md"
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: low** - Operación segura
- **Permisos requeridos:** memory
- **Requiere allowlisting:** false
- **Auto-aprobación:** true (siempre aprobada)

## Uso:

1. Usa esta herramienta para guardar información importante del proyecto
2. El contenido se almacena en `.kogniterm/llm_context.md` por defecto
3. Esta información se puede leer posteriormente con memory_read
4. Útil para mantener contexto entre sesiones

## Archivos de memoria:

- `llm_context.md`: Contexto general del proyecto
- Se pueden crear otros archivos según necesidad
