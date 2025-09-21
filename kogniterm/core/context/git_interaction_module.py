import logging
from typing import List, Optional, Set
from git import Repo, InvalidGitRepositoryError, GitCommandError
import os

logger = logging.getLogger(__name__)

class GitInteractionModule:
    def __init__(self, repo_path: str = '.'):
        self.repo_path = repo_path
        self.repo = self._get_repo()
        self.tracked_files: Set[str] = set()
        if self.repo:
            self.update_tracked_files()

    def _get_repo(self) -> Optional[Repo]:
        try:
            repo = Repo(self.repo_path, search_parent_directories=True)
            return repo
        except InvalidGitRepositoryError:
            logger.warning(f"'{self.repo_path}' no es un repositorio Git válido.")
            return None
        except Exception as e:
            logger.error(f"Error al inicializar el repositorio Git en '{self.repo_path}': {e}")
            return None

    def update_git_status(self) -> Optional[str]:
        if not self.repo:
            return "No es un repositorio Git válido o no se pudo inicializar."
        try:
            # Forzar la actualización del índice de Git para reflejar los cambios del sistema de archivos
            self.repo.index.reset()
            
            modified_files = [item.a_path for item in self.repo.index.diff(None)]
            staged_files = [item.a_path for item in self.repo.index.diff('HEAD')]
            untracked_files = self.repo.untracked_files

            status_parts = []
            if modified_files:
                status_parts.append("Cambios no guardados (modified):")
                status_parts.extend(f"  - {f}" for f in modified_files)
            
            if staged_files:
                status_parts.append("\nCambios para el próximo commit (staged):")
                status_parts.extend(f"  - {f}" for f in staged_files)

            if untracked_files:
                status_parts.append("\nArchivos no rastreados (untracked):")
                status_parts.extend(f"  - {f}" for f in untracked_files)

            if not status_parts:
                return "El repositorio está limpio. No hay cambios pendientes."

            return "\n".join(status_parts)
        except GitCommandError as e:
            logger.error(f"Error de comando Git al obtener el estado: {e}")
            return f"Error de Git: {e}"
        except Exception as e:
            logger.error(f"Error inesperado al obtener el estado de Git: {e}")
            return f"Error inesperado: {e}"

    def update_tracked_files(self):
        if not self.repo:
            return
        try:
            # repo.git.ls_files() devuelve rutas relativas al directorio raíz del repo
            tracked_files_list = self.repo.git.ls_files().splitlines()
            # Es crucial tener la ruta absoluta para comparaciones consistentes
            repo_root = self.repo.working_dir
            self.tracked_files = {os.path.join(repo_root, f) for f in tracked_files_list}
        except GitCommandError as e:
            logger.error(f"Error de Git al obtener los archivos rastreados: {e}")
        except Exception as e:
            logger.error(f"Error inesperado al obtener los archivos rastreados: {e}")
 
    def is_tracked(self, file_path: str) -> bool:
        """
        Verifica si un archivo está siendo rastreado por Git.
        Normaliza la ruta para asegurar la comparación correcta.
        """
        if not self.repo:
            return False
        
        # Normalizar la ruta del archivo a una ruta absoluta para una comparación fiable
        abs_file_path = os.path.abspath(file_path)
        
        # Comprobar si la ruta normalizada está en nuestro conjunto de archivos rastreados
        return abs_file_path in self.tracked_files