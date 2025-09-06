import logging
from .python_executor import PythonTool # Importar la nueva herramienta Python

# Configuración básica del logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Lista para registrar todas las clases de herramientas disponibles para el LLM.
# Aquí se añadirán las clases de las herramientas que se implementen.
ALL_TOOLS = [
    PythonTool, # Añadir PythonTool a la lista de herramientas
]

# Esta función instanciará todas las herramientas de la lista ALL_TOOLS
def get_callable_tools():
    callable_tools = []
    for tool_class in ALL_TOOLS:
        try:
            callable_tools.append(tool_class())
        except Exception as e:
            logger.error(f"Error instanciando la herramienta {tool_class.__name__}: {e}")
    return callable_tools
