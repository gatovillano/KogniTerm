import asyncio
from typing import Type, Any
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class WebScrapingTool(BaseTool):
    name: str = "web_scraping"
    description: str = "Útil para extraer datos estructurados de una página HTML usando selectores CSS."

    class WebScrapingInput(BaseModel):
        html_content: str = Field(description="El contenido HTML de la página.")
        selector: str = Field(description="El selector CSS para extraer los datos.")

    args_schema: Type[BaseModel] = WebScrapingInput

    def _run(self, html_content: str, selector: str) -> str:
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            elements = soup.select(selector)
            scraped_content_list = []
            for e in elements:
                pretty_e = e.prettify()
                if isinstance(pretty_e, bytes):
                    scraped_content_list.append(pretty_e.decode('utf-8', errors='ignore'))
                else:
                    scraped_content_list.append(pretty_e)
            
            scraped_content = "\n".join(scraped_content_list)
            
            return f'''### Resultados del Scraping (Selector: `{selector}`)
```html
{scraped_content}
```'''
        except Exception as e:
            logger.error(f"Error al hacer scraping con selector '{selector}': {e}", exc_info=True)
            return f"Error al hacer scraping: {e}"

    async def _arun(self, html_content: str, selector: str) -> str:
        return await asyncio.to_thread(self._run, html_content, selector)