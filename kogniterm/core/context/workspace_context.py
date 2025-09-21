import os
import logging
from pathlib import Path
from typing import List, Callable, Optional
from pydantic import BaseModel, Field
from kogniterm.core.context.file_system_watcher import FileSystemWatcher
from kogniterm.core.context.config_file_analyzer import ConfigFileAnalyzer, parsePackageJson, parseTsconfigJson, parseEslintrcJson
from kogniterm.core.context.folder_structure_analyzer import FolderStructureAnalyzer
from kogniterm.core.context.git_interaction_module import GitInteractionModule
from kogniterm.core.context.ignore_pattern_manager import IgnorePatternManager

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

    class Config:
        arbitrary_types_allowed = True

    def __post_init__(self):
        if self.watch_workspace:
            self._start_file_system_watcher()
        if self.directories:
            self.git_interaction_module = GitInteractionModule(str(self.directories[0]))
            self.git_interaction_module.update_tracked_files() # Inicializar los archivos rastreados

    def _notify_callbacks(self):
        for callback in self.callbacks:
            callback()

    def handle_file_system_event(self, event_type: str, src_path: str, dest_path: Optional[str] = None):
        """
        Maneja los eventos del sistema de archivos y actualiza el contexto del proyecto.
        """
        #logger.info(f"Evento del sistema de archivos: {event_type} en la ruta: {src_path}")
        
        if self.folder_structure_analyzer:
            if event_type == 'created':
                self.folder_structure_analyzer.on_created(src_path)
            elif event_type == 'deleted':
                self.folder_structure_analyzer.on_deleted(src_path)
            elif event_type == 'moved':
                if dest_path:
                    self.folder_structure_analyzer.on_moved(src_path, dest_path)
            # 'modified' events currently don't alter the structure, so we can ignore them for now.
        
        file_path = Path(src_path)
        
        # Recargar archivos de configuración
        if self.config_file_analyzer.is_config_file(file_path.name):
            self.config_file_analyzer.handle_config_change(str(file_path))

        # Actualizar el estado de Git si el módulo está inicializado
        if self.git_interaction_module:
            # Solo reaccionar a cambios en archivos rastreados por Git
            if self.git_interaction_module.is_tracked(str(file_path)):
                # logger.debug(f"El archivo {src_path} ha cambiado, actualizando el estado de Git.")
                self.git_interaction_module.update_git_status()
            else:
                pass
                # logger.debug(f"Cambio en {src_path} ignorado, no rastreado por Git.")

        # Gestionar patrones de ignorado si .gitignore cambia
        if file_path.name == ".gitignore":
            # logger.debug(".gitignore modificado. Recargando patrones de ignorado.")
            self._update_folder_structure()

        self._notify_callbacks()

    def _update_folder_structure(self):
        """
        Actualiza la representación de la estructura de carpetas y el módulo de Git.
        """
        if self.directories:
            try:
                root_dir = str(self.directories[0])
                # Actualizar la estructura de carpetas
                self.folder_structure_analyzer = FolderStructureAnalyzer(root_dir, self.ignore_pattern_manager.get_ignore_patterns(root_dir))
                # logger.debug("Estructura de carpetas actualizada.")
                
                # Inicializar o actualizar el módulo de Git
                self.git_interaction_module = GitInteractionModule(root_dir)
                # logger.debug("Módulo de Git inicializado/actualizado.")

            except Exception as e:
                logger.error(f"Error al actualizar la estructura de carpetas o el módulo de Git: {e}")

    def _start_file_system_watcher(self):
        if self.file_system_watcher:
            self.file_system_watcher.stop()
        
        # Observar todos los directorios del workspace
        if self.directories:
            # Para simplificar, observamos el primer directorio del workspace.
            # En una implementación más robusta, se podría observar cada directorio
            # o un directorio raíz común.
            directory_to_watch = str(self.directories[0])
            self.file_system_watcher = FileSystemWatcher(
                directory=directory_to_watch,
                callback=self.handle_file_system_event,
                ignore_patterns=self.ignore_patterns
            )
            self.file_system_watcher.start()
            # print(f"FileSystemWatcher iniciado para: {directory_to_watch}")

    def _stop_file_system_watcher(self):
        if self.file_system_watcher:
            self.file_system_watcher.stop()
            self.file_system_watcher = None
            # print("FileSystemWatcher detenido.")

    def get_working_directory(self) -> str:
        """Devuelve el directorio de trabajo principal del workspace."""
        if self.directories:
            return str(self.directories[0])
        return os.getcwd()

    def addDirectory(self, directory: str):
        path = Path(directory).resolve()
        if path not in self.directories:
            self.directories.append(path)
            self._notify_callbacks()
            if self.watch_workspace:
                self._start_file_system_watcher() # Reiniciar el observador si se añade un nuevo directorio
                self._update_folder_structure() # Actualizar la estructura de carpetas al añadir un directorio
                if self.git_interaction_module:
                    self.git_interaction_module.update_tracked_files() # Actualizar los archivos rastreados

    def removeDirectory(self, directory: str):
        path = Path(directory).resolve()
        if path in self.directories:
            self.directories.remove(path)
            self._notify_callbacks()
            if self.watch_workspace:
                self._start_file_system_watcher() # Reiniciar el observador si se elimina un directorio
                self._update_folder_structure() # Actualizar la estructura de carpetas al eliminar un directorio
                if self.git_interaction_module:
                    self.git_interaction_module.update_tracked_files() # Actualizar los archivos rastreados

    def getDirectories(self) -> List[str]:
        return [str(p) for p in self.directories]

    def isPathWithinWorkspace(self, path: str) -> bool:
        target_path = Path(path).resolve()
        for workspace_dir in self.directories:
            try:
                target_path.relative_to(workspace_dir)
                return True
            except ValueError:
                continue
        return False

    def resolvePath(self, path: str) -> str:
        # Si la ruta ya es absoluta o si es un archivo que existe en el sistema
        # y no necesitamos resolverlo relativo al workspace, la devolvemos tal cual.
        # Esto asume que las rutas dentro del workspace son relativas a uno de los
        # directorios del workspace, o absolutas que caen dentro de ellos.
        target_path = Path(path)
        if target_path.is_absolute():
            return str(target_path.resolve())

        for workspace_dir in self.directories:
            resolved_path = (workspace_dir / target_path).resolve()
            if resolved_path.exists(): # Esto es una validación simple de existencia
                return str(resolved_path)
        
        # Si no se encuentra, devolvemos la ruta original como string,
        # o podríamos levantar una excepción si se prefiere un comportamiento más estricto.
        return str(target_path)

    def onDirectoriesChanged(self, callback: Callable[[], None]):
        if callback not in self.callbacks:
            self.callbacks.append(callback)
