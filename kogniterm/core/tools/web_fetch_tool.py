import asyncio
from typing import Type, Any
from pydantic import BaseModel, Field
from langchain_community.utilities import RequestsWrapper
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class WebFetchTool(BaseTool):
    name: str = "web_fetch"
    description: str = "Útil para obtener el contenido HTML de una URL."

    class WebFetchInput(BaseModel):
        url: str = Field(description="La URL de la página web a obtener.")

    args_schema: Type[BaseModel] = WebFetchInput

    def _run(self, url: str) -> str:
        requests_wrapper = RequestsWrapper()
        try:
            response = requests_wrapper.get(url)
            if isinstance(response, dict) and 'text' in response:
                return response['text']
            return str(response)
        except Exception as e:
            logger.error(f"Error al obtener la URL {url}: {e}", exc_info=True)
            return f"Error al obtener la URL {url}: {e}"
    
    async def _arun(self, url: str) -> str:
        requests_wrapper = RequestsWrapper()
        try:
            response = await asyncio.to_thread(requests_wrapper.get, url)
            if isinstance(response, dict) and 'text' in response:
                return response['text']
            return str(response)
        except Exception as e:
            logger.error(f"Error al obtener la URL {url} de forma asíncrona: {e}", exc_info=True)
            return f"Error al obtener la URL {url}: {e}"