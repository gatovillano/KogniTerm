from crewai import Agent

class PlannerAgent:
    def __init__(self, llm, tools_dict: dict = None):
        self.llm = llm
        self.tools = tools_dict or {}

    def agent(self) -> Agent:
        return Agent(
            role='Planificador',
            goal='Diseñar la ruta de investigación y apoyar al equipo con estrategia.',
            backstory="""Eres el cerebro estratégico. Tu especialidad es identificar qué especialistas 
            necesitan intervenir y qué preguntas críticas deben responder. Trabajas codo a codo con el 
            Director para asegurar que no quede ningún cabo suelto.""",
            tools=[self.tools.get('think_tool')] if self.tools.get('think_tool') else [],
            llm=self.llm,
            verbose=True,
            allow_delegation=True
        )

class SynthesizerAgent:
    def __init__(self, llm, tools_dict: dict = None):
        self.llm = llm
        self.tools = tools_dict or {}

    def agent(self) -> Agent:
        return Agent(
            role='Sintetizador',
            goal='Unificar los hallazgos de todos los especialistas en una estructura coherente.',
            backstory="""Eres un experto en procesamiento de información técnica. Tu trabajo es recibir 
            los hallazgos brutos y el análisis de cada especialista (Código, GitHub, Web) y 
            transformarlos en una 'Mini-Investigación' estructurada. 
            
            Para cada especialista que haya intervenido, debes generar un objeto JSON que contenga:
            1. Resumen ejecutivo del hallazgo.
            2. Datos técnicos clave (rutas, fragmentos de código, URLs).
            3. Análisis de impacto.
            4. Conclusiones específicas.
            
            Tu salida debe ser una colección de estas síntesis estructuradas, lista para ser procesada por el Redactor.""",
            tools=[self.tools.get('think_tool')] if self.tools.get('think_tool') else [],
            llm=self.llm,
            verbose=True,
            allow_delegation=True
        )

class ReporterAgent:
    def __init__(self, llm, tools_dict: dict = None):
        self.llm = llm
        self.tools = tools_dict or {}

    def agent(self) -> Agent:
        return Agent(
            role='Redactor',
            goal='Crear el informe final Markdown basado en la inteligencia colectiva del equipo.',
            backstory="""Eres un arquitecto de la comunicación técnica. Tu especialidad es tomar 
            las 'Mini-Investigaciones' estructuradas en JSON que te entrega el Sintetizador y 
            unificarlas en un documento Markdown de alta calidad. 
            
            Debes asegurar que cada bloque de información de los especialistas se presente de forma 
            clara, manteniendo el rigor técnico y proporcionando una narrativa coherente que 
            responda a la consulta original del usuario.""",
            tools=[self.tools.get('think_tool')] if self.tools.get('think_tool') else [],
            llm=self.llm,
            verbose=True,
            allow_delegation=True
        )

class ResearchDirector:
    def __init__(self, llm, tools_dict: dict = None):
        self.llm = llm
        self.tools = tools_dict or {}

    def agent(self) -> Agent:
        return Agent(
            role='Director',
            goal='Moderar la mesa redonda técnica y asegurar que el equipo colabore para hallar la verdad.',
            backstory="""Eres el líder de una unidad de investigación de élite. Tu misión es resolver la consulta del usuario 
            mediante la colaboración extrema. Tienes el poder de decidir quién interviene, pedir a los agentes que 
            se cuestionen entre sí y validar que la información recopilada sea suficiente.
            
            Fomentas que los agentes se envíen mensajes, se pidan datos y discutan hallazgos. 
            Mantienes un 'Estado de Investigación' mental y solo das por finalizada la misión cuando el equipo 
            ha llegado a una conclusión sólida y documentada.""",
            tools=[self.tools.get('think_tool')] if self.tools.get('think_tool') else [],
            llm=self.llm,
            verbose=True,
            allow_delegation=True
        )
