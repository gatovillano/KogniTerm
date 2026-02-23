---
name: search_memory
version: 1.0.0
author: "KogniTerm Core"
description: "Permite al agente guardar y consultar resultados de búsqueda para evitar búsquedas redundantes."
category: "memory"
tags: ["memory", "search", "cache", "results"]
dependencies: []
required_permissions: ["memory"]
security_level: "low"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite guardar y consultar resultados de búsqueda en memoria para evitar búsquedas redundantes.

## Herramientas disponibles:

### search_memory

Guarda y consulta resultados de búsqueda almacenados en memoria.

**Para guardar un resultado de búsqueda:**
- `query` (string, requerido): La consulta de búsqueda original
- `result` (string, requerido): El resultado relevante de la búsqueda para guardar

**Para buscar resultados:**
- `query` (string, requerido): La consulta para la que se buscan resultados relevantes en la memoria

**Ejemplo - Guardar resultado:**
```json
{
  "tool": "search_memory",
  "args": {
    "query": "cómo instalar python",
    "result": "Puedes instalar Python desde python.org o usando apt-get install python3"
  }
}
```

**Ejemplo - Buscar resultado:**
```json
{
  "tool": "search_memory",
  "args": {
    "query": "python"
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: low** - Operación de solo lectura/escritura en memoria
- **Permisos requeridos:** memory
- **Requiere allowlisting:** false
- **Auto-aprobación:** true (siempre aprobada)

## Uso:

1. Usa esta herramienta para guardar resultados de búsquedas frecuentes
2. La memoria mantiene un máximo de 10 resultados (el más antiguo se elimina)
3. La búsqueda es case-insensitive y busca coincidencias parciales
4. Útil para evitar hacer la misma búsqueda múltiples veces

## Limitaciones:

- Esta skill usa una búsqueda simple por coincidencia de texto
- Para búsquedas más sofisticadas se podrían usar embeddings
