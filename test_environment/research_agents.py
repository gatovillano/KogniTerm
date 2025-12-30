from crewai import Agent
from typing import List, Any


class ResearchAgents:
    """Colección de agentes investigadores especializados."""

    def __init__(self, llm):
        self.llm = llm

    def codebase_specialist(self) -> Agent:
        """Agente experto en analizar el código fuente local."""
        return Agent(
            role='Especialista en Código Base',
            goal='Explorar y entender la estructura del código local para responder consultas técnicas.',
            backstory="""Eres un arquitecto de software experto que conoce cada rincón del proyecto. 
            Tu habilidad principal es rastrear definiciones, encontrar lógica de negocio y entender 
            cómo interactúan los módulos de KogniTerm.""",
            tools=[codebase_search_tool, file_operations],
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

    def static_analyzer(self) -> Agent:
        """Agente experto en calidad y métricas de código."""
        return Agent(
            role='Analista Estático de Código',
            goal='Analizar la complejidad, mantenibilidad y posibles errores en el código Python/JS.',
            backstory="""Eres un experto en QA y optimización. Te enfocas en la complejidad ciclomática, 
            el cumplimiento de PEP8 y en encontrar cuellos de botella en la lógica mediante análisis estático.""",
            tools=[code_analysis],
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

    def documentation_specialist(self) -> Agent:
        """Agente encargado de revisar documentación y archivos Markdown."""
        return Agent(
            role='Especialista en Documentación',
            goal='Extraer información relevante de archivos README, planes y guías del proyecto.',
            backstory="""Eres el bibliotecario del proyecto. Sabes exactamente dónde están los planes 
            de refactorización, los manuales de usuario y las especificaciones técnicas.""",
            tools=[file_operations],
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

    def github_explorer(self) -> Agent:
        """Agente experto en investigar repositorios y tendencias en GitHub."""
        return Agent(
            role='Explorador de GitHub',
            goal='Buscar repositorios, ejemplos de código y mejores prácticas en GitHub relacionadas con la consulta.',
            backstory="""Eres un cazador de código abierto. Sabes encontrar los mejores repositorios, 
            entender arquitecturas ajenas y extraer patrones de diseño que pueden aplicarse a KogniTerm. 
            Te especializas en buscar en la API de GitHub y analizar tendencias tech.""",
            tools=[], # Aquí se integraría la herramienta de búsqueda de GitHub
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

    def internet_researcher(self, search_tool: Any) -> Agent:
        """Agente experto en búsqueda global utilizando Tavily."""
        return Agent(
            role='Investigador de Internet',
            goal='Realizar búsquedas precisas en la web para obtener información actualizada, documentación de librerías y soluciones a errores.',
            backstory="""Eres un experto en OSINT y búsqueda avanzada. Utilizas motores de búsqueda como Tavily 
            para filtrar el ruido de internet y traer solo la información técnica más relevante y veraz. 
            Nada se te escapa en la red.""",
            tools=[search_tool],
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
