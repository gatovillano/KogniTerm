import asyncio
import logging
from typing import Optional, Any

from playwright.async_api import async_playwright # Importar async_playwright

logger = logging.getLogger(__name__)

class PlaywrightBrowserManager:
    _instance: Optional[Any] = None
    _browser: Optional[Any] = None
    _lock: asyncio.Lock
    _playwright_context: Optional[Any] = None # Para mantener el contexto de playwright

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PlaywrightBrowserManager, cls).__new__(cls)
            cls._lock = asyncio.Lock()
        return cls._instance

    async def get_browser(self) -> Any:
        if self._browser is None:
            async with self._lock:
                if self._browser is None:
                    logger.info("Inicializando Playwright browser...")
                    # Iniciar Playwright y el navegador directamente en el bucle de eventos existente
                    self._playwright_context = await async_playwright().start()
                    self._browser = await self._playwright_context.chromium.launch()
                    logger.info("Playwright browser inicializado.")
        return self._browser

    async def close_browser(self):
        if self._browser:
            logger.info("Cerrando Playwright browser...")
            await self._browser.close()
            self._browser = None
            if self._playwright_context:
                await self._playwright_context.stop()
                self._playwright_context = None
            logger.info("Playwright browser cerrado.")

# Para asegurar que el navegador se cierre al finalizar la aplicación
# Esto es un ejemplo, la integración real dependerá del ciclo de vida de KogniTerm
async def close_playwright_browser_on_exit():
    manager = PlaywrightBrowserManager()
    await manager.close_browser()

# Puedes registrar esta función para que se ejecute al salir de la aplicación
# Por ejemplo, con atexit o un manejador de señales en el bucle principal de KogniTerm.
