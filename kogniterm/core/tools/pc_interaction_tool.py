
import platform
import os
import subprocess
from typing import Any, Type, Optional
try:
    import pyautogui
    import pywinctl as gw
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

class PCInteractionTool(BaseTool):
    name: str = "pc_interaction"
    description: str = """Herramienta para interactuar con el entorno del PC a través del navegador, permitiendo abrir páginas, tomar capturas de pantalla, mover el mouse, hacer clic y ingresar texto.
    
    Args:
        action: La acción a realizar: 'open_url', 'screenshot', 'click', 'type_text', 'move_mouse'.
        selector: 
        text: 
        url: 
        x: 
        y: 
    """

    class PCInteractionInput(BaseModel):
        action: str = Field(description="La acción a realizar: 'open_url', 'screenshot', 'click', 'type_text', 'move_mouse'.")
        x: Optional[float] = Field(None, description="Coordenada X para acciones de ratón.")
        y: Optional[float] = Field(None, description="Coordenada Y para acciones de ratón.")
        text: Optional[str] = Field(None, description="Texto a escribir.")
        url: Optional[str] = Field(None, description="URL a abrir.")
        selector: Optional[str] = Field(None, description="Selector CSS para interacciones web.") # Aunque la descripción de la herramienta lo menciona, en la implementación actual se enfoca en el escritorio. Se podría expandir.

    args_schema: Type[BaseModel] = PCInteractionInput

    def get_action_description(self, **kwargs) -> str:
        action = kwargs.get("action")
        if action == "open_url":
            return f"Abriendo URL: {kwargs.get('url')}"
        elif action == "type_text":
            return f"Escribiendo texto: {kwargs.get('text')}"
        elif action == "click":
            return f"Haciendo clic en ({kwargs.get('x')}, {kwargs.get('y')})"
        elif action == "move_mouse":
            return f"Moviendo ratón a ({kwargs.get('x')}, {kwargs.get('y')})"
        elif action == "screenshot":
            return "Tomando captura de pantalla"
        return f"Interactuando con PC: {action}"

    def _check_x11_dependencies(self) -> bool:
        """Verifica si las dependencias de X11 están instaladas."""
        try:
            # Intentar ejecutar un comando que requiere X11, como xclip
            subprocess.run(["xclip", "-version"], check=True, capture_output=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _is_wayland(self) -> bool:
        """Detecta si el entorno de escritorio es Wayland."""
        return "wayland" in os.environ.get("XDG_SESSION_TYPE", "").lower()

    def _run(self, action: str, x: Optional[float] = None, y: Optional[float] = None, text: Optional[str] = None, url: Optional[str] = None, selector: Optional[str] = None) -> Any:
        if not PYAUTOGUI_AVAILABLE:
            return {"error": "Las dependencias 'pyautogui' y 'pywinctl' no están instaladas. Esta herramienta no está disponible."}
        
        current_os = platform.system()
        if current_os not in ["Linux", "Darwin"]:
            return {"error": f"Esta herramienta no es compatible con {current_os} actualmente."}

        if current_os == "Linux":
            if self._is_wayland():
                return {"warning": "Detectado entorno Wayland. La interacción con el escritorio puede ser limitada o requerir configuración adicional (ej. ydotool). Funcionalidad parcial esperada."}

            if not self._check_x11_dependencies():
                return {"error": "Dependencias de X11 no encontradas. Por favor, instala 'python3-tk' y 'python3-dev' con 'sudo apt-get install python3-tk python3-dev' para una funcionalidad completa."}
        elif current_os == "Darwin":
            # En macOS, avisar sobre permisos de accesibilidad
            pass # pyautogui lanzará un error descriptivo si faltan permisos

        try:
            if action == "open_url":
                if url:
                    if current_os == "Linux":
                        subprocess.run(["xdg-open", url], check=True)
                    elif current_os == "Darwin":
                        subprocess.run(["open", url], check=True)
                    return {"status": f"URL {url} abierta exitosamente."}
                else:
                    return {"error": "Se requiere una URL para la acción 'open_url'."}

            elif action == "screenshot":
                screenshot = pyautogui.screenshot()
                # En macOS/Linux usar /tmp es seguro
                screenshot_path = "/tmp/kogniterm_screenshot.png"
                screenshot.save(screenshot_path)
                return {"status": f"Captura de pantalla tomada y guardada en {screenshot_path}."}

            elif action == "click":
                if x is not None and y is not None:
                    pyautogui.click(x=int(x), y=int(y))
                    return {"status": f"Clic en coordenadas ({int(x)}, {int(y)}) realizado."}
                else:
                    return {"error": "Se requieren coordenadas x e y para la acción 'click'."}

            elif action == "type_text":
                if text:
                    pyautogui.write(text)
                    return {"status": f"Texto '{text}' escrito exitosamente."}
                else:
                    return {"error": "Se requiere texto para la acción 'type_text'."}
            
            elif action == "move_mouse":
                if x is not None and y is not None:
                    pyautogui.moveTo(x=int(x), y=int(y))
                    return {"status": f"Ratón movido a ({int(x)}, {int(y)}) exitosamente."}
                else:
                    return {"error": "Se requieren coordenadas x e y para la acción 'move_mouse'."}

            else:
                return {"error": f"Acción '{action}' no soportada."}
        except Exception as e:
            if "Accessibility" in str(e) or "permissions" in str(e).lower():
                return {"error": f"Error de permisos: KogniTerm requiere permisos de Accesibilidad y Grabación de Pantalla en macOS para esta acción. Error: {str(e)}"}
            return {"error": f"Ocurrió un error durante la interacción: {str(e)}"}

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Implementación asincrónica de la herramienta (opcional)."""
        # Por simplicidad, se puede llamar a _run directamente o implementar lógica asincrónica si es necesario.
        return self._run(*args, **kwargs)

