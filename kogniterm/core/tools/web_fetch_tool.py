import logging
from typing import Type
from pydantic import BaseModel, Field
from langchain_community.utilities import RequestsWrapper
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class WebFetchTool(BaseTool):
    name: str = "web_fetch"
    description: str = "Útil para obtener el contenido HTML de una URL."

    class WebFetchInput(BaseModel):
        url: str = Field(description="La URL de la página web a obtener.")

    args_schema: Type[BaseModel] = WebFetchInput

    def get_action_description(self, **kwargs) -> str:
        url = kwargs.get("url", "")
        return f"Obteniendo contenido de: {url}"

    def _run(self, url: str) -> str:
        requests_wrapper = RequestsWrapper()
        try:
            content = requests_wrapper.get(url)
            MAX_OUTPUT_LENGTH = 20000 # Definir la longitud máxima de la salida
            if len(content) > MAX_OUTPUT_LENGTH:
                truncated_content = content[:MAX_OUTPUT_LENGTH] + f"\n... [Contenido truncado a {MAX_OUTPUT_LENGTH} caracteres] ..."
                return truncated_content
            return content
        except Exception as e:
            logger.error(f"Error al obtener la URL {url}: {e}", exc_info=True)
            return f"Error al obtener la URL {url}: {e}"
    
    async def _arun(self, url: str) -> str:
        raise NotImplementedError("web_fetch does not support async")
