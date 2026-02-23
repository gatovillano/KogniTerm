---
name: codebase_search
version: 1.0.0
author: "KogniTerm Core"
description: "Búsqueda semántica de snippets de código en la base de datos vectorial del proyecto"
category: "code"
tags: ["search", "codebase", "semantic", "vector", "ai", "retrieval"]
dependencies: ["langchain", "numpy"]
required_permissions: ["filesystem"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite realizar búsquedas semánticas de snippets de código en la base de datos vectorial del proyecto. Utiliza embeddings para encontrar código relevante basado en el significado de la consulta.

## Herramientas disponibles:

### codebase_search

Realiza búsquedas semánticas de código en la base de datos vectorial.

**Parámetros:**
- `query` (string, requerido): La consulta de búsqueda para encontrar snippets de código relevantes
- `k` (integer, opcional, default: 5): Número de snippets de código a retornar
- `file_path_filter` (string, opcional): Filtro para buscar solo dentro de una ruta de archivo específica (puede ser substring o coincidencia exacta)
- `language_filter` (string, opcional): Filtro para buscar solo snippets de un lenguaje de programación específico (ej: 'python', 'javascript')

**Ejemplo:**
```json
{
  "tool": "codebase_search",
  "args": {
    "query": "función de autenticación de usuarios",
    "k": 3,
    "language_filter": "python"
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: standard** - No requiere aprobación
- **Permisos requeridos:** filesystem
- **Requiere allowlisting:** false
- **Auto-aprobado:** true

## Requisitos:

- Se necesita que el proyecto esté indexado previamente en la base de datos vectorial
- Se requieren los servicios de embeddings y vector DB manager inicializados
- Las dependencias necesarias: langchain, numpy

## Uso recomendado:

1. Usa esta herramienta para encontrar código relacionado con funcionalidades específicas
2. Ideal para entender la estructura del código existente
3. Útil para reutilizar código existente en lugar de escribir desde cero
4. Los resultados incluyen ruta del archivo, líneas de código, lenguaje y tipo de snippet
5. Puedes filtrar por lenguaje o ruta de archivo para búsquedas más específicas
6. El parámetro `k` controla cuántos resultados mostrar (default: 5)