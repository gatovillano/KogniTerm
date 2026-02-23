---
name: memory_init
version: 1.0.0
author: "KogniTerm Core"
description: "Inicializa la memoria contextual del proyecto creando un archivo 'llm_context.md' si no existe."
category: "memory"
tags: ["memory", "context", "init", "initialize"]
dependencies: []
required_permissions: ["memory"]
security_level: "low"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite inicializar la memoria contextual del proyecto.

## Herramientas disponibles:

### memory_init

Inicializa un archivo de memoria en el directorio `.kogniterm/`.

**Parámetros:**
- `file_path` (string, opcional): Ruta del archivo de memoria (default: "llm_context.md")

**Ejemplo:**
```json
{
  "tool": "memory_init",
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

1. Usa esta herramienta para crear un archivo de memoria vacío
2. El archivo se crea en `.kogniterm/llm_context.md` por defecto
3. Si el archivo ya existe, retornará un mensaje indicando que no se requiere inicialización
4. Útil para comenzar a guardar información del proyecto

## Archivos de memoria:

- `llm_context.md`: Contexto general del proyecto
- Se pueden crear otros archivos según necesidad
