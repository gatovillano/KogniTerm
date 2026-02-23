"""
Web Scraping Skill - Extrae datos estructurados de HTML usando selectores CSS.

Esta es una skill migrada desde web_scraping_tool.py.
Provee funcionalidad para extraer datos de páginas web usando selectores CSS.
"""

from typing import Generator


# Metadata de la herramienta
name = "web_scraping"
description = "Útil para extraer datos estructurados de una página HTML usando selectores CSS."


def web_scraping(html_content: str, selector: str) -> Generator[str, None, None]:
    """
    Extrae datos estructurados de contenido HTML usando selectores CSS.

    Args:
        html_content: El contenido HTML de la página
        selector: El selector CSS para extraer los datos

    Yields:
        str: Datos extraídos en formato HTML formateado

    Raises:
        Exception: Errores de parsing o selección
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        yield "Error: El paquete 'beautifulsoup4' no está instalado.\n"
        yield "Ejecuta: pip install beautifulsoup4\n"
        return

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        elements = soup.select(selector)

        if not elements:
            yield f"No se encontraron elementos con el selector: {selector}\n"
            return

        scraped_content = "\n".join([e.prettify() for e in elements])
        
        yield f"### Resultados del Scraping (Selector: `{selector}`)\n"
        yield "```html\n"
        yield scraped_content
        yield "\n```\n"

    except Exception as e:
        yield f"Error al hacer scraping con selector '{selector}': {str(e)}\n"


# Función alternativa para ejecución síncrona
def web_scraping_sync(html_content: str, selector: str) -> str:
    """
    Versión síncrona de web_scraping.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in web_scraping(html_content, selector):
        output.append(chunk)
    return "".join(output)


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "html_content": {
            "type": "string",
            "description": "El contenido HTML de la página"
        },
        "selector": {
            "type": "string",
            "description": "El selector CSS para extraer los datos"
        }
    },
    "required": ["html_content", "selector"]
}
