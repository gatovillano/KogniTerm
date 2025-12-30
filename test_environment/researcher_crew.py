from crewai import Crew, Process, Task
from test_environment.planner_agent import PlannerAgent
from test_environment.research_agents import ResearchAgents
from test_environment.synthesizer_agent import SynthesizerAgent
from test_environment.reporter_agent import ReporterAgent

class ResearcherCrew:
    def __init__(self, llm):
        self.llm = llm
        # Instanciar fábricas de agentes
        self.planner_factory = PlannerAgent(llm)
        self.research_factory = ResearchAgents(llm)
        self.synthesizer_factory = SynthesizerAgent(llm)
        self.reporter_factory = ReporterAgent(llm)

    def run(self, query: str):
        # 1. Definir Agentes
        planner = self.planner_factory.agent()
        code_researcher = self.research_factory.codebase_specialist()
        web_researcher = self.research_factory.internet_researcher()
        synthesizer = self.synthesizer_factory.agent()
        reporter = self.reporter_factory.agent()

        # 2. Definir Tareas
        plan_task = Task(
            description=f"Desglosar la siguiente consulta en un plan de investigación técnica: {query}",
            expected_output="Un plan detallado con objetivos para el investigador de código y el de internet.",
            agent=planner
        )

        research_task = Task(
            description="Ejecutar la investigación siguiendo el plan. Buscar en el código local y en la web.",
            expected_output="Informes detallados de hallazgos, incluyendo archivos revisados, URLs y metodología.",
            agent=code_researcher, # CrewAI permite múltiples agentes en procesos más complejos, aquí simplificamos
            context=[plan_task]
        )

        # Nota: En una Crew secuencial, el contexto fluye. 
        # Añadimos explícitamente al investigador web si es necesario o usamos una lista de tareas.

        synthesis_task = Task(
            description="Extraer los hallazgos de los investigadores y formatearlos en un JSON estructurado con 'agente', 'metodologia', 'hallazgos_clave' y 'referencias'.",
            expected_output="Un objeto JSON puro con la trazabilidad completa de la investigación.",
            agent=synthesizer,
            context=[research_task]
        )

        report_task = Task(
            description="Transformar el JSON de hallazgos en un informe Markdown profesional con secciones de Metodología y Resultados.",
            expected_output="Un informe Markdown completo y bien formateado.",
            agent=reporter,
            context=[synthesis_task]
        )

        # 3. Orquestar la Crew
        crew = Crew(
            agents=[planner, code_researcher, web_researcher, synthesizer, reporter],
            tasks=[plan_task, research_task, synthesis_task, report_task],
            process=Process.sequential,
            verbose=True
        )

        return crew.kickoff()
