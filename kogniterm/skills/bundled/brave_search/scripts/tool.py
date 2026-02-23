"""
Brave Search Skill - Búsqueda web usando Brave Search API.

Esta es una skill migrada desde brave_search_tool.py.
Provee funcionalidad para buscar información actualizada en la web.
"""

import os
from typing import Generator


# Metadata de la herramienta
name = "brave_search"
description = "Útil para buscar información actualizada en la web."

# Límite de caracteres para la salida
MAX_OUTPUT_LENGTH = 30000


def brave_search(query: str) -> Generator[str, None, None]:
    """
    Realiza una búsqueda en la web usando Brave Search API.

    Args:
        query: La consulta de búsqueda

    Yields:
        str: Resultados de la búsqueda

    Raises:
        Exception: Errores de conexión o API
    """
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    
    if not api_key:
        yield "Error: La variable de entorno 'BRAVE_SEARCH_API_KEY' no está configurada.\n"
        yield "Obtén una clave API gratuita en: https://brave.com/search/api/\n"
        return

    try:
        from langchain_community.tools import BraveSearch
    except ImportError:
        yield "Error: El paquete 'langchain-community' no está instalado.\n"
        yield "Ejecuta: pip install langchain-community\n"
        return

    try:
        search_tool = BraveSearch(api_key=api_key)
        search_result = search_tool.run(query)

        if len(search_result) > MAX_OUTPUT_LENGTH:
            search_result = search_result[:MAX_OUTPUT_LENGTH] + f"\n... [Contenido truncado a {MAX_OUTPUT_LENGTH} caracteres] ..."

        yield search_result

    except Exception as e:
        yield f"Error al realizar la búsqueda: {str(e)}\n"


# Función alternativa para ejecución síncrona
def brave_search_sync(query: str) -> str:
    """
    Versión síncrona de brave_search.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in brave_search(query):
        output.append(chunk)
    return "".join(output)


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "La consulta de búsqueda para Brave Search"
        }
    },
    "required": ["query"]
}
