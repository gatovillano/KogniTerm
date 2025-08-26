import asyncio
import os
from typing import Any, Type, Optional, Union
from pydantic import BaseModel, Field
from github import GithubException
from github import Github # Importación de PyGithub
from langchain_core.tools import BaseTool # Importación faltante
import logging

logger = logging.getLogger(__name__)

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