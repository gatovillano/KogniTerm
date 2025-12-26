from typing import Type, Optional, Dict, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from rich.console import Console
import os

from kogniterm.core.agents.code_agent import create_code_agent
from kogniterm.core.agents.researcher_agent import create_researcher_agent
from kogniterm.core.agent_state import AgentState
from langchain_core.messages import HumanMessage

console = Console()

# Límite de recursión configurable para el research agent
# Puedes ajustarlo mediante la variable de entorno RESEARCHER_RECURSION_LIMIT
RESEARCHER_RECURSION_LIMIT = int(os.getenv("RESEARCHER_RECURSION_LIMIT", "100"))

class CallAgentInput(BaseModel):
    agent_name: str = Field(..., description="El nombre del agente a invocar: 'code_agent' o 'researcher_agent'.")
    task: str = Field(..., description="La tarea específica que el agente debe realizar.")

class CallAgentTool(BaseTool):
    name: str = "call_agent"
    description: str = "Invoca a un agente especializado para realizar tareas complejas. Agentes disponibles: 'code_agent' (para tareas de código y edición), 'researcher_agent' (para investigación y análisis de código)."
    args_schema: Type[BaseModel] = CallAgentInput
    
    llm_service: Any = None
    terminal_ui: Any = None
    interrupt_queue: Any = None

    def __init__(self, llm_service, terminal_ui=None, interrupt_queue=None, **kwargs):
        super().__init__(**kwargs)
        self.llm_service = llm_service
        self.terminal_ui = terminal_ui
        self.interrupt_queue = interrupt_queue

    def _run(self, agent_name: str, task: str) -> str:
        """Ejecuta el agente especificado con la tarea dada."""
        
        console.print(f"\n[bold green]🤖 Delegando tarea a: {agent_name}[/bold green]")
        console.print(f"[italic]Tarea: {task}[/italic]\n")

        agent_graph = None
        
        if agent_name == "code_agent":
            agent_graph = create_code_agent(self.llm_service, self.terminal_ui, self.interrupt_queue)
        elif agent_name == "researcher_agent":
            agent_graph = create_researcher_agent(self.llm_service, self.terminal_ui, self.interrupt_queue)
        else:
            return f"Error: Agente '{agent_name}' no reconocido. Opciones válidas: 'code_agent', 'researcher_agent'."

        # Crear estado inicial para el sub-agente
        initial_state = AgentState(
            messages=[HumanMessage(content=task)]
        )

        try:
            # Ejecutar el grafo del agente con límite de recursión configurable
            # Para research_agent usamos el límite configurable, para code_agent usamos el default
            config = {}
            if agent_name == "researcher_agent":
                config = {"recursion_limit": RESEARCHER_RECURSION_LIMIT}
                console.print(f"[dim]ℹ️  Límite de recursión: {RESEARCHER_RECURSION_LIMIT} iteraciones[/dim]")
            
            final_state = agent_graph.invoke(initial_state, config=config)
            
            # Extraer la última respuesta del agente
            last_message = final_state["messages"][-1]
            return f"Respuesta de {agent_name}:\n{last_message.content}"
            
        except Exception as e:
            return f"Error al ejecutar {agent_name}: {str(e)}"

    async def _arun(self, agent_name: str, task: str) -> str:
        # Implementación asíncrona si fuera necesaria, por ahora delegamos a síncrona
        return self._run(agent_name, task)
