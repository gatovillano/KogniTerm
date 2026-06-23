"""
Tavily Search Skill - Búsqueda web optimizada para agentes de IA.

Provee funcionalidad para búsqueda web especializada en temas técnicos.
"""

import os
from typing import Generator, Optional


import logging
logger = logging.getLogger(__name__)

# Metadata de la herramienta
name = "tavily_search"
description = "Búsqueda web optimizada para agentes de IA usando Tavily."


def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic"
) -> Generator[str, None, None]:
    """
    Realiza una búsqueda usando la API de Tavily.

    Args:
        query: La consulta de búsqueda. Sé específico y técnico
        max_results: Número máximo de resultados (1-10, default: 5)
        search_depth: Profundidad de búsqueda: 'basic' o 'advanced' (default: 'basic')

    Yields:
        str: Resultados de la búsqueda formateados

    Raises:
        Exception: Errores de conexión o API
    """
    logger.info(f"Ejecutando tavily_search con query='{query}', max_results={max_results}")
    api_key = os.getenv("TAVILY_API_KEY")
    
    if not api_key:
        logger.error("TAVILY_API_KEY no configurada")
        yield "Error: La variable de entorno 'TAVILY_API_KEY' no está configurada.\n"
        yield "Obtén una clave gratuita en: https://tavily.com\n"
        return

    # Importar tavily-python
    try:
        from tavily import TavilyClient
    except ImportError:
        yield "Error: El paquete 'tavily-python' no está instalado.\n"
        yield "Ejecuta: pip install tavily-python\n"
        return

    try:
        # Inicializar cliente
        client = TavilyClient(api_key=api_key)

        # Validar parámetros
        max_results = int(max_results) if max_results is not None else 5
        max_results = max(1, min(max_results, 10))  # Limitar entre 1 y 10
        
        if search_depth not in ["basic", "advanced"]:
            search_depth = "basic"

        # Notificar inicio
        yield f"# Resultados de búsqueda: {query}\n\n"

        # Realizar búsqueda
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
            include_answer=True,  # Incluir respuesta resumida
            include_raw_content=False  # No incluir HTML completo
        )

        # Incluir respuesta resumida si está disponible
        if response.get("answer"):
            yield f"## Resumen\n{response['answer']}\n\n"

        # Incluir resultados individuales
        yield "## Fuentes\n\n"
        
        results = response.get("results", [])
        if not results and not response.get("answer"):
            yield "No se encontraron resultados relevantes para esta búsqueda.\n"
        else:
            for i, result in enumerate(results, 1):
                title = result.get("title", "Sin título")
                url = result.get("url", "")
                content = result.get("content", "")
                score = result.get("score", 0)

                yield f"### {i}. {title}\n"
                yield f"**URL:** {url}\n"
                yield f"**Relevancia:** {score:.2f}\n\n"
                yield f"{content}\n\n"
                yield "---\n\n"

    except Exception as e:
        yield f"Error al realizar la búsqueda con Tavily: {str(e)}\n"


# Función alternativa para ejecución síncrona
def tavily_search_sync(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic"
) -> str:
    """
    Versión síncrona de tavily_search.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in tavily_search(query, max_results, search_depth):
        output.append(chunk)
    return "".join(output)


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "La consulta de búsqueda. Sé específico y técnico."
        },
        "max_results": {
            "type": "integer",
            "description": "Número máximo de resultados (1-10)",
            "default": 5
        },
        "search_depth": {
            "type": "string",
            "description": "Profundidad de búsqueda: 'basic' o 'advanced'",
            "default": "basic"
        }
    },
    "required": ["query"]
}
