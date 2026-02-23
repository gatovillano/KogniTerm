"""
Skill: pc_interaction
Herramienta genérica para interactuar con el PC
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field
import json

logger = logging.getLogger(__name__)

class PCInteractionInput(BaseModel):
    """Schema de entrada para la herramienta pc_interaction"""
    action: str = Field(description="La acción a realizar: 'get_windows', 'activate_window', 'click', 'double_click', 'right_click', 'move_mouse', 'drag_mouse', 'type_text', 'press_key', 'key_combo', 'scroll', 'screenshot'.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parámetros para la acción (x, y, text, key, combo, window_title, amount, etc.).")

def _check_gui() -> bool:
    """Verificar si hay un entorno gráfico disponible"""
    if not os.environ.get("DISPLAY") and os.name != 'nt':
        logger.debug("No se detectó entorno gráfico (DISPLAY no definido).")
        return False
        
    try:
        import pyautogui
        import pywinctl
        # Test simple
        pyautogui.size()
        return True
    except Exception as e:
        logger.debug(f"Error al inicializar librerías GUI: {e}")
        return False

def pc_interaction_skill(action: str, params: Dict[str, Any] = None) -> str:
    """
    Función principal que implementa la funcionalidad de pc_interaction
    
    Args:
        action: La acción a realizar
        params: Parámetros para la acción
    
    Returns:
        str: Resultado de la operación
    """
    if not _check_gui():
        return "Error: No hay un entorno gráfico disponible o faltan dependencias (pyautogui, pywinctl)."

    if params is None:
        params = {}

    try:
        import pyautogui
        import pywinctl

        if action == "get_windows":
            windows = pywinctl.getAllWindows()
            result = "Ventanas abiertas:\n"
            for w in windows:
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

        elif action == "move_mouse":
            x, y = params.get("x"), params.get("y")
            if x is None or y is None: 
                return "Error: Se requieren 'x' e 'y'."
            pyautogui.moveTo(x, y, duration=0.25)
            return f"Ratón movido a ({x}, {y})."

        elif action == "click":
            x, y = params.get("x"), params.get("y")
            if x is not None and y is not None:
                pyautogui.click(x, y)
            else:
                pyautogui.click()
            return "Click realizado."

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
            pyautogui.dragTo(x, y, duration=0.5)
            return f"Elemento arrastrado a ({x}, {y})."

        elif action == "type_text":
            text = params.get("text")
            if not text: 
                return "Error: Se requiere 'text'."
            pyautogui.write(text, interval=0.01)
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
            filename = params.get("filename", f"screenshot_{int(time.time())}.png")
            path = os.path.join(os.getcwd(), filename)
            pyautogui.screenshot(path)
            return f"Captura de pantalla guardada en: {path}"

        else:
            return f"Acción '{action}' no reconocida."

    except Exception as e:
        return f"Error al ejecutar la acción de PC: {str(e)}"

# Schema para el LLM
tool_schema = {
    "name": "pc_interaction",
    "description": "Herramienta genérica para interactuar con el PC: controlar ratón, teclado, ventanas y capturas de pantalla.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "La acción a realizar: 'get_windows', 'activate_window', 'click', 'double_click', 'right_click', 'move_mouse', 'drag_mouse', 'type_text', 'press_key', 'key_combo', 'scroll', 'screenshot'.",
                "enum": ["get_windows", "activate_window", "click", "double_click", "right_click", "move_mouse", "drag_mouse", "type_text", "press_key", "key_combo", "scroll", "screenshot"]
            },
            "params": {
                "type": "object",
                "description": "Parámetros para la acción (x, y, text, key, combo, window_title, amount, etc.).",
                "properties": {
                    "x": {"type": "number", "description": "Coordenada X"},
                    "y": {"type": "number", "description": "Coordenada Y"},
                    "text": {"type": "string", "description": "Texto a escribir"},
                    "key": {"type": "string", "description": "Tecla a presionar"},
                    "combo": {"type": "array", "description": "Lista de teclas para la combinación", "items": {"type": "string"}},
                    "window_title": {"type": "string", "description": "Título de la ventana a activar"},
                    "amount": {"type": "number", "description": "Cantidad de scroll (positivo hacia arriba, negativo hacia abajo)"},
                    "filename": {"type": "string", "description": "Nombre del archivo de captura"}
                }
            }
        },
        "required": ["action"]
    }
}