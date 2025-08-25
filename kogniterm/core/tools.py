import asyncio
import os
import difflib
import json
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
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return "Error: La variable de entorno 'BRAVE_SEARCH_API_KEY' no está configurada."
        search_tool = BraveSearch(api_key=api_key)
        # BraveSearch no tiene un método arun nativo en todas las versiones, usamos to_thread por seguridad
        return await asyncio.to_thread(search_tool.run, query)

class WebFetchTool(BaseTool):
    name: str = "web_fetch"
    description: str = "Útil para obtener el contenido HTML de una URL."

    class WebFetchInput(BaseModel):
        url: str = Field(description="La URL de la página web a obtener.")

    args_schema: Type[BaseModel] = WebFetchInput

    def _run(self, url: str) -> str:
        requests_wrapper = RequestsWrapper()
        try:
            response = requests_wrapper.get(url)
            if isinstance(response, dict) and 'text' in response:
                return response['text']
            return str(response)
        except Exception as e:
            logger.error(f"Error al obtener la URL {url}: {e}", exc_info=True)
            return f"Error al obtener la URL {url}: {e}"
    
    async def _arun(self, url: str) -> str:
        requests_wrapper = RequestsWrapper()
        try:
            return await asyncio.to_thread(requests_wrapper.get, url)
        except Exception as e:
            logger.error(f"Error al obtener la URL {url} de forma asíncrona: {e}", exc_info=True)
            return f"Error al obtener la URL {url}: {e}"

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
            # Asegurarse de que prettify() devuelva str, o manejar bytes si es el caso
            scraped_content_list = []
            for e in elements:
                pretty_e = e.prettify()
                if isinstance(pretty_e, bytes):
                    scraped_content_list.append(pretty_e.decode('utf-8', errors='ignore'))
                else:
                    scraped_content_list.append(pretty_e)
            
            scraped_content = "\n".join(scraped_content_list)
            
            return f'''### Resultados del Scraping (Selector: `{selector}`)
```html
{scraped_content}
```'''
        except Exception as e:
            logger.error(f"Error al hacer scraping con selector '{selector}': {e}", exc_info=True)
            return f"Error al hacer scraping: {e}"

    async def _arun(self, html_content: str, selector: str) -> str:
        return await asyncio.to_thread(self._run, html_content, selector)

class GitHubTool(BaseTool):
    name: str = "github_tool"
    description: str = "Una herramienta unificada para interactuar con repositorios de GitHub. Permite obtener información del repositorio, listar contenidos de directorios, leer archivos y leer directorios recursivamente."

    class GitHubToolInput(BaseModel):
        action: str = Field(description="La acción a realizar: 'get_repo_info', 'list_contents', 'read_file', 'read_directory', 'read_recursive_directory'.")
        repo_name: str = Field(description="El nombre completo del repositorio de GitHub (ej. 'octocat/Spoon-Knife').")
        path: Optional[str] = Field(default=None, description="La ruta del archivo o directorio dentro del repositorio (opcional, por defecto la raíz).")
        github_token: Optional[str] = Field(default=None, description="Token de GitHub para autenticación (opcional).")

    args_schema: Type[BaseModel] = GitHubToolInput

    def _get_github_instance(self, github_token: Optional[str]) -> Github:
        if github_token is None:
            logger.debug("GitHubTool: No se proporcionó un token, buscando en las variables de entorno...")
            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                logger.error("GitHubTool: No se encontró el token en la variable de entorno 'GITHUB_TOKEN'.")
                raise ValueError("La variable de entorno 'GITHUB_TOKEN' no está configurada y no se proporcionó un token.")
            else:
                logger.debug("GitHubTool: Token encontrado en la variable de entorno.")
        else:
            logger.debug("GitHubTool: Usando el token proporcionado en los argumentos.")
        return Github(github_token)

    def _get_repo(self, g: Github, repo_name: str):
        try:
            return g.get_repo(repo_name)
        except GithubException as e:
            raise ValueError(f"Error al acceder al repositorio '{repo_name}': {e}")

    def _get_file_content(self, repo, path: str) -> str:
        try:
            # Asegurarse de que path no sea None
            if path is None:
                raise ValueError("La ruta del archivo no puede ser None.")
            
            content_file = repo.get_contents(path)
            
            # Manejar archivos con codificación 'none' (p. ej., vacíos o binarios)
            if content_file.encoding == 'none':
                return f"### Contenido de '{path}' (no se pudo decodificar, podría ser binario o estar vacío)\n"
            
            file_content = content_file.decoded_content.decode('utf-8')
            return f"### Contenido de '{path}'\n```\n{file_content}\n```"
        except GithubException as e:
            raise ValueError(f"Error al leer el archivo '{path}': {e}")

    def _list_contents(self, repo, path: str) -> str:
        try:
            # Asegurarse de que path no sea None
            if path is None:
                raise ValueError("La ruta del directorio no puede ser None.")
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
            # Asegurarse de que path no sea None
            if path is None:
                raise ValueError("La ruta del directorio no puede ser None.")
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

    def _run(self, action: str, repo_name: str, path: Optional[str] = None, github_token: Optional[str] = None) -> str:
        try:
            g = self._get_github_instance(github_token)
            repo = self._get_repo(g, repo_name)

            # Asegurarse de que path sea una cadena vacía si es None para evitar errores en get_contents
            effective_path = path if path is not None else ""

            if action == 'get_repo_info':
                return f"""### Información del Repositorio: {repo.name}\n- **Descripción:** {repo.description}\n- **URL:** {repo.html_url}\n- **Estrellas:** {repo.stargazers_count} ⭐"""
            elif action == 'list_contents':
                return self._list_contents(repo, effective_path)
            elif action == 'read_file':
                return self._get_file_content(repo, effective_path)
            elif action == 'read_directory':
                # Non-recursive read, just list contents and get content for files
                output = f"### Contenido de '{effective_path}' en '{repo.full_name}'\n"
                contents = repo.get_contents(effective_path)
                if not isinstance(contents, list): # Es un solo archivo
                    return self._get_file_content(repo, effective_path)
                for content in contents:
                    if content.type == "file":
                        output += f"- Archivo: {content.path}\n"
                        output += self._get_file_content(repo, content.path) + "\n"
                    else:
                        output += f"- Directorio: {content.path}\n"
                return output
            elif action == 'read_recursive_directory':
                return self._read_directory_recursive(repo, effective_path)
            else:
                return f"Error: Acción de GitHub '{action}' no reconocida."
        except ValueError as e:
            logger.error(f"Error en GitHubTool: {e}", exc_info=True)
            return f"Error en GitHubTool: {e}"
        except Exception as e:
            logger.error(f"Error inesperado en GitHubTool: {e}", exc_info=True)
            return f"Error inesperado en GitHubTool: {e}"

    async def _arun(self, action: str, repo_name: str, path: Optional[str] = "", github_token: Optional[str] = None) -> str:
        return await asyncio.to_thread(self._run, action, repo_name, path, github_token)

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

    async def _arun(self, command: str) -> str:
        """Run the tool asynchronously."""
        # Por ahora, ejecutamos la versión síncrona en un hilo separado.
        # Una futura mejora sería hacer que CommandExecutor sea completamente asíncrono.
        return await asyncio.to_thread(self._run, command)

