from crewai import Agent
from typing import Any

class CodeCrewAgents:
    """Colección de agentes especializados para desarrollo de software en KogniTerm."""

    def __init__(self, llm, tools_dict: dict):
        self.llm = llm
        self.tools = tools_dict

    def software_architect(self) -> Agent:
        return Agent(
            role='Arquitecto de Software Senior',
            goal='Diseñar soluciones técnicas robustas, escalables y bien estructuradas.',
            backstory="""Eres un veterano de la industria con décadas de experiencia. 
            Tu trabajo es analizar los requisitos, descomponer problemas complejos en pasos técnicos 
            y asegurar que la arquitectura del código sea limpia y mantenible. 
            No escribes código directamente, pero guías al equipo sobre CÓMO debe hacerse.""",
            tools=[self.tools.get('codebase_search'), self.tools.get('file_ops')],
            llm=self.llm,
            verbose=True,
            allow_delegation=True,
            max_iter=15
        )

    def senior_developer(self) -> Agent:
        return Agent(
            role='Desarrollador Senior Python/JS',
            goal='Implementar código de alta calidad, eficiente y libre de errores.',
            backstory="""Eres un programador experto. Tu código es elegante, eficiente y sigue 
            estrictamente las mejores prácticas (PEP8, Clean Code). 
            Tu responsabilidad es ejecutar el plan del arquitecto y materializarlo en código funcional.
            Eres extremadamente cuidadoso al editar archivos existentes.""",
            tools=[
                self.tools.get('codebase_search'), 
                self.tools.get('file_ops'), 
                self.tools.get('advanced_file_editor'), 
                self.tools.get('python_executor')
            ],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
            max_iter=15
        )

    def qa_engineer(self) -> Agent:
        return Agent(
            role='Ingeniero de QA y Code Reviewer',
            goal='Asegurar que el código implementado funcione, sea seguro y cumpla los estándares.',
            backstory="""Eres el guardián de la calidad. Revisas cada línea de código escrita por el desarrollador.
            Buscas bugs, problemas de seguridad, falta de manejo de errores y violaciones de estilo.
            Si algo no está perfecto, lo devuelves para corrección.""",
            tools=[
                self.tools.get('code_analysis'), 
                self.tools.get('python_executor'), 
                self.tools.get('file_ops')
            ],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
            max_iter=15
        )
