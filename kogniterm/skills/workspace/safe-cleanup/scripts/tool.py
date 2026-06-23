import os
import shutil
import json
import glob
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import fnmatch

# Esquema de parámetros
parameters_schema = {
    "type": "object",
    "properties": {
        "project_path": {
            "type": "string",
            "description": "Ruta del proyecto a limpiar",
            "default": "."
        },
        "dry_run": {
            "type": "boolean",
            "description": "Si True, solo simula sin eliminar",
            "default": True
        },
        "categories": {
            "type": "array",
            "items": {"type": "string", "enum": ["build", "temp", "backup", "cache", "duplicates", "all"]},
            "description": "Categorías de archivos a limpiar",
            "default": ["all"]
        },
        "exclude_patterns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Patrones glob a excluir",
            "default": []
        },
        "move_to_trash": {
            "type": "boolean",
            "description": "Si True, mueve a carpeta trash/ en lugar de eliminar",
            "default": True
        },
        "generate_report": {
            "type": "boolean",
            "description": "Si True, genera archivo de reporte",
            "default": True
        }
    }
}

def safe_cleanup(
    project_path: str = ".",
    dry_run: bool = True,
    categories: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    move_to_trash: bool = True,
    generate_report: bool = True
) -> Dict[str, Any]:
    """
    Limpia archivos basura técnica del proyecto de forma segura.
    
    Args:
        project_path: Ruta del proyecto (default: directorio actual)
        dry_run: Si True, solo simula sin eliminar (default: True)
        categories: Lista de categorías a limpiar (default: ["all"])
        exclude_patterns: Patrones glob a excluir
        move_to_trash: Si True, mueve a carpeta trash/ (default: True)
        generate_report: Si True, genera archivo de reporte (default: True)
    
    Returns:
        Dict con estadísticas, archivos encontrados y acciones realizadas
    """
    if categories is None:
        categories = ["all"]
    if exclude_patterns is None:
        exclude_patterns = []
    
    project_path = Path(project_path).resolve()
    trash_dir = project_path / "trash" / f"cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Definir categorías de limpieza
    cleanup_categories = {
        "build": {
            "patterns": [
                "**/build/",
                "**/dist/",
                "**/out/",
                "**/.next/",
                "**/node_modules/.cache",
                "**/__pycache__",
                "**/.pytest_cache",
                "**/.mypy_cache",
                "**/.coverage",
                "**/coverage/",
                "**/.nyc_output",
                "**/tmp/",
                "**/temp/",
                "**/.cache/",
                "**/data-gym-cache/",
                "**/thumbnails/",
            ],
            "description": "Archivos de compilación y build"
        },
        "temp": {
            "patterns": [
                "**/*.tmp",
                "**/*.temp",
                "**/*.log",
                "**/*.pid",
                "**/*.seed",
                "**/.env.local",
                "**/.env.*.local",
                "**/logs.txt",
                "**/model_debug.txt",
            ],
            "description": "Archivos temporales y logs"
        },
        "backup": {
            "patterns": [
                "**/*.bak",
                "**/*.backup",
                "**/*.old",
                "**/*~",
                "**/#*#",
                "**/.*.bak",
                "**/.*.backup",
            ],
            "description": "Archivos de backup"
        },
        "cache": {
            "patterns": [
                "**/.eslintcache",
                "**/tsconfig.tsbuildinfo",
                "**/.DS_Store",
                "**/Thumbs.db",
                "**/.gradle/",
                "**/.idea/",
                "**/.vscode/",
                "**/android/app/build/",
                "**/android/build/",
                "**/ios/build/",
                "**/kogninotes-app/android/app/build/",
                "**/kogninotes-app/android/build/",
            ],
            "description": "Archivos de caché y configuraciones de IDE"
        },
        "duplicates": {
            "patterns": [
                "**/builtin_tools/",  # Duplica skills/
                "**/core/agents_langgraph_backup/",  # Backup de agentes
                "**/llm_context.txt",  # Duplicado de llm_context.md
            ],
            "description": "Archivos duplicados o redudantes"
        }
    }
    
    # Determinar categorías a procesar
    if "all" in categories:
        cats_to_process = list(cleanup_categories.keys())
    else:
        cats_to_process = [c for c in categories if c in cleanup_categories]
    
    # Recopilar archivos por categoría
    found_files: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in cats_to_process}
    total_size = 0
    processed_paths: Set[Path] = set()
    
    for category in cats_to_process:
        cat_info = cleanup_categories[category]
        for pattern in cat_info["patterns"]:
            # Buscar archivos/directorios que coincidan
            for match in project_path.glob(pattern):
                if match in processed_paths:
                    continue
                
                # Verificar exclude_patterns
                relative_path = str(match.relative_to(project_path))
                excluded = any(fnmatch.fnmatch(relative_path, pat) for pat in exclude_patterns)
                if excluded:
                    continue
                
                # Clasificar
                file_info = {
                    "path": str(match.relative_to(project_path)),
                    "absolute_path": str(match),
                    "size_bytes": match.stat().st_size if match.is_file() else 0,
                    "is_dir": match.is_dir(),
                    "category": category,
                    "pattern": pattern
                }
                found_files[category].append(file_info)
                total_size += file_info["size_bytes"]
                processed_paths.add(match)
    
    # Generar reporte
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("🔍 REPORTE DE LIMPIEZA DE PROYECTO")
    report_lines.append("=" * 60)
    report_lines.append(f"Proyecto: {project_path}")
    report_lines.append(f"Fecha: {datetime.now().isoformat()}")
    report_lines.append(f"Modo: {'SIMULACIÓN (dry_run)' if dry_run else 'ELIMINACIÓN REAL'}")
    report_lines.append("")
    
    grand_total_size = 0
    grand_total_count = 0
    
    for category in cats_to_process:
        files = found_files[category]
        if not files:
            continue
        
        cat_size = sum(f["size_bytes"] for f in files)
        grand_total_size += cat_size
        grand_total_count += len(files)
        
        report_lines.append(f"📁 {category.upper()} - {cleanup_categories[category]['description']}")
        report_lines.append(f"   Archivos/dirs: {len(files)} | Tamaño: {cat_size:,} bytes ({cat_size/1024/1024:.2f} MB)")
        report_lines.append("")
        
        for f in files:
            size_str = f"{f['size_bytes']:,} bytes" if f['size_bytes'] > 0 else "<dir>"
            report_lines.append(f"   - {f['path']} ({size_str})")
        report_lines.append("")
    
    report_lines.append("=" * 60)
    report_lines.append(f"TOTAL: {grand_total_count} elementos | {grand_total_size:,} bytes ({grand_total_size/1024/1024:.2f} MB)")
    report_lines.append("=" * 60)
    
    report_text = "\n".join(report_lines)
    
    # Si dry_run, solo mostramos reporte
    if dry_run:
        result = {
            "status": "dry_run",
            "message": "Análisis completado (modo simulación). No se eliminó nada.",
            "total_files_found": grand_total_count,
            "total_size_bytes": grand_total_size,
            "categories": {cat: len(files) for cat, files in found_files.items()},
            "report": report_text,
            "recommendation": "Ejecute con dry_run=False para realizar la limpieza"
        }
    else:
        # Modo real: mover a trash/ o eliminar
        actions_performed = []
        errors = []
        
        if move_to_trash:
            trash_dir.mkdir(parents=True, exist_ok=True)
        
        for category in cats_to_process:
            for file_info in found_files[category]:
                src = Path(file_info["absolute_path"])
                try:
                    if move_to_trash:
                        # Mover a carpeta trash preservando estructura relativa
                        dest = trash_dir / file_info["path"]
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(src), str(dest))
                        actions_performed.append({
                            "action": "moved",
                            "from": file_info["path"],
                            "to": str(dest.relative_to(project_path))
                        })
                    else:
                        # Eliminar directamente
                        if src.is_dir():
                            shutil.rmtree(src)
                        else:
                            src.unlink()
                        actions_performed.append({
                            "action": "deleted",
                            "path": file_info["path"]
                        })
                except Exception as e:
                    errors.append({
                        "path": file_info["path"],
                        "error": str(e)
                    })
        
        # Generar log
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "project_path": str(project_path),
            "dry_run": dry_run,
            "move_to_trash": move_to_trash,
            "trash_location": str(trash_dir.relative_to(project_path)) if move_to_trash else None,
            "categories_processed": cats_to_process,
            "total_files_found": grand_total_count,
            "total_size_bytes": grand_total_size,
            "actions_performed": actions_performed,
            "errors": errors
        }
        
        if generate_report:
            log_file = project_path / "cleanup_log.json"
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
        
        result = {
            "status": "completed",
            "message": f"Limpieza completada. {len(actions_performed)} elementos procesados, {len(errors)} errores.",
            "total_processed": len(actions_performed),
            "total_errors": len(errors),
            "trash_location": str(trash_dir.relative_to(project_path)) if move_to_trash else None,
            "log_file": "cleanup_log.json" if generate_report else None,
            "errors": errors
        }
    
    # Si generate_report, guardar reporte de análisis
    if generate_report:
        report_file = project_path / ("cleanup_report_dry.txt" if dry_run else "cleanup_report.txt")
        with open(report_file, 'w') as f:
            f.write(report_text)
        result["report_file"] = str(report_file.relative_to(project_path))
    
    return result