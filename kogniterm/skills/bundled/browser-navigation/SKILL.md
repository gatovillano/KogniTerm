---
name: browser-navigation
description: Use when the user wants the agent to browse the web using an interactive Playwright browser, either visible in real-time on the desktop screen (headless=False) or in the background (headless=True), to navigate websites, click elements, fill forms, search, extract content, or take page screenshots.
metadata:
  version: "1.0.0"
  author: "KogniTerm Core"
  category: "web"
  tags: ["browser", "playwright", "web", "automation", "navigation", "scraping"]
  dependencies: ["playwright"]
  required_permissions: ["system", "network"]
  security_level: "medium"
  allowlist: false
  auto_approve: false
---

# Instructions for browser-navigation Skill

Esta skill le permite al agente navegar por la web utilizando **Playwright**.
Admite dos modos de ejecución:
1. **Modo Gráfico en Tiempo Real (`headless: false`, por defecto):** Abre la ventana del navegador (Chromium) directamente en la pantalla de la PC para que el usuario pueda ver en tiempo real la navegación del agente.
2. **Modo Segundo Plano (`headless: true`):** Ejecuta la navegación de forma transparente sin abrir ventanas.

## Herramientas disponibles:

### browser_navigation

Herramienta principal para interactuar con sitios web.

**Parámetros:**
- `action` (string, requerido): La acción web a realizar.
- `params` (object, opcional): Parámetros para la acción.

**Acciones disponibles:**
- `navigate`: Visitar una URL (`url`, `headless`: default `false`).
- `click`: Hacer click en un botón, enlace o campo (`selector` CSS/XPath o `text`).
- `type_text`: Escribir texto en un campo de entrada (`selector`, `text`, `press_enter`: opcional).
- `press_key`: Presionar una tecla del teclado (ej: 'Enter', 'Tab', 'Escape').
- `get_content`: Extraer el texto o HTML de la página o de un elemento específico (`selector`, `mode`: 'text'|'html').
- `take_screenshot`: Tomar una captura de pantalla del sitio web (`filename`, `full_page`).
- `scroll`: Desplazarse hacia abajo o arriba (`direction`: 'down'|'up', `amount`: píxeles).
- `close`: Cerrar la ventana del navegador.

**Ejemplo de uso:**
```json
{
  "tool": "browser_navigation",
  "args": {
    "action": "navigate",
    "params": {
      "url": "https://www.google.com",
      "headless": false
    }
  }
}
```

## Requisitos:

- Paquete Python `playwright` instalado (`pip install playwright`).
- Binarios de navegadores Playwright instalados (`playwright install chromium`).
- Entorno gráfico activo (`DISPLAY` o `WAYLAND_DISPLAY`) para el modo `headless: false`.

## Consideraciones:

- **Persistencia:** La sesión del navegador se mantiene abierta entre llamadas consecutivas (navegar -> hacer click -> escribir -> extraer), lo que permite flujos complejos multi-paso.
- **Visibilidad:** Por defecto `headless` es `false`, lo que permite supervisión visual directa por parte del usuario.
