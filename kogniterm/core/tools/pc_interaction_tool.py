import asyncio
import logging
import base64
from typing import Optional, Dict, Any, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

from kogniterm.utils.playwright_browser_manager import PlaywrightBrowserManager

logger = logging.getLogger(__name__)

class PCInteractionTool(BaseTool):
    name: str = "pc_interaction"
    description: str = "Herramienta para interactuar con el entorno del PC a través del navegador, permitiendo abrir páginas, tomar capturas de pantalla, mover el mouse, hacer clic y ingresar texto."

    manager: Optional[PlaywrightBrowserManager] = None
    context: Optional[Any] = None
    page: Optional[Any] = None

    def model_post_init(self, __context: Any) -> None:
        if self.manager is None:
            self.manager = PlaywrightBrowserManager()

    async def _ensure_page(self):
        if self.page is None:
            browser = await self.manager.get_browser()
            self.context = await browser.new_context()
            self.page = await self.context.new_page()

    class PCInteractionInput(BaseModel):
        action: str = Field(description="La acción a realizar: 'open_url', 'screenshot', 'click', 'type_text', 'move_mouse'.")
        url: Optional[str] = Field(default=None, description="URL para 'open_url'.")
        selector: Optional[str] = Field(default=None, description="Selector CSS para 'click' o 'type_text'.")
        text: Optional[str] = Field(default=None, description="Texto a ingresar para 'type_text'.")
        x: Optional[float] = Field(default=None, description="Coordenada X para 'click' o 'move_mouse'.")
        y: Optional[float] = Field(default=None, description="Coordenada Y para 'click' o 'move_mouse'.")

    args_schema: Type[BaseModel] = PCInteractionInput

    def _run(self, action: str, url: Optional[str] = None, selector: Optional[str] = None, text: Optional[str] = None, x: Optional[float] = None, y: Optional[float] = None) -> Dict[str, Any]:
        # Since Playwright is async, we need to run in an event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we can't use run_until_complete, need to use create_task or something
                # For simplicity, assume it's called in async context, but since _run is sync, we need to handle
                # Actually, for langchain tools, _run is sync, but we can make it async by overriding _arun
                raise NotImplementedError("Use _arun for async operations")
            else:
                return loop.run_until_complete(self._perform_action(action, url, selector, text, x, y))
        except RuntimeError:
            # No event loop
            return asyncio.run(self._perform_action(action, url, selector, text, x, y))

    async def _arun(self, action: str, url: Optional[str] = None, selector: Optional[str] = None, text: Optional[str] = None, x: Optional[float] = None, y: Optional[float] = None) -> str:
        result = await self._perform_action(action, url, selector, text, x, y)
        return str(result)

    async def _perform_action(self, action: str, url: Optional[str], selector: Optional[str], text: Optional[str], x: Optional[float], y: Optional[float]) -> Dict[str, Any]:
        await self._ensure_page()
        try:
            if action == 'open_url':
                if not url:
                    return {"error": "URL requerida para 'open_url'."}
                await self.page.goto(url)
                return {"status": "success", "message": f"Página abierta: {url}"}

            elif action == 'screenshot':
                screenshot_bytes = await self.page.screenshot()
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                return {"status": "success", "screenshot": screenshot_b64}

            elif action == 'click':
                if selector:
                    await self.page.click(selector)
                elif x is not None and y is not None:
                    await self.page.mouse.click(x, y)
                else:
                    return {"error": "Selector o coordenadas requeridas para 'click'."}
                return {"status": "success", "message": "Clic realizado."}

            elif action == 'type_text':
                if not selector or not text:
                    return {"error": "Selector y texto requeridos para 'type_text'."}
                await self.page.fill(selector, text)
                return {"status": "success", "message": f"Texto '{text}' ingresado en {selector}."}

            elif action == 'move_mouse':
                if x is None or y is None:
                    return {"error": "Coordenadas requeridas para 'move_mouse'."}
                await self.page.mouse.move(x, y)
                return {"status": "success", "message": f"Mouse movido a ({x}, {y})."}

            else:
                return {"error": f"Acción '{action}' no soportada."}

        except Exception as e:
            return {"error": f"Error en acción '{action}': {str(e)}"}

    async def close(self):
        if self.page:
            await self.page.close()
            self.page = None
        if self.context:
            await self.context.close()
            self.context = None
        await self.manager.close_browser()