from typing import Type, Optional, Dict, Any
from langchain_core.tools import BaseTool as LangChainBaseTool
from pydantic import BaseModel, Field
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
import os
import logging

logger = logging.getLogger(__name__)

from kogniterm.core.agents.code_agent import create_code_agent
from kogniterm.core.agent_state import AgentState
from langchain_core.messages import HumanMessage

console = Console()

# Límite de recursión configurable para el research agent
# Puedes ajustarlo mediante la variable de entorno RESEARCHER_RECURSION_LIMIT
RESEARCHER_RECURSION_LIMIT = int(os.getenv("RESEARCHER_RECURSION_LIMIT", "100"))

class CallAgentInput(BaseModel):
    agent_name: str = Field(..., description="El nombre del agente a invocar: 'code_agent' o 'researcher_agent'.")
    task: str = Field(..., description="La tarea específica que el agente debe realizar.")

class CallAgentTool(LangChainBaseTool):
    name: str = "call_agent"
    description: str = "Invoca a un agente especializado para realizar tareas complejas. Agentes disponibles: 'code_agent' (para tareas de código y edición), 'researcher_agent' (para investigación y tareas complejas)."
    args_schema: Type[BaseModel] = CallAgentInput
    
    def get_action_description(self, **kwargs) -> str:
        agent_name = kwargs.get("agent_name")
        task = kwargs.get("task", "")
        agent_display = "Researcher Agent" if agent_name == "researcher_agent" else "Code Agent"
        return f"Delegando tarea al {agent_display}: {task}"
    
    llm_service: Any = None
    terminal_ui: Any = None
    interrupt_queue: Any = None
    approval_handler: Any = None

    def __init__(self, llm_service, terminal_ui=None, interrupt_queue=None, approval_handler=None, **kwargs):
        super().__init__(**kwargs)
        self.llm_service = llm_service
        self.terminal_ui = terminal_ui
        self.interrupt_queue = interrupt_queue
        self.approval_handler = approval_handler

    def _run(self, agent_name: str, task: str) -> str:
        """Ejecuta el agente especificado con la tarea dada."""
        
        console.print(f"\n[bold green]🤖 Delegando tarea a: {agent_name}[/bold green]")
        console.print(f"[italic]Tarea: {task}[/italic]\n")

        if agent_name == "code_agent" or agent_name == "code_crew":
            from kogniterm.core.agents.deep_coder import create_deep_coder
            
            agent_display = "DeepCoder" if agent_name == "code_agent" else "DeepCoder (Legacy Crew Name)"
            console.print(f"[dim]ℹ️  Invocando al motor de desarrollo profundo ({agent_display})...[/dim]")
            
            agent_graph = create_deep_coder(self.llm_service, self.terminal_ui, self.interrupt_queue)
            initial_state = AgentState(messages=[HumanMessage(content=task)])
            
            try:
                final_state = agent_graph.invoke(initial_state, config={"recursion_limit": RESEARCHER_RECURSION_LIMIT})
                last_message = final_state["messages"][-1]
                
                result_str = last_message.content
                
                if not result_str.strip():
                    logger.warning(f"{agent_display} devolvió un resultado vacío.")
                    return "Error: El motor de desarrollo no pudo generar un resultado."

                console.print(Panel(
                    Markdown(result_str),
                    title=f"[bold green]✅ Tarea de Código Finalizada por {agent_display}[/bold green]",
                    border_style="green",
                    padding=(1, 2)
                ))
                return f"Respuesta de {agent_display}:\n\n{result_str}"
            except Exception as e:
                error_msg = f"Error al ejecutar {agent_display}: {str(e)}"
                logger.error(error_msg)
                return error_msg

        elif agent_name == "researcher_agent":
            from kogniterm.core.agents.deep_researcher import create_deep_researcher
            
            console.print("[dim]ℹ️  Invocando al motor de investigación profunda (DeepResearcher)...[/dim]")
            
            agent_graph = create_deep_researcher(self.llm_service, self.terminal_ui, self.interrupt_queue)
            initial_state = AgentState(messages=[HumanMessage(content=task)])
            
            try:
                final_state = agent_graph.invoke(initial_state, config={"recursion_limit": RESEARCHER_RECURSION_LIMIT})
                last_message = final_state["messages"][-1]
                
                result_str = last_message.content
                
                if not result_str.strip():
                    logger.warning("DeepResearcher devolvió un resultado vacío.")
                    return "Error: El motor de investigación no pudo generar un resultado."

                console.print(Panel(
                    Markdown(result_str),
                    title="[bold green]✅ Informe de Investigación Finalizado[/bold green]",
                    border_style="green",
                    padding=(1, 2)
                ))
                return f"Respuesta de DeepResearcher:\n\n{result_str}"
            except Exception as e:
                error_msg = f"Error al ejecutar DeepResearcher: {str(e)}"
                logger.error(error_msg)
                return error_msg

        else:
            return f"Error: Agente '{agent_name}' no reconocido. Opciones válidas: 'code_agent', 'researcher_agent'."

    async def _arun(self, agent_name: str, task: str) -> str:
        # Implementación asíncrona si fuera necesaria, por ahora delegamos a síncrona
        return self._run(agent_name, task)