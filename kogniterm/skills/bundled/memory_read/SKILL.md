---
name: memory_read
version: 1.0.0
author: "KogniTerm Core"
description: "Lee el contenido de la memoria contextual del proyecto desde 'llm_context.md'."
category: "memory"
tags: ["memory", "context", "read", "view"]
dependencies: []
required_permissions: ["memory"]
security_level: "low"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite leer el contenido de la memoria contextual del proyecto.

## Herramientas disponibles:

### memory_read

Lee el contenido de un archivo de memoria en el directorio `.kogniterm/`.

**Parámetros:**
- `file_path` (string, opcional): Ruta del archivo de memoria (default: "llm_context.md")

**Ejemplo:**
```json
{
  "tool": "memory_read",
  "args": {
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

1. Usa esta herramienta para leer información almacenada en la memoria
2. El archivo se lee desde `.kogniterm/llm_context.md` por defecto
3. Si el archivo no existe, retornará un error indicando que no fue encontrado
4. Útil para recuperar contexto entre sesiones

## Archivos de memoria:

- `llm_context.md`: Contexto general del proyecto
- Se pueden leer otros archivos según necesidad
