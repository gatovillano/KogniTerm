import logging
from typing import Type
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class WebScrapingTool(BaseTool):
    name: str = "web_scraping"
    description: str = "Útil para extraer datos estructurados de una página HTML usando selectores CSS."

    class WebScrapingInput(BaseModel):
        html_content: str = Field(description="El contenido HTML de la página.")
        selector: str = Field(description="El selector CSS para extraer los datos.")

    args_schema: Type[BaseModel] = WebScrapingInput

    def get_action_description(self, **kwargs) -> str:
        selector = kwargs.get("selector", "")
        return f"Extrayendo datos con selector: {selector}"

    def _run(self, html_content: str, selector: str) -> str:
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            elements = soup.select(selector)
            scraped_content = "\n".join([e.prettify() for e in elements])
            return f'''### Resultados del Scraping (Selector: `{selector}`)
```html
{scraped_content}
```'''
        except Exception as e:
            logger.error(f"Error al hacer scraping con selector '{selector}': {e}", exc_info=True)
            return f"Error al hacer scraping: {e}"

    async def _arun(self, html_content: str, selector: str) -> str:
        raise NotImplementedError("web_scraping does not support async")
