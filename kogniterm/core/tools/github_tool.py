import os
import logging
from typing import Type, Optional, Any
from pydantic import BaseModel, Field
from github import GithubException, Github
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class GitHubTool(BaseTool):
    name: str = "github_tool"
    description: str = "Una herramienta unificada para interactuar con repositorios de GitHub. Permite obtener información del repositorio, listar contenidos de directorios, leer archivos y leer directorios recursivamente."

    class GitHubToolInput(BaseModel):
        action: str = Field(description="La acción a realizar: 'get_repo_info', 'list_contents', 'read_file', 'read_directory', 'read_recursive_directory'.")
        repo_name: str = Field(description="El nombre completo del repositorio de GitHub (ej. 'octocat/Spoon-Knife').")
        path: Optional[str] = Field(default="", description="La ruta del archivo o directorio dentro del repositorio (opcional, por defecto la raíz).")
        github_token: Optional[str] = Field(default=None, description="Token de GitHub para autenticación (opcional).")

    args_schema: Type[BaseModel] = GitHubToolInput

    def get_action_description(self, **kwargs) -> str:
        action = kwargs.get("action")
        repo_name = kwargs.get("repo_name", "")
        path = kwargs.get("path", "")
        
        if action == "get_repo_info":
            return f"Obteniendo info del repo: {repo_name}"
        elif action == "list_contents":
            return f"Listando contenidos de {repo_name}/{path}"
        elif action == "read_file":
            return f"Leyendo archivo de GitHub: {repo_name}/{path}"
        elif action == "read_directory":
            return f"Leyendo directorio de GitHub: {repo_name}/{path}"
        elif action == "read_recursive_directory":
            return f"Leyendo recursivamente GitHub: {repo_name}/{path}"
        return f"Interactuando con GitHub: {repo_name}"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

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

    MAX_GITHUB_FILE_CONTENT_LENGTH: int = 100000 # Limite de caracteres para el contenido del archivo de GitHub

    def _get_file_content(self, repo, path: str) -> str:
        try:
            content_obj = repo.get_contents(path)
            # Intentar decodificar como UTF-8
            try:
                file_content = content_obj.decoded_content.decode('utf-8')
                
                if len(file_content) > self.MAX_GITHUB_FILE_CONTENT_LENGTH:
                    file_content = file_content[:self.MAX_GITHUB_FILE_CONTENT_LENGTH] + f"\n... [Contenido truncado a {self.MAX_GITHUB_FILE_CONTENT_LENGTH} caracteres] ..."

                return f"### Contenido de '{path}'\n```\n{file_content}\n```"
            except UnicodeDecodeError:
                # Si falla la decodificación UTF-8, asumimos que es un archivo binario
                return f"### Contenido de '{path}'\n[Archivo binario. No se puede mostrar el contenido.]"
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
                    output += self._read_directory_recursive(repo, content.path) # Llamada recursiva
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
                return f"""Obteniendo información del repositorio: {repo.full_name}...\n\n### Información del Repositorio: {repo.name}\n- **Descripción:** {repo.description}\n- **URL:** {repo.html_url}\n- **Estrellas:** {repo.stargazers_count} ⭐"""
            elif action == 'list_contents':
                return f"""Listando contenidos en '{path}' del repositorio '{repo.full_name}'...\n\n""" + self._list_contents(repo, str(path))
            elif action == 'read_file':
                return f"""Leyendo archivo '{path}' del repositorio '{repo.full_name}'...\n\n""" + self._get_file_content(repo, str(path))
            elif action == 'read_directory':
                # Non-recursive read, just list contents and get content for files
                output = f"""### Contenido de '{path}' en '{repo.full_name}'\n"""
                contents = repo.get_contents(str(path))
                if not isinstance(contents, list): # Es un solo archivo
                    return f"""Leyendo directorio '{path}' del repositorio '{repo.full_name}'...\n\n""" + self._get_file_content(repo, str(path))
                for content in contents:
                    if content.type == "file":
                        output += f"- Archivo: {content.path}\n"
                        output += self._get_file_content(repo, content.path) + "\n"
                    else:
                        output += f"- Directorio: {content.path}\n"
                return f"""Leyendo directorio '{path}' del repositorio '{repo.full_name}'...\n\n""" + output
            elif action == 'read_recursive_directory':
                return f"""Leyendo directorio recursivamente '{path}' del repositorio '{repo.full_name}'...\n\n""" + self._read_directory_recursive(repo, str(path))
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

# Este archivo ahora es principalmente un marcador de posición, ya que las herramientas
# han sido modularizadas en el subdirectorio 'tools/' y la función
# 'get_callable_tools' se ha movido a 'tools/__init__.py'.
# han sido modularizadas en el subdirectorio 'tools/' y la función
# 'get_callable_tools' se ha movido a 'tools/__init__.py'.
