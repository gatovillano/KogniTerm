import sys
from langchain.tools import BaseTool
from typing import Type, Any
from pydantic import BaseModel, Field

class ThinkInput(BaseModel):
    thought: str = Field(..., description="El razonamiento detallado o análisis antes de realizar una acción.")

class ThinkTool(BaseTool):
    name: str = "think_tool"
    description: str = "Usa esta herramienta para razonar, planificar y analizar antes de tomar decisiones o ejecutar otras herramientas. Es obligatoria para procesos de pensamiento profundo."
    args_schema: Type[BaseModel] = ThinkInput
    terminal_ui: Any = None

    def __init__(self, terminal_ui=None, **kwargs):
        super().__init__(**kwargs)
        self.terminal_ui = terminal_ui

    def _run(self, thought: str) -> str:
        """Usa el razonamiento proporcionado con efecto de streaming."""
        if self.terminal_ui:
            from kogniterm.terminal.themes import ColorPalette, Icons
            # Mostrar encabezado de pensamiento
            self.terminal_ui.console.print(f"\n[bold {ColorPalette.PRIMARY_LIGHT}]{Icons.THINKING} KogniTerm está pensando...[/bold {ColorPalette.PRIMARY_LIGHT}]")
            
            # Streaming del pensamiento
            self.terminal_ui.print_stream(thought, delay=0.01)
            self.terminal_ui.console.print() # Nueva línea al final
            
        return f"Razonamiento procesado correctamente."

    async def _arun(self, thought: str) -> str:
        """Usa el razonamiento proporcionado de forma asíncrona."""
        return self._run(thought)
