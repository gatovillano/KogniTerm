---
name: tavily_search
version: 1.0.0
author: "KogniTerm Core"
description: "Búsqueda web optimizada para agentes de IA usando Tavily, ideal para información técnica actualizada"
category: "web"
tags: ["search", "web", "tavily", "ai", "research", "technical"]
dependencies: ["tavily-python"]
required_permissions: ["network"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite realizar búsquedas web optimizadas para agentes de IA usando Tavily.

## Herramientas disponibles:

### tavily_search

Realiza una búsqueda web usando Tavily, optimizada para agentes de IA.

**Parámetros:**
- `query` (string, requerido): La consulta de búsqueda. Sé específico y técnico
- `max_results` (integer, opcional): Número máximo de resultados (1-10, default: 5)
- `search_depth` (string, opcional): Profundidad de búsqueda: 'basic' o 'advanced' (default: 'basic')

**Ejemplo:**
```json
{
  "tool": "tavily_search",
  "args": {
    "query": "CrewAI multi-agent architecture best practices",
    "max_results": 5,
    "search_depth": "advanced"
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: standard** - No requiere aprobación
- **Permisos requeridos:** network
- **Requiere allowlisting:** false
- **Auto-aprobado:** true

## Requisitos:

- Se necesita la variable de entorno `TAVILY_API_KEY`
- Obtén una clave gratuita en: https://tavily.com

## Características:

- Devuelve resultados estructurados con título, URL, snippet y score de relevancia
- Incluye respuesta resumida (answer) cuando está disponible
- Ideal para investigación técnica, documentación y artículos especializados
- Profundidad 'advanced' realiza búsquedas más exhaustivas

## Uso recomendado:

1. Usa esta herramienta para investigación web profunda sobre temas técnicos
2. Ideal para encontrar documentación, artículos y discusiones actualizadas
3. Los resultados incluyen score de relevancia para filtrar los más útiles
4. La respuesta resumida (answer) proporciona contexto inmediato
