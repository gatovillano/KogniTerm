
import os
import sys
import fnmatch

# Mock dependencies
from unittest.mock import MagicMock
sys.modules['kogniterm.core.embeddings_service'] = MagicMock()
sys.modules['kogniterm.terminal.config_manager'] = MagicMock()
sys.modules['rich.progress'] = MagicMock()
sys.modules['rich.console'] = MagicMock()

sys.path.append(os.getcwd())
from kogniterm.core.context.codebase_indexer import CodebaseIndexer

def debug_ignore():
    workspace = os.getcwd()
    indexer = CodebaseIndexer(workspace)
    
    print(f"Ignore patterns: {indexer.ignore_patterns}")
    
    count = 0
    for root, dirs, files in os.walk(workspace):
        # Imprimir qué directorios estamos viendo
        rel_root = os.path.relpath(root, workspace)
        
        # Filtrar directorios
        original_dirs = list(dirs)
        dirs[:] = [d for d in dirs if not indexer._should_ignore(os.path.join(root, d), is_dir=True)]
        
        ignored_dirs = set(original_dirs) - set(dirs)
        if ignored_dirs:
            print(f"  [Ignored Dirs in {rel_root}]: {ignored_dirs}")

        for file in files:
            file_path = os.path.join(root, file)
            if not indexer._should_ignore(file_path, is_dir=False):
                print(f" FOUND: {os.path.relpath(file_path, workspace)}")
                count += 1
                if count >= 50:
                    print("... limit reached")
                    return

if __name__ == "__main__":
    debug_ignore()
