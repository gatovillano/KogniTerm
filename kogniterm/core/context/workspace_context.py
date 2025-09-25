import os
import logging
from pathlib import Path
from typing import List, Callable, Optional, Any
from pydantic import BaseModel, Field
from kogniterm.core.context.file_system_watcher import FileSystemWatcher
from kogniterm.core.context.config_file_analyzer import ConfigFileAnalyzer, parsePackageJson, parseTsconfigJson, parseEslintrcJson
from kogniterm.core.context.folder_structure_analyzer import FolderStructureAnalyzer
from kogniterm.core.context.git_interaction_module import GitInteractionModule
from kogniterm.core.context.ignore_pattern_manager import IgnorePatternManager
from kogniterm.core.context.path_manager import PathManager
from kogniterm.core.context.context_indexer import ContextIndexer # Importar ContextIndexer

logger = logging.getLogger(__name__)

class WorkspaceContext(BaseModel):
    watch_workspace: bool = False
    ignore_patterns: List[str] = Field(default_factory=list)
    directories: List[Path] = Field(default_factory=list, exclude=True)
    callbacks: List[Callable[[], None]] = Field(default_factory=list, exclude=True)
    file_system_watcher: Optional[FileSystemWatcher] = Field(default=None, exclude=True)
    ignore_pattern_manager: IgnorePatternManager = Field(default_factory=IgnorePatternManager, exclude=True)
    folder_structure_analyzer: Optional[FolderStructureAnalyzer] = Field(default=None, exclude=True)
    config_file_analyzer: ConfigFileAnalyzer = Field(default_factory=ConfigFileAnalyzer, exclude=True)
    git_interaction_module: Optional[GitInteractionModule] = Field(default=None, exclude=True)
    path_manager: PathManager = Field(default_factory=lambda: PathManager([]), exclude=True)
    llm_context_builder: Any = Field(default=None, exclude=True) # Usamos Any para evitar dependencia circular
    context_indexer: Optional[ContextIndexer] = Field(default=None, exclude=True) # Añadir ContextIndexer
    llm_service_ref: Any = Field(default=None, exclude=True) # Referencia al LLMService para acceder al historial

    class Config:
        arbitrary_types_allowed = True

    def __post_init__(self):
        if self.directories:
            self.path_manager = PathManager(self.directories)
            self._initialize_modules() # Inicializar módulos aquí
        if self.watch_workspace:
            self._start_file_system_watcher()

    def _initialize_modules(self):
        if self.directories:
            main_directory = str(self.directories[0])
            self.ignore_pattern_manager = IgnorePatternManager()
            self.git_interaction_module = GitInteractionModule(main_directory)
            self.git_interaction_module.update_tracked_files()
            self._reinitialize_ignore_patterns_and_folder_structure(main_directory) # Nueva llamada
            # pylint: disable=no-member
            self.config_file_analyzer.find_and_parse_config_files(main_directory, self.ignore_pattern_manager.get_ignore_patterns(main_directory))
            self.context_indexer = ContextIndexer(Path(main_directory)) # Inicializar ContextIndexer
        else:
            logger.warning("No hay directorios configurados para inicializar los módulos.")

    def _reinitialize_ignore_patterns_and_folder_structure(self, main_directory: str):
        self.ignore_pattern_manager = IgnorePatternManager() # Reinicializar para recargar patrones
        self.folder_structure_analyzer = FolderStructureAnalyzer(
            main_directory,
            self.ignore_pattern_manager
        )

    def _update_folder_structure(self):
        if self.directories:
            main_directory = str(self.directories[0])
            self._reinitialize_ignore_patterns_and_folder_structure(main_directory) # Llamar al nuevo método
            self.git_interaction_module.update_tracked_files() # Solo actualizar Git si es necesario
        else:
            logger.warning("No hay directorios configurados para actualizar la estructura de carpetas.")

    def _notify_callbacks(self):
        for callback in self.callbacks:
            callback()

    def handle_file_system_event(self, event_type: str, src_path: str, dest_path: Optional[str] = None):
        """
        Maneja los eventos del sistema de archivos y actualiza el contexto del proyecto.
        """
        if self.ignore_pattern_manager.check_ignored(src_path, self.get_working_directory()):
            logger.debug(f"Evento en ruta ignorada: {src_path}. Saltando procesamiento.")
            return
        
        if self.folder_structure_analyzer:
            if event_type == 'created':
                self.folder_structure_analyzer.on_created(src_path)
            elif event_type == 'deleted':
                self.folder_structure_analyzer.on_deleted(src_path)
            elif event_type == 'moved':
                if dest_path:
                    self.folder_structure_analyzer.on_moved(src_path, dest_path)
            elif event_type == 'modified':
                if self.llm_context_builder:
                    self.llm_context_builder.invalidate_file_cache(src_path)
        
        file_path = Path(src_path)
        
        # Recargar archivos de configuración
        # pylint: disable=no-member
        if self.config_file_analyzer.is_config_file(file_path.name):
            # pylint: disable=no-member
            self.config_file_analyzer.handle_config_change(str(file_path))

        # Actualizar el estado de Git si el módulo está inicializado
        if self.git_interaction_module:
            # Solo reaccionar a cambios en archivos rastreados por Git
            if self.git_interaction_module.is_tracked(str(file_path)):
                logger.debug(f"El archivo {src_path} ha cambiado, actualizando el estado de Git.")
            else:
                logger.debug(f"Cambio en {src_path} ignorado, no rastreado por Git.")

        # Gestionar patrones de ignorado si .gitignore cambia
        if file_path.name == ".gitignore":
            logger.debug(".gitignore modificado. Recargando patrones de ignorado.")
            self._update_folder_structure()

        self._notify_callbacks()

    def _start_file_system_watcher(self):
        if self.file_system_watcher:
            self.file_system_watcher.stop()
        
        # Observar todos los directorios del workspace
        if self.directories:
            # Para simplificar, observamos el primer directorio del workspace.
            # En una implementación más robusta, se podría observar cada directorio
            # o un directorio raíz común.
            directory_to_watch = str(self.directories[0])
            patterns_for_watcher = self.ignore_pattern_manager.get_ignore_patterns(directory_to_watch)
            logger.debug(f"Patrones de ignorado pasados a FileSystemWatcher para {directory_to_watch}: {patterns_for_watcher}")
            self.file_system_watcher = FileSystemWatcher(
                directory=directory_to_watch,
                callback=self.handle_file_system_event,
                ignore_patterns=patterns_for_watcher
            )
            self.file_system_watcher.start()

    def _stop_file_system_watcher(self):
        if self.file_system_watcher:
            self.file_system_watcher.stop()
            self.file_system_watcher = None

    def get_working_directory(self) -> str:
        """Devuelve el directorio de trabajo principal del workspace."""
        if self.directories:
            return str(self.directories[0])
        return os.getcwd()

    def addDirectory(self, directory: str):
        path = Path(directory).resolve()
        if path not in self.directories:
            # pylint: disable=no-member
            self.directories.append(path)
            self.path_manager.working_directories = self.directories # Actualizar PathManager
            self._notify_callbacks()
            if self.watch_workspace:
                self._start_file_system_watcher() # Reiniciar el observador si se añade un nuevo directorio
            self._initialize_modules() # Actualizar la estructura de carpetas y Git al añadir un directorio

    def removeDirectory(self, directory: str):
        path = Path(directory).resolve()
        if path in self.directories:
            # pylint: disable=no-member
            self.directories.remove(path)
            self.path_manager.working_directories = self.directories # Actualizar PathManager
            self._notify_callbacks()
            if self.watch_workspace:
                self._start_file_system_watcher() # Reiniciar el observador si se elimina un directorio
            self._initialize_modules() # Actualizar la estructura de carpetas y Git al eliminar un directorio

    def isPathWithinWorkspace(self, path: str) -> bool:
        return self.path_manager.is_path_within_workspace(path)

    def resolvePath(self, path: str) -> str:
        return self.path_manager.resolve_path(path)

    def onDirectoriesChanged(self, callback: Callable[[], None]):
        if callback not in self.callbacks:
            # pylint: disable=no-member
            self.callbacks.append(callback)

    def register_llm_context_builder(self, builder: Any):
        self.llm_context_builder = builder

    def set_llm_service_ref(self, llm_service_instance: Any):
        """Establece la referencia al LLMService."""
        self.llm_service_ref = llm_service_instance

    def get_conversation_history(self) -> List[Any]: # Usamos Any para evitar dependencia circular con BaseMessage
        """Devuelve el historial de conversación del LLMService."""
        if self.llm_service_ref and hasattr(self.llm_service_ref, 'conversation_history'):
            return self.llm_service_ref.conversation_history
        return []
