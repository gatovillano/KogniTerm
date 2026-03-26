import sys
from crewai import Crew, Process, Task
from .code_crew_agents import CodeCrewAgents
from kogniterm.terminal.command_approval_handler import CommandApprovalHandler

class CodeCrew:
    def __init__(self, llm, tools_dict: dict, approval_handler=None):
        self.agents = CodeCrewAgents(llm, tools_dict, approval_handler=approval_handler)
        self.approval_handler = approval_handler

    def _step_callback(self, step):
        """Callback ejecutado tras cada paso de un agente en la Crew."""
        from kogniterm.terminal.visual_components import create_tool_output_panel
        from rich.console import Console
        console = Console()
        
        # Intentar extraer información del paso
        try:
            # En CrewAI, step es un objeto que contiene la acción y el resultado
            action = getattr(step, 'action', None)
            result = getattr(step, 'result', None)
            
            if action and result:
                tool_name = getattr(action, 'tool', 'Unknown Tool')
                # Imprimir el panel formateado en Markdown
                console.print(create_tool_output_panel(tool_name, str(result)))
        except Exception:
            pass

    async def run(self, requirement: str):
        # 1. Instanciar Agentes
        architect = self.agents.software_architect()
        developer = self.agents.senior_developer()
        qa = self.agents.qa_engineer()

        # 2. Definir Tareas
        design_task = Task(
            description=f"Analizar el siguiente requerimiento y crear un plan de diseño técnico detallado: {requirement}. Define la estructura de archivos, clases y funciones necesarias.",
            expected_output="Un documento de diseño técnico con pseudocódigo y estructura de archivos.",
            agent=architect
        )

        implementation_task = Task(
            description="Implementar el código siguiendo estrictamente el diseño técnico aprobado. Escribe el código real en los archivos correspondientes.",
            expected_output="Código fuente implementado y funcional en los archivos del proyecto.",
            agent=developer,
            context=[design_task]
        )

        review_task = Task(
            description="Revisar el código implementado. Ejecutar análisis estático y verificar que cumpla con los requisitos y estándares de calidad.",
            expected_output="Un informe de QA aprobando los cambios o listando los errores encontrados para corrección.",
            agent=qa,
            context=[implementation_task]
        )

        # 3. Determinar qué tareas ejecutar basándose en el requerimiento
        req_lower = requirement.lower()
        is_only_architecture = any(word in req_lower for word in ["arquitectura", "diseño", "design", "architecture"]) and \
                               not any(word in req_lower for word in ["implementa", "programa", "escribe", "code", "implement"])

        active_tasks = [design_task]
        active_agents = [architect]

        if not is_only_architecture:
            active_tasks.extend([implementation_task, review_task])
            active_agents.extend([developer, qa])

        # 4. Orquestar la Crew
        crew = Crew(
            agents=active_agents,
            tasks=active_tasks,
            process=Process.sequential,
            verbose=True,
            step_callback=self._step_callback,
            max_rpm=10,
            cache=True
        )

        return crew.kickoff()
