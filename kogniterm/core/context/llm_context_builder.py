
import os
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime

from kogniterm.core.context.folder_structure_analyzer import FolderStructure
from kogniterm.core.context.workspace_context import WorkspaceContext
from kogniterm.core.context.folder_structure_analyzer import FolderStructureAnalyzer
from kogniterm.core.context.ignore_pattern_manager import IgnorePatternManager
from kogniterm.core.context.git_interaction_module import GitInteractionModule
from kogniterm.core.context.context_indexer import ContextIndexer # Importar ContextIndexer

logger = logging.getLogger(__name__)

class LLMContextBuilder:
    """
    Clase responsable de construir y optimizar el contexto para el LLM,
    recopilando información relevante del WorkspaceContext.
    """

    def __init__(self, workspace_context: WorkspaceContext):
        self.workspace_context = workspace_context
        self.workspace_context.register_llm_context_builder(self) # Registrarse con WorkspaceContext
        self._file_content_cache: Dict[str, str] = {} # Caché para el contenido de los archivos

        # Configuración para la selección de archivos relevantes
        self.priority_extensions = ['.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rb', '.php', '.html', '.css', '.scss', '.json', '.yaml', '.yml', '.xml', '.md', '.txt']
        self.max_file_size_bytes = 100 * 1024 # 100 KB
        self.max_content_length_per_file = 10000 # Caracteres, aproximadamente 2000-3000 tokens

    async def build_context_for_llm(self, task: str, current_conversation: str) -> str:
        """
        Construye un prompt de contexto optimizado para el LLM.

        Args:
            task: La tarea actual que el LLM debe realizar.
            current_conversation: La parte más reciente de la conversación con el usuario.

        Returns:
            Una cadena de texto que representa el contexto optimizado para el LLM.
        """
        context_parts: List[str] = []

        # 1. Información básica del proyecto
        context_parts.append(self._get_basic_project_info())

        # 2. Estructura de carpetas
        context_parts.append(self._get_folder_structure_info())

        # 3. Estado de Git
        context_parts.append(await self._get_git_status_info())

        # 4. Contenido de archivos relevantes (a implementar con selección inteligente)
        context_parts.append(await self._get_relevant_file_contents(task, current_conversation))

        # 5. Memoria de la sesión (conversación anterior, resultados de herramientas)
        context_parts.append(await self._get_session_memory_info())

        # 6. Tarea y conversación actual
        context_parts.append(f"## Tarea Actual\n{task}\n")
        context_parts.append(f"## Conversación Reciente\n{current_conversation}\n")

        final_context = "\n".join(context_parts)
        logger.debug(f"System Message final enviado al LLM:\n{final_context}")
        return final_context

    def _get_basic_project_info(self) -> str:
        """
        Obtiene información básica del proyecto.
        """
        working_dir = self.workspace_context.get_working_directory()
        return f"## Información del Proyecto\nDirectorio de Trabajo: {working_dir}\n"

    def _get_folder_structure_info(self) -> str:
        """
        Obtiene la estructura de carpetas del proyecto.
        """
        if self.workspace_context.folder_structure_analyzer:
            return f"## Estructura de Carpetas\n```\n{self.workspace_context.folder_structure_analyzer.get_tree_representation()}\n```\n"
        return "## Estructura de Carpetas\nNo disponible.\n"

    async def _get_git_status_info(self) -> str:
        """
        Obtiene el estado actual de Git.
        """
        if self.workspace_context.git_interaction_module:
            status = await self.workspace_context.git_interaction_module.get_git_status()
            if status:
                return f"## Estado de Git\n```\n{status}\n```\n"
        return "## Estado de Git\nNo disponible o no es un repositorio Git.\n"

    async def _get_session_memory_info(self) -> str:
        """
        Obtiene el contenido de la memoria de la sesión desde el historial de conversación.
        """
        try:
            conversation_history = self.workspace_context.get_conversation_history()
            if conversation_history:
                # Convertir el historial a una cadena de texto para el LLM
                # Asegurarse de que los mensajes sean representados de forma útil para el LLM
                memory_content_parts = []
                for msg in conversation_history:
                    if hasattr(msg, 'content') and msg.content:
                        memory_content_parts.append(f"{msg.__class__.__name__}: {msg.content}")
                    elif hasattr(msg, 'tool_calls') and msg.tool_calls:
                        memory_content_parts.append(f"{msg.__class__.__name__}: Tool Calls: {msg.tool_calls}")
                    else:
                        memory_content_parts.append(str(msg))
                
                memory_content = "\n".join(memory_content_parts)

                # Truncar si es demasiado largo para no sobrecargar el contexto del LLM
                max_memory_length = self.max_content_length_per_file * 4 # Permitir más memoria de sesión
                if len(memory_content) > max_memory_length:
                    logger.info(f"Memoria de sesión truncada de {len(memory_content)} a {max_memory_length} caracteres.")
                    memory_content = memory_content[:max_memory_length] + "\n... [Memoria de sesión truncada] ..."
                return f"## Memoria de Sesión\n```\n{memory_content}\n```\n"
            else:
                logger.debug("No hay memoria de sesión disponible.")
                return "## Memoria de Sesión\nNo hay memoria de sesión disponible.\n"
        except Exception as e:
            logger.error(f"Error al cargar la memoria de sesión: {e}")
            return "## Memoria de Sesión\nError al cargar la memoria de sesión.\n"

    async def _get_relevant_file_contents(self, task: str, current_conversation: str) -> str:
        """
        Obtiene el contenido de archivos relevantes para la tarea actual, priorizando
        archivos modificados recientemente, aquellos mencionados en la conversación/tarea,
        y aquellos semánticamente similares a la consulta.
        """
        if not self.workspace_context.folder_structure_analyzer:
            return "## Contenido de Archivos Relevantes\nNo disponible (analizador de estructura de carpetas no inicializado).\n"

        all_files = self._get_all_files_from_structure(self.workspace_context.folder_structure_analyzer.structure)
        
        # Filtrar archivos por relevancia básica (extensión y tamaño)
        candidate_files = [f for f in all_files if self._is_file_relevant(f)]

        # Asignar una puntuación de relevancia a cada archivo
        scored_files: Dict[str, float] = {f: 0.0 for f in candidate_files}

        # Puntuación por mención en la tarea o conversación
        for file_path in candidate_files:
            if file_path in task or file_path in current_conversation:
                scored_files[file_path] += 10.0
            elif Path(file_path).name in task or Path(file_path).name in current_conversation:
                scored_files[file_path] += 5.0
            
            # Puntuación por fecha de última modificación (más reciente = mayor puntuación)
            try:
                mod_time = os.path.getmtime(file_path)
                time_diff = datetime.now().timestamp() - mod_time
                # Escala inversa: archivos más recientes tienen menor time_diff, por lo tanto mayor puntuación
                scored_files[file_path] += max(0, 10 - (time_diff / (3600 * 24 * 7))) # Puntuación decrece en 10 puntos por semana
            except OSError as e:
                logger.warning(f"No se pudo obtener la fecha de modificación de {file_path}: {e}")
        
        # Puntuación por similitud semántica usando ContextIndexer
        if self.workspace_context.context_indexer:
            query = f"{task}\n{current_conversation}"
            semantic_scores = await self.workspace_context.context_indexer.search_relevant_files(query, top_k=len(candidate_files))
            for file_path_obj, score in semantic_scores:
                file_path_str = str(file_path_obj)
                if file_path_str in scored_files:
                    scored_files[file_path_str] += score * 10 # Multiplicador para dar más peso a la similitud semántica

        # Convertir a lista de tuplas y ordenar
        sorted_scored_files = sorted(scored_files.items(), key=lambda item: item[1], reverse=True)

        relevant_files_content: List[str] = []
        max_files_to_include = 20 # Aumentar el límite para proporcionar más contexto
        files_included_count = 0

        for file_path, score in sorted_scored_files:
            if files_included_count >= max_files_to_include:
                break
            content = await self._read_file_content(file_path)
            if content:
                relevant_files_content.append(f"### Contenido de {file_path} (Relevancia: {score:.2f})\n```\n{content}\n```\n")
                files_included_count += 1

        if not relevant_files_content:
            return "## Contenido de Archivos Relevantes\nNo se encontraron archivos relevantes o el contenido está vacío.\n"

        return "## Contenido de Archivos Relevantes\n" + "\n".join(relevant_files_content)

    def _get_all_files_from_structure(self, node: FolderStructure) -> List[str]:
        """
        Recorre recursivamente la estructura de carpetas y devuelve una lista de rutas de archivo.
        """
        files: List[str] = []
        if node['type'] == 'file':
            files.append(node['path'])
        elif node['type'] == 'directory':
            for child in node['children']:
                files.extend(self._get_all_files_from_structure(child))
        return files

    def _is_file_relevant(self, file_path: str) -> bool:
        """
        Determina si un archivo es relevante basándose en su extensión y tamaño.
        """
        path = Path(file_path)
        if not path.is_file():
            return False

        # Verificar extensión
        if path.suffix not in self.priority_extensions:
            return False

        # Verificar tamaño del archivo
        try:
            if os.path.getsize(file_path) > self.max_file_size_bytes:
                return False
        except OSError as e:
            logger.warning(f"No se pudo obtener el tamaño del archivo {file_path}: {e}")
            return False

        return True

    async def _read_file_content(self, file_path: str) -> Optional[str]:
        """
        Lee el contenido de un archivo, utilizando caché.
        """
        resolved_path = self.workspace_context.resolvePath(file_path)
        if resolved_path in self._file_content_cache:
            return self._file_content_cache[resolved_path]

        try:
            with open(resolved_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if len(content) > self.max_content_length_per_file:
                    content = content[:self.max_content_length_per_file] + f"\n... [Contenido truncado. Solo se muestran los primeros {self.max_content_length_per_file} caracteres] ..."
                self._file_content_cache[resolved_path] = content
                return content
        except Exception as e:
            logger.warning(f"No se pudo leer el archivo {resolved_path}: {e}")
            return None

    def invalidate_file_cache(self, file_path: str):
        """
        Invalida la caché de un archivo específico.
        """
        resolved_path = self.workspace_context.resolvePath(file_path)
        if resolved_path in self._file_content_cache:
            del self._file_content_cache[resolved_path]
            logger.debug(f"Caché invalidada para: {resolved_path}")