class FileCRUDTool(BaseTool):
    name: str = "file_crud_tool"
    description: str = "Una herramienta para realizar operaciones CRUD (Crear, Leer, Actualizar, Eliminar) en archivos."

    class FileCRUDInput(BaseModel):
        action: str = Field(description="La acción a realizar: 'create', 'read', 'update', 'delete'.")
        path: str = Field(description="La ruta del archivo.")
        content: Optional[str] = Field(default=None, description="El contenido del archivo para las acciones 'create' y 'update'.")
        confirm: Optional[bool] = Field(default=False, description="Confirmación para la acción 'update'.")

    args_schema: Type[BaseModel] = FileCRUDInput

    def _run(self, action: str, path: str, content: Optional[str] = None, confirm: Optional[bool] = False) -> str:
        try:
            if action == 'create':
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'w') as f:
                    f.write(content if content is not None else "")
                return f"Archivo '{path}' creado/sobrescrito exitosamente."
            elif action == 'read':
                with open(path, 'r') as f:
                    file_content = f.read()
                return f"### Contenido de '{path}'\n```\n{file_content}\n```"
            elif action == 'update':
                if not os.path.exists(path):
                    return f"Error: El archivo '{path}' no existe para actualizar."
                
                with open(path, 'r') as f:
                    old_content = f.read()

                if content is None:
                    return "Error: El contenido no puede ser None para la acción 'update'."

                if not confirm:
                    diff = list(difflib.unified_diff(
                        old_content.splitlines(keepends=True),
                        content.splitlines(keepends=True),
                        fromfile=f'a/{path}',
                        tofile=f'b/{path}',
                    ))
                    if not diff:
                        return f"No hay cambios detectados para '{path}'. No se requiere actualización."
                    
                    diff_output = "".join(diff)
                    return json.dumps({
                        "status": "pending_confirmation",
                        "message": f"Se detectaron cambios para '{path}'. Por favor, confirma para aplicar:",
                        "diff": diff_output
                    })
                else:
                    with open(path, 'w') as f:
                        f.write(content)
                    return f"Archivo '{path}' actualizado exitosamente."
            elif action == 'delete':
                os.remove(path)
                return f"Archivo '{path}' eliminado exitosamente."
            else:
                return f"Error: Acción de FileCRUDTool '{action}' no reconocida."
        except FileNotFoundError:
            return f"Error: El archivo o directorio '{path}' no fue encontrado."
        except Exception as e:
            logger.error(f"Error en FileCRUDTool al realizar la acción '{action}' en '{path}': {e}", exc_info=True)
            return f"Error en FileCRUDTool: {e}"

    async def _arun(self, action: str, path: str, content: Optional[str] = None, confirm: Optional[bool] = False) -> str:
        return await asyncio.to_thread(self._run, action, path, content, confirm)

# Esta función será llamada por interpreter.py para obtener las funciones ejecutables reales
def get_callable_tools():
    return [
        BraveSearchTool(),
        WebFetchTool(),
        WebScrapingTool(),
        GitHubTool(), # Reemplazamos GitHubRepoInfoTool por la nueva GitHubTool
        ExecuteCommandTool(),
        FileCRUDTool()
    ]
