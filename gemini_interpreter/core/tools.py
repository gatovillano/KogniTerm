import os
from langchain_community.utilities import RequestsWrapper
from bs4 import BeautifulSoup
from typing import Any
from typing import Optional
from github import Github, GithubException
from langchain_community.tools import BraveSearch
from langchain_core.tools import BaseTool
from .command_executor import CommandExecutor
import sys
import logging

# Configuración básica del logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- Herramientas de acción ---

def brave_search_tool_wrapper(query: str, api_key: str) -> str:
    """Útil para buscar información actualizada en la web."""
    search_tool = BraveSearch(api_key=api_key)
    return search_tool.run(query)

def web_fetch_wrapper(url: str) -> str:
    """Útil para obtener el contenido HTML de una URL."""
    requests_wrapper = RequestsWrapper()
    try:
        return requests_wrapper.get(url)
    except Exception as e:
        logger.error(f"Error al obtener la URL {url}: {e}", exc_info=True)
        return f"Error al obtener la URL {url}: {e}"

def web_scraping_wrapper(html_content: str, selector: str) -> str:
    """Útil para extraer datos estructurados de una página HTML usando selectores CSS."""
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        elements = soup.select(selector)
        scraped_content = "\n".join([e.prettify() for e in elements])
        return f'''### Resultados del Scraping (Selector: `{selector}`)
```html
{scraped_content}
```'''
    except Exception as e:
        logger.error(f"Error al hacer scraping con selector '{selector}': {e}", exc_info=True)
        return f"Error al hacer scraping: {e}"

def get_github_repo_info_wrapper(repo_name: str, github_token: str) -> str:
    """Obtiene información de un repositorio de GitHub."""
    try:
        g = Github(github_token)
        repo = g.get_user().get_repo(repo_name)
        return f"""### Información del Repositorio: {repo.name}
- **Descripción:** {repo.description}
- **URL:** {repo.html_url}
- **Estrellas:** {repo.stargazers_count} ⭐"""
    except GithubException as e:
        logger.error(f"Error de GitHub al obtener información del repositorio '{repo_name}': {e}", exc_info=True)
        return f"Error de GitHub: {e}"
    except Exception as e:
        logger.error(f"Error inesperado al obtener información del repositorio '{repo_name}': {e}", exc_info=True)
        return f"Error inesperado: {e}"

# Esta función será llamada por interpreter.py para obtener las funciones ejecutables reales
def get_callable_tools():
    return {
        "brave_search_tool_wrapper": brave_search_tool_wrapper,
        "web_fetch_wrapper": web_fetch_wrapper,
        "web_scraping_wrapper": web_scraping_wrapper,
        "get_github_repo_info_wrapper": get_github_repo_info_wrapper,
        "execute_command": ExecuteCommandTool().run
    }

class ExecuteCommandTool(BaseTool):
    name: str = "execute_command"
    description: str = "Ejecuta un comando bash y devuelve su salida."
    
    command_executor: Optional[CommandExecutor] = None

    def model_post_init(self, __context: Any) -> None:
        if self.command_executor is None:
            self.command_executor = CommandExecutor()

    def _run(self, command: str) -> str:
        """Usa el CommandExecutor para ejecutar el comando."""
        logger.debug(f"ExecuteCommandTool - Recibido comando: '{command}'")
        full_output = "" # Initialize full_output here
        assert self.command_executor is not None
        try:
            # Add a message indicating command execution is starting
            print("\n--- Ejecutando comando ---\n", flush=True)
            for chunk in self.command_executor.execute(command):
                print(chunk, end='', flush=True) # Print each chunk immediately
                full_output += chunk # Still collect for the return value
            print("\n--- Comando finalizado ---\n", flush=True) # Add a message indicating command execution is finished
            logger.debug(f"ExecuteCommandTool - Salida del comando: '{full_output}'")
            print(f"\n--- DEBUG: ExecuteCommandTool returning full_output: '{full_output}' ---\n", flush=True) # Added debug print
            return full_output
        except Exception as e:
            error_message = f"ERROR: ExecuteCommandTool - Error al ejecutar el comando '{command}': {type(e).__name__}: {e}"
            print(f"\n--- Error al ejecutar el comando: {e} ---\n", file=sys.stderr, flush=True) # Print error immediately
            logger.error(error_message, exc_info=True)
            return error_message

    def get_command_generator(self, command: str):
        """Devuelve un generador para ejecutar el comando de forma incremental."""
        logger.debug(f"ExecuteCommandTool - Obteniendo generador para comando: '{command}'")
        assert self.command_executor is not None
        return self.command_executor.execute(command)

    async def _arun(self, command: str) -> str:
        """Run the tool asynchronously."""
        raise NotImplementedError("execute_command_tool does not support async")