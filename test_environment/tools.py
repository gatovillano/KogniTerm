import os
from langchain_community.tools.tavily_search import TavilySearchResults

def get_tavily_tool():
    """
    Configura y devuelve la herramienta de búsqueda de Tavily.
    Requiere TAVILY_API_KEY en las variables de entorno.
    """
    if not os.environ.get("TAVILY_API_KEY"):
        print("⚠️ Advertencia: TAVILY_API_KEY no encontrada. La búsqueda web fallará.")
    
    return TavilySearchResults(
        max_results=5,
        search_depth="advanced",
        include_answer=True,
        include_raw_content=True
    )
