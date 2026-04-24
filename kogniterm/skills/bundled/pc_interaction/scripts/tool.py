"""
Skill: pc_interaction
Herramienta avanzada para interactuar con el PC: control total de GUI, ventanas y visión básica.
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

# Intentar importar dependencias
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
    
    if not os.environ.get("DISPLAY") and os.name != 'nt':
        return False, "Error: No se detectó entorno gráfico (DISPLAY no definido). Esta herramienta requiere una sesión X11/GUI activa."
        
    try:
        pyautogui.size()
        return True, ""
    except Exception as e:
        return False, f"Error al acceder al servidor gráfico: {e}"

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
            windows = pywinctl.getAllWindows()
            result = "Ventanas abiertas:\n"
            for w in windows:
                if w.title:
                    result += f"- [{w.title}] (PID: {w.getAppName()})\n"
            return result

        elif action == "activate_window":
            title = params.get("window_title")
            if not title: 
                return "Error: Se requiere 'window_title'."
            win = pywinctl.getWindowsWithTitle(title)
            if win:
                win[0].activate()
                return f"Ventana '{title}' activada."
            return f"No se encontró ninguna ventana con el título '{title}'."

        elif action == "get_mouse_pos":
            pos = pyautogui.position()
            return f"Posición actual del ratón: x={pos.x}, y={pos.y}"

        elif action == "get_screen_size":
            size = pyautogui.size()
            return f"Resolución de pantalla: {size.width}x{size.height}"

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
            
            # Asegurar que esté en un lugar accesible, preferiblemente workspace
            path = os.path.abspath(filename)
            pyautogui.screenshot(path)
            return f"Captura de pantalla guardada en: {path}"

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
                return f"Error al buscar imagen: {e}"

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
                return f"Error al procesar click en imagen: {e}"

        else:
            return f"Acción '{action}' no reconocida."

    except Exception as e:
        logger.error(f"Error en pc_interaction: {e}", exc_info=True)
        return f"Error al ejecutar la acción de PC: {str(e)}"

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