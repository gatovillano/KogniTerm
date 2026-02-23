"""
Skill: call_agent
Herramienta para invocar agentes especializados
"""

import os
import logging
from typing import Type, Optional, Dict, Any
from pydantic import BaseModel, Field
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
import json

logger = logging.getLogger(__name__)

console = Console()

# Límite de recursión configurable para el research agent
RESEARCHER_RECURSION_LIMIT = int(os.getenv("RESEARCHER_RECURSION_LIMIT", "100"))

class CallAgentInput(BaseModel):
    """Schema de entrada para la herramienta call_agent"""
    agent_name: str = Field(..., description="El nombre del agente a invocar: 'code_agent' o 'researcher_agent'.")
    task: str = Field(..., description="La tarea específica que el agente debe realizar.")

def call_agent_skill(agent_name: str, task: str, llm_service: Any = None, terminal_ui: Any = None, interrupt_queue: Any = None, approval_handler: Any = None) -> str:
    """
    Función principal que implementa la funcionalidad de call_agent
    
    Args:
        agent_name: Nombre del agente a invocar
        task: Tarea específica que el agente debe realizar
        llm_service: Servicio LLM para el agente
        terminal_ui: Interfaz de terminal
        interrupt_queue: Cola de interrupciones
        approval_handler: Manejador de aprobaciones
    
    Returns:
        str: Resultado de la ejecución del agente
    """
    
    console.print(f"\n[bold green]🤖 Delegando tarea a: {agent_name}[/bold green]")
    console.print(f"[italic]Tarea: {task}[/italic]\n")

    if agent_name == "code_agent" or agent_name == "code_crew":
        from kogniterm.core.agents.deep_coder import create_deep_coder
        
        agent_display = "DeepCoder" if agent_name == "code_agent" else "DeepCoder (Legacy Crew Name)"
        console.print(f"[dim]ℹ️  Invocando al motor de desarrollo profundo ({agent_display})...[/dim]")
        
        from kogniterm.core.agent_state import AgentState
        from langchain_core.messages import HumanMessage
        
        agent_graph = create_deep_coder(llm_service, terminal_ui, interrupt_queue)
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
        
        from kogniterm.core.agent_state import AgentState
        from langchain_core.messages import HumanMessage
        
        agent_graph = create_deep_researcher(llm_service, terminal_ui, interrupt_queue)
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

# Schema para el LLM
tool_schema = {
    "name": "call_agent",
    "description": "Invoca a un agente especializado para realizar tareas complejas. Agentes disponibles: 'code_agent' (para tareas de código y edición), 'researcher_agent' (para investigación y tareas complejas).",
    "parameters": {
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "description": "El nombre del agente a invocar: 'code_agent' o 'researcher_agent'.",
                "enum": ["code_agent", "researcher_agent"]
            },
            "task": {
                "type": "string",
                "description": "La tarea específica que el agente debe realizar."
            }
        },
        "required": ["agent_name", "task"]
    }
}