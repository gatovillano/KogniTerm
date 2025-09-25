import os
import logging
from pathlib import Path
from gitignore_parser import parse_gitignore
import tempfile # Importar tempfile

logger = logging.getLogger(__name__)

class IgnorePatternManager:
    DEFAULT_IGNORE_PATTERNS = [
        "venv/**", ".git/**", "__pycache__/", "*.pyc", "*.tmp", "*.log", ".env", ".DS_Store", "*.kogniterm_temp_gitignore"
    ]

    def __init__(self):
        self.universal_patterns = self.DEFAULT_IGNORE_PATTERNS

    def get_ignore_patterns(self, directory: str) -> list[str]:
        """
        Analiza los archivos .gitignore en un directorio y devuelve una lista de patrones de ignorado,
        combinados con los patrones universales por defecto. Los patrones de .gitignore tienen prioridad.
        """
        ignore_file_path = Path(directory) / ".gitignore"
        project_patterns = []

        if ignore_file_path.is_file():
            try:
                with open(ignore_file_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            project_patterns.append(line)
            except FileNotFoundError:
                logger.debug(f"No se encontró el archivo .gitignore en {directory}")
            except Exception as e:
                logger.error(f"Error al leer o parsear .gitignore en {directory}: {e}")
        
        # Combinar patrones universales y de proyecto, dando prioridad a los de proyecto
        # Esto se hace para que si un patrón universal es 'a' y un patrón de proyecto es '!a',
        # el patrón de proyecto tenga efecto. Sin embargo, para la simple lista de strings,
        # simplemente agregamos los patrones de proyecto después de los universales.
        # La lógica de prioridad real se maneja mejor en el `parse_gitignore` para la verificación.
        combined_patterns = list(self.universal_patterns)
        for pattern in project_patterns:
            if pattern not in combined_patterns:
                combined_patterns.append(pattern)
        
        logger.debug(f"Patrones de ignorado combinados para {directory}: {combined_patterns}")
        return combined_patterns

    def check_ignored(self, file_path: str, directory: str) -> bool:
        """
        Verifica si un archivo debe ser ignorado basándose en los patrones de .gitignore
        y los patrones universales.
        """
        all_patterns = self.universal_patterns + self.get_ignore_patterns(directory)
        
        temp_gitignore_path = None # Inicializar a None

        try:
            # Usar tempfile para crear un archivo temporal de forma segura
            with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as temp_file:
                temp_file.write("\n".join(all_patterns))
                temp_gitignore_path = Path(temp_file.name) # Obtener la ruta del archivo temporal
            
            # El archivo ya está cerrado aquí, listo para ser leído por parse_gitignore
            match_func = parse_gitignore(str(temp_gitignore_path), directory)
            
            # Convertir file_path a una ruta relativa al 'directory'
            relative_file_path = Path(file_path).relative_to(directory)
            is_ignored = match_func(str(relative_file_path))
            logger.debug(f"Verificando si {file_path} (relativo: {relative_file_path}) es ignorado en {directory}. Resultado: {is_ignored}")
            return is_ignored
        except Exception as e:
            logger.error(f"Error al verificar ignorado para {file_path} en {directory} con patrones combinados: {e}")
            return False
        finally:
            # Asegurarse de que el archivo temporal se elimine, incluso si hubo un error
            if temp_gitignore_path and temp_gitignore_path.exists(): # Verificar si se asignó y existe
                os.remove(temp_gitignore_path)
