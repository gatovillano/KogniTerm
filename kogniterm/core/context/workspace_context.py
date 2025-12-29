import os
from typing import List, Dict, Optional
from langchain_core.messages import SystemMessage
import fnmatch # Importar fnmatch

class WorkspaceContext:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.context_data: Optional[str] = None
        self.ignore_patterns = [
            '.git', '.venv', 'venv', 'build', '__pycache__', '.kogniterm',
            'node_modules', '.vscode', '.idea', 'dist', 'target',
            '*.pyc', '*.log', '*.tmp', '*.bak', '*.swp',
            '*.DS_Store', 'Thumbs.db', # macOS and Windows specific
            '*.egg-info', # Python packaging
            '*.bin', '*.obj', '*.dll', '*.exe', # Binary files
            '*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp', '*.svg', '*.ico', # Image files
            '*.pdf', '*.zip', '*.tar', '*.gz', '*.rar', # Archives and PDFs
        ]
        # Cargar patrones adicionales desde .gitignore
        self.git_ignore_patterns = self._load_ignore_patterns()

    def _load_ignore_patterns(self) -> List[str]:
        """Loads ignore patterns from .gitignore and .kognitermignore."""
        patterns = []
        for filename in ['.gitignore', '.kognitermignore']:
            file_path = os.path.join(self.root_dir, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                patterns.append(line)
                except Exception:
                    pass
        return patterns

    def _matches_git_ignore(self, item_name: str, rel_path: str, is_dir: bool) -> bool:
        """Checks if a path matches any of the git ignore patterns."""
        # Normalizar la ruta para comparaciones consistentes
        rel_path = rel_path.replace(os.sep, '/')
        
        for pattern in self.git_ignore_patterns:
            pattern = pattern.replace(os.sep, '/')
            if not pattern or pattern.startswith('#'):
                continue
            
            is_dir_only_pattern = pattern.endswith('/')
            if is_dir_only_pattern:
                pattern = pattern.rstrip('/')

            if fnmatch.fnmatch(item_name, pattern) or \
               fnmatch.fnmatch(rel_path, pattern) or \
               rel_path.startswith(pattern + '/') or \
               any(fnmatch.fnmatch(part, pattern) for part in rel_path.split('/')):
                return True
        return False

    def _should_ignore(self, item_name: str, is_dir: bool, path: Optional[str] = None) -> bool:
        # 1. Verificar patrones fijos
        for pattern in self.ignore_patterns:
            if pattern.startswith('.') and item_name.startswith('.') and item_name == pattern:
                return True
            if pattern.endswith('/') and is_dir and item_name == pattern.rstrip('/'):
                return True
            if fnmatch.fnmatch(item_name, pattern):
                return True
        
        # 2. Verificar patrones de .gitignore si tenemos la ruta relativa
        if path:
            rel_path = os.path.relpath(path, self.root_dir)
            if self._matches_git_ignore(item_name, rel_path, is_dir):
                return True
        return False

    def _get_folder_structure(self, path: str, indent: int = 0) -> str:
        structure = []
        if not os.path.exists(path):
            return ""

        items = sorted(os.listdir(path))
        for item in items:
            item_path = os.path.join(path, item)
            is_dir = os.path.isdir(item_path)

            if self._should_ignore(item, is_dir, item_path):
                continue

            if is_dir:
                structure.append(f"{ '    ' * indent }├───{item}/")
                sub_structure = self._get_folder_structure(item_path, indent + 1)
                if sub_structure:
                    structure.append(sub_structure)
            else:
                structure.append(f"{ '    ' * indent }├───{item}")
        return "\n".join(structure)

    def _get_file_contents(self, file_paths: List[str]) -> Dict[str, str]:
        contents = {}
        for file_path in file_paths:
            abs_path = os.path.join(self.root_dir, file_path)
            is_dir = os.path.isdir(abs_path)

            if self._should_ignore(os.path.basename(file_path), is_dir):
                contents[file_path] = "Archivo ignorado por las reglas de contexto."
                continue

            # Aplicar _should_ignore aquí también, antes de intentar leer
            if self._should_ignore(os.path.basename(file_path), is_dir) or \
               self._should_ignore(file_path, is_dir): # Verificar también la ruta completa
                contents[file_path] = "Archivo ignorado por las reglas de contexto."
                continue

            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                try:
                    # Intentar detectar si es un archivo de texto o binario
                    # Una forma simple es intentar leer una pequeña parte
                    with open(abs_path, 'rb') as f:
                        # Leer los primeros N bytes para detectar si es binario
                        # Si contiene bytes nulos, es probable que sea binario
                        # O si la decodificación falla en los primeros bytes
                        header = f.read(512)
                        is_binary = b'\0' in header

                    if is_binary:
                        contents[file_path] = "(Contenido binario no legible)"
                    else:
                        with open(abs_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()
                            # Truncar el contenido si es muy largo
                            MAX_FILE_CONTENT_LENGTH = 5000 # Definir un límite razonable
                            if len(file_content) > MAX_FILE_CONTENT_LENGTH:
                                contents[file_path] = file_content[:MAX_FILE_CONTENT_LENGTH] + "\n... [Contenido truncado]"
                            else:
                                contents[file_path] = file_content
                except Exception as e:
                    contents[file_path] = f"Error al leer el archivo: {e}"
            else:
                contents[file_path] = "Archivo no encontrado o no es un archivo."
        return contents

    def initialize_context(self, files_to_include: Optional[List[str]] = None):
        folder_structure = self._get_folder_structure(self.root_dir)
        
        context_parts = []
        context_parts.append(f"Directorio de trabajo actual: {self.root_dir}\n")
        context_parts.append("Aquí está la estructura de carpetas del proyecto:\n")
        context_parts.append(folder_structure)
        context_parts.append("\n")

        if files_to_include:
            file_contents = self._get_file_contents(files_to_include)
            context_parts.append("Aquí está el contenido de algunos archivos clave:\n")
            for file_path, content in file_contents.items():
                context_parts.append(f"--- Contenido de {file_path} ---")
                context_parts.append(content)
                context_parts.append("----------------------------------\n")
        
        self.context_data = "\n".join(context_parts)

    def build_context_message(self) -> Optional[SystemMessage]:
        if self.context_data:
            return SystemMessage(content=self.context_data)
        return None
