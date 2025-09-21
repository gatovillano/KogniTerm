import os
import logging
from pathlib import Path
from gitignore_parser import parse_gitignore

logger = logging.getLogger(__name__)

class IgnorePatternManager:
    DEFAULT_IGNORE_PATTERNS = [
        "venv/", ".git/", "__pycache__/", "*.pyc", "*.tmp", "*.log", ".env", ".DS_Store"
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
        
        return combined_patterns

    def check_ignored(self, file_path: str, directory: str) -> bool:
        """
        Verifica si un archivo debe ser ignorado basándose en los patrones de .gitignore
        y los patrones universales.
        """
        all_patterns = self.universal_patterns + self.get_ignore_patterns(directory)
        
        # Crear un archivo temporal para combinar todos los patrones y que parse_gitignore los procese.
        # Esto es necesario porque parse_gitignore solo lee de un archivo.
        # Una alternativa sería modificar la librería o escribir nuestra propia lógica de parseo,
        # pero para mantener la compatibilidad, usaremos un archivo temporal.
        temp_gitignore_content = "\n".join(all_patterns)
        temp_gitignore_path = Path(directory) / ".kogniterm_temp_gitignore"
        
        try:
            with open(temp_gitignore_path, "w") as f:
                f.write(temp_gitignore_content)
            
            matches = parse_gitignore(str(temp_gitignore_path), directory)
            return matches.match(file_path)
        except Exception as e:
            logger.error(f"Error al verificar ignorado para {file_path} en {directory} con patrones combinados: {e}")
            return False
        finally:
            if temp_gitignore_path.exists():
                os.remove(temp_gitignore_path)
