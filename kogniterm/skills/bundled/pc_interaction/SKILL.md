---
name: pc_interaction
version: 1.0.0
author: "KogniTerm Core"
description: "Herramienta genérica para interactuar con el PC: controlar ratón, teclado, ventanas y capturas de pantalla"
category: "system"
tags: ["pc", "automation", "gui", "control", "interaction"]
dependencies: ["pyautogui", "pywinctl"]
required_permissions: ["system", "filesystem"]
security_level: "high"
allowlist: false
auto_approve: false
sandbox_required: true
---

# Instrucciones para el LLM

Esta skill permite interactuar con el entorno gráfico del PC mediante control del ratón, teclado, ventanas y capturas de pantalla.

## Herramientas disponibles:

### pc_interaction

Herramienta genérica para interactuar con el PC.

**Parámetros:**
- `action` (string, requerido): La acción a realizar
- `params` (object, opcional): Parámetros para la acción

**Acciones disponibles:**
- `get_windows`: Listar ventanas abiertas
- `activate_window`: Activar una ventana específica
- `move_mouse`: Mover el ratón a una posición
- `click`: Realizar un click del ratón
- `double_click`: Realizar un doble click
- `right_click`: Realizar un click derecho
- `drag_mouse`: Arrastrar el ratón a una posición
- `type_text`: Escribir texto
- `press_key`: Presionar una tecla
- `key_combo`: Presionar combinación de teclas
- `scroll`: Realizar scroll
- `screenshot`: Tomar captura de pantalla

**Ejemplo:**
```json
{
  "tool": "pc_interaction",
  "args": {
    "action": "move_mouse",
    "params": {
      "x": 100,
      "y": 200
    }
  }
}
```

## Parámetros por acción:

### get_windows
- No requiere parámetros adicionales

### activate_window
- `window_title` (string): Título de la ventana a activar

### move_mouse, drag_mouse
- `x` (number): Coordenada X
- `y` (number): Coordenada Y

### click, double_click, right_click
- `x` (number, opcional): Coordenada X
- `y` (number, opcional): Coordenada Y

### type_text
- `text` (string): Texto a escribir

### press_key
- `key` (string): Tecla a presionar

### key_combo
- `combo` (array): Lista de teclas para la combinación

### scroll
- `amount` (number): Cantidad de scroll (positivo hacia arriba, negativo hacia abajo)

### screenshot
- `filename` (string, opcional): Nombre del archivo de captura

## Consideraciones de seguridad:

- **Nivel de seguridad: high** - Requiere aprobación manual
- **Permisos requeridos:** system, filesystem
- **Requiere allowlisting:** false
- **Auto-aprobado:** false
- **Requiere sandbox:** true

## Requisitos:

- Se necesita un entorno gráfico disponible (DISPLAY en Linux)
- Se requieren las dependencias: pyautogui, pywinctl
- En Windows, pywinctl funciona de forma nativa
- En Linux, se requiere un entorno X11 activo

## Uso recomendado:

1. Usa `get_windows` para identificar las ventanas disponibles
2. Usa `activate_window` para enfocar la ventana correcta
3. Usa `move_mouse` y `click` para interactuar con elementos de la interfaz
4. Usa `type_text` para introducir texto en campos de texto
5. Usa `key_combo` para atajos de teclado (Ctrl+C, Ctrl+V, etc.)
6. Usa `screenshot` para capturar el estado actual de la pantalla

## Limitaciones:

- Requiere un entorno gráfico activo
- Las acciones son inmediatas y no se pueden deshacer
- El control del ratón puede interferir con el usuario
- Se recomienda usar con precaución en sistemas de producción