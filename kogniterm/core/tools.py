import os
from langchain_community.utilities import RequestsWrapper
from bs4 import BeautifulSoup
from typing import Any, Type
from pydantic import BaseModel, Field
from typing import Optional
from github import GithubException
from github import Github # Importación de PyGithub
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

class BraveSearchTool(BaseTool):
    name: str = "brave_search"
    description: str = "Útil para buscar información actualizada en la web."

    class BraveSearchInput(BaseModel):
        query: str = Field(description="La consulta de búsqueda para Brave Search.")

    args_schema: Type[BaseModel] = BraveSearchInput

    def _run(self, query: str) -> str:
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return "Error: La variable de entorno 'BRAVE_SEARCH_API_KEY' no está configurada."
        search_tool = BraveSearch(api_key=api_key)
        return search_tool.run(query)

    async def _arun(self, query: str) -> str:
        raise NotImplementedError("brave_search does not support async")

class WebFetchTool(BaseTool):
    name: str = "web_fetch"
    description: str = "Útil para obtener el contenido HTML de una URL."

    class WebFetchInput(BaseModel):
        url: str = Field(description="La URL de la página web a obtener.")

    args_schema: Type[BaseModel] = WebFetchInput

    def _run(self, url: str) -> str:
        requests_wrapper = RequestsWrapper()
        try:
            return requests_wrapper.get(url)
        except Exception as e:
            logger.error(f"Error al obtener la URL {url}: {e}", exc_info=True)
            return f"Error al obtener la URL {url}: {e}"
    
    async def _arun(self, url: str) -> str:
        raise NotImplementedError("web_fetch does not support async")

class WebScrapingTool(BaseTool):
    name: str = "web_scraping"
    description: str = "Útil para extraer datos estructurados de una página HTML usando selectores CSS."

    class WebScrapingInput(BaseModel):
        html_content: str = Field(description="El contenido HTML de la página.")
        selector: str = Field(description="El selector CSS para extraer los datos.")

    args_schema: Type[BaseModel] = WebScrapingInput

    def _run(self, html_content: str, selector: str) -> str:
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

    async def _arun(self, html_content: str, selector: str) -> str:
        raise NotImplementedError("web_scraping does not support async")


class GitHubRepoInfoTool(BaseTool):
    name: str = "get_github_repo_info"
    description: str = "Obtiene información de un repositorio de GitHub."

    class GitHubRepoInfoInput(BaseModel):
        repo_name: str = Field(description="El nombre completo del repositorio de GitHub (ej. 'octocat/Spoon-Knife').")
        github_token: Optional[str] = Field(default=None, description="Token de GitHub para autenticación (opcional).")

    args_schema: Type[BaseModel] = GitHubRepoInfoInput

    def _run(self, repo_name: str, github_token: Optional[str] = None) -> str:
        if github_token is None:
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                return "Error: La variable de entorno 'GITHUB_TOKEN' no está configurada y no se proporcionó un token."
        try:
            g = Github(github_token)
            repo = g.get_repo(repo_name)
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

    async def _arun(self, repo_name: str, github_token: str) -> str:
        raise NotImplementedError("get_github_repo_info does not support async")

# Esta función será llamada por interpreter.py para obtener las funciones ejecutables reales
def get_callable_tools():
    return [
        BraveSearchTool(),
        WebFetchTool(),
        WebScrapingTool(),
        GitHubRepoInfoTool(),
        ExecuteCommandTool()
    ]

class ExecuteCommandTool(BaseTool):
    name: str = "execute_command"
    description: str = "Ejecuta un comando bash y devuelve su salida."
    
    class ExecuteCommandInput(BaseModel):
        command: str = Field(description="El comando bash a ejecutar.")

    args_schema: Type[BaseModel] = ExecuteCommandInput

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
            logger.debug(f"ExecuteCommandTool - Salida del comando: \"{full_output}\"")
            print(f"\n--- DEBUG: ExecuteCommandTool returning full_output: \"{full_output}\" ---", flush=True)
            return full_output
        except Exception as e:
            error_message = f"ERROR: ExecuteCommandTool - Error al ejecutar el comando '{command}': {type(e).__name__}: {e}"
            print(f"\n--- Error al ejecutar el comando: {e} ---", file=sys.stderr, flush=True) # Print error immediately
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

