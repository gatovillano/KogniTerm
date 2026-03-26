import logging
from typing import Type, List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from ..agent_state import AgentState # Importar AgentState

logger = logging.getLogger(__name__)

class SearchMemoryTool(BaseTool):
    name: str = "search_memory_tool"
    description: str = "Permite al agente guardar y consultar resultados de búsqueda para evitar búsquedas redundantes."
    agent_state: Optional[AgentState] = Field(None, exclude=True) # Referencia al estado del agente

    class AddSearchResultInput(BaseModel):
        query: str = Field(description="La consulta de búsqueda original.")
        result: str = Field(description="El resultado relevante de la búsqueda para guardar.")

    class GetRelevantSearchResultsInput(BaseModel):
        query: str = Field(description="La consulta para la que se buscan resultados relevantes en la memoria.")

    def get_action_description(self, **kwargs) -> str:
        if "result" in kwargs and "query" in kwargs:
            return f"Guardando resultado de búsqueda para: {kwargs.get('query')}"
        elif "query" in kwargs:
            return f"Buscando en memoria de resultados: {kwargs.get('query')}"
        return "Interactuando con memoria de búsqueda"

    def _run(self, **kwargs: Any) -> str:
        if "result" in kwargs and "query" in kwargs:
            return self._add_search_result(kwargs["query"], kwargs["result"])
        elif "query" in kwargs:
            return self._get_relevant_search_results(kwargs["query"])
        else:
            return "Error: Se requiere 'query' y 'result' para añadir, o solo 'query' para obtener resultados."

    def _add_search_result(self, query: str, result: str) -> str:
        if not self.agent_state:
            return "Error: El estado del agente no está vinculado a la herramienta de memoria."
        # Limitar el tamaño de la memoria para evitar que crezca indefinidamente
        if len(self.agent_state.search_memory) >= 10: # Mantener un máximo de 10 resultados en memoria
            self.agent_state.search_memory.pop(0) # Eliminar el más antiguo

        self.agent_state.search_memory.append({"query": query, "result": result})
        logger.info(f"Resultado de búsqueda guardado en memoria para la consulta: {query}")
        return f"Resultado de búsqueda guardado en memoria para la consulta: '{query}'."

    def _get_relevant_search_results(self, query: str) -> str:
        if not self.agent_state:
            return "Error: El estado del agente no está vinculado a la herramienta de memoria."
        relevant_results = []
        for item in self.agent_state.search_memory:
            # Una lógica simple para determinar la relevancia: si la consulta está contenida en la consulta guardada
            # o viceversa. Esto podría mejorarse con embeddings o algoritmos de similitud.
            if query.lower() in item["query"].lower() or item["query"].lower() in query.lower():
                relevant_results.append(f"Consulta anterior: '{item['query']}'\nResultado: {item['result']}")
        
        if relevant_results:
            return "Resultados relevantes encontrados en la memoria de búsqueda:\n" + "\n---\n".join(relevant_results)
        else:
            return "No se encontraron resultados relevantes en la memoria de búsqueda."

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("SearchMemoryTool does not support async")
