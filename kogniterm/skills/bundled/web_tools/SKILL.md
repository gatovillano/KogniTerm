---
name: web_tools
version: 1.0.0
author: "KogniTerm Core"
description: "Colección unificada de herramientas para interacción web: búsqueda, obtención de contenido, scraping e integración con GitHub"
category: "web"
tags: ["web", "search", "tavily", "scraping", "github", "fetch"]
dependencies: ["beautifulsoup4", "tavily-python", "langchain-community", "PyGithub"]
required_permissions: ["network"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM - Web Tools

Esta skill unifica diversas herramientas para interactuar con la web, realizar búsquedas y acceder a repositorios externos.

## Herramientas disponibles:

### 1. tavily_search
Búsqueda web optimizada para agentes de IA usando la API de Tavily.
- **Parámetros:** `query` (string), `max_results` (int, default: 5), `search_depth` (string: 'basic' o 'advanced', default: 'basic')

### 2. web_fetch
Obtiene el contenido HTML crudo de una URL.
- **Parámetros:** `url` (string)

### 3. web_scraping
Extrae datos estructurados de contenido HTML usando selectores CSS.
- **Parámetros:** `html_content` (string), `selector` (string)

### 4. github
Herramienta unificada para interactuar con repositorios de GitHub (info, listar, leer, buscar).
- **Parámetros:** `action` (string), `repo_name` (string, opcional), `path` (string, opcional), `query` (string, opcional), `github_token` (string, opcional)

## Flujo de trabajo recomendado:

1. **Búsqueda**: Usa `tavily_search` para encontrar información o URLs relevantes.
2. **Obtención**: Usa `web_fetch` para obtener el HTML de una página específica.
3. **Extracción**: Usa `web_scraping` con selectores CSS para obtener datos específicos del HTML obtenido.
4. **Repositorios**: Usa `github` para explorar y leer código de repositorios directamente.

## Consideraciones de seguridad:
- Todas las herramientas requieren acceso a la red.
- `tavily_search` requiere `TAVILY_API_KEY`.
- `github` recomienda `GITHUB_TOKEN` para evitar límites de tasa (rate limits).
- Los resultados de scraping y fetch pueden ser extensos; procésalos con cuidado.
