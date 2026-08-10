"""
Skill: pc_interaction
Herramienta avanzada para interactuar con el PC: control total de GUI, ventanas y visión básica.
"""

import os
import time
import logging
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

# Intentar importar dependencias
MSS_AVAILABLE = False
try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    pass

try:
    import pyautogui
    import pywinctl
    import cv2
    import numpy as np
    from PIL import Image
    GUI_AVAILABLE = True
except (ImportError, Exception, SystemExit):
    GUI_AVAILABLE = False

logger = logging.getLogger(__name__)

# Configuración de PyAutoGUI
if GUI_AVAILABLE:
    try:
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
    except (Exception, SystemExit):
        GUI_AVAILABLE = False


class PCInteractionInput(BaseModel):
    """Schema de entrada para la herramienta pc_interaction"""
    action: str = Field(description="La acción a realizar: 'get_windows', 'activate_window', 'click', 'double_click', 'right_click', 'move_mouse', 'drag_mouse', 'type_text', 'press_key', 'key_combo', 'scroll', 'screenshot', 'get_mouse_pos', 'get_screen_size', 'find_image', 'click_image'.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parámetros para la acción.")


def _check_gui() -> Tuple[bool, str]:
    """Verificar si hay un entorno gráfico disponible y dependencias"""
    if not GUI_AVAILABLE:
        return False, "Error: Faltan dependencias (pyautogui, pywinctl, opencv-python, pillow). Instálelas en su entorno."
    
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY") and os.name != 'nt':
        return False, "Error: No se detectó entorno gráfico (DISPLAY/WAYLAND_DISPLAY no definido). Esta herramienta requiere una sesión GUI activa."
        
    try:
        pyautogui.size()
        return True, ""
    except Exception as e:
        if MSS_AVAILABLE:
            try:
                with mss.mss() if hasattr(mss, 'mss') else mss.MSS() as sct:
                    if sct.monitors:
                        return True, ""
            except Exception:
                pass
        return False, f"Error al acceder al servidor gráfico: {type(e).__name__}: {e or repr(e)}"


