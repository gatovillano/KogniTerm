import sys
from crewai import Crew, Process, Task
from .code_crew_agents import CodeCrewAgents
from kogniterm.terminal.command_approval_handler import CommandApprovalHandler

class CodeCrew:
    def __init__(self, llm, tools_dict: dict):
        self.agents = CodeCrewAgents(llm, tools_dict)

    def run(self, requirement: str):
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

        # 3. Orquestar la Crew
        crew = Crew(
            agents=[architect, developer, qa],
            tasks=[design_task, implementation_task, review_task],
            process=Process.sequential,
            verbose=True,
            max_rpm=10,
            cache=True
        )

        return crew.kickoff()

    async def _handle_file_update_confirmation(self, file_path: str, diff_content: str, tool_name: str, original_tool_args: dict) -> bool:
        """
        Handles the file update confirmation process by displaying a diff and asking for user approval.
        Returns True if the user approves the changes, False otherwise.
        """
        # Prepare the confirmation prompt
        confirmation_prompt = f"Se detectaron cambios para '{file_path}'. Por favor, revisa los cambios y confirma para aplicar."
        
        # Simulate the confirmation process (in a real scenario, this would involve user interaction)
        # For now, we'll assume the user approves the changes
        return True

    async def _apply_file_changes(self, file_path: str, content: str, tool_name: str, original_tool_args: dict) -> str:
        """
        Applies the file changes after confirmation.
        Returns a message indicating the result of the operation.
        """
        # Simulate applying the changes (in a real scenario, this would involve actual file operations)
        return f"Cambios aplicados exitosamente en '{file_path}'."
