from crewai import Crew, Process, Task
from .research_agents import ResearchAgents
from .specialized_agents import PlannerAgent, SynthesizerAgent, ReporterAgent, ResearchDirector

class ResearcherCrew:
    def __init__(self, llm, tools_dict: dict):
        self.llm = llm
        self.tools = tools_dict
        
        # Instanciar fábricas de agentes
        self.planner_factory = PlannerAgent(llm, tools_dict)
        self.research_factory = ResearchAgents(llm, tools_dict)
        self.synthesizer_factory = SynthesizerAgent(llm, tools_dict)
        self.reporter_factory = ReporterAgent(llm, tools_dict)
        self.director_factory = ResearchDirector(llm, tools_dict)

    def run(self, query: str):
        # 0. Generar árbol de directorios del proyecto como contexto inicial
        project_tree = ""
        try:
            file_ops_tool = self.tools.get('file_ops')
            if file_ops_tool:
                import os
                project_root = os.getcwd()
                tree_result = file_ops_tool.run({
                    "operation": "list_directory",
                    "path": project_root,
                    "recursive": True
                })
                # list_directory recursivo devuelve un string con líneas separadas por \n
                if isinstance(tree_result, str):
                    tree_lines = tree_result.split('\n')[:100]  # Limitar a 100 líneas
                    project_tree = f"\n\n**Estructura del Proyecto (primeras 100 entradas):**\n```\n{chr(10).join(tree_lines)}\n```\n"
                elif isinstance(tree_result, list):
                    # Si por alguna razón devuelve una lista directamente
                    tree_lines = tree_result[:100]
                    project_tree = f"\n\n**Estructura del Proyecto (primeras 100 entradas):**\n```\n{chr(10).join(tree_lines)}\n```\n"
        except Exception as e:
            project_tree = f"\n\n(No se pudo generar el árbol de directorios: {e})\n"
        
        # 1. Definir Agentes
        director = self.director_factory.agent()
        planner = self.planner_factory.agent()
        code_researcher = self.research_factory.codebase_specialist()
        github_researcher = self.research_factory.github_researcher()
        web_researcher = self.research_factory.web_researcher()
        static_analyzer = self.research_factory.static_analyzer()
        synthesizer = self.synthesizer_factory.agent()
        reporter = self.reporter_factory.agent()

        # 2. Definir la Dinámica de Mesa Redonda
        # Todos los agentes pueden consultarse entre sí.
        
        research_task = Task(
            description=f"""Misión: Resolver la consulta '{query}' mediante una investigación colaborativa en mesa redonda.
            
            PROTOCOLO DE EQUIPO:
            1. El Director inicia la sesión y coordina quién empieza.
            2. Los especialistas (Codigo, Web, GitHub, Analista) deben investigar sus áreas.
            3. SI NECESITAS CONTEXTO de otro área, PREGUNTA a tu colega (ej: Codigo pregunta a Web sobre una librería).
            4. No trabajes solo. Si encuentras algo interesante, compártelo o pide una segunda opinión.
            5. El Sintetizador y Redactor deben estar atentos a la conversación para capturar la esencia del consenso.
            
{project_tree}

            El objetivo es un informe Markdown que sea el resultado de una discusión técnica real.""",
            expected_output="Informe técnico maestro en Markdown, fruto de la colaboración y consulta cruzada.",
            agent=director
        )

        # 3. Orquestar la Crew (Mesa Redonda)
        # Habilitamos delegación para TODOS para permitir preguntas cruzadas
        director.allow_delegation = True
        planner.allow_delegation = True
        code_researcher.allow_delegation = True
        github_researcher.allow_delegation = True
        web_researcher.allow_delegation = True
        static_analyzer.allow_delegation = True
        synthesizer.allow_delegation = True
        reporter.allow_delegation = True

        crew = Crew(
            agents=[director, planner, code_researcher, github_researcher, web_researcher, static_analyzer, synthesizer, reporter],
            tasks=[research_task],
            process=Process.sequential, # Secuencial para orden, pero con delegación libre para charla
            verbose=True,
            max_rpm=10,
            cache=True
        )

        return crew.kickoff()
