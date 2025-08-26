import asyncio
import os
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_community.tools import BraveSearch
from langchain_core.tools import BaseTool
import logging

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
        search_tool = BraveSearch()
        return search_tool.run(query)

    async def _arun(self, query: str) -> str:
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return "Error: La variable de entorno 'BRAVE_SEARCH_API_KEY' no está configurada."
        search_tool = BraveSearch()
        # BraveSearch no tiene un método arun nativo en todas las versiones, usamos to_thread por seguridad
        return await asyncio.to_thread(search_tool.run, query)