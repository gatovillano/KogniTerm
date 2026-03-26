"""
Skill: github
Herramienta unificada para interactuar con repositorios de GitHub
"""

import os
import logging
from typing import Type, Optional, Dict, Any
from pydantic import BaseModel, Field
from github import GithubException, Github
import json

logger = logging.getLogger(__name__)

# Metadata de la herramienta
name = "github"
description = "Una herramienta unificada para interactuar con repositorios de GitHub. Permite obtener información del repositorio, listar contenidos de directorios, leer archivos y leer directorios recursivamente."

class GitHubInput(BaseModel):
    """Schema de entrada para la herramienta github"""
    action: str = Field(description="La acción a realizar: 'get_repo_info', 'list_contents', 'read_file', 'read_directory', 'read_recursive_directory', 'search_repositories', 'search_code'.")
    repo_name: Optional[str] = Field(default=None, description="El nombre completo del repositorio de GitHub (ej. 'octocat/Spoon-Knife'). Requerido para todas las acciones excepto 'search_repositories'.")
    path: Optional[str] = Field(default="", description="La ruta del archivo o directorio dentro del repositorio (opcional, por defecto la raíz).")
    query: Optional[str] = Field(default=None, description="La consulta de búsqueda para las acciones 'search_repositories' o 'search_code'.")
    github_token: Optional[str] = Field(default=None, description="Token de GitHub para autenticación (opcional).")

def _get_github_instance(github_token: Optional[str]) -> Github:
    """Obtener instancia de GitHub"""
    if github_token is None:
        github_token = os.getenv("GITHUB_TOKEN")
    try:
        if github_token:
            return Github(github_token)
        else:
            # Intentar crear una instancia sin autenticación para repositorios públicos
            return Github()
    except GithubException as e:
        raise ValueError(f"Error al crear la instancia de GitHub: {e}")

def _get_repo(g: Github, repo_name: str):
    """Obtener repositorio"""
    try:
        return g.get_repo(repo_name)
    except GithubException as e:
        raise ValueError(f"Error al acceder al repositorio '{repo_name}': {e}")

MAX_GITHUB_FILE_CONTENT_LENGTH = 100000  # Límite de caracteres para el contenido del archivo de GitHub

def _get_file_content(repo, path: str) -> str:
    """Obtener contenido de un archivo"""
    try:
        content_obj = repo.get_contents(path)
        # Intentar decodificar como UTF-8
        try:
            file_content = content_obj.decoded_content.decode('utf-8')
            
            if len(file_content) > MAX_GITHUB_FILE_CONTENT_LENGTH:
                file_content = file_content[:MAX_GITHUB_FILE_CONTENT_LENGTH] + f"\n... [Contenido truncado a {MAX_GITHUB_FILE_CONTENT_LENGTH} caracteres] ..."

            return f"### Contenido de '{path}'\n```\n{file_content}\n```"
        except UnicodeDecodeError:
            # Si falla la decodificación UTF-8, asumimos que es un archivo binario
            return f"### Contenido de '{path}'\n[Archivo binario. No se puede mostrar el contenido.]"
    except GithubException as e:
        raise ValueError(f"Error al leer el archivo '{path}': {e}")

def _list_contents(repo, path: str) -> str:
    """Listar contenidos de un directorio"""
    try:
        contents = repo.get_contents(path)
        if not isinstance(contents, list):  # Es un solo archivo
            return _get_file_content(repo, path)
        
        output = f"### Contenidos de '{path}' en '{repo.full_name}'\n"
        for content in contents:
            output += f"- {content.type}: {content.name}\n"
        return output
    except GithubException as e:
        raise ValueError(f"Error al listar contenidos en '{path}': {e}")

def _read_directory_recursive(repo, path: str) -> str:
    """Leer directorio recursivamente"""
    output = f"### Contenido recursivo de '{path}' en '{repo.full_name}'\n"
    try:
        contents = repo.get_contents(path)
        if not isinstance(contents, list):  # Es un solo archivo
            return _get_file_content(repo, path)

        for content in contents:
            if content.type == "dir":
                output += f"\n#### Directorio: {content.path}\n"
                output += _read_directory_recursive(repo, content.path)  # Llamada recursiva
            else:
                output += f"- Archivo: {content.path}\n"
                output += _get_file_content(repo, content.path) + "\n"
        return output
    except GithubException as e:
        raise ValueError(f"Error al leer recursivamente el directorio '{path}': {e}")

def _search_repositories(g: Github, query: str) -> str:
    """Buscar repositorios"""
    try:
        repositories = g.search_repositories(query=query)
        output = f"## Fuentes\n\n### Resultados de búsqueda de repositorios para '{query}'\n"
        count = 0
        for repo in repositories:
            if count >= 10: break
            output += f"- **{repo.full_name}**: {repo.description} (Estrellas: {repo.stargazers_count}) - [Link]({repo.html_url})\n"
            count += 1
        if count == 0:
            output += "No se encontraron repositorios."
        return output
    except GithubException as e:
        raise ValueError(f"Error al buscar repositorios: {e}")