def pc_interaction_skill(action: str, params: Dict[str, Any] = None) -> str:
    """
    Función principal que implementa la funcionalidad de pc_interaction
    """
    ok, err = _check_gui()
    if not ok:
        return err

    if params is None:
        params = {}

    try:
        if action == "get_windows":
            windows_info = []
            
            # Intento 1: pywinctl.getAllWindows() con manejo seguro elemento a elemento
            try:
                all_wins = pywinctl.getAllWindows()
                for w in all_wins:
                    try:
                        title = getattr(w, 'title', None)
                        if title and str(title).strip():
                            app_name = "Desconocido"
                            try:
                                app_name = w.getAppName() or "N/A"
                            except Exception:
                                pass
                            windows_info.append(f"- [{title.strip()}] (App: {app_name})")
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"pywinctl.getAllWindows falló: {e}")

            # Intento 2: pywinctl.getAllTitles()
            if not windows_info:
                try:
                    titles = pywinctl.getAllTitles()
                    for t in titles:
                        if t and str(t).strip():
                            windows_info.append(f"- [{t.strip()}]")
                except Exception as e:
                    logger.warning(f"pywinctl.getAllTitles falló: {e}")

            # Intento 3: fallback con ewmh en Linux X11
            if not windows_info and os.name != 'nt':
                try:
                    from pywinctl._pywinctl_linux import defaultEwmhRoot
                    ewmh_wins = defaultEwmhRoot.getClientListStacking()
                    for w in ewmh_wins:
                        try:
                            t = getattr(w, 'title', '')
                            if t and str(t).strip():
                                windows_info.append(f"- [{t.strip()}]")
                        except Exception:
                            pass
                except Exception:
                    pass

            if windows_info:
                return "Ventanas abiertas:\n" + "\n".join(windows_info)
            else:
                return "No se pudieron enumerar las ventanas activas (posible entorno Wayland sin soporte de inspección X11 o sin ventanas visibles)."

        elif action == "activate_window":
            title = params.get("window_title")
            if not title: 
                return "Error: Se requiere 'window_title'."
            try:
                win = pywinctl.getWindowsWithTitle(title)
                if win and len(win) > 0:
                    win[0].activate()
                    return f"Ventana '{title}' activada."
                return f"No se encontró ninguna ventana con el título '{title}'."
            except Exception as e:
                return f"Error al activar ventana '{title}': {type(e).__name__}: {e or repr(e)}"

        elif action == "get_mouse_pos":
            try:
                pos = pyautogui.position()
                return f"Posición actual del ratón: x={pos.x}, y={pos.y}"
            except Exception as e:
                return f"Error al obtener posición del ratón: {type(e).__name__}: {e or repr(e)}"

        elif action == "get_screen_size":
            errors = []
            try:
                size = pyautogui.size()
                return f"Resolución de pantalla: {size.width}x{size.height}"
            except Exception as e:
                errors.append(f"PyAutoGUI error: {e}")

            if MSS_AVAILABLE:
                try:
                    mss_factory = getattr(mss, 'MSS', None) or getattr(mss, 'mss', None)
                    with mss_factory() as sct:
                        if sct.monitors:
                            mon = sct.monitors[0]
                            return f"Resolución de pantalla: {mon['width']}x{mon['height']}"
                except Exception as e:
                    errors.append(f"MSS error: {e}")

            return f"Error al obtener resolución de pantalla: {'; '.join(errors)}"

        elif action == "move_mouse":
            x, y = params.get("x"), params.get("y")
            if x is None or y is None: 
                return "Error: Se requieren 'x' e 'y'."
            pyautogui.moveTo(x, y, duration=params.get("duration", 0.25))
            return f"Ratón movido a ({x}, {y})."

        elif action == "click":
            x, y = params.get("x"), params.get("y")
            button = params.get("button", "left")
            if x is not None and y is not None:
                pyautogui.click(x, y, button=button)
                return f"Click {button} en ({x}, {y})."
            else:
                pyautogui.click(button=button)
                return f"Click {button} en posición actual."

        elif action == "double_click":
            pyautogui.doubleClick()
            return "Doble click realizado."

        elif action == "right_click":
            pyautogui.rightClick()
            return "Click derecho realizado."

        elif action == "drag_mouse":
            x, y = params.get("x"), params.get("y")
            if x is None or y is None: 
                return "Error: Se requieren 'x' e 'y'."
            pyautogui.dragTo(x, y, duration=params.get("duration", 0.5))
            return f"Elemento arrastrado a ({x}, {y})."

        elif action == "type_text":
            text = params.get("text")
            if not text: 
                return "Error: Se requiere 'text'."
            pyautogui.write(text, interval=params.get("interval", 0.01))
            return f"Texto escrito: '{text}'."

        elif action == "press_key":
            key = params.get("key")
            if not key: 
                return "Error: Se requiere 'key'."
            pyautogui.press(key)
            return f"Tecla '{key}' presionada."

        elif action == "key_combo":
            combo = params.get("combo", [])
            if not combo: 
                return "Error: Se requiere 'combo' (lista de teclas)."
            pyautogui.hotkey(*combo)
            return f"Combinación de teclas ejecutada: {'+'.join(combo)}."

        elif action == "scroll":
            amount = params.get("amount", 0)
            pyautogui.scroll(amount)
            return f"Scroll realizado de {amount} unidades."

        elif action == "screenshot":
            filename = params.get("filename")
            if not filename:
                filename = f"screenshot_{int(time.time())}.png"
            
            path = os.path.abspath(filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            errors = []

            # Intento 1: MSS (Robusto y libre de dependencias de subprocesos CLI)
            if MSS_AVAILABLE:
                try:
                    mss_factory = getattr(mss, 'MSS', None) or getattr(mss, 'mss', None)
                    with mss_factory() as sct:
                        sct.shot(output=path)
                    if os.path.exists(path) and os.path.getsize(path) > 0:
                        return f"Captura de pantalla guardada en: {path}"
                except Exception as e:
                    errors.append(f"MSS error: {type(e).__name__}: {e or repr(e)}")

            # Intento 2: PyAutoGUI
            try:
                pyautogui.screenshot(path)
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    return f"Captura de pantalla guardada en: {path}"
            except Exception as e:
                errors.append(f"PyAutoGUI error: {type(e).__name__}: {e or repr(e)}")

            # Intento 3: PIL ImageGrab
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                if img:
                    img.save(path)
                    if os.path.exists(path) and os.path.getsize(path) > 0:
                        return f"Captura de pantalla guardada en: {path}"
            except Exception as e:
                errors.append(f"PIL ImageGrab error: {type(e).__name__}: {e or repr(e)}")

            # Intento 4: Subprocesos CLI de fallback (grim, gnome-screenshot)
            for cmd in [
                ['grim', path],
                ['gnome-screenshot', '-f', path]
            ]:
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if res.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0:
                        return f"Captura de pantalla guardada en: {path}"
                    else:
                        err_msg = res.stderr.strip() or res.stdout.strip() or f"código de salida {res.returncode}"
                        errors.append(f"{cmd[0]} error: {err_msg}")
                except Exception as e:
                    errors.append(f"{cmd[0]} exec error: {e}")

            return f"Error al capturar pantalla. Fallaron todos los métodos:\n" + "\n".join(f"- {err}" for err in errors)

        elif action == "find_image":
            image_path = params.get("image_path")
            confidence = params.get("confidence", 0.8)
            if not image_path:
                return "Error: Se requiere 'image_path' para buscar."
            
            try:
                location = pyautogui.locateOnScreen(image_path, confidence=confidence)
                if location:
                    center = pyautogui.center(location)
                    return f"Imagen encontrada en: {location} (Centro: {center.x}, {center.y})"
                return "Imagen no encontrada en pantalla."
            except Exception as e:
                return f"Error al buscar imagen: {type(e).__name__}: {e or repr(e)}"

        elif action == "click_image":
            image_path = params.get("image_path")
            confidence = params.get("confidence", 0.8)
            if not image_path:
                return "Error: Se requiere 'image_path'."
            
            try:
                location = pyautogui.locateOnScreen(image_path, confidence=confidence)
                if location:
                    center = pyautogui.center(location)
                    pyautogui.click(center.x, center.y)
                    return f"Click realizado en el centro de la imagen ({center.x}, {center.y})."
                return "Imagen no encontrada, no se pudo hacer click."
            except Exception as e:
                return f"Error al procesar click en imagen: {type(e).__name__}: {e or repr(e)}"

        else:
            return f"Acción '{action}' no reconocida."

    except Exception as e:
        logger.error(f"Error en pc_interaction ({action}): {e}", exc_info=True)
        return f"Error al ejecutar la acción de PC '{action}': {type(e).__name__}: {str(e) or repr(e)}"


# Schema para el LLM
tool_schema = {
    "name": "pc_interaction",
    "description": "Herramienta avanzada para interactuar con el PC: controlar ratón, teclado, ventanas y capturas de pantalla.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "La acción a realizar.",
                "enum": [
                    "get_windows", "activate_window", "click", "double_click", 
                    "right_click", "move_mouse", "drag_mouse", "type_text", 
                    "press_key", "key_combo", "scroll", "screenshot",
                    "get_mouse_pos", "get_screen_size", "find_image", "click_image"
                ]
            },
            "params": {
                "type": "object",
                "description": "Parámetros específicos para cada acción.",
                "properties": {
                    "x": {"type": "number", "description": "Coordenada X"},
                    "y": {"type": "number", "description": "Coordenada Y"},
                    "text": {"type": "string", "description": "Texto a escribir"},
                    "key": {"type": "string", "description": "Tecla a presionar (ej: 'enter', 'esc', 'f1')"},
                    "combo": {"type": "array", "description": "Lista de teclas (ej: ['ctrl', 'c'])", "items": {"type": "string"}},
                    "window_title": {"type": "string", "description": "Título de la ventana"},
                    "amount": {"type": "number", "description": "Cantidad de scroll"},
                    "filename": {"type": "string", "description": "Nombre de archivo para captura"},
                    "image_path": {"type": "string", "description": "Ruta a una imagen para buscar en pantalla"},
                    "confidence": {"type": "number", "description": "Nivel de confianza para búsqueda de imagen (0.1 a 1.0)"},
                    "duration": {"type": "number", "description": "Duración del movimiento en segundos"},
                    "button": {"type": "string", "description": "Botón del ratón ('left', 'right', 'middle')", "default": "left"}
                }
            }
        },
        "required": ["action"]
    }
}