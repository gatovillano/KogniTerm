"""
Skill: browser_navigation
Navegación web avanzada mediante Playwright en modo gráfico visible (tiempo real) o segundo plano (headless).
"""

import os
import time
import logging
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Intentar importar playwright
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


class BrowserNavigationInput(BaseModel):
    """Schema de entrada para la herramienta browser_navigation"""
    action: str = Field(description="Acción web a realizar: 'navigate', 'click', 'type_text', 'press_key', 'get_content', 'take_screenshot', 'scroll', 'close'.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parámetros para la acción.")


class BrowserSession:
    """Manejador de sesión persistente para Playwright"""
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.headless: bool = False

    def get_or_create_page(self, headless: bool = False) -> Page:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright no está instalado en el entorno Python.")

        # Si el modo headless cambió o el navegador está cerrado, reiniciar
        if self.browser and self.headless != headless:
            self.close()

        if self.page and not self.page.is_closed():
            return self.page

        if not self.playwright:
            self.playwright = sync_playwright().start()

        if not self.browser:
            self.headless = headless
            self.browser = self.playwright.chromium.launch(
                headless=headless,
                args=["--start-maximized", "--no-sandbox"]
            )

        if not self.context:
            self.context = self.browser.new_context(no_viewport=True if not headless else False)

        if not self.page or self.page.is_closed():
            self.page = self.context.new_page()

        return self.page

    def close(self):
        try:
            if self.page and not self.page.is_closed():
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error cerrando sesión de navegador: {e}")
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None


# Instancia global de sesión de navegador
_SESSION = BrowserSession()


def browser_navigation_skill(action: str, params: Dict[str, Any] = None) -> str:
    """
    Función principal para la navegación web con Playwright.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return "Error: La librería 'playwright' no está disponible en el entorno Python."

    if params is None:
        params = {}

    headless = params.get("headless", False)  # Por defecto visible en tiempo real

    try:
        if action == "navigate":
            url = params.get("url")
            if not url:
                return "Error: Se requiere el parámetro 'url'."
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url

            page = _SESSION.get_or_create_page(headless=headless)
            page.goto(url, timeout=params.get("timeout", 30000), wait_until="domcontentloaded")
            title = page.title()
            return f"Navegado con éxito a: {url}\nTítulo de la página: '{title}'"

        elif action == "click":
            selector = params.get("selector")
            text = params.get("text")
            if not selector and not text:
                return "Error: Se requiere 'selector' (CSS/XPath) o 'text' del elemento a hacer click."

            page = _SESSION.get_or_create_page(headless=headless)

            if selector:
                page.click(selector, timeout=params.get("timeout", 10000))
                return f"Click realizado en el elemento selector: '{selector}'."
            else:
                page.click(f"text={text}", timeout=params.get("timeout", 10000))
                return f"Click realizado en el elemento con texto: '{text}'."

        elif action == "type_text":
            selector = params.get("selector")
            text = params.get("text")
            if not selector or text is None:
                return "Error: Se requieren 'selector' y 'text'."

            page = _SESSION.get_or_create_page(headless=headless)
            page.fill(selector, str(text), timeout=params.get("timeout", 10000))
            if params.get("press_enter", False):
                page.press(selector, "Enter")
                return f"Texto '{text}' ingresado en '{selector}' y tecla Enter presionada."
            return f"Texto '{text}' ingresado en el campo '{selector}'."

        elif action == "press_key":
            key = params.get("key", "Enter")
            selector = params.get("selector")

            page = _SESSION.get_or_create_page(headless=headless)
            if selector:
                page.press(selector, key)
            else:
                page.keyboard.press(key)
            return f"Tecla '{key}' presionada."

        elif action == "get_content":
            selector = params.get("selector")
            mode = params.get("mode", "text")  # 'text' o 'html'

            page = _SESSION.get_or_create_page(headless=headless)
            if selector:
                element = page.query_selector(selector)
                if not element:
                    return f"No se encontró el elemento selector: '{selector}'."
                content = element.inner_text() if mode == "text" else element.inner_html()
            else:
                content = page.inner_text("body") if mode == "text" else page.content()

            # Limitar longitud para prevenir desbordamientos en contexto
            max_len = params.get("max_length", 4000)
            if len(content) > max_len:
                content = content[:max_len] + f"\n\n...[Contenido truncado. Total caracteres: {len(content)}]"

            return f"Contenido extraído ({mode}):\n\n{content}"

        elif action == "take_screenshot":
            filename = params.get("filename")
            if not filename:
                filename = f"browser_screenshot_{int(time.time())}.png"

            path = os.path.abspath(filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)

            page = _SESSION.get_or_create_page(headless=headless)
            page.screenshot(path=path, full_page=params.get("full_page", False))
            return f"Captura de pantalla de navegador guardada en: {path}"

        elif action == "scroll":
            direction = params.get("direction", "down")
            amount = params.get("amount", 500)

            page = _SESSION.get_or_create_page(headless=headless)
            delta_y = amount if direction == "down" else -amount
            page.mouse.wheel(0, delta_y)
            return f"Desplazamiento (scroll) realizado: {direction} ({amount}px)."

        elif action == "close":
            _SESSION.close()
            return "Navegador cerrado correctamente."

        else:
            return f"Acción '{action}' no reconocida para navegación web."

    except Exception as e:
        logger.error(f"Error en browser_navigation ({action}): {e}", exc_info=True)
        return f"Error al ejecutar acción web '{action}': {type(e).__name__}: {str(e) or repr(e)}"


# Schema de herramienta para el LLM
tool_schema = {
    "name": "browser_navigation",
    "description": "Navegación web interactiva en tiempo real (visible en pantalla) o en segundo plano (headless) usando Playwright. Permite visitar páginas, hacer click, rellenar formularios, extraer información y tomar capturas.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "La acción web a ejecutar.",
                "enum": [
                    "navigate", "click", "type_text", "press_key", 
                    "get_content", "take_screenshot", "scroll", "close"
                ]
            },
            "params": {
                "type": "object",
                "description": "Parámetros específicos según la acción.",
                "properties": {
                    "url": {"type": "string", "description": "URL a la que navegar"},
                    "selector": {"type": "string", "description": "Selector CSS o XPath del elemento objetivo"},
                    "text": {"type": "string", "description": "Texto a escribir o texto del elemento a buscar"},
                    "key": {"type": "string", "description": "Tecla a presionar (ej: 'Enter', 'Tab', 'Escape')", "default": "Enter"},
                    "headless": {"type": "boolean", "description": "False para navegador visible en tiempo real (por defecto), True para segundo plano", "default": False},
                    "press_enter": {"type": "boolean", "description": "Si es True, presiona Enter tras escribir texto", "default": False},
                    "mode": {"type": "string", "description": "Modo de extracción de contenido ('text' o 'html')", "default": "text"},
                    "filename": {"type": "string", "description": "Ruta/nombre del archivo de captura de pantalla"},
                    "full_page": {"type": "boolean", "description": "Captura de la página completa incluyendo scroll", "default": False},
                    "direction": {"type": "string", "description": "Dirección del scroll ('down' o 'up')", "default": "down"},
                    "amount": {"type": "number", "description": "Cantidad en píxeles para el scroll", "default": 500},
                    "timeout": {"type": "number", "description": "Tiempo máximo de espera en milisegundos", "default": 30000}
                }
            }
        },
        "required": ["action"]
    }
}
