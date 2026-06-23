"""
Codebase Search Skill - Búsqueda semántica de código en la base de datos vectorial.

Provee funcionalidad para buscar snippets de código relevantes usando embeddings.
"""

import asyncio
import logging
from typing import Generator, Optional

logger = logging.getLogger(__name__)

# Metadata de la herramienta
name = "codebase_search"
description = "Busca snippets de código relevantes en la base de datos vectorial del proyecto. Utiliza embeddings para encontrar código basado en el significado de la consulta."


def codebase_search(
    query: str, 
    k: int = 5, 
    file_path_filter: Optional[str] = None, 
    language_filter: Optional[str] = None
) -> Generator[str, None, None]:
    """
    Realiza búsqueda semántica de código en la base de datos vectorial.

    Args:
        query: La consulta de búsqueda para encontrar snippets de código relevantes
        k: Número de snippets de código a retornar
        file_path_filter: Filtro para buscar solo dentro de una ruta de archivo específica
        language_filter: Filtro para buscar solo snippets de un lenguaje específico

    Yields:
        str: Resultados de la búsqueda formateados

    Raises:
        Exception: Errores durante la búsqueda
    """
    # Importaciones dinámicas para evitar dependencias obligatorias
    try:
        from kogniterm.core.embeddings_service import EmbeddingsService
        from kogniterm.core.context.vector_db_manager import VectorDBManager
    except ImportError as e:
        yield f"Error: No se pudieron importar los servicios necesarios: {str(e)}"
        return

    # Inicializar servicios
    vector_db_manager = None
    embeddings_service = None
    
    try:
        # Intentar obtener instancias existentes
        vector_db_manager = VectorDBManager.get_instance()
        embeddings_service = EmbeddingsService.get_instance()
    except Exception as e:
        yield f"Error: No se pudieron inicializar los servicios: {str(e)}"
        return

    if not vector_db_manager:
        yield "Error: VectorDBManager no está inicializado. Por favor indexe el proyecto primero."
        return

    # 1. Generar embedding de la consulta
    try:
        logger.info(f"CodebaseSearch: Generando embedding para la consulta: '{query}'")
        query_embeddings = embeddings_service.generate_embeddings([query])
    except Exception as e:
        logger.error(f"CodebaseSearch: Error generando embedding para la consulta: {e}")
        yield f"Error generando embedding para query: {str(e)}"
        return

    if not query_embeddings:
        logger.warning("CodebaseSearch: No se pudo generar embedding para la consulta.")
        yield "Error: No se pudo generar embedding para la consulta."
        return

    # 2. Buscar en la base de datos vectorial
    try:
        logger.info(f"CodebaseSearch: Realizando búsqueda en la base de datos vectorial con k={k}, file_path_filter={file_path_filter}, language_filter={language_filter}")
        search_results = vector_db_manager.search(
            query_embeddings[0], 
            k=k,
            file_path_filter=file_path_filter,
            language_filter=language_filter
        )
    except Exception as e:
         logger.error(f"CodebaseSearch: Error buscando en la base de datos vectorial: {e}")
         yield f"Error searching vector database: {str(e)}"
         return

    # 3. Formatear resultados
    if not search_results:
        yield "No se encontraron snippets de código relevantes para la consulta."
        return

    formatted_results = []
    for i, result in enumerate(search_results):
        content = result.get('content', 'Content not available')
        metadata = result.get('metadata', {})
        file_path = metadata.get('file_path', 'Unknown path')
        start_line = metadata.get('start_line', 'N/A')
        end_line = metadata.get('end_line', 'N/A')
        language = metadata.get('language', 'N/A')
        snippet_type = metadata.get('type', 'N/A')
        
        formatted_results.append(
            f"""--- Code Snippet {i+1} ---
File: {file_path}
Lines: {start_line}-{end_line}
Language: {language}
Type: {snippet_type}
Content:
```
{content}
```"""
        )
    
    yield "\n".join(formatted_results)


# Función alternativa para ejecución síncrona
def codebase_search_sync(
    query: str, 
    k: int = 5, 
    file_path_filter: Optional[str] = None, 
    language_filter: Optional[str] = None
) -> str:
    """
    Versión síncrona de codebase_search.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in codebase_search(query, k, file_path_filter, language_filter):
        output.append(chunk)
    return "".join(output)


def get_action_description(query: str, **kwargs) -> str:
    """Devuelve una descripción legible de la acción que realiza la herramienta."""
    return f"Buscando código relacionado con: '{query}'..."

# Asignar explícitamente
codebase_search.get_action_description = get_action_description


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "La consulta de búsqueda para encontrar snippets de código relevantes"
        },
        "k": {
            "type": "integer",
            "description": "Número de snippets de código a retornar",
            "default": 5
        },
        "file_path_filter": {
            "type": "string",
            "description": "Filtro para buscar solo dentro de una ruta de archivo específica (puede ser substring o coincidencia exacta)"
        },
        "language_filter": {
            "type": "string",
            "description": "Filtro para buscar solo snippets de un lenguaje de programación específico (ej: 'python', 'javascript')"
        }
    },
    "required": ["query"]
}
