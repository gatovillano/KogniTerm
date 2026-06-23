---
name: pc-interaction
version: 1.1.0
author: "KogniTerm Core"
description: "Herramienta avanzada para interactuar con el PC: controlar ratón, teclado, ventanas y visión por computadora"
category: "system"
tags: ["pc", "automation", "gui", "control", "interaction", "vision"]
dependencies: ["pyautogui", "pywinctl", "opencv-python", "pillow"]
required_permissions: ["system", "filesystem"]
security_level: "high"
allowlist: false
auto_approve: false
sandbox_required: true
---

# Instrucciones para el LLM

Esta skill permite interactuar con el entorno gráfico del PC mediante control del ratón, teclado, ventanas y procesamiento de imágenes básico (vision).

## Herramientas disponibles:

### pc_interaction

Herramienta para interactuar con el entorno gráfico.

**Parámetros:**
- `action` (string, requerido): La acción a realizar
- `params` (object, opcional): Parámetros para la acción

**Acciones disponibles:**
- `get_windows`: Listar ventanas abiertas.
- `activate_window`: Activar una ventana específica (foco).
- `get_mouse_pos`: Obtener coordenadas (x, y) actuales del puntero.
- `get_screen_size`: Obtener la resolución de pantalla.
- `move_mouse`: Mover el ratón a una posición suavemente.
- `click`: Click en una posición o posición actual. Soporta `button` (left, right, middle).
- `double_click`: Doble click.
- `right_click`: Click derecho rápido.
- `drag_mouse`: Arrastrar desde posición actual a una nueva.
- `type_text`: Escribir texto (simula teclado).
- `press_key`: Presionar una sola tecla (ej: 'enter', 'esc').
- `key_combo`: Atajos de teclado (ej: ['ctrl', 'c']).
- `scroll`: Scroll vertical.
- `screenshot`: Captura de pantalla completa.
- `find_image`: Busca una imagen pequeña en la pantalla y devuelve su ubicación.
- `click_image`: Busca una imagen y hace click en ella si la encuentra.

**Ejemplo de Visión:**
```json
{
  "tool": "pc_interaction",
  "args": {
    "action": "click_image",
    "params": {
      "image_path": "/path/to/button_icon.png",
      "confidence": 0.9
    }
  }
}
```

## Requisitos:

- Entorno gráfico activo (X11 en Linux, nativo en Windows/macOS).
- Dependencias instaladas: `pyautogui`, `pywinctl`, `opencv-python`, `pillow`.

## Consideraciones:

- **Failsafe**: Mover el ratón a la esquina superior izquierda de la pantalla abortará cualquier acción de PyAutoGUI.
- **Seguridad**: Nivel **High**. Requiere confirmación del usuario para cada acción.
- **Velocidad**: Las acciones tienen retrasos mínimos intencionales para asegurar que la UI responda.