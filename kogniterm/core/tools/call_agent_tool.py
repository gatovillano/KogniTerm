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
# from kogniterm.core.agents.researcher_agent import create_researcher_agent # Eliminado
from kogniterm.core.agents.researcher_crew import ResearcherCrew # Agregado
from kogniterm.core.agents.code_crew import CodeCrew # Agregado
from kogniterm.core.agent_state import AgentState
from langchain_core.messages import HumanMessage

# Importar ChatLiteLLM para CrewAI
try:
    from langchain_litellm import ChatLiteLLM
except ImportError:
    from langchain_community.chat_models.litellm import ChatLiteLLM


console = Console()

# Importar BaseTool de crewai.tools (ubicación correcta para Pydantic v2)
from crewai.tools import BaseTool as CrewAIBaseTool

class CrewAIWrapper(CrewAIBaseTool):
    name: str
    description: str
    lc_tool: Any
    args_schema: Optional[Type[BaseModel]] = None

    def _run(self, *args, **kwargs):
        # Delegar la ejecución a la herramienta de LangChain
        # Manejar argumentos posicionales y de palabra clave
        try:
            if args and not kwargs:
                result = self.lc_tool.run(args[0])
            else:
                result = self.lc_tool.run(kwargs)
        except Exception as e:
            result = f"Error ejecutando herramienta {self.name}: {str(e)}"
        
        # CRÍTICO: CrewAI espera siempre strings. 
        # Si el resultado es una lista, diccionario o cualquier cosa que no sea string,
        # lo convertimos a JSON o string plano.
        if result is None:
            return "Operación completada sin salida."
            
        if not isinstance(result, str):
            import json
            try:
                # Intentar serializar a JSON para mantener la estructura
                return json.dumps(result, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                # Si falla (ej: contiene objetos no serializables), forzar a string
                return str(result)
        
        return result

# Límite de recursión configurable para el research agent
# Puedes ajustarlo mediante la variable de entorno RESEARCHER_RECURSION_LIMIT
RESEARCHER_RECURSION_LIMIT = int(os.getenv("RESEARCHER_RECURSION_LIMIT", "100"))

class CallAgentInput(BaseModel):
    agent_name: str = Field(..., description="El nombre del agente a invocar: 'code_agent' o 'researcher_agent'.")
    task: str = Field(..., description="La tarea específica que el agente debe realizar.")

class CallAgentTool(LangChainBaseTool):
    name: str = "call_agent"
    description: str = "Invoca a un agente especializado para realizar tareas complejas. Agentes disponibles: 'code_agent' (para tareas de código y edición), 'researcher_agent' (para investigación y análisis de código), 'code_crew' (equipo de desarrollo multi-agente)."
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

        def get_valid_tool(name_in_service):
            """Obtiene una herramienta de LangChain y la envuelve en CrewAI BaseTool."""
            lc_tool = self.llm_service.get_tool(name_in_service)
            if lc_tool is None:
                console.print(f"[bold yellow]⚠️ Advertencia: Herramienta '{name_in_service}' no encontrada en LLMService.[/bold yellow]")
                return None
            
            return CrewAIWrapper(
                name=lc_tool.name,
                description=lc_tool.description,
                lc_tool=lc_tool,
                args_schema=lc_tool.args_schema
            )

        if agent_name == "code_agent":
            agent_graph = create_code_agent(self.llm_service, self.terminal_ui, self.interrupt_queue)
            initial_state = AgentState(messages=[HumanMessage(content=task)])
            try:
                config = {} # No hay limite de recursión específico para code_agent aquí, se usa el default de LangGraph
                final_state = agent_graph.invoke(initial_state, config=config)
                last_message = final_state["messages"][-1]
                return f"Respuesta de {agent_name}:\n{last_message.content}"
            except Exception as e:
                return f"Error al ejecutar {agent_name}: {str(e)}"

        elif agent_name == "researcher_agent":
            console.print("[dim]ℹ️  Invocando al equipo de investigación (ResearcherCrew)...[/dim]")
            
            # Instanciar el LLM para CrewAI usando la configuración de LLMService
            crew_llm = ChatLiteLLM(
                model=self.llm_service.model_name,
                api_key=self.llm_service.api_key,
                temperature=self.llm_service.generation_params.get("temperature", 0.7),
                max_retries=3,
                timeout=120,
            )

            # Preparar las herramientas que la ResearcherCrew necesita

            # Obtener herramientas críticas
            codebase_search = get_valid_tool("codebase_search")
            file_ops = get_valid_tool("file_operations")
            code_analysis = get_valid_tool("code_analysis")
            
            # Verificar herramientas críticas
            if not codebase_search or not file_ops:
                return "Error: No se pudieron cargar las herramientas críticas (codebase_search o file_operations) para el ResearcherCrew."

            crew_tools = {
                "codebase_search": codebase_search,
                "file_ops": file_ops,
                "code_analysis": code_analysis,
                "brave_search": get_valid_tool("brave_search"),
                "web_fetch": get_valid_tool("web_fetch"),
                "web_scraping": get_valid_tool("web_scraping"),
                "github_tool": get_valid_tool("github_tool"),
                "tavily_search": get_valid_tool("tavily_search"),
            }
            
            try:
                # Instanciar la ResearcherCrew con el LLM y las herramientas
                researcher_crew_instance = ResearcherCrew(crew_llm, crew_tools)
                
                # Ejecutar la Crew con la tarea
                console.print(f"[dim]🚀 Iniciando proceso de CrewAI para la tarea: {task[:50]}...[/dim]")
                crew_result = researcher_crew_instance.run(task)
                
                # Asegurarse de que el resultado sea una cadena y no un objeto CrewOutput
                result_str = str(crew_result)
                
                if not result_str.strip():
                    logger.warning("ResearcherCrew devolvió un resultado vacío.")
                    return "Error: El equipo de investigación no pudo generar un resultado. Por favor, intenta ser más específico con la tarea."

                console.print(Panel(
                    Markdown(result_str),
                    title="[bold green]✅ Respuesta Final del Equipo de Investigación[/bold green]",
                    border_style="green",
                    padding=(1, 2)
                ))
                return f"Respuesta del equipo de investigación (ResearcherCrew):\n\n{result_str}"
            except Exception as e:
                error_msg = f"Error al ejecutar ResearcherCrew: {str(e)}"
                logger.error(error_msg)
                return error_msg
        elif agent_name == "code_crew":
            console.print("[dim]ℹ️  Invocando al equipo de desarrollo (CodeCrew)...[/dim]")
            
            # Instanciar el LLM para CrewAI
            crew_llm = ChatLiteLLM(
                model=self.llm_service.model_name,
                api_key=self.llm_service.api_key,
                temperature=self.llm_service.generation_params.get("temperature", 0.7),
                max_retries=3,
                timeout=120,
            )


            # Obtener herramientas necesarias para CodeCrew
            crew_tools = {
                "codebase_search": get_valid_tool("codebase_search"),
                "file_ops": get_valid_tool("file_operations"),
                "advanced_file_editor": get_valid_tool("advanced_file_editor"),
                "python_executor": get_valid_tool("python_executor"),
                "code_analysis": get_valid_tool("code_analysis"),
            }
            
            try:
                code_crew_instance = CodeCrew(crew_llm, crew_tools)
                console.print(f"[dim]🚀 Iniciando proceso de CodeCrew para la tarea: {task[:50]}...[/dim]")
                crew_result = code_crew_instance.run(task)
                
                result_str = str(crew_result)
                if not result_str.strip():
                    return "Error: CodeCrew devolvió un resultado vacío."

                console.print(Panel(
                    Markdown(result_str),
                    title="[bold green]✅ Respuesta Final del Equipo de Desarrollo[/bold green]",
                    border_style="green",
                    padding=(1, 2)
                ))
                return f"Respuesta del equipo de desarrollo (CodeCrew):\n\n{result_str}"
            except Exception as e:
                error_msg = f"Error al ejecutar CodeCrew: {str(e)}"
                logger.error(error_msg)
                return error_msg

        else:
            return f"Error: Agente '{agent_name}' no reconocido. Opciones válidas: 'code_agent', 'researcher_agent', 'code_crew'."

    async def _arun(self, agent_name: str, task: str) -> str:
        # Implementación asíncrona si fuera necesaria, por ahora delegamos a síncrona
        return self._run(agent_name, task)