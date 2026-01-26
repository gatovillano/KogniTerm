
import os
import time
import logging
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class PCInteractionInput(BaseModel):
    action: str = Field(description="La acción a realizar: 'get_windows', 'activate_window', 'click', 'double_click', 'right_click', 'move_mouse', 'drag_mouse', 'type_text', 'press_key', 'key_combo', 'scroll', 'screenshot'.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parámetros para la acción (x, y, text, key, combo, window_title, amount, etc.).")

class PCInteractionTool(BaseTool):
    name: str = "pc_interaction"
    description: str = "Herramienta genérica para interactuar con el PC: controlar ratón, teclado, ventanas y capturas de pantalla."
    args_schema: Type[BaseModel] = PCInteractionInput

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self._gui_checked = False
        self._gui_available = False

    def _check_gui(self):
        if self._gui_checked:
            return self._gui_available
        
        self._gui_checked = True
        if not os.environ.get("DISPLAY") and os.name != 'nt':
            logger.debug("No se detectó entorno gráfico (DISPLAY no definido).")
            self._gui_available = False
            return False
            
        try:
            import pyautogui
            import pywinctl
            # Test simple
            pyautogui.size()
            self._gui_available = True
        except Exception as e:
            logger.debug(f"Error al inicializar librerías GUI: {e}")
            self._gui_available = False
        
        return self._gui_available

    def _run(self, action: str, params: Dict[str, Any] = None) -> str:
        if not self._check_gui():
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
                if not title: return "Error: Se requiere 'window_title'."
                win = pywinctl.getWindowsWithTitle(title)
                if win:
                    win[0].activate()
                    return f"Ventana '{title}' activada."
                return f"No se encontró ninguna ventana con el título '{title}'."

            elif action == "move_mouse":
                x, y = params.get("x"), params.get("y")
                if x is None or y is None: return "Error: Se requieren 'x' e 'y'."
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
                if x is None or y is None: return "Error: Se requieren 'x' e 'y'."
                pyautogui.dragTo(x, y, duration=0.5)
                return f"Elemento arrastrado a ({x}, {y})."

            elif action == "type_text":
                text = params.get("text")
                if not text: return "Error: Se requiere 'text'."
                pyautogui.write(text, interval=0.01)
                return f"Texto escrito: '{text}'."

            elif action == "press_key":
                key = params.get("key")
                if not key: return "Error: Se requiere 'key'."
                pyautogui.press(key)
                return f"Tecla '{key}' presionada."

            elif action == "key_combo":
                combo = params.get("combo", [])
                if not combo: return "Error: Se requiere 'combo' (lista de teclas)."
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

    async def _arun(self, action: str, params: Dict[str, Any] = None) -> str:
        # Implementación síncrona básica por ahora
        return self._run(action, params)
