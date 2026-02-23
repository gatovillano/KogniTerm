---
name: web_fetch
version: 1.0.0
author: "KogniTerm Core"
description: "Obtiene el contenido HTML de una URL especificada"
category: "web"
tags: ["web", "fetch", "http", "html", "scraping"]
dependencies: ["langchain-community"]
required_permissions: ["network"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite obtener el contenido HTML de páginas web.

## Herramientas disponibles:

### web_fetch

Obtiene el contenido HTML de una URL especificada.

**Parámetros:**
- `url` (string, requerido): La URL de la página web a obtener

**Ejemplo:**
```json
{
  "tool": "web_fetch",
  "args": {
    "url": "https://example.com"
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: standard** - No requiere aprobación
- **Permisos requeridos:** network
- **Requiere allowlisting:** false
- **Auto-aprobado:** true

## Uso recomendado:

1. Usa esta herramienta para obtener el contenido de páginas web
2. Ideal para leer artículos, documentación o cualquier contenido web
3. El contenido se limita a 20000 caracteres para evitar sobrecarga
4. Combina con web_scraping para extraer datos específicos
