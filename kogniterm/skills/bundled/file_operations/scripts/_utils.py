import os

IGNORED_DIRECTORIES = ['venv', '.git', '__pycache__', '.venv', 'node_modules']

def matches_ignore(item_name: str, is_dir: bool = False) -> bool:
    """Verifica si un item debe ser ignorado."""
    if is_dir and item_name in IGNORED_DIRECTORIES:
        return True
    if item_name.startswith('.'):  # Archivos/dirs ocultos
        return True
    return False

def clean_path(path: str) -> str:
    """Limpia la ruta de caracteres innecesarios y la convierte a absoluta si es relativa."""
    if not path:
        return ""
    cleaned = path.strip().replace('@', '')
    if not os.path.isabs(cleaned):
        cleaned = os.path.abspath(cleaned)
    return cleaned
