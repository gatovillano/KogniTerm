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

    def _should_ignore(self, item_name: str, is_dir: bool) -> bool:
        for pattern in self.ignore_patterns:
            if pattern.startswith('.') and item_name.startswith('.') and item_name == pattern:
                return True
            if pattern.endswith('/') and is_dir and item_name == pattern.rstrip('/'):
                return True
            if fnmatch.fnmatch(item_name, pattern):
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

            if self._should_ignore(item, is_dir):
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

            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                try:
                    with open(abs_path, 'r', encoding='utf-8') as f:
                        contents[file_path] = f.read()
                except Exception as e:
                    contents[file_path] = f"Error al leer el archivo: {e}"
            else:
                contents[file_path] = "Archivo no encontrado o no es un archivo."
        return contents

    def initialize_context(self, files_to_include: Optional[List[str]] = None):
        folder_structure = self._get_folder_structure(self.root_dir)
        
        context_parts = []
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
