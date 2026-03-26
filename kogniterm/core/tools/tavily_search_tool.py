import os
import logging
from typing import Type, Optional, Any, List, Dict
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class TavilySearchTool(BaseTool):
    name: str = "tavily_search"
    description: str = """Búsqueda web optimizada para agentes de IA usando Tavily. 
    Ideal para encontrar información técnica actualizada, documentación, artículos y discusiones.
    
    Devuelve resultados estructurados con:
    - Título y URL de cada resultado
    - Snippet/resumen del contenido
    - Score de relevancia
    
    Ejemplo de uso: {"query": "CrewAI multi-agent architecture best practices"}
    
    IMPORTANTE: Usa esta herramienta para investigación web profunda sobre temas técnicos."""

    class TavilySearchInput(BaseModel):
        query: str = Field(description="La consulta de búsqueda. Sé específico y técnico.")
        max_results: Optional[int] = Field(default=5, description="Número máximo de resultados (1-10).")
        search_depth: Optional[str] = Field(default="basic", description="Profundidad de búsqueda: 'basic' o 'advanced'.")

    args_schema: Type[BaseModel] = TavilySearchInput

    def get_action_description(self, **kwargs) -> str:
        query = kwargs.get("query", "")
        return f"Buscando en la web: {query}"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def _run(self, query: str, max_results: int = 5, search_depth: str = "basic") -> str:
        """Ejecuta una búsqueda usando la API de Tavily."""
        try:
            # Obtener API key
            api_key = os.getenv("TAVILY_API_KEY")
            if not api_key:
                return "Error: La variable de entorno 'TAVILY_API_KEY' no está configurada. Obtén una clave gratuita en https://tavily.com"

            # Importar tavily-python
            try:
                from tavily import TavilyClient
            except ImportError:
                return "Error: El paquete 'tavily-python' no está instalado. Ejecuta: pip install tavily-python"

            # Inicializar cliente
            client = TavilyClient(api_key=api_key)

            # Validar parámetros
            max_results = max(1, min(max_results, 10))  # Limitar entre 1 y 10
            if search_depth not in ["basic", "advanced"]:
                search_depth = "basic"

            # Realizar búsqueda
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_answer=True,  # Incluir respuesta resumida
                include_raw_content=False  # No incluir HTML completo
            )

            # Formatear resultados
            output = f"# Resultados de búsqueda: {query}\n\n"

            # Incluir respuesta resumida si está disponible
            if response.get("answer"):
                output += f"## Resumen\n{response['answer']}\n\n"

            # Incluir resultados individuales
            output += "## Fuentes\n\n"
            for i, result in enumerate(response.get("results", []), 1):
                title = result.get("title", "Sin título")
                url = result.get("url", "")
                content = result.get("content", "")
                score = result.get("score", 0)

                output += f"### {i}. {title}\n"
                output += f"**URL:** {url}\n"
                output += f"**Relevancia:** {score:.2f}\n\n"
                output += f"{content}\n\n"
                output += "---\n\n"

            return output

        except Exception as e:
            logger.error(f"Error en TavilySearchTool: {e}", exc_info=True)
            return f"Error al realizar la búsqueda con Tavily: {str(e)}"

    async def _arun(self, query: str, max_results: int = 5, search_depth: str = "basic") -> str:
        raise NotImplementedError("TavilySearchTool no soporta ejecución asíncrona")
