import os
import logging
from typing import Type
from pydantic import BaseModel, Field
from langchain_community.tools import BraveSearch
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class BraveSearchTool(BaseTool):
    name: str = "brave_search"
    description: str = "Útil para buscar información actualizada en la web."

    class BraveSearchInput(BaseModel):
        query: str = Field(description="La consulta de búsqueda para Brave Search.")

    args_schema: Type[BaseModel] = BraveSearchInput

    def _run(self, query: str) -> str:
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return "Error: La variable de entorno 'BRAVE_SEARCH_API_KEY' no está configurada."
        search_tool = BraveSearch(api_key=api_key)
        return search_tool.run(query)

    async def _arun(self, query: str) -> str:
        raise NotImplementedError("brave_search does not support async")
