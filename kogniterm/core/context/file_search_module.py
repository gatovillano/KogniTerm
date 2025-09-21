import os
import fnmatch
from pathlib import Path
from typing import List

def findFiles(directory: str, pattern: str, ignore_patterns: List[str] = None) -> List[str]:
    """
    Busca archivos que coincidan con un patrón de búsqueda en un directorio y devuelve una lista de rutas de archivo.

    :param directory: La ruta del directorio donde se realizará la búsqueda.
    :param pattern: El patrón de búsqueda (glob) para los archivos.
    :param ignore_patterns: Una lista de patrones glob para ignorar archivos y directorios.
    :return: Una lista de rutas de archivo que coinciden con el patrón y no son ignoradas.
    """
    if ignore_patterns is None:
        ignore_patterns = []

    matched_files = []
    base_path = Path(directory)

    if not base_path.is_dir():
        raise ValueError(f"El directorio '{directory}' no existe o no es un directorio válido.")

    for root, dirnames, filenames in os.walk(directory):
        current_path = Path(root)
        
        # Check if the current directory should be ignored
        if any(fnmatch.fnmatch(current_path.name, p) or fnmatch.fnmatch(str(current_path.relative_to(base_path)), p) for p in ignore_patterns):
            # If the directory matches an ignore pattern, prune the walk
            dirnames[:] = []  # Don't recurse into ignored directories
            continue
        
        # Filter out ignored subdirectories for the current level
        dirnames[:] = [d for d in dirnames if not any(fnmatch.fnmatch(d, p) for p in ignore_patterns)]

        for filename in filenames:
            file_path = current_path / filename
            relative_file_path = file_path.relative_to(base_path)

            # Check against ignore patterns for files
            if any(fnmatch.fnmatch(filename, p) or fnmatch.fnmatch(str(relative_file_path), p) for p in ignore_patterns):
                continue
            
            if fnmatch.fnmatch(filename, pattern):
                matched_files.append(str(file_path))
                
    return matched_files

if __name__ == '__main__':
    # Ejemplo de uso:
    test_dir = "test_search_module"
    os.makedirs(os.path.join(test_dir, "subdir1"), exist_ok=True)
    os.makedirs(os.path.join(test_dir, "subdir2"), exist_ok=True)
    os.makedirs(os.path.join(test_dir, "subdir_ignored"), exist_ok=True)

    with open(os.path.join(test_dir, "file1.txt"), "w") as f:
        f.write("contenido txt")
    with open(os.path.join(test_dir, "file2.py"), "w") as f:
        f.write("print('hello')")
    with open(os.path.join(test_dir, "subdir1", "script.py"), "w") as f:
        f.write("import os")
    with open(os.path.join(test_dir, "subdir2", "data.json"), "w") as f:
        f.write("{'key': 'value'}")
    with open(os.path.join(test_dir, "subdir_ignored", "secret.txt"), "w") as f:
        f.write("secret info")
    with open(os.path.join(test_dir, "temp.log"), "w") as f:
        f.write("log entry")

    print("--- Buscando todos los archivos .py ---")
    python_files = findFiles(test_dir, "*.py")
    for f in python_files:
        print(f)

    print("\n--- Buscando todos los archivos, ignorando .log y subdir_ignored ---")
    all_files_filtered = findFiles(test_dir, "*", ignore_patterns=["*.log", "subdir_ignored", "test_search_module/subdir_ignored/*"])
    for f in all_files_filtered:
        print(f)

    print("\n--- Buscando archivos .txt en subdir1 (debería ser vacío) ---")
    txt_in_subdir1 = findFiles(os.path.join(test_dir, "subdir1"), "*.txt")
    for f in txt_in_subdir1:
        print(f)
    if not txt_in_subdir1:
        print("No se encontraron archivos .txt en subdir1.")

    # Limpiar archivos y directorios temporales
    import shutil
    shutil.rmtree(test_dir)