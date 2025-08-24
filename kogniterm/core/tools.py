import os
from langchain_community.utilities import RequestsWrapper
from bs4 import BeautifulSoup
from typing import Any, Type, Optional, Union
from pydantic import BaseModel, Field
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

class GitHubTool(BaseTool):
    name: str = "github_tool"
    description: str = "Una herramienta unificada para interactuar con repositorios de GitHub. Permite obtener información del repositorio, listar contenidos de directorios, leer archivos y leer directorios recursivamente."

    class GitHubToolInput(BaseModel):
        action: str = Field(description="La acción a realizar: 'get_repo_info', 'list_contents', 'read_file', 'read_directory', 'read_recursive_directory'.")
        repo_name: str = Field(description="El nombre completo del repositorio de GitHub (ej. 'octocat/Spoon-Knife').")
        path: Optional[str] = Field(default="", description="La ruta del archivo o directorio dentro del repositorio (opcional, por defecto la raíz).")
        github_token: Optional[str] = Field(default=None, description="Token de GitHub para autenticación (opcional).")

    args_schema: Type[BaseModel] = GitHubToolInput

    def _get_github_instance(self, github_token: Optional[str]) -> Github:
        if github_token is None:
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                raise ValueError("La variable de entorno 'GITHUB_TOKEN' no está configurada y no se proporcionó un token.")
        return Github(github_token)

    def _get_repo(self, g: Github, repo_name: str):
        try:
            return g.get_repo(repo_name)
        except GithubException as e:
            raise ValueError(f"Error al acceder al repositorio '{repo_name}': {e}")

    def _get_file_content(self, repo, path: str) -> str:
        try:
            file_content = repo.get_contents(path).decoded_content.decode('utf-8')
            return f"### Contenido de '{path}'\n```\n{file_content}\n```"
        except GithubException as e:
            raise ValueError(f"Error al leer el archivo '{path}': {e}")

    def _list_contents(self, repo, path: str) -> str:
        try:
            contents = repo.get_contents(path)
            if not isinstance(contents, list): # Es un solo archivo
                return self._get_file_content(repo, path)
            
            output = f"### Contenidos de '{path}' en '{repo.full_name}'\n"
            for content in contents:
                output += f"- {content.type}: {content.name}\n"
            return output
        except GithubException as e:
            raise ValueError(f"Error al listar contenidos en '{path}': {e}")

    def _read_directory_recursive(self, repo, path: str) -> str:
        output = f"### Contenido recursivo de '{path}' en '{repo.full_name}'\n"
        try:
            contents = repo.get_contents(path)
            if not isinstance(contents, list): # Es un solo archivo
                return self._get_file_content(repo, path)

            for content in contents:
                if content.type == "dir":
                    output += f"\n#### Directorio: {content.path}\n"
                    output += self._read_directory_recursive(repo, content.path)
                else:
                    output += f"- Archivo: {content.path}\n"
                    output += self._get_file_content(repo, content.path) + "\n"
            return output
        except GithubException as e:
            raise ValueError(f"Error al leer recursivamente el directorio '{path}': {e}")

    def _run(self, action: str, repo_name: str, path: Optional[str] = "", github_token: Optional[str] = None) -> str:
        try:
            g = self._get_github_instance(github_token)
            repo = self._get_repo(g, repo_name)

            if action == 'get_repo_info':
                return f"""### Información del Repositorio: {repo.name}\n- **Descripción:** {repo.description}\n- **URL:** {repo.html_url}\n- **Estrellas:** {repo.stargazers_count} ⭐"""
            elif action == 'list_contents':
                return self._list_contents(repo, path)
            elif action == 'read_file':
                return self._get_file_content(repo, path)
            elif action == 'read_directory':
                # Non-recursive read, just list contents and get content for files
                output = f"### Contenido de '{path}' en '{repo.full_name}'\n"
                contents = repo.get_contents(path)
                if not isinstance(contents, list): # Es un solo archivo
                    return self._get_file_content(repo, path)
                for content in contents:
                    if content.type == "file":
                        output += f"- Archivo: {content.path}\n"
                        output += self._get_file_content(repo, content.path) + "\n"
                    else:
                        output += f"- Directorio: {content.path}\n"
                return output
            elif action == 'read_recursive_directory':
                return self._read_directory_recursive(repo, path)
            else:
                return f"Error: Acción de GitHub '{action}' no reconocida."
        except ValueError as e:
            logger.error(f"Error en GitHubTool: {e}", exc_info=True)
            return f"Error en GitHubTool: {e}"
        except Exception as e:
            logger.error(f"Error inesperado en GitHubTool: {e}", exc_info=True)
            return f"Error inesperado en GitHubTool: {e}"

    async def _arun(self, action: str, repo_name: str, path: Optional[str] = "", github_token: Optional[str] = None) -> str:
        raise NotImplementedError("github_tool does not support async")

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
            for chunk in self.command_executor.execute(command):
                full_output += chunk # Still collect for the return value
            logger.debug(f"ExecuteCommandTool - Salida del comando: \"{full_output}\"\n")
            return full_output
        except Exception as e:
            error_message = f"ERROR: ExecuteCommandTool - Error al ejecutar el comando '{command}': {type(e).__name__}: {e}"
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

# Esta función será llamada por interpreter.py para obtener las funciones ejecutables reales
def get_callable_tools():
    return [
        BraveSearchTool(),
        WebFetchTool(),
        WebScrapingTool(),
        GitHubTool(), # Reemplazamos GitHubRepoInfoTool por la nueva GitHubTool
        ExecuteCommandTool()
    ]