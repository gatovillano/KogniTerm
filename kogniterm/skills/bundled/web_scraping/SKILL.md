---
name: web_scraping
version: 1.0.0
author: "KogniTerm Core"
description: "Extrae datos estructurados de contenido HTML usando selectores CSS"
category: "web"
tags: ["web", "scraping", "css", "selector", "html", "extraction"]
dependencies: ["beautifulsoup4"]
required_permissions: ["network"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite extraer datos estructurados de páginas HTML usando selectores CSS.

## Herramientas disponibles:

### web_scraping

Extrae datos estructurados de contenido HTML usando selectores CSS.

**Parámetros:**
- `html_content` (string, requerido): El contenido HTML de la página
- `selector` (string, requerido): El selector CSS para extraer los datos

**Ejemplo:**
```json
{
  "tool": "web_scraping",
  "args": {
    "html_content": "<html><div class='item'>Contenido</div></html>",
    "selector": "div.item"
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: standard** - No requiere aprobación
- **Permisos requeridos:** network
- **Requiere allowlisting:** false
- **Auto-aprobado:** true

## Selectores CSS comunes:

- `div` - Todas las etiquetas div
- `.classname` - Elementos con clase
- `#idname` - Elementos con ID
- `tag[attribute="value"]` - Elementos con atributo específico
- `parent > child` - Elementos hijo directos
- `ancestor descendant` - Elementos descendientes

## Uso recomendado:

1. Usa web_fetch primero para obtener el HTML de la página
2. Luego usa web_scraping con el selector CSS apropiado
3. Los resultados se formatean como HTML pretty-printed
4. Ideal para extraer tablas, listas, productos, artículos, etc.
