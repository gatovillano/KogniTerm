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

    def _step_callback(self, step):
        """Callback ejecutado tras cada paso de un agente en la Crew."""
        from kogniterm.terminal.visual_components import create_tool_output_panel
        from rich.console import Console
        import logging
        logger = logging.getLogger(__name__)
        console = Console()

        # Intentar extraer información del paso
        try:
            action = getattr(step, 'action', None)
            # En versiones modernas de crewai, el resultado está en 'observation'
            result = getattr(step, 'observation', getattr(step, 'result', None))

            if action and result:
                tool_name = getattr(action, 'tool', 'Unknown Tool')
                tool_input = getattr(action, 'tool_input', None)
                logger.debug(f"DEBUG: Tool called: {tool_name}, input: {tool_input}, result type: {type(result)}")

                output_str = ""
                if isinstance(result, str):
                    output_str = result
                elif isinstance(result, (list, tuple)):
                    items = []
                    for item in result:
                        if hasattr(item, 'content') and isinstance(item.content, str):
                            items.append(item.content)
                        elif isinstance(item, dict):
                            items.append("\n".join([f"  - {k}: {v}" for k, v in item.items()]))
                        else:
                            items.append(str(item))
                    output_str = "\n".join([f"- {item}" for item in items])
                elif isinstance(result, dict):
                    output_str = "\n".join([f"- **{k}**: {v}" for k, v in result.items()])
                elif hasattr(result, 'content') and isinstance(result.content, str):
                    output_str = result.content
                else:
                    output_str = str(result)

                # Imprimir el panel formateado en Markdown
                console.print(create_tool_output_panel(tool_name, output_str))
        except Exception as e:
            logger.error(f"Error in _step_callback: {e}")
            pass

    def run(self, query: str):
        # 1. Definir Agentes
        director = self.director_factory.agent()
        planner = self.planner_factory.agent()
        code_researcher = self.research_factory.codebase_specialist()
        github_researcher = self.research_factory.github_researcher()
        web_researcher = self.research_factory.web_researcher()
        static_analyzer = self.research_factory.static_analyzer()
        doc_specialist = self.research_factory.documentation_specialist()
        synthesizer = self.synthesizer_factory.agent()
        reporter = self.reporter_factory.agent()

        # 2. Definir la Dinámica de Mesa Redonda
        research_task = Task(
            description=f"""Misión: Resolver la consulta '{query}' mediante una investigación colaborativa en mesa redonda.
            
            PROTOCOLO DE EQUIPO:
            1. El Director inicia la sesión y coordina quién empieza.
            2. Los especialistas (Codigo, Web, GitHub, Analista, Documentación) deben investigar sus áreas.
            3. SI NECESITAS CONTEXTO de otro área, PREGUNTA a tu colega.
            4. No trabajes solo. Si encuentras algo interesante, compártelo o pide una segunda opinión.
            5. El Sintetizador y Redactor deben estar atentos a la conversación para capturar la esencia del consenso.
            
            El objetivo es un informe Markdown que sea el resultado de una discusión técnica real.""",
            expected_output="Informe técnico maestro en Markdown, fruto de la colaboración y consulta cruzada.",
            agent=director
        )

        # 3. Orquestar la Crew
        director.allow_delegation = True
        planner.allow_delegation = True
        code_researcher.allow_delegation = True
        github_researcher.allow_delegation = True
        web_researcher.allow_delegation = True
        static_analyzer.allow_delegation = True
        doc_specialist.allow_delegation = True
        synthesizer.allow_delegation = True
        reporter.allow_delegation = True

        crew = Crew(
            agents=[director, planner, code_researcher, github_researcher, web_researcher, static_analyzer, doc_specialist, synthesizer, reporter],
            tasks=[research_task],
            process=Process.sequential,
            verbose=True,
            step_callback=self._step_callback,
            max_rpm=10,
            cache=True
        )

        return crew.kickoff()
