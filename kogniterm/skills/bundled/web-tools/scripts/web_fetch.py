"""
Web Fetch Skill - Obtiene contenido HTML de páginas web.

Provee funcionalidad para obtener el contenido de URLs.
"""

from typing import Generator


# Metadata de la herramienta
name = "web_fetch"
description = "Útil para obtener el contenido HTML de una URL."



def web_fetch(url: str) -> Generator[str, None, None]:
    """
    Obtiene el contenido HTML de una URL especificada.

    Args:
        url: La URL de la página web a obtener

    Yields:
        str: Contenido HTML de la página

    Raises:
        Exception: Errores de conexión o HTTP
    """
    try:
        from langchain_community.utilities import RequestsWrapper
    except ImportError:
        yield "Error: El paquete 'langchain-community' no está instalado.\n"
        yield "Ejecuta: pip install langchain-community\n"
        return

    try:
        requests_wrapper = RequestsWrapper()
        content = requests_wrapper.get(url)

        yield content

    except Exception as e:
        yield f"Error al obtener la URL {url}: {str(e)}\n"


# Función alternativa para ejecución síncrona
def web_fetch_sync(url: str) -> str:
    """
    Versión síncrona de web_fetch.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in web_fetch(url):
        output.append(chunk)
    return "".join(output)


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "La URL de la página web a obtener"
        }
    },
    "required": ["url"]
}
