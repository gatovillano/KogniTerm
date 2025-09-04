import logging
from .tools import ALL_TOOLS # Import ALL_TOOLS from the new directory

# Configuración básica del logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# This function will now instantiate all tools from the ALL_TOOLS list
def get_callable_tools():
    callable_tools = []
    for tool_class in ALL_TOOLS:
        try:
            callable_tools.append(tool_class())
        except Exception as e:
            logger.error(f"Error instantiating tool {tool_class.__name__}: {e}")
    return callable_tools
