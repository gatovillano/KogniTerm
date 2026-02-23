"""
Think Skill - Herramienta de razonamiento y planificación.

Esta es una skill migrada desde think_tool.py.
Provee funcionalidad para razonar, planificar y analizar antes de tomar decisiones.
"""

import sys
from typing import Generator, Optional

# Metadata de la herramienta
name = "think"
description = "Usa esta herramienta para razonar, planificar y analizar antes de tomar decisiones o ejecutar otras herramientas. Es obligatoria para procesos de pensamiento profundo."


def think(thought: str) -> Generator[str, None, None]:
    """
    Usa el razonamiento proporcionado con efecto de streaming.

    Args:
        thought: El razonamiento detallado o análisis antes de realizar una acción

    Yields:
        str: Confirmación de procesamiento del razonamiento

    Raises:
        Exception: Errores durante el procesamiento
    """
    # Mostrar encabezado de pensamiento
    yield "\n🧠 KogniTerm está pensando..."
    
    # Streaming del pensamiento (simulado)
    words = thought.split()
    for i, word in enumerate(words):
        yield word + " "
        # Pequeña pausa para efecto de streaming (simulado)
        if i % 10 == 0:  # Cada 10 palabras
            yield "\n"
    
    yield "\n✅ Razonamiento procesado correctamente.\n"


# Función alternativa para ejecución síncrona
def think_sync(thought: str) -> str:
    """
    Versión síncrona de think.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in think(thought):
        output.append(chunk)
    return "".join(output)


# Función con soporte para UI terminal (opcional)
def think_with_ui(thought: str, terminal_ui=None) -> Generator[str, None, None]:
    """
    Versión de think con soporte para UI terminal.
    
    Args:
        thought: El razonamiento detallado
        terminal_ui: Objeto UI terminal opcional para mostrar efectos visuales
    """
    if terminal_ui:
        try:
            # Intentar importar desde el módulo de terminal
            from kogniterm.terminal.themes import ColorPalette, Icons
            
            # Mostrar encabezado de pensamiento
            terminal_ui.console.print(f"\n[bold {ColorPalette.PRIMARY_LIGHT}]{Icons.THINKING} KogniTerm está pensando...[/bold {ColorPalette.PRIMARY_LIGHT}]")
            
            # Streaming del pensamiento
            terminal_ui.print_stream(thought, delay=0.01)
            terminal_ui.console.print()  # Nueva línea al final
            
            yield "Razonamiento procesado correctamente con UI."
            
        except ImportError:
            # Si no hay UI terminal disponible, usar la versión básica
            for chunk in think(thought):
                yield chunk
    else:
        # Sin UI terminal, usar la versión básica
        for chunk in think(thought):
            yield chunk


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "thought": {
            "type": "string",
            "description": "El razonamiento detallado o análisis antes de realizar una acción"
        }
    },
    "required": ["thought"]
}