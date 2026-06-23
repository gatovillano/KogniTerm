import os
import json
from pathlib import Path

def project_analyzer(**kwargs):
    """
    Analiza un directorio de proyectos y resume información clave.
    
    Args:
        project_path: Ruta al directorio del proyecto a analizar
        
    Returns:
        Diccionario con información resumida del proyecto
    """
    project_path = kwargs.get('project_path')
    if not project_path:
        return {"error": "Se requiere el parámetro 'project_path'"}
    
    project_path = Path(project_path)
    if not project_path.exists() or not project_path.is_dir():
        return {"error": f"La ruta '{project_path}' no existe o no es un directorio"}
    
    # Información básica
    result = {
        "project_name": project_path.name,
        "project_path": str(project_path.absolute()),
        "files_found": {},
        "summary": ""
    }
    
    # Archivos clave a buscar
    key_files = {
        "README": ["README.md", "README.txt", "README"],
        "package_json": ["package.json"],
        "requirements": ["requirements.txt", "requirements-dev.txt", "pyproject.toml"],
        "docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
        "config": [".env", ".env.example", "config.json", "settings.json"]
    }
    
    # Buscar archivos clave
    for category, filenames in key_files.items():
        found_files = []
        for filename in filenames:
            file_path = project_path / filename
            if file_path.exists() and file_path.is_file():
                found_files.append(str(file_path.relative_to(project_path)))
        if found_files:
            result["files_found"][category] = found_files
    
    # Leer contenido de archivos importantes para generar resumen
    readme_content = ""
    package_info = {}
    requirements_content = ""
    
    # Intentar leer README
    for readme_file in key_files["README"]:
        readme_path = project_path / readme_file
        if readme_path.exists():
            try:
                readme_content = readme_path.read_text(encoding='utf-8')[:500]  # Primeros 500 chars
                break
            except Exception:
                pass
    
    # Intentar leer package.json
    package_json_path = project_path / "package.json"
    if package_json_path.exists():
        try:
            package_info = json.loads(package_json_path.read_text(encoding='utf-8'))
        except Exception:
            pass
    
    # Intentar leer requirements.txt
    requirements_path = project_path / "requirements.txt"
    if requirements_path.exists():
        try:
            requirements_content = requirements_path.read_text(encoding='utf-8')[:300]  # Primeros 300 chars
        except Exception:
            pass
    
    # Generar resumen descriptivo
    summary_parts = []
    
    if package_info:
        name = package_info.get("name", "desconocido")
        version = package_info.get("version", "desconocida")
        description = package_info.get("description", "")
        summary_parts.append(f"Proyecto Node.js: {name} v{version}")
        if description:
            summary_parts.append(f"Descripción: {description}")
    
    if requirements_content:
        summary_parts.append("Proyecto Python con dependencias en requirements.txt")
    
    if readme_content:
        # Extraer primera línea significativa del README
        first_line = ""
        for line in readme_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                first_line = line[:100]
                break
        if first_line:
            summary_parts.append(f"README indica: {first_line}")
    
    if not summary_parts:
        summary_parts.append("Proyecto genérico detectado")
    
    result["summary"] = " | ".join(summary_parts)
    result["readme_preview"] = readme_content[:200] + "..." if len(readme_content) > 200 else readme_content
    result["package_info"] = package_info
    result["requirements_preview"] = requirements_content
    
    return result

# Esquema de parámetros para la skill
parameters_schema = {
    "type": "object",
    "properties": {
        "project_path": {
            "type": "string",
            "description": "Ruta al directorio del proyecto a analizar"
        }
    },
    "required": ["project_path"]
}