---
name: brave_search
version: 1.0.0
author: "KogniTerm Core"
description: "Búsqueda web utilizando Brave Search API para obtener información actualizada de internet"
category: "web"
tags: ["search", "web", "brave", "internet", "research"]
dependencies: ["langchain-community", "brave-search"]
required_permissions: ["network"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite realizar búsquedas en la web utilizando la API de Brave Search.

## Herramientas disponibles:

### brave_search

Realiza una búsqueda en la web usando Brave Search API.

**Parámetros:**
- `query` (string, requerido): La consulta de búsqueda

**Ejemplo:**
```json
{
  "tool": "brave_search",
  "args": {
    "query": "últimas noticias sobre inteligencia artificial"
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: standard** - No requiere aprobación
- **Permisos requeridos:** network
- **Requiere allowlisting:** false
- **Auto-aprobado:** true

## Requisitos:

- Se necesita la variable de entorno `BRAVE_SEARCH_API_KEY`
- Obtén una clave API en: https://brave.com/search/api/

## Uso recomendado:

1. Usa esta herramienta para buscar información actualizada en la web
2. Ideal para consultas generales, noticias y temas de actualidad
3. Los resultados incluyen título, descripción y URL de cada resultado
4. El contenido se limita a 30000 caracteres para evitar sobrecarga
