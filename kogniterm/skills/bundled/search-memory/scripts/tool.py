"""
Search Memory Skill - Busca en memoria de resultados de búsqueda.

Esta es una skill migrada desde search_memory_tool.py.
Provee funcionalidad para guardar y consultar resultados de búsqueda.
"""

# Memoria global para almacenar resultados de búsqueda (en memoria del proceso)
_search_memory_store = []


# Metadata de la herramienta
name = "search_memory"
description = "Permite al agente guardar y consultar resultados de búsqueda para evitar búsquedas redundantes."


def search_memory(
    query: str,
    result: str = None
) -> str:
    """
    Guarda o busca resultados en la memoria de búsqueda.

    Args:
        query: La consulta de búsqueda original
        result: El resultado relevante de la búsqueda para guardar (opcional)

    Returns:
        str: Mensaje de éxito o resultados de la búsqueda
    """
    global _search_memory_store

    # Si se proporciona result, guardar en memoria
    if result is not None:
        return _add_search_result(query, result)
    # Si solo se proporciona query, buscar resultados
    else:
        return _get_relevant_search_results(query)


def _add_search_result(query: str, result: str) -> str:
    """
    Añade un resultado de búsqueda a la memoria.

    Args:
        query: La consulta de búsqueda original
        result: El resultado a guardar

    Returns:
        str: Mensaje de confirmación
    """
    global _search_memory_store

    # Limitar el tamaño de la memoria para evitar que crezca indefinidamente
    if len(_search_memory_store) >= 10:  # Mantener un máximo de 10 resultados en memoria
        _search_memory_store.pop(0)  # Eliminar el más antiguo

    _search_memory_store.append({"query": query, "result": result})
    return f"Resultado de búsqueda guardado en memoria para la consulta: '{query}'."


def _get_relevant_search_results(query: str) -> str:
    """
    Busca resultados relevantes en la memoria de búsqueda.

    Args:
        query: La consulta para buscar

    Returns:
        str: Resultados relevantes o mensaje de no hallazgos
    """
    global _search_memory_store

    relevant_results = []
    for item in _search_memory_store:
        # Una lógica simple para determinar la relevancia: si la consulta está contenida en la consulta guardada
        # o viceversa. Esto podría mejorarse con embeddings o algoritmos de similitud.
        if query.lower() in item["query"].lower() or item["query"].lower() in query.lower():
            relevant_results.append(f"Consulta anterior: '{item['query']}'\nResultado: {item['result']}")

    if relevant_results:
        return "Resultados relevantes encontrados en la memoria de búsqueda:\n" + "\n---\n".join(relevant_results)
    else:
        return "No se encontraron resultados relevantes en la memoria de búsqueda."


def _clear_search_memory() -> str:
    """
    Limpia la memoria de búsqueda.

    Returns:
        str: Mensaje de confirmación
    """
    global _search_memory_store
    _search_memory_store = []
    return "Memoria de búsqueda limpiada exitosamente."


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "La consulta de búsqueda original o la consulta para buscar resultados"
        },
        "result": {
            "type": "string",
            "description": "El resultado relevante de la búsqueda para guardar (opcional)"
        }
    },
    "required": ["query"]
}