def _search_code(g: Github, repo_name: str, query: str) -> str:
    """Buscar código en un repositorio"""
    try:
        # Scoping to the repository
        full_query = f"{query} repo:{repo_name}"
        code_results = g.search_code(query=full_query)
        output = f"## Fuentes\n\n### Resultados de búsqueda de código para '{query}' en '{repo_name}'\n"
        count = 0
        for content_file in code_results:
            if count >= 10: break
            output += f"- [{content_file.path}]({content_file.html_url})\n"
            count += 1
        if count == 0:
            output += "No se encontraron resultados de código."
        return output
    except GithubException as e:
        raise ValueError(f"Error al buscar código: {e}")

def github(action: str, repo_name: Optional[str] = None, path: Optional[str] = "", query: Optional[str] = None, github_token: Optional[str] = None) -> str:
    """
    Función principal que implementa la funcionalidad de github
    
    Args:
        action: La acción a realizar
        repo_name: Nombre del repositorio
        path: Ruta del archivo o directorio
        query: Consulta de búsqueda
        github_token: Token de GitHub
    
    Returns:
        str: Resultado de la operación
    """
    try:
        g = _get_github_instance(github_token)

        if action == 'search_repositories':
            if not query:
                return "Error: Se requiere 'query' para buscar repositorios."
            return _search_repositories(g, query)

        if action == 'search_code':
            if not query:
                return "Error: Se requiere 'query' para buscar código."
            
            # Si hay repo_name, buscamos en ese repo; si no, búsqueda global
            if repo_name:
                return _search_code(g, repo_name, query)
            else:
                return _search_code_global(g, query)

        # Para el resto de acciones (lectura e info), repo_name es obligatorio
        if not repo_name:
            return f"Error: 'repo_name' es requerido para la acción '{action}'."

        repo = _get_repo(g, repo_name)

        if action == 'get_repo_info':
            return f"""Obteniendo información del repositorio: {repo.full_name}...\n\n### Información del Repositorio: {repo.name}\n- **Descripción:** {repo.description}\n- **URL:** {repo.html_url}\n- **Estrellas:** {repo.stargazers_count} ⭐"""
        elif action == 'list_contents':
            return f"""Listando contenidos en '{path}' del repositorio '{repo.full_name}'...\n\n""" + _list_contents(repo, str(path))
        elif action == 'read_file':
            return f"""Leyendo archivo '{path}' del repositorio '{repo.full_name}'...\n\n""" + _get_file_content(repo, str(path))
        elif action == 'read_directory':
            # Non-recursive read, just list contents and get content for files
            output = f"""### Contenido de '{path}' en '{repo.full_name}'\n"""
            contents = repo.get_contents(str(path))
            if not isinstance(contents, list):  # Es un solo archivo
                return f"""Leyendo directorio '{path}' del repositorio '{repo.full_name}'...\n\n""" + _get_file_content(repo, str(path))
            for content in contents:
                if content.type == "file":
                    output += f"- Archivo: {content.path}\n"
                    output += _get_file_content(repo, content.path) + "\n"
                else:
                    output += f"- Directorio: {content.path}\n"
            return f"""Leyendo directorio '{path}' del repositorio '{repo.full_name}'...\n\n""" + output
        elif action == 'read_recursive_directory':
            return f"""Leyendo directorio recursivamente '{path}' del repositorio '{repo.full_name}'...\n\n""" + _read_directory_recursive(repo, str(path))
        else:
            return f"Error: Acción de GitHub '{action}' no reconocida."
    except ValueError as e:
        logger.error(f"Error en GitHubTool: {e}", exc_info=True)
        return f"Error en GitHubTool: {e}"
    except Exception as e:
        logger.error(f"Error inesperado en GitHubTool: {e}", exc_info=True)
        return f"Error inesperado en GitHubTool: {e}"

def _search_code_global(g: Github, query: str) -> str:
    """Buscar código de forma global en GitHub"""
    try:
        code_results = g.search_code(query=query)
        output = f"## Fuentes\n\n### Resultados de búsqueda global de código para '{query}'\n"
        count = 0
        for content_file in code_results:
            if count >= 10: break
            output += f"- [{content_file.repository.full_name}: {content_file.path}]({content_file.html_url})\n"
            count += 1
        if count == 0:
            output += "No se encontraron resultados de código."
        return output
    except GithubException as e:
        raise ValueError(f"Error al buscar código globalmente: {e}")

# Schema para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": "La acción a realizar: 'get_repo_info', 'list_contents', 'read_file', 'read_directory', 'read_recursive_directory', 'search_repositories', 'search_code'.",
            "enum": ["get_repo_info", "list_contents", "read_file", "read_directory", "read_recursive_directory", "search_repositories", "search_code"]
        },
        "repo_name": {
            "type": "string",
            "description": "El nombre completo del repositorio de GitHub (ej. 'octocat/Spoon-Knife'). Requerido para acciones de lectura e información de repositorio específico."
        },
        "path": {
            "type": "string",
            "description": "La ruta del archivo o directorio dentro del repositorio (opcional, por defecto la raíz).",
            "default": ""
        },
        "query": {
            "type": "string",
            "description": "La consulta de búsqueda para las acciones 'search_repositories' o 'search_code'."
        },
        "github_token": {
            "type": "string",
            "description": "Token de GitHub para autenticación (opcional)."
        }
    },
    "required": ["action"]
}
