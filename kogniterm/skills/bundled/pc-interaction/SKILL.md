---
name: pc-interaction
description: Use when the user needs to automate or perform graphical desktop (GUI) interactions on the PC, including mouse movement, clicking, keyboard typing, window management, screen resolution queries, taking screenshots, or locating icons/images on screen.
metadata:
  version: "1.2.0"
  author: "KogniTerm Core"
  category: "system"
  tags: ["pc", "automation", "gui", "control", "interaction", "vision"]
  dependencies: ["pyautogui", "pywinctl", "opencv-python", "pillow", "mss"]
  required_permissions: ["system", "filesystem"]
  security_level: "high"
  allowlist: false
  auto_approve: false
---

# Instructions for pc-interaction Skill

Esta skill permite interactuar con el entorno gráfico del PC mediante control del ratón, teclado, ventanas y procesamiento de imágenes básico (visión por computadora).

## Herramientas disponibles:

### pc_interaction

Herramienta para interactuar con el entorno gráfico.

**Parámetros:**
- `action` (string, requerido): La acción a realizar.
- `params` (object, opcional): Parámetros para la acción.

**Acciones disponibles:**
- `get_windows`: Listar ventanas abiertas de forma segura (con fallbacks para X11/Wayland).
- `activate_window`: Activar una ventana específica (foco) mediante su título (`window_title`).
- `get_mouse_pos`: Obtener coordenadas (x, y) actuales del puntero.
- `get_screen_size`: Obtener la resolución de la pantalla principal.
- `move_mouse`: Mover el ratón a una posición suavemente (`x`, `y`, `duration`).
- `click`: Click en una posición o posición actual (`x`, `y`, `button`).
- `double_click`: Doble click en la posición actual.
- `right_click`: Click derecho rápido.
- `drag_mouse`: Arrastrar desde la posición actual a una nueva (`x`, `y`, `duration`).
- `type_text`: Escribir texto simulando teclado (`text`, `interval`).
- `press_key`: Presionar una sola tecla (ej: 'enter', 'esc', 'space').
- `key_combo`: Atajos de teclado (ej: ['ctrl', 'c'], ['alt', 'tab']).
- `scroll`: Scroll vertical (`amount`).
- `screenshot`: Captura de pantalla completa con fallback multi-motor (MSS, PyAutoGUI, PIL, CLI).
- `find_image`: Busca una sub-imagen en la pantalla y devuelve sus coordenadas (`image_path`, `confidence`).
- `click_image`: Busca una imagen y hace click en ella si la encuentra (`image_path`, `confidence`).

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

## Requisitos y Fallbacks:

- Entorno gráfico activo (`DISPLAY` en X11 o `WAYLAND_DISPLAY` en Wayland / nativo en Windows/macOS).
- Dependencias instaladas: `pyautogui`, `pywinctl`, `opencv-python`, `pillow`, `mss`.
- Soporta fallbacks automáticos para captura de pantalla (MSS -> PyAutoGUI -> PIL -> grim/gnome-screenshot) para evitar fallos de subproceso o dependencias no instaladas.

## Consideraciones:

- **Failsafe**: Mover el ratón a la esquina superior izquierda de la pantalla abortará cualquier acción de PyAutoGUI.
- **Seguridad**: Nivel **High**. Requiere confirmación si no se ejecuta en modo autónomo.
- **Diagnóstico**: Cualquier error reporta el tipo explícito de excepción (`type(e).__name__`) y detalle completo sin omitir mensajes de error.