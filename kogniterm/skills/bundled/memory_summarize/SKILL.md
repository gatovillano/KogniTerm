---
name: memory_summarize
version: 1.0.0
author: "KogniTerm Core"
description: "Resume el contenido de la memoria contextual del proyecto en 'llm_context.md'. (Nota: La implementación actual es un placeholder y no realiza una sumarización real con LLM)."
category: "memory"
tags: ["memory", "context", "summarize", "compress"]
dependencies: []
required_permissions: ["memory"]
security_level: "medium"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite resumir el contenido de la memoria contextual del proyecto.

## Herramientas disponibles:

### memory_summarize

Resume el contenido de un archivo de memoria en el directorio `.kogniterm/`. La implementación actual es un placeholder que trunca el contenido a la longitud máxima especificada.

**Parámetros:**
- `file_path` (string, opcional): Ruta del archivo de memoria (default: "llm_context.md")
- `max_length` (integer, opcional): Longitud máxima deseada para el resumen (en caracteres, default: 500)

**Ejemplo:**
```json
{
  "tool": "memory_summarize",
  "args": {
    "file_path": "llm_context.md",
    "max_length": 500
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: medium** - Modifica el archivo de memoria
- **Permisos requeridos:** memory
- **Requiere allowlisting:** false
- **Auto-aprobación:** true (siempre aprobada)

## Uso:

1. Usa esta herramienta para comprimir el contenido de la memoria
2. La implementación actual trunca el contenido a max_length caracteres
3. El archivo de memoria es sobrescrito con el contenido resumido
4. Nota: Esta es una implementación placeholder, no realiza summarización real con LLM

## Archivos de memoria:

- `llm_context.md`: Contexto general del proyecto
- Se pueden resumir otros archivos según necesidad
