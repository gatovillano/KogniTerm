import os
from pathlib import Path
from typing import List

class PathManager:
    def __init__(self, working_directories: List[Path]):
        self.working_directories = working_directories

    def resolve_path(self, path: str) -> str:
        """
        Resuelve una ruta dada, intentando hacerla absoluta si es relativa
        y verificando su existencia dentro de los directorios de trabajo.
        """
        target_path = Path(path)
        if target_path.is_absolute():
            return str(target_path.resolve())

        for workspace_dir in self.working_directories:
            resolved_path = (workspace_dir / target_path).resolve()
            if resolved_path.exists():
                return str(resolved_path)
        
        # Si no se encuentra, devolvemos la ruta original como string,
        # o podríamos levantar una excepción si se prefiere un comportamiento más estricto.
        return str(target_path)

    def is_path_within_workspace(self, path: str) -> bool:
        """
        Verifica si una ruta dada se encuentra dentro de alguno de los directorios de trabajo.
        """
        target_path = Path(path).resolve()
        for workspace_dir in self.working_directories:
            try:
                target_path.relative_to(workspace_dir)
                return True
            except ValueError:
                continue
        return False
