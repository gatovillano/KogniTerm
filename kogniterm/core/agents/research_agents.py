from crewai import Agent
from typing import Any

class ResearchAgents:
    """Colección de agentes investigadores especializados para KogniTerm."""

    def __init__(self, llm, tools_dict: dict):
        """
        Args:
            llm: Instancia del modelo de lenguaje.
            tools_dict: Diccionario que contiene las herramientas de KogniTerm 
                       (codebase_search, file_ops, code_analysis, etc.)
        """
        self.llm = llm
        self.tools = tools_dict

    def codebase_specialist(self) -> Agent:
        tools = [
            self.tools.get('codebase_search'), 
            self.tools.get('file_ops'),
            self.tools.get('github_tool'),
            self.tools.get('brave_search'),
            self.tools.get('tavily_search')
        ]
        valid_tools = [t for t in tools if t is not None]
        think_tool = self.tools.get('think_tool')
        if think_tool:
            valid_tools.append(think_tool)
        
        return Agent(
            role='Codigo',
            goal='Explorar y entender la estructura del código de KogniTerm para responder consultas técnicas.',
            backstory="""Eres un arquitecto de software experto. Tu habilidad principal es rastrear 
            definiciones y entender cómo interactúan los módulos internos del core.
            
            COLABORACIÓN EXTERNA: Tienes acceso a GitHub. Si detectas que el código local depende de 
            librerías externas o si necesitas comparar una implementación con estándares de la industria, 
            puedes investigar repositorios en GitHub. 
            
            IMPORTANTE: Antes de usar 'github_tool', DEBES usar herramientas de búsqueda para encontrar 
            los nombres reales y exactos de los repositorios (owner/repo).
            
            EFICIENCIA: Cuando analices múltiples archivos locales, usa 'read_many_files' de file_operations.""",
            tools=valid_tools,
            llm=self.llm,
            verbose=True,
            allow_delegation=True
        )

    def static_analyzer(self) -> Agent:
        tools = [self.tools.get('code_analysis')]
        valid_tools = [t for t in tools if t is not None]
        think_tool = self.tools.get('think_tool')
        if think_tool:
            valid_tools.append(think_tool)
        
        return Agent(
            role='Analista',
            goal='Analizar la calidad, complejidad y mantenibilidad del código.',
            backstory="""Experto en QA. Te enfocas en la complejidad ciclomática y en encontrar 
            posibles errores lógicos mediante análisis estático.""",
            tools=valid_tools,
            llm=self.llm,
            verbose=True,
            allow_delegation=True
        )

    def documentation_specialist(self) -> Agent:
        tools = [self.tools.get('file_ops')]
        valid_tools = [t for t in tools if t is not None]
        think_tool = self.tools.get('think_tool')
        if think_tool:
            valid_tools.append(think_tool)
        
        return Agent(
            role='Especialista en Documentación',
            goal='Extraer información de READMEs y especificaciones del proyecto.',
            backstory="""El bibliotecario del proyecto. Sabes dónde están los planes y guías.""",
            tools=valid_tools,
            llm=self.llm,
            verbose=True
        )

    def github_researcher(self) -> Agent:
        tools = [self.tools.get('github_tool'), self.tools.get('brave_search'), self.tools.get('tavily_search'), self.tools.get('web_fetch')]
        valid_tools = [t for t in tools if t is not None]
        think_tool = self.tools.get('think_tool')
        if think_tool:
            valid_tools.append(think_tool)
        
        return Agent(
            role='GitHub',
            goal='Investigar repositorios de GitHub para encontrar implementaciones de referencia, patrones de código y mejores prácticas.',
            backstory="""Eres un investigador experto en código open source. 
            
            IMPORTANTE: Antes de usar las herramientas de GitHub, DEBES usar 'brave_search' o 'tavily_search' 
            para encontrar los nombres reales y exactos de los repositorios (en formato 'propietario/nombre-repo') 
            relacionados con la consulta. No intentes adivinar los nombres.
            
            Una vez tengas los nombres exactos, usa 'github_tool' para:
            - Obtener información detallada (get_repo_info)
            - Listar contenidos y estructura (list_contents)
            - Leer archivos clave (read_file)
            - Analizar el código de forma recursiva (read_recursive_directory)
            
            Tu objetivo es comparar arquitecturas, descubrir patrones de diseño y extraer 
            las mejores prácticas aplicables al problema.""",
            tools=valid_tools,
            llm=self.llm,
            verbose=True,
            allow_delegation=True
        )

    def web_researcher(self) -> Agent:
        tools = [self.tools.get('tavily_search'), self.tools.get('brave_search'), self.tools.get('web_fetch')]
        valid_tools = [t for t in tools if t is not None]
        think_tool = self.tools.get('think_tool')
        if think_tool:
            valid_tools.append(think_tool)
        
        return Agent(
            role='Web',
            goal='Buscar documentación técnica, artículos, tutoriales y discusiones en la web sobre temas relacionados con la consulta.',
            backstory="""Eres un investigador experto en búsqueda de información técnica en internet. 
            Tu especialidad es encontrar documentación oficial, artículos de blog técnicos, 
            discusiones en foros (Stack Overflow, Reddit, GitHub Discussions) y tutoriales relevantes.
            
            Usas tavily_search como tu herramienta principal para búsquedas profundas y estructuradas.
            También tienes brave_search como alternativa y web_fetch para leer contenido específico.
            
            Priorizas fuentes confiables como:
            - Documentación oficial
            - Artículos de desarrolladores reconocidos
            - Discusiones técnicas con soluciones verificadas
            - Tutoriales paso a paso con ejemplos de código
            
            Siempre incluyes enlaces a las fuentes en tu análisis.""",
            tools=valid_tools,
            llm=self.llm,
            verbose=True,
            allow_delegation=True
        )

    