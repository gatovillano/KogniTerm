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
            definiciones y entender cómo interactúan los módulos internos de cualquier proyecto.
            
            PROTOCOLO DE RAZONAMIENTO: Antes de iniciar una búsqueda, USA tags <thinking>...</thinking> para definir:
            1. ¿Qué estoy buscando exactamente? (Definiciones, Referencias, Lógica).
            2. ¿Dónde es más probable que esté? (Módulos, Directorios).
            3. Estrategia de búsqueda (Semántica vs Grep).
            
            ALCANCE: No te limites al código de KogniTerm. Eres capaz de analizar cualquier base de código
            en el directorio de trabajo actual. Adaptarte a diferentes lenguajes y estructuras.
            
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
            posibles errores lógicos mediante análisis estático.
            
            PROTOCOLO DE RAZONAMIENTO: Antes de reportar métricas, USA tags <thinking>...</thinking> para interpretar:
            1. ¿Qué significan estos números en este contexto?
            2. ¿Es un falso positivo?
            3. Recomendación de refactorización justificada.""",
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
            goal='Extraer y sintetizar información de todo tipo de documentos (técnicos, negocio, guías).',
            backstory="""El bibliotecario del proyecto. Tu alcance NO se limita a READMEs técnicos.
            Debes ser capaz de procesar y entender documentos de negocio, especificaciones funcionales,
            notas de reuniones y guías de estilo, ya sean cualitativos o cuantitativos.
            
            PROTOCOLO DE RAZONAMIENTO: Usa tags <thinking>...</thinking> para clasificar el tipo de documento
            y definir qué información clave se busca extraer (fechas, requisitos, métricas, etc.).""",
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
            
            PROTOCOLO DE RAZONAMIENTO ESTRICTO:
            1. BÚSQUEDA DE REPOSITORIOS: Usa la acción 'search_repositories' de 'github_tool' para encontrar repositorios relevantes.
               - Esta acción NO requiere 'repo_name', solo 'query'.
               - Ejemplo: action='search_repositories', query='python web framework'
               - Retorna una lista de repositorios con nombre, descripción, estrellas y URL.
            
            2. BÚSQUEDA PREVIA (alternativa): Antes de tocar la 'github_tool', puedes buscar en la web ('brave_search' o 'tavily_search')
               para encontrar el nombre EXACTO y CORRECTO del repositorio (owner/repo). NO ASUMAS NOMBRES.
            
            3. EXPLORACIÓN NO DESTRUCTIVA: NUNCA clones el repositorio completo a menos que sea estrictamente necesario.
               Usa las herramientas de exploración remota ('list_contents', 'read_file', 'read_directory') de 'github_tool'.
               - 'list_contents': Lista archivos y carpetas en una ruta
               - 'read_file': Lee el contenido de un archivo específico
               - 'read_directory': Lee todos los archivos en un directorio
               - 'read_recursive_directory': Lee recursivamente todo el contenido
            
            4. BÚSQUEDA DE CÓDIGO: Usa 'search_code' para buscar código específico DENTRO de un repositorio.
               - Requiere 'repo_name' (formato: 'owner/repo') y 'query'
               - Ejemplo: action='search_code', repo_name='facebook/react', query='useState hook'
            
            5. USA tags <thinking>...</thinking> para justificar la elección del repositorio y tu plan de exploración.
            
            ACCIONES DISPONIBLES EN github_tool:
            - 'search_repositories': Buscar repositorios en GitHub (solo requiere 'query')
            - 'get_repo_info': Obtener información de un repositorio (requiere 'repo_name')
            - 'list_contents': Listar contenidos de un directorio (requiere 'repo_name', opcional 'path')
            - 'read_file': Leer un archivo (requiere 'repo_name' y 'path')
            - 'read_directory': Leer directorio (requiere 'repo_name', opcional 'path')
            - 'read_recursive_directory': Leer recursivamente (requiere 'repo_name', opcional 'path')
            - 'search_code': Buscar código dentro de un repo (requiere 'repo_name' y 'query')""",
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
            backstory="""Eres un investigador experto en búsqueda de información técnica y datos en internet.
            Tu alcance incluye datos cualitativos (opiniones, discusiones, tendencias) y cuantitativos (métricas, benchmarks).
            
            PROTOCOLO DE RAZONAMIENTO: Antes de navegar, USA tags <thinking>...</thinking> para:
            1. Diseñar queries de búsqueda optimizadas para el tipo de dato requerido.
            2. Seleccionar fuentes de autoridad variadas.
            3. Filtrar ruido.
            
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

    