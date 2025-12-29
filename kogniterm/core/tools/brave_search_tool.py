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

    def get_action_description(self, **kwargs) -> str:
        query = kwargs.get("query", "")
        return f"Buscando en la web: '{query}'"

    MAX_BRAVE_SEARCH_OUTPUT_LENGTH: int = 30000 # Limite de caracteres para la salida de Brave Search

    def _run(self, query: str) -> str:
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return "Error: La variable de entorno 'BRAVE_SEARCH_API_KEY' no está configurada."
        search_tool = BraveSearch(api_key=api_key)
        # print(f"🌐 Buscando en Brave Search con la consulta: \"{query}\"") # Mensaje de depuración
        search_result = search_tool.run(query)

        if len(search_result) > self.MAX_BRAVE_SEARCH_OUTPUT_LENGTH:
            search_result = search_result[:self.MAX_BRAVE_SEARCH_OUTPUT_LENGTH] + f"\n... [Contenido truncado a {self.MAX_BRAVE_SEARCH_OUTPUT_LENGTH} caracteres] ..."

        return search_result

    async def _arun(self, query: str) -> str:
        raise NotImplementedError("brave_search does not support async")
